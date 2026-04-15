"""
Pravaah OS — JWT + API Key Authentication (v2)

Provides:
  - generate_tokens(user_id, role) → {access_token, refresh_token}
  - require_auth(roles=None)       → decorator for route protection
  - hash_password / check_password → bcrypt helpers
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, Optional

import jwt
import bcrypt
from flask import g, jsonify, request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
_ALGORITHM = "HS256"
_ACCESS_TOKEN_TTL_HOURS = 24
_REFRESH_TOKEN_TTL_DAYS = 7


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def generate_tokens(user_id: int, role: str) -> dict:
    """
    Generate an access token (24 h) and a refresh token (7 d).

    Returns
    -------
    dict with keys: access_token, refresh_token, expires_in (seconds)
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())

    access_payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(hours=_ACCESS_TOKEN_TTL_HOURS),
        "type": "access",
    }

    refresh_payload = {
        "sub": user_id,
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(days=_REFRESH_TOKEN_TTL_DAYS),
        "type": "refresh",
    }

    access_token = jwt.encode(access_payload, _JWT_SECRET, algorithm=_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, _JWT_SECRET, algorithm=_ALGORITHM)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": _ACCESS_TOKEN_TTL_HOURS * 3600,
    }


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT. Returns payload dict or None on failure."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _is_token_blacklisted(jti: str) -> bool:
    """Check Redis blacklist for the given jti. Returns False if Redis unavailable."""
    try:
        from .app import redis_client
        if redis_client is None:
            return False
        return redis_client.exists(f"blacklist:{jti}") > 0
    except Exception:
        return False


def blacklist_token(jti: str, ttl_seconds: int = _ACCESS_TOKEN_TTL_HOURS * 3600) -> None:
    """Add a jti to the Redis blacklist with TTL."""
    try:
        from .app import redis_client
        if redis_client:
            redis_client.setex(f"blacklist:{jti}", ttl_seconds, "1")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns the hash as a str."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def require_auth(roles: Optional[list[str]] = None) -> Callable:
    """
    Route decorator that enforces JWT or API-key authentication.

    Sets g.current_user = {"id": int, "username": str, "role": str}

    Parameters
    ----------
    roles : list[str] | None
        If provided, access is denied unless g.current_user["role"] is in the list.
        e.g. @require_auth(roles=["admin"])
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_info = _authenticate_request()
            if user_info is None:
                return jsonify(
                    {"status": "error", "code": "UNAUTHORIZED", "message": "Authentication required."}
                ), 401

            if roles and user_info.get("role") not in roles:
                return jsonify(
                    {"status": "error", "code": "FORBIDDEN", "message": "Insufficient permissions."}
                ), 403

            g.current_user = user_info
            return f(*args, **kwargs)
        return wrapper
    return decorator


def _authenticate_request() -> Optional[dict]:
    """
    Try to authenticate the current request via:
    1. Authorization: Bearer <JWT>
    2. X-API-Key: <api_key>

    Returns user info dict or None.
    """
    # --- JWT Bearer ---
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            jti = payload.get("jti", "")
            if _is_token_blacklisted(jti):
                return None
            # Fetch fresh user info from DB
            try:
                from . import database as db_module
                user = db_module.get_user_by_id(payload["sub"])
                if user and user.is_active:
                    return {
                        "id": user.id,
                        "username": user.username,
                        "role": user.role,
                        "jti": jti,
                    }
            except Exception:
                pass
        return None

    # --- API Key ---
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        try:
            from . import database as db_module
            user = db_module.get_user_by_api_key(api_key)
            if user and user.is_active:
                return {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "jti": None,
                }
        except Exception:
            pass

    return None
