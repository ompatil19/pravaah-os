"""
Pravaah OS — Deepgram Aura TTS REST Client

Converts text to speech using the Deepgram Aura REST API and returns raw
MP3 bytes ready for base64-encoding and delivery to the browser.
"""

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"
_DEFAULT_VOICE = "aura-asteria-en"
_REQUEST_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1.0


class DeepgramTTSClient:
    """
    Synchronous Deepgram Aura TTS REST client.

    Converts text to MP3 audio bytes using the Deepgram /v1/speak endpoint.
    Retries up to ``_MAX_RETRIES`` times with exponential backoff on failure.

    Parameters
    ----------
    api_key : str, optional
        Deepgram API key.  Falls back to the ``DEEPGRAM_API_KEY`` env var.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialise TTS client with API key."""
        self._api_key: str = api_key or os.environ["DEEPGRAM_API_KEY"]
        self._voice: str = os.getenv("DEEPGRAM_TTS_MODEL", _DEFAULT_VOICE)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Token {self._api_key}",
                "Content-Type": "application/json",
            }
        )

    def synthesize(self, text: str) -> bytes:
        """
        Convert text to MP3 audio bytes using the Deepgram Aura REST API.

        Retries up to 3 times on failure with exponential backoff.

        Parameters
        ----------
        text : str
            The text to convert to speech.

        Returns
        -------
        bytes
            Raw MP3 audio bytes suitable for base64-encoding and playback.

        Raises
        ------
        RuntimeError
            If all retry attempts are exhausted without a successful response.
        """
        if not text or not text.strip():
            raise ValueError("synthesize() called with empty text")

        url = f"{_DEEPGRAM_TTS_URL}?model={self._voice}"
        payload = {"text": text.strip()}
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info("TTS request attempt %d/%d for text: %r…", attempt, _MAX_RETRIES, text[:60])
                response = self._session.post(
                    url,
                    json=payload,
                    timeout=_REQUEST_TIMEOUT_SECONDS,
                )
                if response.status_code == 200:
                    audio_bytes = response.content
                    logger.info("TTS success: received %d bytes", len(audio_bytes))
                    return audio_bytes

                # Non-2xx response — log and retry
                logger.warning(
                    "TTS attempt %d returned HTTP %d: %s",
                    attempt,
                    response.status_code,
                    response.text[:300],
                )
                last_exc = RuntimeError(
                    f"Deepgram TTS HTTP {response.status_code}: {response.text[:300]}"
                )

            except requests.exceptions.Timeout as exc:
                logger.warning("TTS attempt %d timed out: %s", attempt, exc)
                last_exc = exc
            except requests.exceptions.RequestException as exc:
                logger.warning("TTS attempt %d request error: %s", attempt, exc)
                last_exc = exc

            if attempt < _MAX_RETRIES:
                backoff = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.info("Retrying TTS in %.1fs…", backoff)
                time.sleep(backoff)

        logger.error("All %d TTS attempts failed", _MAX_RETRIES)
        raise RuntimeError(f"Deepgram TTS failed after {_MAX_RETRIES} attempts") from last_exc

    def close(self) -> None:
        """Close the underlying requests Session."""
        self._session.close()
        logger.debug("DeepgramTTSClient session closed")
