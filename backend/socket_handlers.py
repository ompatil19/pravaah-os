"""
Pravaah OS — Socket.IO Event Handlers

Registers all Socket.IO events for the call audio pipeline:
  join_call    → open Deepgram STT WebSocket for the session
  audio_chunk  → forward binary audio to Deepgram
  leave_call   → close Deepgram WS, trigger LLM pipeline on full transcript

Emits:
  transcript_interim  → live partial transcript
  transcript_final    → persisted final transcript segment
  call_summary        → LLM-generated call summary
  action_items        → extracted action items list
  tts_audio           → base64 MP3 from Deepgram Aura
  error               → pipeline errors
"""

import base64
import logging
import os
import re
import threading
from datetime import datetime, timezone

from flask_socketio import SocketIO, emit, join_room, leave_room

from . import database as db

logger = logging.getLogger(__name__)

# Module-level references set by app.py during init
_socketio: SocketIO | None = None
_session_manager = None  # pipeline.SessionManager

# Per-session conversation history for LLM back-and-forth
# { session_id: [{"role": "user"|"assistant", "content": str}, ...] }
_conversation_histories: dict = {}
_conv_lock = threading.Lock()

# Per-session TTS generation counter — bumped each time user speaks.
# LLM threads capture their generation at start; skip TTS if superseded.
_tts_generation: dict = {}
_gen_lock = threading.Lock()

# Per-session semaphore — at most 2 concurrent realtime-LLM threads per session.
# Prevents pile-up during bursty speech.
_llm_semaphores: dict = {}
_sem_lock = threading.Lock()
_MAX_CONCURRENT_LLM = 2


def _get_llm_semaphore(session_id: str) -> threading.Semaphore:
    with _sem_lock:
        if session_id not in _llm_semaphores:
            _llm_semaphores[session_id] = threading.Semaphore(_MAX_CONCURRENT_LLM)
        return _llm_semaphores[session_id]


def init_handlers(socketio: SocketIO) -> None:
    """Register all Socket.IO event handlers. Called once from app.py."""
    global _socketio
    _socketio = socketio
    _init_session_manager()
    _register_events(socketio)
    logger.info("Socket.IO handlers registered.")


def close_session(session_id: str) -> None:
    """Close the pipeline session for a call. Safe to call if session doesn't exist."""
    if _session_manager:
        _session_manager.close_session(session_id)


# ---------------------------------------------------------------------------
# Session Manager bootstrap
# ---------------------------------------------------------------------------

def _init_session_manager():
    """Lazy-init the pipeline SessionManager with the Deepgram API key."""
    global _session_manager
    try:
        from pipeline.session_manager import SessionManager
        _session_manager = SessionManager(
            deepgram_api_key=os.environ.get("DEEPGRAM_API_KEY", ""),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            on_interim_cb=lambda sid, t: _on_transcript(sid, t, is_final=False),
            on_final_cb=lambda sid, t: _on_transcript(sid, t, is_final=True),
        )
        logger.info("SessionManager initialised.")
    except Exception as exc:
        logger.error("Failed to init SessionManager: %s", exc)


# ---------------------------------------------------------------------------
# Deepgram callbacks (called from background threads)
# ---------------------------------------------------------------------------

def _on_transcript(session_id: str, text: str, is_final: bool) -> None:
    """
    Called by DeepgramSTTClient for each transcript result.
    Emits interim/final events to the browser room.
    """
    if not _socketio:
        return

    timestamp = datetime.now(timezone.utc).isoformat()

    if not is_final:
        _socketio.emit(
            "transcript_interim",
            {"session_id": session_id, "text": text, "timestamp": timestamp},
            room=session_id,
        )
        return

    # Final transcript: persist + emit + trigger LLM
    try:
        db.insert_transcript(session_id, text, is_final=True, speaker=None, timestamp=timestamp)
    except Exception as exc:
        logger.error("[%s] Failed to insert transcript: %s", session_id, exc)

    _socketio.emit(
        "transcript_final",
        {"session_id": session_id, "text": text, "timestamp": timestamp},
        room=session_id,
    )

    # Bump generation — any in-flight LLM thread will abort its TTS output
    with _gen_lock:
        _tts_generation[session_id] = _tts_generation.get(session_id, 0) + 1
        my_gen = _tts_generation[session_id]

    # Trigger non-blocking LLM reply + TTS
    threading.Thread(
        target=_run_realtime_llm,
        args=(session_id, text, my_gen),
        daemon=True,
        name=f"llm-rt-{session_id}",
    ).start()

    # Trigger live summary every 5 final transcript segments
    transcript_count = db.count_transcripts(session_id)
    if transcript_count > 0 and transcript_count % 5 == 0:
        threading.Thread(
            target=_run_live_summary,
            args=(session_id,),
            daemon=True,
            name=f"live-summary-{session_id}",
        ).start()


def _on_pipeline_error(session_id: str, code: str, message: str) -> None:
    """Called by pipeline components to propagate errors to the browser."""
    if _socketio:
        _socketio.emit(
            "error",
            {"session_id": session_id, "code": code, "message": message},
            room=session_id,
        )


# ---------------------------------------------------------------------------
# Response cleaner — strip model chain-of-thought if it leaked into reply
# ---------------------------------------------------------------------------

_THINKING_PREFIXES = (
    "okay,", "ok,", "okay.", "ok.", "alright,", "alright.",
    "let me ", "let's ", "i need to ", "i should ", "i think ",
    "the user ", "they are ", "they said ", "they asked ",
    "hmm,", "hmm.", "well,", "so,", "so the ",
)

def _strip_thinking(text: str) -> str:
    """
    If the model output its chain-of-thought before the actual answer,
    extract only the final answer sentence(s).
    Works by detecting a thinking-style opening and returning the last
    1-2 sentences, which are typically the actual reply.
    """
    stripped = text.strip()
    first_20 = stripped[:20].lower()
    if not any(first_20.startswith(p) for p in _THINKING_PREFIXES):
        return stripped  # Looks clean already

    # Split on double newlines first (sometimes model uses paragraph break)
    paragraphs = [p.strip() for p in re.split(r'\n\n+', stripped) if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs[-1]

    # Single blob: split into sentences, return last 1-2
    sentences = re.split(r'(?<=[.!?])\s+', stripped)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > 2:
        return ' '.join(sentences[-2:])
    if len(sentences) == 2:
        return sentences[-1]
    return stripped


# ---------------------------------------------------------------------------
# LLM pipeline helpers
# ---------------------------------------------------------------------------

def _run_realtime_llm(session_id: str, latest_transcript: str, my_gen: int) -> None:
    """
    After a final transcript: send user message to LLM with conversation
    history, speak the response via TTS, and emit audio back to the browser.
    Runs in a background thread.

    my_gen: the generation counter captured when this thread was spawned.
    If the user speaks again before TTS is ready, the counter increments and
    this thread drops the audio silently (interruption detected).
    """
    sem = _get_llm_semaphore(session_id)
    if not sem.acquire(blocking=False):
        logger.debug("[%s] LLM semaphore full — dropping realtime request", session_id)
        return
    try:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        dg_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key or not dg_key:
            logger.warning("[%s] Missing API keys — skipping LLM/TTS", session_id)
            return

        from pipeline.openrouter_client import OpenRouterLLMClient
        from pipeline.deepgram_tts import DeepgramTTSClient
        from pipeline.prompt_templates import SYSTEM_CONVERSATION

        # ── Build conversation history ──────────────────────────────────────
        with _conv_lock:
            if session_id not in _conversation_histories:
                _conversation_histories[session_id] = []
            history = _conversation_histories[session_id]
            history.append({"role": "user", "content": latest_transcript})
            # Keep last 10 turns (5 user + 5 assistant) to avoid token bloat
            if len(history) > 20:
                history[:] = history[-20:]
            messages_snapshot = list(history)

        # ── LLM call with full conversation context ─────────────────────────
        # Default to claude-3-haiku (non-thinking) — haiku-4-5 outputs chain-of-thought
        llm = OpenRouterLLMClient(api_key=api_key)
        raw_reply = llm._call(
            [{"role": "system", "content": SYSTEM_CONVERSATION}] + messages_snapshot,
            model=os.environ.get("OPENROUTER_LIGHT_MODEL", "anthropic/claude-3-haiku"),
            temperature=0.7,
            max_tokens=120,
        )
        llm.close()
        reply = _strip_thinking(raw_reply)

        # Store assistant reply in history
        with _conv_lock:
            if session_id in _conversation_histories:
                _conversation_histories[session_id].append(
                    {"role": "assistant", "content": reply}
                )

        logger.info("[%s] LLM reply: %r", session_id, reply[:100])

        # Check if user interrupted before we send TTS
        with _gen_lock:
            current_gen = _tts_generation.get(session_id, 0)
        if current_gen != my_gen:
            logger.info("[%s] TTS skipped — user interrupted (gen %d → %d)", session_id, my_gen, current_gen)
            return

        # Emit text reply to frontend (shows in UI)
        if _socketio:
            _socketio.emit(
                "ai_reply",
                {"session_id": session_id, "text": reply},
                room=session_id,
            )

        # ── TTS synthesis ───────────────────────────────────────────────────
        tts = DeepgramTTSClient(api_key=dg_key)
        audio_bytes = tts.synthesize(reply)
        tts.close()

        # Final check — user may have spoken during TTS synthesis
        with _gen_lock:
            current_gen = _tts_generation.get(session_id, 0)
        if current_gen != my_gen:
            logger.info("[%s] TTS audio dropped — interrupted during synthesis (gen %d → %d)", session_id, my_gen, current_gen)
            return

        audio_b64 = base64.b64encode(audio_bytes).decode()
        if _socketio:
            _socketio.emit(
                "tts_audio",
                {"session_id": session_id, "audio": audio_b64},
                room=session_id,
            )

    except Exception as exc:
        logger.warning("[%s] Real-time LLM/TTS failed: %s", session_id, exc)
    finally:
        sem.release()


def _run_live_summary(session_id: str) -> None:
    """
    Generate a partial summary from transcripts so far and emit it
    to the browser during the call. Triggered every 5 final segments.
    """
    try:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return

        transcript_rows = db.get_transcripts(session_id)
        if not transcript_rows:
            return

        full_text = " ".join(r.text for r in transcript_rows if r.is_final)
        if not full_text.strip():
            return

        from pipeline.openrouter_client import OpenRouterLLMClient
        client = OpenRouterLLMClient(api_key=api_key)
        summary_text = client.summarize_transcript(full_text)
        client.close()

        # Persist latest summary (upsert)
        generated_at = datetime.now(timezone.utc).isoformat()
        model_used = os.environ.get("OPENROUTER_HEAVY_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        db.insert_summary(session_id, summary_text, model_used, generated_at)

        if _socketio:
            _socketio.emit(
                "call_summary",
                {"session_id": session_id, "summary": summary_text},
                room=session_id,
            )
        logger.info("[%s] Live summary updated (%d segments).", session_id, len(transcript_rows))

    except Exception as exc:
        logger.warning("[%s] Live summary failed: %s", session_id, exc)


def _run_final_llm_pipeline(session_id: str) -> None:
    """
    On call end: generate full summary + action items and emit them.
    Runs in a background thread.
    """
    try:
        transcript_rows = db.get_transcripts(session_id)
        if not transcript_rows:
            return

        full_text = " ".join(r.text for r in transcript_rows if r.is_final)
        if not full_text.strip():
            return

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return

        from pipeline.openrouter_client import OpenRouterLLMClient

        client = OpenRouterLLMClient(api_key=api_key)

        # Summary
        summary_text = client.summarize_transcript(full_text)
        model_used = os.environ.get("OPENROUTER_HEAVY_MODEL", "anthropic/claude-sonnet-4-5")
        generated_at = datetime.now(timezone.utc).isoformat()

        db.insert_summary(session_id, summary_text, model_used, generated_at)

        if _socketio:
            _socketio.emit(
                "call_summary",
                {"session_id": session_id, "summary": summary_text},
                room=session_id,
            )

        # Action items
        items = client.extract_action_items(full_text)
        saved_items = []
        for item in items:
            text = item.get("action") or item.get("text", "")
            priority = item.get("priority", "medium")
            assignee = item.get("owner") or item.get("assignee")
            if text:
                db.insert_action_item(session_id, text, priority, assignee, generated_at)
                saved_items.append({"text": text, "priority": priority, "assignee": assignee})

        if _socketio and saved_items:
            _socketio.emit(
                "action_items",
                {"session_id": session_id, "items": saved_items},
                room=session_id,
            )

        client.close()
        logger.info("[%s] Final LLM pipeline complete.", session_id)

    except Exception as exc:
        logger.error("[%s] Final LLM pipeline failed: %s", session_id, exc)
        if _socketio:
            _socketio.emit(
                "error",
                {
                    "session_id": session_id,
                    "code": "LLM_PIPELINE_ERROR",
                    "message": str(exc),
                },
                room=session_id,
            )


# ---------------------------------------------------------------------------
# Socket.IO event registrations
# ---------------------------------------------------------------------------

def _register_events(socketio: SocketIO) -> None:

    @socketio.on("join_call")
    def handle_join_call(payload):
        """Client joins a room and opens a Deepgram STT connection."""
        session_id = (payload or {}).get("session_id", "")
        if not session_id:
            emit("error", {"session_id": "", "code": "MISSING_SESSION_ID",
                           "message": "session_id is required."})
            return

        join_room(session_id)
        logger.info("[%s] Client joined room.", session_id)

        if _session_manager:
            try:
                _session_manager.create_session(session_id)
            except Exception as exc:
                logger.error("[%s] STT connect failed: %s", session_id, exc)
                emit("error", {
                    "session_id": session_id,
                    "code": "STT_CONNECT_FAILED",
                    "message": "Could not connect to Deepgram STT.",
                })
        else:
            logger.warning("[%s] SessionManager not available.", session_id)

    @socketio.on("audio_chunk")
    def handle_audio_chunk(payload):
        """Forward a binary audio chunk to Deepgram."""
        if isinstance(payload, bytes):
            # Binary frame with no metadata — can't route without session_id
            logger.debug("Received raw binary without session_id; dropping.")
            return

        session_id = (payload or {}).get("session_id", "")
        audio_data = (payload or {}).get("data")

        if not session_id:
            return
        if audio_data is None:
            return

        # Convert to bytes if needed
        if isinstance(audio_data, str):
            try:
                audio_bytes = base64.b64decode(audio_data)
            except Exception:
                return
        elif isinstance(audio_data, (bytes, bytearray)):
            audio_bytes = bytes(audio_data)
        else:
            return

        if _session_manager:
            session = _session_manager.get(session_id)
            if session:
                session.send_audio(audio_bytes)

    @socketio.on("leave_call")
    def handle_leave_call(payload):
        """Client ends the call; close STT and run final LLM pipeline."""
        session_id = (payload or {}).get("session_id", "")
        if not session_id:
            return

        leave_room(session_id)
        logger.info("[%s] Client left room.", session_id)

        # Clear conversation history, generation counter, and LLM semaphore for this session
        with _conv_lock:
            _conversation_histories.pop(session_id, None)
        with _gen_lock:
            _tts_generation.pop(session_id, None)
        with _sem_lock:
            _llm_semaphores.pop(session_id, None)

        if _session_manager:
            _session_manager.close_session(session_id)

        # Trigger full summary + action items
        call_row = db.get_call(session_id)
        if call_row and not db.get_summary(session_id):
            threading.Thread(
                target=_run_final_llm_pipeline,
                args=(session_id,),
                daemon=True,
                name=f"llm-final-{session_id}",
            ).start()

    @socketio.on("connect")
    def handle_connect(auth=None):
        """
        Validate JWT on connect.
        Client must pass: socket.io({auth: {token: "<JWT>"}})
        Falls back to allowing connection if no token (for backward compat in dev).
        """
        from flask import request as flask_request
        from .auth import decode_token, _is_token_blacklisted

        token = None
        if isinstance(auth, dict):
            token = auth.get("token")
        if not token:
            # Also check query param for legacy clients
            token = flask_request.args.get("token")

        if token:
            payload = decode_token(token)
            if not payload or payload.get("type") != "access":
                logger.warning("Socket.IO connect rejected: invalid JWT.")
                return False  # Reject connection
            jti = payload.get("jti", "")
            if _is_token_blacklisted(jti):
                logger.warning("Socket.IO connect rejected: blacklisted token.")
                return False
            logger.debug("Socket.IO client connected (user_id=%s).", payload.get("sub"))
        else:
            logger.debug("Socket.IO client connected (no auth token — allowed in dev).")

    @socketio.on("subscribe_doc_progress")
    def handle_subscribe_doc_progress(payload):
        """Client subscribes to document processing progress events."""
        doc_id = (payload or {}).get("doc_id", "")
        if not doc_id:
            emit("error", {"code": "MISSING_DOC_ID", "message": "doc_id is required."})
            return
        join_room(f"doc:{doc_id}")
        emit("subscribed", {"doc_id": doc_id, "room": f"doc:{doc_id}"})
        logger.debug("Client subscribed to doc progress: %s", doc_id)

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.debug("Socket.IO client disconnected.")
