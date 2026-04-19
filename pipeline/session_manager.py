"""
Pravaah OS — Session Manager

Tracks per-call state: DeepgramSTTClient instance, transcript buffer,
LLM results, and lifecycle status.  Provides a thread-safe registry so
the Flask/SocketIO handlers can look up sessions by session_id.
"""

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from .deepgram_stt import DeepgramSTTClient
from .deepgram_tts import DeepgramTTSClient
from .openrouter_client import OpenRouterLLMClient

logger = logging.getLogger(__name__)


class CallSession:
    """
    Encapsulates all state for a single active call.

    Attributes
    ----------
    session_id : str
        The UUID4 identifier for this call session.
    stt_client : DeepgramSTTClient
        The Deepgram STT WebSocket client for this call.
    transcript_buffer : list[str]
        Accumulates all final transcript segments during the call.
    created_at : datetime
        UTC timestamp when this session was created.
    is_active : bool
        True while the call is running; False after ``close()`` is called.
    """

    def __init__(
        self,
        session_id: str,
        stt_client: DeepgramSTTClient,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        Initialise a call session.

        Parameters
        ----------
        session_id : str
            Unique identifier for this session.
        stt_client : DeepgramSTTClient
            Pre-created (but not yet connected) STT client.
        loop : asyncio.AbstractEventLoop
            The event loop used to schedule async operations from sync code.
        """
        self.session_id = session_id
        self.stt_client = stt_client
        self.transcript_buffer: List[str] = []
        self.created_at: datetime = datetime.now(tz=timezone.utc)
        self.is_active: bool = True
        self._loop = loop

    def append_transcript(self, text: str) -> None:
        """
        Append a final transcript segment to the buffer.

        Parameters
        ----------
        text : str
            Final transcript text from Deepgram.
        """
        self.transcript_buffer.append(text)

    def full_transcript(self) -> str:
        """Return the entire buffered transcript as a single string."""
        return " ".join(self.transcript_buffer)

    def send_audio(self, chunk: bytes) -> None:
        """
        Forward audio bytes to the Deepgram STT WebSocket.

        This is a synchronous convenience method that submits the coroutine
        to the background event loop used by the STT client.

        Parameters
        ----------
        chunk : bytes
            Raw audio bytes from the browser MediaRecorder.
        """
        if not self.is_active:
            return
        asyncio.run_coroutine_threadsafe(
            self.stt_client.send_audio(chunk), self._loop
        )

    def close(self) -> None:
        """Mark the session as inactive and schedule STT client shutdown."""
        self.is_active = False
        # Set _closing synchronously so reconnect is suppressed even if Deepgram
        # fires a 1011 timeout before the async close() coroutine runs.
        self.stt_client.mark_closing()
        asyncio.run_coroutine_threadsafe(
            self.stt_client.close(), self._loop
        )


class SessionManager:
    """
    Thread-safe registry for active call sessions.

    A single ``SessionManager`` instance is created at app startup and
    shared across all SocketIO handlers.

    Parameters
    ----------
    deepgram_api_key : str, optional
        Deepgram API key; defaults to ``DEEPGRAM_API_KEY`` env var.
    openrouter_api_key : str, optional
        OpenRouter API key; defaults to ``OPENROUTER_API_KEY`` env var.
    on_interim_cb : Callable[[str, str], None], optional
        Called with ``(session_id, interim_text)`` on every interim transcript.
    on_final_cb : Callable[[str, str], None], optional
        Called with ``(session_id, final_text)`` on every final transcript.
    on_summary_cb : Callable[[str, str, list], None], optional
        Called with ``(session_id, summary_text, action_items)`` after a call ends.
    """

    def __init__(
        self,
        deepgram_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        on_interim_cb: Optional[Callable[[str, str], None]] = None,
        on_final_cb: Optional[Callable[[str, str], None]] = None,
        on_summary_cb: Optional[Callable[[str, str, list], None]] = None,
    ) -> None:
        """Initialise the session manager and start the async event loop thread."""
        self._deepgram_api_key = deepgram_api_key
        self._openrouter_api_key = openrouter_api_key
        self._on_interim_cb = on_interim_cb or (lambda sid, t: None)
        self._on_final_cb = on_final_cb or (lambda sid, t: None)
        self._on_summary_cb = on_summary_cb or (lambda sid, s, a: None)

        self._sessions: Dict[str, CallSession] = {}
        self._lock = threading.Lock()

        # A dedicated asyncio loop running in a background thread so that
        # synchronous Flask/SocketIO code can submit coroutines to it.
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            name="pravaah-async-loop",
            daemon=True,
        )
        self._loop_thread.start()
        logger.info("SessionManager async event loop started")

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, session_id: str) -> CallSession:
        """
        Create and register a new call session.

        Opens the Deepgram STT WebSocket connection asynchronously.

        Parameters
        ----------
        session_id : str
            UUID4 session identifier.

        Returns
        -------
        CallSession
            The newly created session object.
        """

        def on_interim(text: str) -> None:
            self._on_interim_cb(session_id, text)

        def on_final(text: str) -> None:
            self._on_final_cb(session_id, text)
            with self._lock:
                session = self._sessions.get(session_id)
            if session:
                session.append_transcript(text)

        stt_client = DeepgramSTTClient(
            api_key=self._deepgram_api_key,
            on_interim=on_interim,
            on_final=on_final,
        )
        session = CallSession(
            session_id=session_id,
            stt_client=stt_client,
            loop=self._loop,
        )

        with self._lock:
            self._sessions[session_id] = session

        # Start STT connection in background — do NOT block the caller (Socket.IO handler).
        # Audio chunks arriving before the connection is ready are buffered inside
        # DeepgramSTTClient._pre_connect_buffer and flushed on first successful connect.
        def _on_connect_done(fut):
            try:
                fut.result()
                logger.info("Session created and STT connected: %s", session_id)
            except Exception as exc:
                logger.error("Failed to open Deepgram STT for session %s: %s", session_id, exc)
                with self._lock:
                    self._sessions.pop(session_id, None)

        future = asyncio.run_coroutine_threadsafe(stt_client.connect(), self._loop)
        future.add_done_callback(_on_connect_done)

        logger.info("Session created, STT connecting in background: %s", session_id)
        return session

    def get(self, session_id: str) -> Optional[CallSession]:
        """
        Retrieve an active session by ID.

        Parameters
        ----------
        session_id : str
            Session UUID4.

        Returns
        -------
        CallSession or None
            The session if found and active, otherwise None.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> Optional[str]:
        """
        Close an active session and trigger the end-of-call LLM pipeline.

        Runs ``summarize_transcript`` and ``extract_action_items`` in a
        background thread, then invokes ``on_summary_cb``.

        Parameters
        ----------
        session_id : str
            Session UUID4 to close.

        Returns
        -------
        str or None
            The full transcript text, or None if session not found.
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)

        if session is None:
            logger.warning("close_session called for unknown session: %s", session_id)
            return None

        transcript = session.full_transcript()
        session.close()
        logger.info("Session closed: %s (%d transcript segments)", session_id, len(session.transcript_buffer))

        # Run end-of-call LLM pipeline in a background thread
        if transcript.strip():
            t = threading.Thread(
                target=self._run_end_of_call_pipeline,
                args=(session_id, transcript),
                daemon=True,
            )
            t.start()

        return transcript

    def list_sessions(self) -> List[str]:
        """Return a list of all active session IDs."""
        with self._lock:
            return list(self._sessions.keys())

    def shutdown(self) -> None:
        """Stop the background async loop and clean up all sessions."""
        logger.info("Shutting down SessionManager…")
        with self._lock:
            session_ids = list(self._sessions.keys())

        for sid in session_ids:
            try:
                self.close_session(sid)
            except Exception as exc:
                logger.warning("Error closing session %s during shutdown: %s", sid, exc)

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=5)
        logger.info("SessionManager shutdown complete")

    # ------------------------------------------------------------------
    # Internal: end-of-call LLM pipeline
    # ------------------------------------------------------------------

    def _run_end_of_call_pipeline(self, session_id: str, transcript: str) -> None:
        """
        Run summary + action item extraction after a call ends.

        Invoked in a background thread; calls ``on_summary_cb`` with results.

        Parameters
        ----------
        session_id : str
            The session that just ended.
        transcript : str
            The full concatenated transcript text.
        """
        try:
            llm = OpenRouterLLMClient(api_key=self._openrouter_api_key)
            logger.info("Running end-of-call LLM pipeline for session %s", session_id)

            summary = llm.summarize_transcript(transcript)
            logger.info("Summary generated for session %s", session_id)

            action_items = llm.extract_action_items(transcript)
            logger.info(
                "Extracted %d action items for session %s", len(action_items), session_id
            )

            self._on_summary_cb(session_id, summary, action_items)
        except Exception as exc:
            logger.error(
                "End-of-call LLM pipeline failed for session %s: %s", session_id, exc, exc_info=True
            )
