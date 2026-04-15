"""
Pravaah OS — /api/calls Blueprint

Endpoints:
  POST /api/calls/start            → create a new call session
  POST /api/calls/<session_id>/end → end a call and trigger async summary
  GET  /api/calls                  → paginated call list
  GET  /api/calls/<session_id>     → full call detail
"""

import logging
import threading
import uuid
from typing import Optional

from flask import Blueprint, request

from .. import database as db
from ..models import (
    action_item_to_dict,
    call_list_item,
    call_to_dict,
    summary_to_dict,
    transcript_to_dict,
)
from ..auth import require_auth
from ..utils import error, get_pagination_params, now_iso, ok, parse_iso

logger = logging.getLogger(__name__)
calls_bp = Blueprint("calls", __name__, url_prefix="/api/calls")


# ---------------------------------------------------------------------------
# POST /api/calls/start
# ---------------------------------------------------------------------------

@calls_bp.route("/start", methods=["POST"])
@require_auth()
def start_call():
    """Create a new call session. Returns session_id and call_id."""
    try:
        body = request.get_json(silent=True) or {}
        agent_id = str(body.get("agent_id", "unknown")).strip() or "unknown"
        language = str(body.get("language", "hi-en")).strip() or "hi-en"
        metadata = body.get("metadata")

        import json
        metadata_str: Optional[str] = json.dumps(metadata) if metadata else None

        session_id = str(uuid.uuid4())
        created_at = now_iso()

        call_id = db.insert_call(session_id, agent_id, language, metadata_str, created_at)

        return ok(
            {
                "session_id": session_id,
                "call_id": call_id,
                "status": "active",
                "created_at": created_at,
            },
            201,
        )
    except Exception as exc:
        logger.exception("Error starting call: %s", exc)
        return error("START_CALL_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# POST /api/calls/<session_id>/end
# ---------------------------------------------------------------------------

@calls_bp.route("/<session_id>/end", methods=["POST"])
@require_auth()
def end_call(session_id: str):
    """End a call session and trigger async LLM summary generation."""
    try:
        call_row = db.get_call(session_id)
        if not call_row:
            return error("CALL_NOT_FOUND", f"Session {session_id} not found.", 404)

        if call_row["status"] == "ended":
            return ok(
                {
                    "session_id": session_id,
                    "status": "ended",
                    "message": "Call already ended.",
                }
            )

        ended_at = now_iso()
        created_at_dt = parse_iso(call_row["created_at"])
        ended_at_dt = parse_iso(ended_at)
        duration = 0
        if created_at_dt and ended_at_dt:
            duration = max(0, int((ended_at_dt - created_at_dt).total_seconds()))

        db.end_call(session_id, ended_at, duration)

        transcript_count = db.count_transcripts(session_id)

        # Fire async summary if transcripts exist and no summary yet
        if transcript_count > 0 and not db.get_summary(session_id):
            _trigger_summary_async(session_id)

        return ok(
            {
                "session_id": session_id,
                "status": "ended",
                "duration_seconds": duration,
                "transcript_count": transcript_count,
                "ended_at": ended_at,
            }
        )
    except Exception as exc:
        logger.exception("Error ending call %s: %s", session_id, exc)
        return error("END_CALL_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/calls
# ---------------------------------------------------------------------------

@calls_bp.route("/", methods=["GET"])
@require_auth()
def list_calls():
    """Paginated call list with optional filters."""
    try:
        page, per_page = get_pagination_params(max_per_page=100)
        agent_id = request.args.get("agent_id") or None
        status = request.args.get("status") or None
        from_date = request.args.get("from") or None
        to_date = request.args.get("to") or None

        # Validate status
        if status and status not in ("active", "ended"):
            return error("INVALID_STATUS", "status must be 'active' or 'ended'.", 400)

        rows, total = db.list_calls(page, per_page, agent_id, status, from_date, to_date)

        calls = []
        for row in rows:
            summary_row = db.get_summary(row["session_id"])
            preview = None
            if summary_row:
                preview = (summary_row["text"] or "")[:120]
            calls.append(call_list_item(row, preview))

        return ok(
            {
                "calls": calls,
                "total": total,
                "page": page,
                "per_page": per_page,
            }
        )
    except Exception as exc:
        logger.exception("Error listing calls: %s", exc)
        return error("LIST_CALLS_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/calls/<session_id>
# ---------------------------------------------------------------------------

@calls_bp.route("/<session_id>", methods=["GET"])
@require_auth()
def get_call(session_id: str):
    """Full call detail including transcripts, summary, and action items."""
    try:
        call_row = db.get_call(session_id)
        if not call_row:
            return error("CALL_NOT_FOUND", f"Session {session_id} not found.", 404)

        call_data = call_to_dict(call_row)

        transcript_rows = db.get_transcripts(session_id)
        call_data["transcripts"] = [transcript_to_dict(t) for t in transcript_rows]

        summary_row = db.get_summary(session_id)
        call_data["summary"] = summary_to_dict(summary_row) if summary_row else None

        action_rows = db.get_action_items(session_id)
        call_data["action_items"] = [action_item_to_dict(a) for a in action_rows]

        return ok(call_data)
    except Exception as exc:
        logger.exception("Error fetching call %s: %s", session_id, exc)
        return error("GET_CALL_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# Internal helper — async LLM summary
# ---------------------------------------------------------------------------

def _trigger_summary_async(session_id: str) -> None:
    """Kick off summary generation in a background thread."""
    thread = threading.Thread(
        target=_generate_summary,
        args=(session_id,),
        daemon=True,
        name=f"summary-{session_id}",
    )
    thread.start()


def _generate_summary(session_id: str) -> None:
    """Background task: call OpenRouter to generate summary + action items."""
    try:
        import os
        from pipeline.openrouter_client import OpenRouterLLMClient

        transcript_rows = db.get_transcripts(session_id)
        if not transcript_rows:
            return

        full_text = " ".join(r["text"] for r in transcript_rows if r["is_final"])
        if not full_text.strip():
            return

        client = OpenRouterLLMClient(api_key=os.environ.get("OPENROUTER_API_KEY", ""))
        generated_at = now_iso()

        # Generate summary
        summary_text = client.summarize_transcript(full_text)
        model_used = os.environ.get("OPENROUTER_HEAVY_MODEL", "anthropic/claude-sonnet-4-5")
        db.insert_summary(session_id, summary_text, model_used, generated_at)

        # Extract action items
        items = client.extract_action_items(full_text)
        for item in items:
            text = item.get("action") or item.get("text", "")
            priority = item.get("priority", "medium")
            assignee = item.get("owner") or item.get("assignee")
            if text:
                db.insert_action_item(session_id, text, priority, assignee, now_iso())

        client.close()
        logger.info("[%s] Async summary + action items generated.", session_id)

    except Exception as exc:
        logger.error("[%s] Async summary generation failed: %s", session_id, exc)
