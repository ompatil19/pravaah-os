"""
Pravaah OS — Backend Configuration

Loads environment variables from .env (if present) and exposes typed constants
for use throughout the backend. Import this module to access all config.
"""

import os

from dotenv import load_dotenv

# Load .env file from the project root (one level above backend/)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_root, ".env"), override=False)

# ---------------------------------------------------------------------------
# Required secrets
# ---------------------------------------------------------------------------
DEEPGRAM_API_KEY: str = os.environ.get("DEEPGRAM_API_KEY", "")
OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
FLASK_SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Set DATABASE_URL to the Supabase connection string (see .env.example).
# Leave DATABASE_PATH only as a local SQLite fallback for dev/testing.
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
DATABASE_PATH: str = os.environ.get(
    "DATABASE_PATH",
    os.path.join(_root, "pravaah.db"),
)

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# ---------------------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------------------
UPLOAD_FOLDER: str = os.environ.get(
    "UPLOAD_FOLDER",
    os.path.join(_root, "uploads"),
)
MAX_UPLOAD_MB: int = int(os.environ.get("MAX_UPLOAD_MB", "10"))
MAX_CONTENT_LENGTH: int = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "doc"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/msword",
}

# ---------------------------------------------------------------------------
# Flask / SocketIO
# ---------------------------------------------------------------------------
FLASK_ENV: str = os.environ.get("FLASK_ENV", "development")
FLASK_HOST: str = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = int(os.environ.get("FLASK_PORT", "5000"))
FLASK_DEBUG: bool = FLASK_ENV == "development"

CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Deepgram
# ---------------------------------------------------------------------------
DEEPGRAM_STT_MODEL: str = os.environ.get("DEEPGRAM_STT_MODEL", "nova-2")
DEEPGRAM_TTS_MODEL: str = os.environ.get("DEEPGRAM_TTS_MODEL", "aura-asteria-en")

# ---------------------------------------------------------------------------
# OpenRouter / LLM
# ---------------------------------------------------------------------------
OPENROUTER_HEAVY_MODEL: str = os.environ.get(
    "OPENROUTER_HEAVY_MODEL", "anthropic/claude-sonnet-4-5"
)
OPENROUTER_LIGHT_MODEL: str = os.environ.get(
    "OPENROUTER_LIGHT_MODEL", "anthropic/claude-haiku-4-5-20251001"
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

# ---------------------------------------------------------------------------
# Redis (v2)
# ---------------------------------------------------------------------------
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")

# ---------------------------------------------------------------------------
# ChromaDB (v2)
# ---------------------------------------------------------------------------
CHROMA_PATH: str = os.environ.get(
    "CHROMA_PATH",
    os.path.join(_root, "chroma_db"),
)

# ---------------------------------------------------------------------------
# JWT (v2)
# ---------------------------------------------------------------------------
JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")

# ---------------------------------------------------------------------------
# Admin (v2)
# ---------------------------------------------------------------------------
ADMIN_TOKEN: str = os.environ.get("ADMIN_TOKEN", "")

# ---------------------------------------------------------------------------
# Embedding model (v2)
# ---------------------------------------------------------------------------
EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
