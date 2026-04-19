"""
Pravaah OS — /api/auth Blueprint (v2)

Endpoints:
  POST /api/auth/login    → {access_token, refresh_token, expires_in, role}
  POST /api/auth/refresh  → {access_token, expires_in}
  POST /api/auth/logout   → invalidate token
  GET  /api/auth/me       → current user info (requires auth)
  POST /api/auth/users    → create user (admin only)
"""

from __future__ import annotations

import logging
import uuid

from flask import Blueprint, g, request

from .. import database as db
from ..auth import (
    blacklist_token,
    check_password,
    decode_token,
    generate_tokens,
    hash_password,
    require_auth,
)
from ..utils import error, ok

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate with username + password. Returns JWT tokens."""
    try:
        body = request.get_json(silent=True) or {}
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", "")).strip()

        if not username or not password:
            return error("MISSING_CREDENTIALS", "username and password are required.", 400)

        user = db.get_user_by_username(username)
        if not user or not user.is_active:
            return error("INVALID_CREDENTIALS", "Invalid username or password.", 401)

        if not check_password(password, user.password_hash):
            return error("INVALID_CREDENTIALS", "Invalid username or password.", 401)

        tokens = generate_tokens(user.id, user.role)
        return ok(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "expires_in": tokens["expires_in"],
                "role": user.role,
                "username": user.username,
            }
        )
    except Exception as exc:
        logger.exception("Login error: %s", exc)
        return error("LOGIN_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------

@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Exchange a refresh token for a new access token."""
    try:
        body = request.get_json(silent=True) or {}
        refresh_token = str(body.get("refresh_token", "")).strip()

        if not refresh_token:
            return error("MISSING_TOKEN", "refresh_token is required.", 400)

        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return error("INVALID_TOKEN", "Invalid or expired refresh token.", 401)

        user = db.get_user_by_id(payload["sub"])
        if not user or not user.is_active:
            return error("USER_NOT_FOUND", "User not found or inactive.", 401)

        tokens = generate_tokens(user.id, user.role)
        return ok(
            {
                "access_token": tokens["access_token"],
                "expires_in": tokens["expires_in"],
            }
        )
    except Exception as exc:
        logger.exception("Refresh error: %s", exc)
        return error("REFRESH_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout", methods=["POST"])
@require_auth()
def logout():
    """Invalidate the current access token (add jti to Redis blacklist)."""
    try:
        jti = g.current_user.get("jti")
        if jti:
            blacklist_token(jti)
        return ok({"message": "Logged out successfully."})
    except Exception as exc:
        logger.exception("Logout error: %s", exc)
        return error("LOGOUT_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

@auth_bp.route("/me", methods=["GET"])
@require_auth()
def me():
    """Return current authenticated user info."""
    try:
        user = db.get_user_by_id(g.current_user["id"])
        if not user:
            return error("USER_NOT_FOUND", "User not found.", 404)
        return ok(user.to_dict())
    except Exception as exc:
        logger.exception("Me error: %s", exc)
        return error("ME_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# POST /api/auth/users
# ---------------------------------------------------------------------------

@auth_bp.route("/users", methods=["GET"])
@require_auth(roles=["admin"])
def list_users():
    """List all users. Admin only."""
    try:
        users = db.list_users()
        return ok({"users": [u.to_dict() for u in users]})
    except Exception as exc:
        logger.exception("List users error: %s", exc)
        return error("LIST_USERS_FAILED", str(exc), 500)


@auth_bp.route("/users", methods=["POST"])
@require_auth(roles=["admin"])
def create_user():
    """Create a new user. Admin only."""
    try:
        body = request.get_json(silent=True) or {}
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", "")).strip()
        role = str(body.get("role", "agent")).strip()

        if not username or not password:
            return error("MISSING_FIELDS", "username and password are required.", 400)

        if role not in ("agent", "supervisor", "admin"):
            return error("INVALID_ROLE", "role must be agent, supervisor, or admin.", 400)

        # Check uniqueness
        existing = db.get_user_by_username(username)
        if existing:
            return error("USERNAME_TAKEN", f"Username '{username}' is already taken.", 409)

        pw_hash = hash_password(password)
        api_key = str(uuid.uuid4())

        user_id = db.create_user(
            username=username,
            password_hash=pw_hash,
            role=role,
            api_key=api_key,
        )

        user = db.get_user_by_id(user_id)
        return ok(user.to_dict(), 201)

    except Exception as exc:
        logger.exception("Create user error: %s", exc)
        return error("CREATE_USER_FAILED", str(exc), 500)
