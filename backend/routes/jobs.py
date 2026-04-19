"""
Pravaah OS — /api/jobs Blueprint (v2)

Endpoints:
  GET /api/jobs/<job_id>  → job status from DB + RQ
  GET /api/jobs/          → list recent jobs (admin only, paginated)
"""

from __future__ import annotations

import logging

from flask import Blueprint
from .. import database as db
from ..auth import require_auth
from ..utils import error, get_pagination_params, ok

logger = logging.getLogger(__name__)
jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


def _rq_job_status_safe(job_id: str) -> str | None:
    """Fetch live RQ job status with a different import path."""
    try:
        import redis as _redis
        import os
        r = _redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        from rq.job import Job as RQJob
        rq_job = RQJob.fetch(job_id, connection=r)
        return rq_job.get_status().value
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GET /api/jobs/<job_id>
# ---------------------------------------------------------------------------

@jobs_bp.route("/<job_id>", methods=["GET"])
@require_auth()
def get_job(job_id: str):
    """Return DB job record plus live RQ status."""
    try:
        job = db.get_job(job_id)
        if not job:
            return error("JOB_NOT_FOUND", f"Job {job_id} not found.", 404)

        job_dict = job.to_dict()
        # Augment with live RQ status
        live_status = _rq_job_status_safe(job_id)
        if live_status:
            job_dict["rq_status"] = live_status

        return ok(job_dict)
    except Exception as exc:
        logger.exception("Get job error for %s: %s", job_id, exc)
        return error("GET_JOB_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/jobs/
# ---------------------------------------------------------------------------

@jobs_bp.route("", methods=["GET"])
@require_auth(roles=["admin"])
def list_jobs():
    """List recent jobs (admin only), paginated."""
    try:
        page, per_page = get_pagination_params(max_per_page=100)
        rows, total = db.list_jobs(page=page, per_page=per_page)

        return ok(
            {
                "jobs": [r.to_dict() for r in rows],
                "total": total,
                "page": page,
                "per_page": per_page,
            }
        )
    except Exception as exc:
        logger.exception("List jobs error: %s", exc)
        return error("LIST_JOBS_FAILED", str(exc), 500)
