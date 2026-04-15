"""
Pravaah OS — /api/analytics Blueprint

Endpoints:
  GET /api/analytics/summary          → aggregate stats across all calls
  GET /api/analytics/agent/<agent_id> → per-agent statistics
"""

import logging

from flask import Blueprint, request

from .. import database as db
from ..auth import require_auth
from ..utils import error, ok

logger = logging.getLogger(__name__)
analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


# ---------------------------------------------------------------------------
# GET /api/analytics/summary
# ---------------------------------------------------------------------------

@analytics_bp.route("/summary", methods=["GET"])
@require_auth()
def analytics_summary():
    """
    Return aggregate call statistics.

    Query params:
        from (ISO8601) — filter calls after this date
        to   (ISO8601) — filter calls before this date
    """
    try:
        from_date = request.args.get("from") or None
        to_date = request.args.get("to") or None
        data = db.analytics_summary(from_date, to_date)
        return ok(data)
    except Exception as exc:
        logger.exception("Error fetching analytics summary: %s", exc)
        return error("ANALYTICS_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/analytics/agent/<agent_id>
# ---------------------------------------------------------------------------

@analytics_bp.route("/agent/<agent_id>", methods=["GET"])
@require_auth()
def analytics_agent(agent_id: str):
    """Return per-agent call statistics."""
    try:
        if not agent_id or not agent_id.strip():
            return error("INVALID_AGENT_ID", "agent_id must not be empty.", 400)

        data = db.analytics_agent(agent_id.strip())
        if data is None:
            return error("AGENT_NOT_FOUND", f"No calls found for agent '{agent_id}'.", 404)

        return ok(data)
    except Exception as exc:
        logger.exception("Error fetching agent analytics for %s: %s", agent_id, exc)
        return error("AGENT_ANALYTICS_FAILED", str(exc), 500)
