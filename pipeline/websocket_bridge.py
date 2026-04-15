"""
Pravaah OS — WebSocket Bridge

Flask-SocketIO event handlers that connect the browser audio stream to the
Deepgram STT pipeline.  This module is imported by ``backend/app.py`` and
registers Socket.IO events on the shared ``socketio`` instance.

Usage in backend/app.py::

    from pipeline.websocket_bridge import register_handlers
    register_handlers(socketio, session_manager)
"""

import base64
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask_socketio import SocketIO
    from .session_manager import SessionManager

logger = logging.getLogger(__name__)


def register_handlers(socketio: "SocketIO", session_mgr: "SessionManager") -> None:
    """
    Register all Socket.IO event handlers on the given SocketIO instance.

    This function wires up the ``join_call``, ``audio_chunk``, and
    ``leave_call`` events and configures the session manager callbacks to
    emit transcript and summary events back to the browser.

    Parameters
    ----------
    socketio : SocketIO
        The Flask-SocketIO instance from ``backend/app.py``.
    session_mgr : SessionManager
        The shared session manager holding per-call state.
    """
    # ----------------------------------------------------------------
    # Session manager callbacks → Socket.IO emits
    # ----------------------------------------------------------------

    def _on_interim(session_id: str, text: str) -> None:
        """Emit interim transcript to the correct browser room."""
        socketio.emit(
            "transcript_interim",
            {
                "session_id": session_id,
                "text": text,
                "timestamp": _now_iso(),
            },
            room=session_id,
        )

    def _on_final(session_id: str, text: str) -> None:
        """Emit final transcript to the correct browser room."""
        socketio.emit(
            "transcript_final",
            {
                "session_id": session_id,
                "text": text,
                "timestamp": _now_iso(),
            },
            room=session_id,
        )

    def _on_summary(session_id: str, summary: str, action_items: list) -> None:
        """Emit call summary and action items, then trigger TTS."""
        socketio.emit(
            "call_summary",
            {"session_id": session_id, "summary": summary},
            room=session_id,
        )
        socketio.emit(
            "action_items",
            {"session_id": session_id, "items": action_items},
            room=session_id,
        )
        logger.info(
            "Emitted call_summary + %d action_items for session %s",
            len(action_items),
            session_id,
        )

    # Attach callbacks to session manager
    session_mgr._on_interim_cb = _on_interim
    session_mgr._on_final_cb = _on_final
    session_mgr._on_summary_cb = _on_summary

    # ----------------------------------------------------------------
    # Socket.IO event handlers
    # ----------------------------------------------------------------

    @socketio.on("join_call")
    def on_join_call(payload: dict) -> None:
        """
        Handle a ``join_call`` event from the browser.

        Creates a new ``CallSession`` and opens a Deepgram STT WebSocket.
        The client is placed in a Socket.IO room keyed by ``session_id`` so
        that server-to-client events can be targeted correctly.

        Expected payload::

            {"session_id": "<uuid4>"}
        """
        from flask_socketio import join_room

        session_id: str = payload.get("session_id", "")
        if not session_id:
            socketio.emit("error", {"code": "MISSING_SESSION_ID", "message": "session_id is required"})
            return

        logger.info("join_call: session_id=%s", session_id)
        join_room(session_id)

        try:
            session_mgr.create_session(session_id)
            socketio.emit(
                "joined",
                {"session_id": session_id, "status": "connected"},
                room=session_id,
            )
        except Exception as exc:
            logger.error("Failed to create session %s: %s", session_id, exc)
            socketio.emit(
                "error",
                {
                    "session_id": session_id,
                    "code": "SESSION_CREATE_FAILED",
                    "message": str(exc),
                },
                room=session_id,
            )

    @socketio.on("audio_chunk")
    def on_audio_chunk(payload: dict) -> None:
        """
        Handle an ``audio_chunk`` event from the browser.

        Forwards the raw audio bytes to the Deepgram STT WebSocket for the
        matching session.

        Expected payload::

            {"session_id": "<uuid4>", "data": <bytes>}
        """
        session_id: str = payload.get("session_id", "")
        audio_data = payload.get("data")

        if not session_id or audio_data is None:
            return  # Silently drop malformed chunks

        session = session_mgr.get(session_id)
        if session is None:
            logger.warning("audio_chunk for unknown/inactive session: %s", session_id)
            return

        # ``data`` may arrive as bytes or as a base64-encoded string depending
        # on the Socket.IO transport / browser encoding.
        if isinstance(audio_data, str):
            try:
                audio_bytes = base64.b64decode(audio_data)
            except Exception:
                logger.warning("audio_chunk data is not valid base64 for session %s", session_id)
                return
        elif isinstance(audio_data, (bytes, bytearray)):
            audio_bytes = bytes(audio_data)
        else:
            logger.warning("Unexpected audio_chunk data type %s for session %s", type(audio_data), session_id)
            return

        session.send_audio(audio_bytes)

    @socketio.on("leave_call")
    def on_leave_call(payload: dict) -> None:
        """
        Handle a ``leave_call`` event from the browser.

        Closes the Deepgram STT WebSocket and triggers the end-of-call LLM
        pipeline (summarize + extract action items → emit results).

        Expected payload::

            {"session_id": "<uuid4>"}
        """
        from flask_socketio import leave_room

        session_id: str = payload.get("session_id", "")
        if not session_id:
            return

        logger.info("leave_call: session_id=%s", session_id)
        leave_room(session_id)

        transcript = session_mgr.close_session(session_id)
        if transcript is None:
            logger.warning("leave_call for unknown session: %s", session_id)
        else:
            socketio.emit(
                "call_ended",
                {"session_id": session_id, "status": "processing"},
                room=session_id,
            )


# ----------------------------------------------------------------
# Utility
# ----------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()
