"""
Pravaah OS — Pipeline End-to-End CLI Test

Records 10 seconds of audio from the default microphone, streams it to
Deepgram Nova-2 STT in real time, prints the transcript, then:
1. Sends the transcript to OpenRouter for summarization
2. Synthesizes the summary using Deepgram Aura TTS
3. Plays the resulting audio via system default audio output

Requirements (beyond requirements.txt):
    pip install pyaudio simpleaudio

Usage:
    python -m pipeline.test_pipeline
    # or directly:
    python pipeline/test_pipeline.py

Environment variables required:
    DEEPGRAM_API_KEY
    OPENROUTER_API_KEY
"""

import asyncio
import base64
import logging
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap path so the script can be run directly
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_pipeline")

# ---------------------------------------------------------------------------
# Check API keys before importing clients
# ---------------------------------------------------------------------------

def _require_env(name: str) -> str:
    """Return the value of an environment variable or exit with an error."""
    val = os.environ.get(name)
    if not val:
        print(f"ERROR: environment variable {name!r} is not set.", file=sys.stderr)
        sys.exit(1)
    return val


DEEPGRAM_API_KEY = _require_env("DEEPGRAM_API_KEY")
OPENROUTER_API_KEY = _require_env("OPENROUTER_API_KEY")

# ---------------------------------------------------------------------------
# Lazy imports (pyaudio / simpleaudio are optional extras)
# ---------------------------------------------------------------------------

def _import_pyaudio():
    """Import pyaudio or print a helpful install message."""
    try:
        import pyaudio
        return pyaudio
    except ImportError:
        print(
            "pyaudio is not installed.  Install with:\n"
            "  pip install pyaudio\n"
            "  # macOS: brew install portaudio && pip install pyaudio",
            file=sys.stderr,
        )
        sys.exit(1)


def _try_import_simpleaudio():
    """Try to import simpleaudio; return None if unavailable."""
    try:
        import simpleaudio
        return simpleaudio
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RECORD_SECONDS = 10
CHUNK_SIZE = 1024          # frames per PyAudio buffer read
AUDIO_FORMAT_PA = None     # set after pyaudio import
CHANNELS = 1
SAMPLE_RATE = 16000        # PCM 16-bit, 16 kHz for simplicity in CLI test
# Note: actual WebSocket params use webm-opus from MediaRecorder; for this
# CLI test we send raw PCM (linear16) to Deepgram, adjusting the params.


# ---------------------------------------------------------------------------
# Async recording + streaming
# ---------------------------------------------------------------------------

async def record_and_stream() -> str:
    """
    Record 10 seconds of audio and stream it to Deepgram STT.

    Returns the full concatenated final transcript.
    """
    from pipeline.deepgram_stt import DeepgramSTTClient

    pyaudio = _import_pyaudio()

    transcript_parts: list[str] = []
    interim_display: list[str] = []
    done_event = asyncio.Event()

    def on_interim(text: str) -> None:
        # Overwrite the current line
        print(f"\r[interim] {text:<80}", end="", flush=True)

    def on_final(text: str) -> None:
        print(f"\r[final]   {text:<80}")
        transcript_parts.append(text)

    # Use linear16 encoding for this CLI test (easier than webm-opus without
    # a browser MediaRecorder)
    import importlib
    stt_mod = importlib.import_module("pipeline.deepgram_stt")

    # Override params temporarily to use linear16 / 16kHz for microphone
    original_params = stt_mod._DEFAULT_PARAMS.copy()
    stt_mod._DEFAULT_PARAMS.update({
        "encoding": "linear16",
        "sample_rate": str(SAMPLE_RATE),
        "channels": str(CHANNELS),
    })

    client = DeepgramSTTClient(
        api_key=DEEPGRAM_API_KEY,
        on_interim=on_interim,
        on_final=on_final,
    )

    try:
        await client.connect()
        print(f"\nConnected to Deepgram STT. Recording {RECORD_SECONDS}s…\n")

        # Open microphone
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        start = time.monotonic()
        while time.monotonic() - start < RECORD_SECONDS:
            chunk = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            await client.send_audio(chunk)
            await asyncio.sleep(0)  # yield to event loop

        stream.stop_stream()
        stream.close()
        pa.terminate()
        print("\nRecording complete. Waiting for final transcript…")
        await asyncio.sleep(2)  # give Deepgram time to flush

    finally:
        await client.close()
        # Restore original params
        stt_mod._DEFAULT_PARAMS.clear()
        stt_mod._DEFAULT_PARAMS.update(original_params)

    return " ".join(transcript_parts)


# ---------------------------------------------------------------------------
# LLM summarization
# ---------------------------------------------------------------------------

def summarize(transcript: str) -> str:
    """Send the transcript to OpenRouter and return the summary string."""
    from pipeline.openrouter_client import OpenRouterLLMClient

    print("\n--- Sending transcript to OpenRouter for summarization ---")
    client = OpenRouterLLMClient(api_key=OPENROUTER_API_KEY)
    try:
        summary = client.summarize_transcript(transcript)
        return summary
    finally:
        client.close()


# ---------------------------------------------------------------------------
# TTS synthesis + playback
# ---------------------------------------------------------------------------

def synthesize_and_play(text: str) -> None:
    """Synthesize text to MP3 and play it back."""
    from pipeline.deepgram_tts import DeepgramTTSClient

    print("\n--- Synthesizing TTS audio via Deepgram Aura ---")
    tts = DeepgramTTSClient(api_key=DEEPGRAM_API_KEY)
    try:
        mp3_bytes = tts.synthesize(text)
    finally:
        tts.close()

    print(f"Received {len(mp3_bytes)} bytes of MP3 audio.")

    # Try simpleaudio first, then fall back to saving to a temp file
    sa = _try_import_simpleaudio()
    if sa is not None:
        try:
            # simpleaudio needs WAV; save MP3 and decode with pydub if available
            try:
                from pydub import AudioSegment
                from io import BytesIO
                seg = AudioSegment.from_mp3(BytesIO(mp3_bytes))
                wav_io = BytesIO()
                seg.export(wav_io, format="wav")
                wav_io.seek(0)
                wave_obj = sa.WaveObject.from_wave_file(wav_io)
                play_obj = wave_obj.play()
                play_obj.wait_done()
                return
            except ImportError:
                pass  # pydub not available; fall through
        except Exception as exc:
            logger.warning("simpleaudio playback failed: %s", exc)

    # Last resort: save to temp file and print path
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_bytes)
        tmppath = f.name
    print(f"Audio saved to: {tmppath}")
    # Attempt system open
    if sys.platform == "darwin":
        os.system(f'afplay "{tmppath}"')
    elif sys.platform.startswith("linux"):
        os.system(f'mpg123 "{tmppath}" 2>/dev/null || ffplay -nodisp -autoexit "{tmppath}" 2>/dev/null')
    else:
        print(f"Open the file manually to play: {tmppath}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full CLI pipeline test: record → STT → summarize → TTS → play."""
    print("=" * 60)
    print("  Pravaah OS — Pipeline End-to-End Test")
    print("=" * 60)

    # Step 1: Record + stream STT
    transcript = asyncio.run(record_and_stream())

    if not transcript.strip():
        print("\nNo transcript received. Please check your microphone and API key.")
        sys.exit(1)

    print("\n\n=== FULL TRANSCRIPT ===")
    print(transcript)

    # Step 2: Summarize
    summary = summarize(transcript)
    print("\n=== SUMMARY ===")
    print(summary)

    # Step 3: TTS playback
    synthesize_and_play(summary[:500])  # Limit to avoid very long TTS

    print("\n=== Pipeline test complete ===")


if __name__ == "__main__":
    main()
