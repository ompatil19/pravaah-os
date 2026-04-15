# Pravaah OS

> AI-powered voice and document intelligence platform for Indian enterprises.

Pravaah OS captures, transcribes, and analyzes multilingual (Hindi-English) calls in real time, then enables semantic search across enterprise document libraries using RAG (Retrieval-Augmented Generation). It ships with JWT authentication, async job queues via Redis/RQ, ChromaDB for vector search, and Supabase (PostgreSQL) as the primary database — without any paid infrastructure beyond Deepgram and OpenRouter.

---

## Screenshots

| Dashboard | Live Call | Documents |
|-----------|-----------|-----------|
| Real-time call list with filters | Waveform visualizer + live transcript | Drag-and-drop upload with embedding progress |

---

## Features

- **Real-time STT** — Deepgram Nova-2 WebSocket streaming, hi-en multilingual
- **Live transcripts** — speaker-diarized, streamed to browser via Socket.IO
- **End-of-call LLM** — automatic summary + prioritized action items (Claude Sonnet)
- **Document RAG** — upload PDFs/DOCX/TXT → chunk → embed → semantic search via ChromaDB
- **Async jobs** — Redis + RQ queue with progress events and rq-dashboard
- **JWT auth** — bcrypt password hashing, token refresh, role-based access (agent/supervisor/admin)
- **Analytics** — call volume, average duration, language breakdown, action item counts
- **Admin panel** — user management, job queue, system health

---

## Architecture

```
Browser (React 18 + Vite + Tailwind)
    │
    │  HTTP REST + Bearer JWT          WebSocket (Socket.IO)
    │  /api/auth  /api/calls           audio_chunk → transcript_*
    │  /api/documents  /api/jobs       doc_progress events
    │  /api/analytics  /admin/rq
    ▼
┌──────────────────────────────────────────────────────────────┐
│              Flask Server (Python 3.11 + gevent)             │
│                                                              │
│  JWT Auth Layer    Rate Limiter (Redis)    structlog         │
│                                                              │
│  Routes: /api/auth  /api/calls  /api/documents               │
│          /api/analytics  /api/jobs  /admin/rq                │
│                                                              │
│  Socket.IO handlers  ←→  SQLAlchemy ORM (Supabase / SQLite)  │
└──────────────────────────────────────────────────────────────┘
    │                 │                  │
    │                 │                  └── Redis (localhost:6379)
    │                 │                       • Rate limit counters
    │                 │                       • Analytics cache (TTL 5m)
    │                 │                       • RQ job queue: pravaah
    │                 │
    │                 └── RQ Workers (rq worker pravaah)
    │                      • ingest_document  → pdfminer → Embeddings → ChromaDB
    │                      • run_end_of_call_llm → summaries, action items
    │                      • generate_analytics_cache
    │
    ├── Supabase (PostgreSQL)
    │      users, calls, transcripts, summaries, action_items, documents, jobs
    │
    ├── ChromaDB  (local vector store at CHROMA_PATH)
    │
    ├── Deepgram Nova-2 STT   wss://api.deepgram.com/v1/listen
    │
    ├── Deepgram Aura TTS     https://api.deepgram.com/v1/speak
    │
    └── OpenRouter LLM        claude-sonnet-4-5 (heavy) / claude-haiku-4-5 (light)
                              + openai/text-embedding-3-small (embeddings)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS 3, Recharts, Socket.IO client |
| Fonts | Outfit (body), Bebas Neue (stats), Fira Code (mono) |
| Backend | Flask 3, Flask-SocketIO (gevent), Flask-Limiter |
| Auth | PyJWT, bcrypt |
| Database | Supabase (PostgreSQL via SQLAlchemy + NullPool) |
| Job Queue | Redis, RQ (python-rq) |
| Vector Store | ChromaDB (local) |
| STT | Deepgram Nova-2 (WebSocket streaming, hi-en) |
| TTS | Deepgram Aura (REST) |
| LLM | OpenRouter → claude-sonnet-4-5 / claude-haiku-4-5 |
| Embeddings | OpenRouter → openai/text-embedding-3-small |

---

## Prerequisites

| Tool | Min version | Install |
|---|---|---|
| Python | 3.10+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |
| Redis | any | macOS: `brew install redis` · Ubuntu: `sudo apt-get install redis-server` |
| Supabase account | — | https://supabase.com (free tier is sufficient) |

**API keys required:**

| Service | Where to get | Free tier |
|---|---|---|
| Deepgram | https://console.deepgram.com/ | 200 min/month |
| OpenRouter | https://openrouter.ai/keys | Yes |
| Supabase | https://supabase.com | 500 MB DB, unlimited auth |

---

## Setup

### 1. Clone

```bash
git clone https://github.com/ompatil19/pravaah-os.git
cd pravaah-os
```

### 2. Create Supabase project

1. Go to [supabase.com](https://supabase.com) → **New project**
2. Note your **Project ref**, **Region**, and **Database password**
3. Open **Project Settings → API** and copy:
   - `Project URL` → `SUPABASE_URL`
   - `anon / public` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`
4. Open **Project Settings → Database → Connection string → URI** (use the **Pooler / Transaction** URI on port `6543`) → `DATABASE_URL`

### 3. Create tables in Supabase SQL Editor

Go to **SQL Editor → New query**, paste and run:

```sql
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'agent',
    api_key       TEXT UNIQUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    is_active     BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS jobs (
    id           SERIAL PRIMARY KEY,
    job_id       TEXT UNIQUE NOT NULL,
    job_type     TEXT NOT NULL,
    status       TEXT DEFAULT 'queued',
    payload_json TEXT,
    result_json  TEXT,
    error        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS calls (
    id               SERIAL PRIMARY KEY,
    session_id       TEXT UNIQUE NOT NULL,
    agent_id         TEXT NOT NULL DEFAULT 'unknown',
    status           TEXT NOT NULL DEFAULT 'active',
    language         TEXT NOT NULL DEFAULT 'hi-en',
    metadata         TEXT,
    created_at       TEXT NOT NULL,
    ended_at         TEXT,
    duration_seconds INTEGER
);

CREATE TABLE IF NOT EXISTS transcripts (
    id         SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES calls(session_id) ON DELETE CASCADE,
    text       TEXT NOT NULL,
    is_final   INTEGER NOT NULL DEFAULT 1,
    speaker    TEXT,
    timestamp  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id           SERIAL PRIMARY KEY,
    session_id   TEXT UNIQUE NOT NULL REFERENCES calls(session_id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    model_used   TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_items (
    id         SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES calls(session_id) ON DELETE CASCADE,
    text       TEXT NOT NULL,
    priority   TEXT NOT NULL DEFAULT 'medium',
    assignee   TEXT,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id           SERIAL PRIMARY KEY,
    doc_id       TEXT UNIQUE NOT NULL,
    session_id   TEXT REFERENCES calls(session_id) ON DELETE SET NULL,
    filename     TEXT NOT NULL,
    mime_type    TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    description  TEXT,
    uploaded_at  TEXT NOT NULL,
    job_id       TEXT REFERENCES jobs(job_id) ON DELETE SET NULL,
    total_pages  INTEGER,
    total_chunks INTEGER,
    status       TEXT DEFAULT 'uploading'
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id              SERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    page_number     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    embedding_model TEXT DEFAULT 'text-embedding-3-small',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transcripts_session   ON transcripts(session_id);
CREATE INDEX IF NOT EXISTS idx_action_items_session  ON action_items(session_id);
CREATE INDEX IF NOT EXISTS idx_documents_session     ON documents(session_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc   ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_calls_agent           ON calls(agent_id);
CREATE INDEX IF NOT EXISTS idx_calls_status          ON calls(status);
```

Then disable Row Level Security (we use our own JWT auth):

```sql
ALTER TABLE users           DISABLE ROW LEVEL SECURITY;
ALTER TABLE jobs            DISABLE ROW LEVEL SECURITY;
ALTER TABLE calls           DISABLE ROW LEVEL SECURITY;
ALTER TABLE transcripts     DISABLE ROW LEVEL SECURITY;
ALTER TABLE summaries       DISABLE ROW LEVEL SECURITY;
ALTER TABLE action_items    DISABLE ROW LEVEL SECURITY;
ALTER TABLE documents       DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks DISABLE ROW LEVEL SECURITY;
```

### 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# Required
DEEPGRAM_API_KEY=...
OPENROUTER_API_KEY=...
FLASK_SECRET_KEY=...       # python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=...         # python -c "import secrets; print(secrets.token_hex(32))"

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

### 5. Install dependencies & start

```bash
make setup   # creates .venv, installs Python + Node deps
./start.sh   # starts Redis + RQ worker + Flask (5000) + Vite (5173)
```

Or run each manually:

```bash
redis-server --daemonize yes
.venv/bin/rq worker pravaah &
.venv/bin/python -m backend.app &
cd frontend && npm run dev
```

### 6. Open

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:5000 |
| Health check | http://localhost:5000/health |
| Job dashboard | http://localhost:5000/admin/rq |

> Vite proxies `/api` and `/socket.io` requests to Flask on port 5000, so the frontend talks to the backend without any CORS issues in dev.

---

## API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Login, returns `access_token` + `refresh_token` |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `POST` | `/api/auth/logout` | Blacklist token |
| `GET` | `/api/auth/me` | Current user profile |
| `POST` | `/api/auth/users` | Create user (admin only) |

### Calls

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/calls` | Start a new call session |
| `GET` | `/api/calls` | List calls (paginated, filterable) |
| `GET` | `/api/calls/:sessionId` | Get call detail with transcripts + summary + action items |
| `PATCH` | `/api/calls/:sessionId/end` | End a call |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload PDF/DOCX/TXT (multipart/form-data) |
| `GET` | `/api/documents` | List documents |
| `GET` | `/api/documents/:docId` | Get document metadata |
| `GET` | `/api/documents/:docId/status` | Embedding progress |
| `POST` | `/api/documents/search` | RAG semantic search |
| `DELETE` | `/api/documents/:docId` | Delete document + chunks |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/analytics/summary` | Aggregate KPIs (total calls, duration, language breakdown) |
| `GET` | `/api/analytics/agent/:agentId` | Per-agent stats |
| `GET` | `/api/analytics/timeline` | Call volume by day |

### Jobs

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/jobs` | List background jobs |
| `GET` | `/api/jobs/:jobId` | Job status + result |

### Socket.IO Events

| Direction | Event | Payload |
|---|---|---|
| Client → Server | `audio_chunk` | `{ session_id, chunk: ArrayBuffer }` |
| Client → Server | `start_call` | `{ session_id, agent_id, language }` |
| Client → Server | `end_call` | `{ session_id }` |
| Server → Client | `transcript_partial` | `{ session_id, text, speaker }` |
| Server → Client | `transcript_final` | `{ session_id, text, speaker, timestamp }` |
| Server → Client | `doc_progress` | `{ doc_id, status, progress, total_pages, total_chunks }` |
| Server → Client | `call_summary` | `{ session_id, summary, action_items }` |

---

## Document Ingestion (RAG)

1. Upload via `POST /api/documents/upload` with `file` + optional `call_session_id`
2. Server saves file, enqueues `ingest_document` job on the `pravaah` Redis queue
3. RQ worker extracts text (pdfminer for PDFs, python-docx for DOCX), chunks it, embeds each chunk via OpenRouter, stores vectors in ChromaDB
4. Progress is emitted as `doc_progress` Socket.IO events: `QUEUED → EXTRACTING → EMBEDDING (0–100%) → DONE`
5. Query via `POST /api/documents/search` with `{ "query": "your question" }`

---

## Folder Structure

```
pravaah-os/
├── .env.example            environment variable template
├── ARCHITECTURE.md         system design document
├── Makefile                setup / dev / test / clean targets
├── README.md               this file
├── start.sh                one-command launcher
│
├── backend/                Flask REST API + Socket.IO server
│   ├── app.py              application factory + SocketIO init
│   ├── auth.py             JWT helpers, token blacklist (Redis)
│   ├── config.py           typed env var constants
│   ├── database.py         SQLAlchemy engine + all DB helper functions
│   ├── models.py           ORM models + legacy dict serializers
│   ├── socket_handlers.py  Socket.IO event handlers (STT bridge)
│   ├── utils.py            pagination, validation
│   ├── requirements.txt    Python dependencies
│   └── routes/
│       ├── auth.py         /api/auth/*
│       ├── calls.py        /api/calls/*
│       ├── documents.py    /api/documents/*
│       ├── jobs.py         /api/jobs/*
│       └── analytics.py    /api/analytics/*
│
├── pipeline/               STT / TTS / LLM clients
│   ├── deepgram_stt.py     Nova-2 WebSocket streaming client
│   ├── deepgram_tts.py     Aura REST TTS client
│   ├── openrouter_client.py LLM + embedding HTTP client
│   ├── prompt_templates.py  system/user prompts
│   └── session_manager.py  per-call state tracker
│
├── frontend/               React 18 + Vite + Tailwind
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── App.jsx         router + auth context + sidebar
│       ├── api.js          axios helpers with JWT interceptor
│       ├── socket.js       Socket.IO singleton
│       ├── index.css       design system (CSS variables, animations)
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx
│       │   ├── ActiveCall.jsx
│       │   ├── CallDetail.jsx
│       │   ├── Documents.jsx
│       │   ├── Analytics.jsx
│       │   └── AdminPage.jsx
│       └── components/
│           ├── WaveformVisualizer.jsx
│           ├── TranscriptBubble.jsx
│           ├── TranscriptDisplay.jsx
│           ├── LiveSummaryPanel.jsx
│           ├── ActionItemRow.jsx
│           ├── ActionItemsList.jsx
│           ├── CallSummaryCard.jsx
│           ├── DocumentUploader.jsx
│           ├── DocProgressBar.jsx
│           ├── CallStatusBadge.jsx
│           └── LanguageBadge.jsx
│
└── tests/
    ├── test_api.py
    ├── test_pipeline.py
    └── test_socket.py
```

---

## Running Tests

```bash
# All tests
make test

# With coverage
.venv/bin/pytest backend/tests/ tests/ --cov=backend --cov=pipeline --cov-report=term-missing

# Pipeline only
make test-pipeline
```

All tests use an isolated temporary SQLite database and mock all external HTTP/WebSocket calls — no real API keys required.

---

## Troubleshooting

**"DEEPGRAM_API_KEY not set" / no transcripts**
Verify `.env` is populated and Flask loaded it: `curl http://localhost:5000/health`

**"Error connecting to Redis"**
Start Redis: `redis-server --daemonize yes` or `brew services start redis`
Verify: `redis-cli ping` → `PONG`

**Documents stuck in "processing"**
Start the RQ worker: `make worker`
Check: `redis-cli lrange rq:queues 0 -1`

**ChromaDB permission error**
```bash
mkdir -p chroma_store && chmod 755 chroma_store
```

**WebSocket CORS error in browser**
- Confirm `VITE_WS_URL=http://localhost:5000` is set in `.env`
- Vite's proxy (`frontend/vite.config.js`) must forward `/socket.io/*` to Flask
- JWT must be passed in Socket.IO handshake auth

**Supabase: "SSL connection required" or prepared statement errors**
Make sure `DATABASE_URL` uses the **Pooler URI** (port `6543`, Transaction mode), not the direct connection (port `5432`). The backend configures `NullPool` + `sslmode=require` automatically.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEEPGRAM_API_KEY` | Yes | — | Deepgram STT + TTS |
| `OPENROUTER_API_KEY` | Yes | — | LLM + embeddings |
| `FLASK_SECRET_KEY` | Yes | dev-secret | Flask session signing |
| `JWT_SECRET_KEY` | Yes | dev-jwt-secret | JWT signing |
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | — | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | — | Supabase service role key |
| `DATABASE_URL` | Yes | — | PostgreSQL connection URI (Supabase pooler) |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection |
| `CHROMA_PATH` | No | `./chroma_store` | ChromaDB storage path |
| `UPLOAD_FOLDER` | No | `./uploads` | File upload directory |
| `MAX_UPLOAD_MB` | No | `200` | Max file size in MB |
| `FLASK_PORT` | No | `5000` | Flask server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `OPENROUTER_HEAVY_MODEL` | No | `anthropic/claude-sonnet-4-5` | LLM for summaries |
| `OPENROUTER_LIGHT_MODEL` | No | `anthropic/claude-haiku-4-5-20251001` | LLM for light tasks |
| `EMBEDDING_MODEL` | No | `openai/text-embedding-3-small` | Embedding model |
| `ADMIN_TOKEN` | No | — | Token to access /admin/rq |

---

## License

MIT
