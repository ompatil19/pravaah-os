# Pravaah OS

> **Multilingual Call Intelligence Platform for Indian Enterprises**

Pravaah OS turns live customer service calls into structured, searchable intelligence — in real time. It transcribes Hindi-English code-switched speech, responds via a conversational AI assistant (with voice playback), auto-generates call summaries and action items, and lets teams query their entire call history and document library with natural language.

Built without any voice frameworks — every layer is wired from first principles so every component is visible, tuneable, and swappable.

---

## Table of Contents

- [What It Solves](#what-it-solves)
- [Feature Walkthrough](#feature-walkthrough)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Socket.IO Events](#socketio-events)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Running the App](#running-the-app)
- [Project Structure](#project-structure)
- [Pages & UI](#pages--ui)
- [Key Design Decisions](#key-design-decisions)
- [Troubleshooting](#troubleshooting)

---

## What It Solves

Indian enterprise call centers handle thousands of multilingual calls every day. The business intelligence inside those calls — customer complaints, agent promises, follow-up actions — is almost impossible to capture at scale.

Pravaah OS sits inside every call and automatically:

1. **Transcribes** mixed Hindi-English speech in real time
2. **Replies** via an AI assistant so agents get instant, spoken support
3. **Summarises** every call the moment it ends
4. **Extracts** prioritised action items with owners and deadlines
5. **Indexes** uploaded documents for plain-English semantic search

---

## Feature Walkthrough

### Real-Time Call Transcription

- Streams microphone audio from the browser to **Deepgram Nova-2** over a WebSocket
- Handles Hindi-English code-switched (`hi-en`) speech natively
- Emits live **interim** transcripts as the speaker talks; persists **final** segments to the database
- Displays an animated waveform visualiser during the call

### Conversational AI Assistant

- After every final transcript segment, a background thread sends the full conversation history to an LLM via **OpenRouter**
- Keeps a rolling 20-turn window to bound token usage
- The LLM reply is immediately shown in the UI via a `ai_reply` Socket.IO event
- The reply is simultaneously spoken aloud using **Deepgram Aura TTS** and streamed back as base64 MP3
- **Interruption detection**: if the user speaks again before TTS is ready, the stale audio is silently dropped — no awkward overlapping speech

### Live & Final Call Summaries

- A lightweight summary is regenerated every 5 transcript segments so supervisors can monitor calls in progress
- On call end, the heavy LLM produces a final structured summary covering: **Issue · Key Facts · Promises Made · Next Action**
- Both live and final summaries are emitted over Socket.IO and persisted to the database

### Action Item Extraction

- On call end, a second LLM pass extracts every follow-up task as structured JSON
- Each item includes: `text`, `priority` (high / medium / low), `assignee`, and `deadline_mentioned`
- Items are stored in the database and displayed per call with priority colour-coding

### Intent & Sentiment Classification

- Classifies each transcript by intent: `inquiry | complaint | order | support | other`
- Returns sentiment: `positive | neutral | negative` with a confidence score between 0 and 1

### Language Detection

- Detects the primary language of any transcript as `hi` · `en` · `hi-en`
- Used to tag calls and drive display formatting

### Document Intelligence (RAG)

- Upload **PDF, DOCX, or TXT** files up to 200 MB
- Documents are chunked (1 000 chars, 100-char overlap) and embedded into **ChromaDB**
- Ingestion runs as an **RQ background job** (falls back to an inline thread if Redis is unavailable)
- Real-time ingestion progress is pushed to the browser over Socket.IO via a Redis pub/sub bridge
- Ask plain-English questions against any subset of documents; the RAG engine retrieves the most relevant chunks, builds a grounded context, and calls the LLM — answers cite source documents
- Query results are cached in Redis for 10 minutes

### Analytics Dashboard

- Aggregate stats: total calls, average handle time, escalation rate, calls per day
- Per-agent breakdown: call count, average duration, sentiment distribution
- Date-range filtering on all analytics endpoints
- Recharts visualisations for call volume trends

### Authentication & Access Control

- **JWT-based auth** with short-lived access tokens and long-lived refresh tokens
- Token blacklisting via Redis (`jti` key stored on logout)
- Role-based access: `agent · supervisor · admin`
- Socket.IO connections validate the JWT at connect time — unauthenticated connections are rejected

### Rate Limiting & Observability

- Redis-backed rate limiter: 200 req/min, 20 req/sec per IP (falls back to in-memory if Redis is down)
- **structlog** structured JSON logging (pretty-printed in development mode)
- Per-request duration logged with method, path, status code, and user ID
- `/health` endpoint reports Flask and Redis status

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Speech-to-Text** | Deepgram Nova-2 — WebSocket streaming, `hi-en` language model |
| **Text-to-Speech** | Deepgram Aura — REST synthesis, base64 MP3 |
| **LLM — heavy tasks** | OpenRouter (summaries, action items, RAG answers) |
| **LLM — realtime** | OpenRouter (live conversational replies, ≤8 s timeout) |
| **Embeddings** | OpenRouter embedding model (configurable) |
| **Backend** | Python 3.12 · Flask 3 · Flask-SocketIO · SQLAlchemy 2 |
| **Database** | Supabase (PostgreSQL) |
| **Vector Store** | ChromaDB 0.5 — persistent local filesystem |
| **Job Queue** | Redis + RQ |
| **Frontend** | React 18 · Vite 5 · Tailwind CSS 3 · Recharts · socket.io-client 4 |
| **Auth** | PyJWT + bcrypt |

---

## Architecture

```
Browser (React + Vite)
  │
  ├── REST (axios)        ──►  Flask Blueprints
  │                              ├── /api/auth         JWT login / refresh / logout
  │                              ├── /api/calls        Session CRUD + summaries
  │                              ├── /api/documents    Upload + RAG search
  │                              ├── /api/analytics    Aggregate + per-agent stats
  │                              └── /api/jobs         RQ job status
  │
  └── Socket.IO           ──►  Flask-SocketIO
        │                        ├── join_call   → opens Deepgram WebSocket
        │                        ├── audio_chunk → forwards PCM to Deepgram
        │                        └── leave_call  → closes WS, triggers LLM pipeline
        │
        ◄── transcript_interim / transcript_final
        ◄── ai_reply / tts_audio
        ◄── call_summary / action_items
        ◄── doc_progress

Pipeline (background threads)
  ├── DeepgramSTTClient       WebSocket → transcript callbacks
  ├── DeepgramTTSClient       REST → MP3 bytes
  ├── OpenRouterLLMClient     chat completions (retry + exponential backoff)
  ├── RAGEngine               ChromaDB retrieval + LLM grounded answer
  └── DocumentProcessor       chunk + embed + store  (RQ job)

Data
  ├── Supabase (PostgreSQL)   calls · transcripts · summaries · action_items
  │                           documents · document_chunks · users · jobs
  ├── ChromaDB                document chunk embeddings
  └── Redis                   rate limits · JWT blacklist · RQ queues · pub/sub
```

### LLM Model Routing

Heavy tasks (summarise, extract action items, RAG answers) go to `OPENROUTER_HEAVY_MODEL`.  
Light / realtime tasks (conversation replies, language detection, intent) go to `OPENROUTER_LIGHT_MODEL`.  
Both are fully configurable via environment variables — swap to any model on OpenRouter with no code changes.

---

## API Reference

All endpoints except `/health` and `/api/auth/login` require `Authorization: Bearer <access_token>`.

### Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Login with `username` + `password` → `access_token`, `refresh_token`, `role` |
| `POST` | `/api/auth/refresh` | Exchange `refresh_token` → new `access_token` |
| `POST` | `/api/auth/logout` | Blacklist the current `jti` in Redis |
| `GET` | `/api/auth/me` | Current authenticated user info |
| `GET` | `/api/auth/users` | List all users *(admin only)* |
| `POST` | `/api/auth/users` | Create user *(admin only)* — `{username, password, role}` |

### Calls

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/calls/start` | Create a call session → `{session_id, call_id, status}` |
| `POST` | `/api/calls/:session_id/end` | End a call; triggers async summary generation |
| `GET` | `/api/calls` | Paginated list — query params: `agent_id`, `status`, `from`, `to`, `page`, `per_page` |
| `GET` | `/api/calls/:session_id` | Full detail: transcripts + summary + action items |

### Documents

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Multipart upload (PDF, DOCX, TXT) — fields: `file`, `call_session_id?`, `description?` |
| `GET` | `/api/documents` | Paginated document list |
| `GET` | `/api/documents/:doc_id` | Document record |
| `GET` | `/api/documents/:doc_id/status` | Ingestion status + RQ job status |
| `POST` | `/api/documents/search` | RAG semantic search — `{query, doc_ids?, top_k?}` → `{answer, sources, cached}` |

### Analytics

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/analytics/summary` | Aggregate stats — query params: `from`, `to` |
| `GET` | `/api/analytics/agent/:agent_id` | Per-agent call statistics |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | `{status, version, redis: bool}` |

---

## Socket.IO Events

The Socket.IO client must pass a JWT at connection time:

```js
io(WS_URL, { auth: { token: localStorage.getItem('pravaah_access_token') } })
```

### Client → Server

| Event | Payload | Description |
|---|---|---|
| `join_call` | `{session_id}` | Open a Deepgram STT WebSocket for the session |
| `audio_chunk` | `{session_id, data: base64}` | Forward a raw PCM audio chunk |
| `leave_call` | `{session_id}` | Close STT; trigger final summary + action items |
| `subscribe_doc_progress` | `{doc_id}` | Subscribe to document ingestion progress events |

### Server → Client

| Event | Payload | Description |
|---|---|---|
| `transcript_interim` | `{session_id, text, timestamp}` | Live partial transcript (not persisted) |
| `transcript_final` | `{session_id, text, timestamp}` | Persisted final transcript segment |
| `ai_reply` | `{session_id, text}` | LLM text reply (always emitted before TTS check) |
| `tts_audio` | `{session_id, audio: base64 MP3}` | Synthesised voice reply |
| `call_summary` | `{session_id, summary}` | Live (every 5 segments) or final summary |
| `action_items` | `{session_id, items: [{text, priority, assignee}]}` | Extracted action items |
| `doc_progress` | `{doc_id, status, ...}` | Real-time ingestion progress via Redis pub/sub |
| `error` | `{session_id, code, message}` | Pipeline error |

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11 + | Tested on 3.12 |
| Node.js | 18 + | For the Vite dev server |
| Redis | 7 + | `brew install redis` on macOS |
| Deepgram account | — | Free tier: 200 min/month |
| OpenRouter account | — | Free tier available |
| Supabase project | — | Free tier available |

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/pravaah-os.git
cd pravaah-os
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in every required value. Full reference in the [Environment Variables](#environment-variables) section below.

### 3. Create tables in Supabase

Go to **Supabase dashboard → SQL Editor → New query**, paste and run the following:

```sql
-- Users
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'agent',
    api_key       TEXT UNIQUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    is_active     BOOLEAN DEFAULT TRUE
);

-- Jobs (RQ task tracking)
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

-- Calls
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

-- Transcripts
CREATE TABLE IF NOT EXISTS transcripts (
    id         SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES calls(session_id) ON DELETE CASCADE,
    text       TEXT NOT NULL,
    is_final   INTEGER NOT NULL DEFAULT 1,
    speaker    TEXT,
    timestamp  TEXT NOT NULL
);

-- Summaries
CREATE TABLE IF NOT EXISTS summaries (
    id           SERIAL PRIMARY KEY,
    session_id   TEXT UNIQUE NOT NULL REFERENCES calls(session_id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    model_used   TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

-- Action items
CREATE TABLE IF NOT EXISTS action_items (
    id         SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES calls(session_id) ON DELETE CASCADE,
    text       TEXT NOT NULL,
    priority   TEXT NOT NULL DEFAULT 'medium',
    assignee   TEXT,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

-- Documents
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

-- Document chunks (for RAG)
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
CREATE INDEX IF NOT EXISTS idx_transcripts_session  ON transcripts(session_id);
CREATE INDEX IF NOT EXISTS idx_action_items_session ON action_items(session_id);
CREATE INDEX IF NOT EXISTS idx_documents_session    ON documents(session_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc  ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_calls_agent          ON calls(agent_id);
CREATE INDEX IF NOT EXISTS idx_calls_status         ON calls(status);
```

Then disable Supabase Row Level Security (the app uses its own JWT auth):

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

### 4. Set up the Python backend

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

pip install -r backend/requirements.txt
```

### 5. Set up the React frontend

```bash
cd frontend && npm install && cd ..
```

### 6. Start Redis

```bash
# macOS (Homebrew)
brew services start redis

# or directly
redis-server
```

Verify: `redis-cli ping` should return `PONG`.

### 7. (Optional) Start the RQ worker

The backend falls back to an inline thread if Redis is unavailable, but a dedicated worker is recommended for production and large PDFs.

```bash
source .venv/bin/activate
rq worker pravaah --url redis://localhost:6379/0
```

---

## Environment Variables

Copy `.env.example` → `.env` and fill in every value.

```env
# ── Deepgram ─────────────────────────────────────────────────────
DEEPGRAM_API_KEY=           # console.deepgram.com → API Keys (free: 200 min/month)

# ── OpenRouter ───────────────────────────────────────────────────
OPENROUTER_API_KEY=         # openrouter.ai/keys (free tier available)
OPENROUTER_HEAVY_MODEL=meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_LIGHT_MODEL=meta-llama/llama-3.1-8b-instruct:free
EMBEDDING_MODEL=nvidia/llama-nemotron-embed-vl-1b-v2:free

# ── Flask ────────────────────────────────────────────────────────
FLASK_SECRET_KEY=           # python -c "import secrets; print(secrets.token_hex(32))"
FLASK_ENV=development
FLASK_HOST=0.0.0.0
FLASK_PORT=8000

# ── Supabase ─────────────────────────────────────────────────────
# Project Settings → API
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
# Project Settings → Database → Connection string → Session mode URI (port 5432)
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres

# ── Redis ────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── ChromaDB ─────────────────────────────────────────────────────
CHROMA_PATH=./chroma_store

# ── Auth ─────────────────────────────────────────────────────────
JWT_SECRET_KEY=             # python -c "import secrets; print(secrets.token_hex(32))"
ADMIN_TOKEN=                # any strong password — protects /admin/rq

# ── File Upload ──────────────────────────────────────────────────
UPLOAD_FOLDER=./uploads
MAX_UPLOAD_MB=200

# ── Frontend ─────────────────────────────────────────────────────
VITE_API_URL=http://localhost:8000
VITE_WS_URL=http://localhost:8000

# ── Logging ──────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

### Where to get each key

**Deepgram** — [console.deepgram.com](https://console.deepgram.com) → API Keys → Create a New API Key

**OpenRouter** — [openrouter.ai/keys](https://openrouter.ai/keys) → Create Key. The default models are free; swap them for any model (Claude, GPT-4o, Gemini) by changing `OPENROUTER_HEAVY_MODEL` / `OPENROUTER_LIGHT_MODEL`.

**Supabase**
1. Create a project at [supabase.com](https://supabase.com)
2. **Project Settings → API** → copy `URL`, `anon key`, and `service_role key`
3. **Project Settings → Database → Connection string** → select **Session mode** (port **5432**) and copy the URI into `DATABASE_URL`

---

## Running the App

Open **two terminal windows**.

### Terminal 1 — Backend

```bash
source .venv/bin/activate
python -m backend.app
```

Flask starts at `http://localhost:8000`.

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Vite starts at `http://localhost:5173`.

Open **http://localhost:5173** in your browser.

> **Default admin credentials** — on first startup `init_db()` creates an admin account:
> - Username: `admin`
> - Password: `admin123`
>
> Change these immediately via `POST /api/auth/users` (admin only) or directly in Supabase.

---

## Project Structure

```
pravaah-os/
│
├── .env.example                  Template for all environment variables
├── .env                          Your local secrets — never commit this
│
├── backend/                      Flask application
│   ├── app.py                    Application factory, SocketIO init, Redis pub/sub listener
│   ├── auth.py                   JWT generation, validation, blacklisting, bcrypt
│   ├── config.py                 Centralised env-var loading
│   ├── database.py               SQLAlchemy session + all query helpers
│   ├── models.py                 ORM models: Call, Transcript, Summary, ActionItem, Document, User
│   ├── socket_handlers.py        All Socket.IO handlers + LLM/TTS pipeline dispatch
│   ├── utils.py                  Response helpers, pagination, file utilities
│   ├── requirements.txt          Python dependencies
│   └── routes/
│       ├── auth.py               /api/auth — login, refresh, logout, user management
│       ├── calls.py              /api/calls — start, end, list, detail
│       ├── documents.py          /api/documents — upload, status, RAG search
│       ├── analytics.py          /api/analytics — summary, per-agent stats
│       └── jobs.py               /api/jobs — RQ job status
│
├── pipeline/                     AI/ML processing layer
│   ├── session_manager.py        Per-call STT session lifecycle
│   ├── deepgram_stt.py           Deepgram WebSocket STT client
│   ├── deepgram_tts.py           Deepgram Aura REST TTS client
│   ├── openrouter_client.py      OpenRouter LLM client (retry, backoff, model routing)
│   ├── rag_engine.py             ChromaDB retrieval + LLM answer generation + Redis cache
│   ├── embeddings.py             Embedding client (configurable model via OpenRouter)
│   ├── document_processor.py     PDF/DOCX/TXT chunking + ChromaDB ingestion (RQ job)
│   ├── prompt_templates.py       All system and user prompt constants
│   └── websocket_bridge.py       Low-level Deepgram WebSocket management
│
└── frontend/                     React 18 + Vite + Tailwind CSS
    └── src/
        ├── main.jsx              React entry point, router setup
        ├── App.jsx               Route definitions
        ├── api.js                Axios client with JWT auth interceptor
        ├── socket.js             Singleton Socket.IO client (lazy JWT)
        ├── pages/
        │   ├── Dashboard.jsx         Stat cards + active call list + new call modal
        │   ├── ActiveCall.jsx        Live call — waveform, transcript, AI reply
        │   ├── CallDetail.jsx        Full call view — transcript, summary, action items
        │   ├── CallHistoryPage.jsx   Searchable paginated call log
        │   ├── Documents.jsx         Drag-and-drop upload + status + RAG search
        │   ├── Analytics.jsx         Recharts call volume and sentiment charts
        │   ├── AdminPage.jsx         User management (admin only)
        │   └── Login.jsx             JWT login form
        └── components/
            ├── AudioRecorder.jsx     Mic capture + audio chunk streaming via Socket.IO
            ├── WaveformVisualizer.jsx  Animated real-time waveform using Web Audio API
            ├── TranscriptDisplay.jsx   Scrolling interim/final transcript bubbles
            ├── LiveSummaryPanel.jsx    Live summary sidebar (updates every 5 segments)
            ├── ActionItemsList.jsx     Action items with priority colour badges
            ├── DocumentUploader.jsx    Drag-and-drop file upload with mime validation
            ├── DocProgressBar.jsx      Real-time ingestion progress driven by Socket.IO
            ├── CallStatusBadge.jsx     Coloured status chips (active / ended)
            ├── LanguageBadge.jsx       Language tag (hi / en / hi-en)
            └── NavBar.jsx              Top navigation with role-aware links
```

---

## Pages & UI

| Page | Route | What it shows |
|---|---|---|
| **Dashboard** | `/` | Stat cards (active calls, calls today, avg handle time, escalations), live call list, new call button |
| **Live Call** | `/calls/:session_id` | Real-time waveform, interim + final transcript stream, AI text reply panel, live summary sidebar |
| **Call Detail** | `/calls/:session_id/detail` | Full final transcript, structured summary card, prioritised action items list |
| **Call History** | `/history` | Paginated, searchable log of all calls with status and language badges |
| **Documents** | `/documents` | Drag-and-drop file upload, per-document ingestion progress bar, RAG search input |
| **Analytics** | `/analytics` | Recharts bar and line charts for call volume, duration trends, sentiment distribution |
| **Admin** | `/admin` | Create and manage users by role (agent / supervisor / admin) |
| **Login** | `/login` | Username / password form; stores JWT in localStorage |

---

## Key Design Decisions

**No voice framework**
The pipeline is built from first principles — raw WebSocket to Deepgram, direct HTTP to OpenRouter — so there are no hidden abstractions between the audio stream and the LLM. This makes it straightforward to swap models, tune prompts, or add pipeline stages.

**Threading instead of async**
Flask-SocketIO runs in `threading` mode to stay compatible with the standard Werkzeug dev server without requiring monkey-patching. Every I/O-heavy task (STT callbacks, LLM calls, TTS synthesis, document ingestion) runs in daemon background threads so the main thread never blocks.

**Interruption detection**
Each session tracks a monotonically increasing generation counter. When the user speaks, the counter increments. Any in-flight LLM thread captures its generation at start; if the counter has moved by the time TTS audio is ready, the audio is silently dropped — no stale voice replies play over the user's next sentence.

**RAG caching**
Identical queries against the same document set are cached in Redis for 10 minutes using a SHA-256 hash of `(question, sorted_doc_ids, top_k)` as the key. This cuts repeated-query latency from ~2 s to under 10 ms.

**LLM model routing**
Two model tiers share a single client. Heavy tasks (summarise, extract action items, RAG) use `OPENROUTER_HEAVY_MODEL`; realtime conversational replies use `OPENROUTER_LIGHT_MODEL` with an 8-second hard timeout to prevent stale replies arriving after the call ends. Both are environment-variable-driven — no code change needed to swap models.

**At-most-2 concurrent LLM threads per session**
A per-session semaphore (`_MAX_CONCURRENT_LLM = 2`) prevents pile-up during bursty speech, where many final transcript events could otherwise queue dozens of LLM requests simultaneously.

---

## Troubleshooting

**No transcripts appearing**
- Check `DEEPGRAM_API_KEY` is set: `curl http://localhost:8000/health`
- Ensure the browser has microphone permission
- Confirm `VITE_WS_URL=http://localhost:8000` is set

**"Error connecting to Redis"**
```bash
redis-server --daemonize yes   # start
redis-cli ping                  # should return PONG
```

**Documents stuck in "processing"**
```bash
# Start the RQ worker
source .venv/bin/activate
rq worker pravaah --url redis://localhost:6379/0
```

**ChromaDB permission error**
```bash
mkdir -p chroma_store && chmod 755 chroma_store
```

**WebSocket CORS error in browser**
- Confirm both `VITE_API_URL` and `VITE_WS_URL` point to `http://localhost:8000`
- The Socket.IO client must pass the JWT in the `auth` object at connect time

**Supabase SSL / prepared statement errors**
Use the **Session mode** URI (port **5432**), not the Transaction pooler (port 6543). The backend configures `NullPool` and `sslmode=require` automatically.

---

## License

MIT — free to use, modify, and distribute.
