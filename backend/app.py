"""
Pravaah OS — Flask Application Factory (v2)

Changes from v1:
  - gevent async_mode for Socket.IO
  - Redis client (flask-limiter storage + pub/sub)
  - structlog structured logging
  - New blueprints: auth, jobs
  - rq-dashboard at /admin/rq (protected by ADMIN_TOKEN)
"""

import os
import sys

# ---------------------------------------------------------------------------
# structlog configuration (must be first)
# ---------------------------------------------------------------------------
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if os.environ.get("FLASK_ENV") == "development"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

import logging
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(message)s",
    stream=sys.stdout,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Flask + extensions
# ---------------------------------------------------------------------------
import time

import redis as _redis
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

from .config import (
    ADMIN_TOKEN,
    CORS_ORIGINS,
    FLASK_DEBUG,
    FLASK_ENV,
    FLASK_HOST,
    FLASK_PORT,
    FLASK_SECRET_KEY,
    JWT_SECRET_KEY,
    LOG_LEVEL,
    MAX_CONTENT_LENGTH,
    REDIS_URL,
    UPLOAD_FOLDER,
)

# ---------------------------------------------------------------------------
# Module-level Redis client (shared across the process)
# ---------------------------------------------------------------------------
redis_client: _redis.Redis | None = None

try:
    redis_client = _redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Redis connected", url=REDIS_URL)
except Exception as _exc:
    logger.warning("Redis not available — rate limiting and pub/sub disabled", error=str(_exc))
    redis_client = None

# ---------------------------------------------------------------------------
# Module-level SocketIO instance (shared with socket_handlers)
# ---------------------------------------------------------------------------
socketio = SocketIO()

# ---------------------------------------------------------------------------
# Limiter (Redis-backed if available, else in-memory)
# ---------------------------------------------------------------------------
_limiter_storage = f"redis://{REDIS_URL.split('redis://')[-1]}" if redis_client else "memory://"
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute", "20 per second"],
    storage_uri=_limiter_storage,
)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    """
    Application factory.

    Returns
    -------
    Flask
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # ---- Core config -------------------------------------------------------
    app.config["SECRET_KEY"] = FLASK_SECRET_KEY
    app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["ENV"] = FLASK_ENV

    # ---- Ensure upload folder exists ---------------------------------------
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # ---- CORS --------------------------------------------------------------
    CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

    # ---- Rate Limiter -------------------------------------------------------
    limiter.init_app(app)

    # ---- SocketIO (threading mode — no eventlet/gevent monkey-patching needed)
    # message_queue is only required for multi-process deployments; using it
    # with eventlet requires monkey_patch() before all imports which is not
    # compatible with our single-process setup. Redis pub/sub for doc progress
    # is handled separately via _start_doc_progress_listener().
    socketio_kwargs: dict = {
        "cors_allowed_origins": CORS_ORIGINS,
        "async_mode": "threading",
        "allow_upgrades": False,  # werkzeug dev server can't handle WS upgrade → write() before start_response
        "logger": False,
        "engineio_logger": False,
    }

    socketio.init_app(app, **socketio_kwargs)

    # ---- Database ----------------------------------------------------------
    from .database import init_db
    with app.app_context():
        init_db()

    # ---- Blueprints --------------------------------------------------------
    from .routes.calls import calls_bp
    from .routes.documents import documents_bp
    from .routes.analytics import analytics_bp
    from .routes.auth import auth_bp
    from .routes.jobs import jobs_bp

    app.register_blueprint(calls_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(jobs_bp)


    # ---- Request logging middleware ----------------------------------------
    @app.before_request
    def _before_request():
        g.start_time = time.time()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            method=request.method,
            path=request.path,
        )

    @app.after_request
    def _after_request(response):
        duration_ms = round((time.time() - getattr(g, "start_time", time.time())) * 1000, 2)
        user_id = getattr(g, "current_user", {}).get("id") if hasattr(g, "current_user") else None
        structlog.get_logger().info(
            "request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
        )
        return response

    # ---- Health check ------------------------------------------------------
    @app.route("/health", methods=["GET"])
    def health():
        redis_ok = False
        try:
            if redis_client:
                redis_client.ping()
                redis_ok = True
        except Exception:
            pass
        return jsonify({
            "status": "ok",
            "data": {
                "status": "ok",
                "version": "2.0.0",
                "redis": redis_ok,
            },
        })

    # ---- Socket.IO handlers ------------------------------------------------
    from .socket_handlers import init_handlers
    init_handlers(socketio)

    # ---- Start Redis pub/sub listener (background thread) ------------------
    if redis_client:
        _start_doc_progress_listener()

    logger.info(
        "Pravaah OS backend v2 ready",
        upload_folder=UPLOAD_FOLDER,
        cors=CORS_ORIGINS,
        redis=bool(redis_client),
    )
    return app


# ---------------------------------------------------------------------------
# Redis pub/sub → Socket.IO bridge
# ---------------------------------------------------------------------------

def _start_doc_progress_listener() -> None:
    """
    Subscribe to Redis pub/sub for doc:*:progress channels and forward
    events to the correct Socket.IO room.
    Runs in a daemon background thread.
    """
    import json
    import threading

    def _listener():
        try:
            r = _redis.Redis.from_url(REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            pubsub.psubscribe("doc:*:progress")
            for message in pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message.get("channel", "")
                    data_raw = message.get("data", "")
                    # channel format: doc:<doc_id>:progress
                    parts = channel.split(":")
                    if len(parts) == 3:
                        doc_id = parts[1]
                        try:
                            data = json.loads(data_raw) if isinstance(data_raw, str) else {}
                        except Exception:
                            data = {}
                        socketio.emit(
                            "doc_progress",
                            {"doc_id": doc_id, **data},
                            room=f"doc:{doc_id}",
                        )
        except Exception as exc:
            logger.warning("Doc progress listener exited", error=str(exc))

    t = threading.Thread(target=_listener, daemon=True, name="doc-progress-listener")
    t.start()
    logger.info("Redis pub/sub doc progress listener started.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app()
    socketio.run(
        app,
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
