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
import threading
from datetime import datetime, timezone

from flask_socketio import SocketIO, emit, join_room, leave_room

from . import database as db

logger = logging.getLogger(__name__)

# Module-level references set by app.py during init
_socketio: SocketIO | None = None
_session_manager = None  # pipeline.SessionManager


def init_handlers(socketio: SocketIO) -> None:
    """Register all Socket.IO event handlers. Called once from app.py."""
    global _socketio
    _socketio = socketio
    _init_session_manager()
    _register_events(socketio)
    logger.info("Socket.IO handlers registered.")


# ---------------------------------------------------------------------------
# Session Manager bootstrap
# ---------------------------------------------------------------------------

def _init_session_manager():
    """Lazy-init the pipeline SessionManager with the Deepgram API key."""
    global _session_manager
    try:
        from pipeline.session_manager import SessionManager
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        _session_manager = SessionManager(
            api_key=api_key,
            on_transcript=_on_transcript,
            on_error=_on_pipeline_error,
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

    # Trigger non-blocking LLM ack + TTS
    threading.Thread(
        target=_run_realtime_llm,
        args=(session_id, text),
        daemon=True,
        name=f"llm-rt-{session_id}",
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
# LLM pipeline helpers
# ---------------------------------------------------------------------------

def _run_realtime_llm(session_id: str, latest_transcript: str) -> None:
    """
    After a final transcript: generate a short TTS acknowledgement and
    emit it as audio. Runs in a background thread.
    """
    try:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        dg_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key or not dg_key:
            return

        from pipeline.openrouter_client import OpenRouterLLMClient
        from pipeline.deepgram_tts import DeepgramTTSClient

        llm = OpenRouterLLMClient(api_key=api_key)
        ack_text = llm.detect_language(latest_transcript)  # light model call
        # Generate acknowledgement
        from pipeline.prompt_templates import SYSTEM_ACK
        ack_text = llm._call(
            [
                {"role": "system", "content": SYSTEM_ACK},
                {"role": "user", "content": f"Customer said: {latest_transcript}\nAcknowledge briefly."},
            ],
            model=os.environ.get("OPENROUTER_LIGHT_MODEL", "anthropic/claude-haiku-4-5-20251001"),
            temperature=0.5,
            max_tokens=60,
        )
        llm.close()

        # TTS
        tts = DeepgramTTSClient(api_key=dg_key)
        audio_bytes = tts.synthesize(ack_text)
        tts.close()

        audio_b64 = base64.b64encode(audio_bytes).decode()
        if _socketio:
            _socketio.emit(
                "tts_audio",
                {"session_id": session_id, "audio": audio_b64},
                room=session_id,
            )
    except Exception as exc:
        logger.warning("[%s] Real-time LLM/TTS failed: %s", session_id, exc)


def _run_final_llm_pipeline(session_id: str) -> None:
    """
    On call end: generate full summary + action items and emit them.
    Runs in a background thread.
    """
    try:
        transcript_rows = db.get_transcripts(session_id)
        if not transcript_rows:
            return

        full_text = " ".join(r["text"] for r in transcript_rows if r["is_final"])
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
            call_row = db.get_call(session_id)
            language = call_row["language"] if call_row else "hi-en"
            ok = _session_manager.create_session(session_id, language)
            if not ok:
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
            _session_manager.send_audio(session_id, audio_bytes)

    @socketio.on("leave_call")
    def handle_leave_call(payload):
        """Client ends the call; close STT and run final LLM pipeline."""
        session_id = (payload or {}).get("session_id", "")
        if not session_id:
            return

        leave_room(session_id)
        logger.info("[%s] Client left room.", session_id)

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
