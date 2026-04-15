"""
Pravaah OS — Backend Utilities

Helpers for pagination, input validation, and consistent JSON responses.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from flask import jsonify, request


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def ok(data: Any, status_code: int = 200):
    """Return a standard success JSON response."""
    return jsonify({"status": "ok", "data": data}), status_code


def error(code: str, message: str, status_code: int = 400):
    """Return a standard error JSON response."""
    return jsonify({"status": "error", "code": code, "message": message}), status_code


# ---------------------------------------------------------------------------
# Date / time
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """Return the current UTC time as an ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO8601 string. Returns None on failure."""
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def get_pagination_params(max_per_page: int = 100) -> tuple[int, int]:
    """
    Extract and validate ``page`` and ``per_page`` query parameters.

    Returns
    -------
    tuple[int, int]
        (page, per_page) both clamped to sensible bounds.
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = min(max_per_page, max(1, int(request.args.get("per_page", 20))))
    except (ValueError, TypeError):
        per_page = 20
    return page, per_page


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def require_json_fields(data: dict, *fields: str) -> Optional[str]:
    """
    Check that all listed fields are present and non-empty in ``data``.

    Returns
    -------
    str or None
        Error message string if a field is missing, or None if all present.
    """
    for field in fields:
        if field not in data or data[field] is None or str(data[field]).strip() == "":
            return f"Missing required field: {field}"
    return None


def allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed extension."""
    from .config import ALLOWED_EXTENSIONS
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_filename(filename: str) -> str:
    """Return a werkzeug-safe version of the filename."""
    from werkzeug.utils import secure_filename
    return secure_filename(filename)


def ensure_upload_folder() -> str:
    """Create the upload folder if it doesn't exist and return its path."""
    from .config import UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    return UPLOAD_FOLDER
