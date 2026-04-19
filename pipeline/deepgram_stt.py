"""
Pravaah OS — Deepgram Nova-2 STT WebSocket Client

Streams raw audio bytes to Deepgram and delivers interim and final transcripts
via async callbacks. Supports automatic reconnection with exponential backoff.
"""

import asyncio
import json
import logging
import os
from typing import Callable, Optional
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)

# Deepgram WebSocket endpoint
_DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

# Query parameters for Deepgram Nova-2 streaming WebSocket.
# NOTE: Do NOT specify encoding/sample_rate for browser MediaRecorder audio.
# Browser sends audio/webm;codecs=opus — Deepgram auto-detects from container.
# Specifying encoding=webm-opus causes HTTP 400 (invalid value).
_DEFAULT_PARAMS = {
    "model": "nova-2",
    "language": "hi",
    "punctuate": "true",
    "interim_results": "true",
    "smart_format": "true",
    "endpointing": "500",
}

_MAX_RECONNECT_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 1.0


class DeepgramSTTClient:
    """
    Async Deepgram Nova-2 STT WebSocket client.

    Opens a persistent WebSocket connection to Deepgram, forwards raw audio
    chunks, and invokes callbacks for interim and final transcript events.

    Parameters
    ----------
    api_key : str
        Deepgram API key.  Falls back to the ``DEEPGRAM_API_KEY`` env var if
        not supplied explicitly.
    on_interim : Callable[[str], None]
        Called with the interim transcript text on every non-final result.
    on_final : Callable[[str], None]
        Called with the final transcript text on every final result.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        on_interim: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialise the STT client with API key and transcript callbacks."""
        self._api_key: str = api_key or os.environ["DEEPGRAM_API_KEY"]
        self._on_interim: Callable[[str], None] = on_interim or (lambda t: None)
        self._on_final: Callable[[str], None] = on_final or (lambda t: None)
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected: bool = False
        self._closing: bool = False
        self._receive_task: Optional[asyncio.Task] = None
        # Buffer chunks that arrive before the WebSocket is ready
        self._pre_connect_buffer: list = []
        self._MAX_BUFFER_CHUNKS: int = 40  # ~10 s at 250 ms slices

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Open a WebSocket connection to Deepgram with correct query params.

        Retries up to ``_MAX_RECONNECT_ATTEMPTS`` times with exponential
        backoff (1 s, 2 s, 4 s) before raising the last exception.
        """
        await self._connect_with_retry()

    async def send_audio(self, chunk: bytes) -> None:
        """
        Forward raw audio bytes to the Deepgram WebSocket.

        Parameters
        ----------
        chunk : bytes
            Raw audio bytes from the browser MediaRecorder (webm/opus).
        """
        if not self._connected or self._ws is None:
            if not self._closing and len(self._pre_connect_buffer) < self._MAX_BUFFER_CHUNKS:
                self._pre_connect_buffer.append(chunk)
                logger.debug("STT not yet connected; buffering chunk (%d buffered)", len(self._pre_connect_buffer))
            else:
                logger.warning("send_audio: not connected and buffer full or closing; dropping chunk")
            return
        try:
            await self._ws.send(chunk)
        except (ConnectionClosed, WebSocketException) as exc:
            logger.error("WebSocket error while sending audio: %s", exc)
            self._connected = False
            if not self._closing:
                logger.info("Attempting to reconnect after send failure…")
                await self._connect_with_retry()

    def mark_closing(self) -> None:
        """
        Synchronously mark this client as closing so reconnection is suppressed.

        Call this from synchronous code before scheduling the async close(),
        to avoid a race where Deepgram drops the connection (e.g. 1011 timeout)
        before the async close() coroutine has a chance to set _closing = True.
        """
        self._closing = True

    async def close(self) -> None:
        """
        Gracefully shut down the WebSocket connection.

        Sends a JSON close message to Deepgram before closing the socket so
        that any buffered audio is flushed and a final transcript is returned.
        """
        self._closing = True
        self._connected = False
        self._pre_connect_buffer.clear()
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._ws is not None:
            try:
                # Ask Deepgram to flush remaining audio
                await self._ws.send(json.dumps({"type": "CloseStream"}))
            except Exception:
                pass
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        logger.info("DeepgramSTTClient closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(self) -> str:
        """Construct the full Deepgram WebSocket URL with query params."""
        params = _DEFAULT_PARAMS.copy()
        # Allow env-var overrides for model
        params["model"] = os.getenv("DEEPGRAM_STT_MODEL", params["model"])
        url = f"{_DEEPGRAM_WS_URL}?{urlencode(params)}"
        logger.info("Deepgram STT URL: %s", url)
        return url

    def _build_headers(self) -> dict:
        """Return the Authorization headers required by Deepgram."""
        return {"Authorization": f"Token {self._api_key}"}

    async def _connect_with_retry(self) -> None:
        """
        Attempt to (re)connect to Deepgram with exponential backoff.

        Raises the final exception if all attempts are exhausted.
        """
        if self._closing:
            logger.debug("STT client is closing; skipping reconnect")
            return
        url = self._build_url()
        headers = self._build_headers()
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
            try:
                logger.info("Connecting to Deepgram STT (attempt %d/%d)…", attempt, _MAX_RECONNECT_ATTEMPTS)
                self._ws = await asyncio.wait_for(
                    websockets.connect(url, extra_headers=headers, ping_interval=20, ping_timeout=30),
                    timeout=30.0,
                )
                self._connected = True
                self._closing = False
                logger.info("Connected to Deepgram STT WebSocket")
                # Flush any audio that arrived before the connection was ready
                if self._pre_connect_buffer:
                    logger.info("Flushing %d buffered audio chunks to Deepgram", len(self._pre_connect_buffer))
                    for buffered_chunk in self._pre_connect_buffer:
                        try:
                            await self._ws.send(buffered_chunk)
                        except Exception as flush_exc:
                            logger.warning("Error flushing buffered chunk: %s", flush_exc)
                            break
                    self._pre_connect_buffer.clear()
                # Kick off background receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())
                return
            except (OSError, WebSocketException, asyncio.TimeoutError) as exc:
                last_exc = exc
                backoff = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                # Log response body for HTTP errors to aid debugging
                body = ""
                if hasattr(exc, "response") and exc.response is not None:
                    try:
                        body = f" | body: {exc.response.body.decode()}"
                    except Exception:
                        body = f" | headers: {dict(getattr(exc.response, 'headers', {}))}"
                logger.warning(
                    "Deepgram STT connect attempt %d failed: %s%s. Retrying in %.1fs…",
                    attempt,
                    exc,
                    body,
                    backoff,
                )
                await asyncio.sleep(backoff)

        logger.error("All %d Deepgram STT connect attempts failed", _MAX_RECONNECT_ATTEMPTS)
        raise last_exc  # type: ignore[misc]

    async def _receive_loop(self) -> None:
        """
        Background task: read JSON messages from Deepgram and invoke callbacks.

        Automatically triggers reconnection if the socket drops unexpectedly.
        """
        assert self._ws is not None
        try:
            async for raw_message in self._ws:
                if isinstance(raw_message, bytes):
                    # Deepgram may send binary keep-alives; ignore
                    continue
                self._handle_message(raw_message)
        except asyncio.CancelledError:
            logger.debug("STT receive loop cancelled")
        except ConnectionClosed as exc:
            logger.warning("Deepgram STT WebSocket closed unexpectedly: %s", exc)
            self._connected = False
            if not self._closing:
                logger.info("Reconnecting Deepgram STT after unexpected close…")
                try:
                    await self._connect_with_retry()
                except Exception as reconnect_exc:
                    logger.error("STT reconnect failed: %s", reconnect_exc)
        except Exception as exc:
            logger.error("Unexpected error in STT receive loop: %s", exc, exc_info=True)

    def _handle_message(self, raw: str) -> None:
        """
        Parse a Deepgram JSON message and invoke the appropriate callback.

        Parameters
        ----------
        raw : str
            Raw JSON string received from Deepgram WebSocket.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse Deepgram message: %r", raw[:200])
            return

        msg_type = data.get("type", "")
        if msg_type != "Results":
            # Metadata, SpeechStarted, UtteranceEnd, etc. — log at debug level
            logger.debug("Deepgram non-results message: type=%s", msg_type)
            return

        try:
            alt = data["channel"]["alternatives"][0]
            transcript: str = alt.get("transcript", "").strip()
        except (KeyError, IndexError):
            logger.debug("Deepgram message missing expected fields: %s", data)
            return

        if not transcript:
            return

        is_final: bool = bool(data.get("is_final", False))
        if is_final:
            logger.debug("Final transcript: %s", transcript)
            self._on_final(transcript)
        else:
            logger.debug("Interim transcript: %s", transcript)
            self._on_interim(transcript)
