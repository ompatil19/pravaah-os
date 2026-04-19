# Pravaah OS — How Everything Works

> Read this if you want to understand the whole system in one go.
> Status: **APPROVED** (QA v2 passed, 2026-04-14)

---

## What Is This?

Pravaah OS is a **multilingual call intelligence platform** for Indian enterprises.
It records live calls, transcribes Hindi/English speech in real-time, summarizes them
with an LLM, and lets users search across call history and uploaded documents using RAG.

---

## The Big Picture

```
User's Browser
      │
      │  REST (/api/*)          WebSocket (Socket.IO)
      ▼
┌─────────────────────────────────────────────┐
│          Flask Server  (port 5000)          │
│  JWT auth  •  rate limiting  •  structlog   │
│                                             │
│  Routes: /auth  /calls  /documents  /jobs   │
│  Socket handlers: audio_chunk, call events  │
└──────┬──────────────┬──────────────┬────────┘
       │              │              │
    SQLite         Redis          RQ Workers
    (WAL mode)   (localhost      (separate process)
    or Postgres   :6379)          └─ ingest_document
                                  └─ end_of_call_llm
                                  └─ analytics_cache
       │
  ─────┼──────────────────────────────────────
       │
  External APIs
  ├── Deepgram Nova-2 STT  (WebSocket, hi-en)
  ├── Deepgram Aura TTS    (REST)
  └── OpenRouter LLM       (claude-sonnet-4-5 / haiku-4-5)
       └── Embeddings      (OpenRouter Embeddings API)
       └── ChromaDB        (local vector store, CHROMA_PATH)
```

---

## A Live Call — Step by Step

```
1. User opens browser, logs in → gets JWT
2. User clicks "Start Call"
   → POST /api/calls  →  call row created in SQLite
   → Browser connects Socket.IO  →  join_call event (sends JWT)

3. Browser captures mic audio (PCM chunks every ~100ms)
   → emit audio_chunk events over Socket.IO

4. Flask socket handler receives chunk
   → forwards raw bytes over WebSocket to Deepgram Nova-2

5. Deepgram returns transcripts (interim + final)
   → interim: emit transcript_interim → browser shows live text
   → final:   append to DB transcript table

6. When user ends call → end_call event
   → Flask closes Deepgram WS
   → enqueues RQ job: run_end_of_call_llm

7. RQ worker picks up job
   → sends full transcript to OpenRouter (claude-sonnet-4-5)
   → gets: summary, action items, sentiment
   → saves to DB

8. Browser polls /api/calls/{id} → shows summary when ready
```

---

## Document Upload & RAG — Step by Step

```
1. User uploads PDF/TXT/DOCX via Documents page
   → POST /api/documents/upload
   → Flask saves file, creates Document row, enqueues RQ job: ingest_document
   → returns job_id immediately

2. RQ worker: ingest_document
   → pdfminer (PDF) / python-docx / plain text extraction
   → splits into 512-token chunks, 100-token overlap (tiktoken cl100k_base)
   → embeds each chunk via OpenRouter Embeddings API (batches of 100)
   → stores vectors in ChromaDB  (collection: doc_{id})
   → publishes progress events via Redis pub/sub  →  browser progress bar updates live

3. User asks a question in the RAG panel
   → POST /api/documents/search
   → Flask calls RAGEngine.query()
     a. check Redis cache (TTL 10min) — return if hit
     b. embed the question
     c. cosine-similarity search in ChromaDB
     d. top-K chunks → prompt → OpenRouter (claude-sonnet-4-5, temp 0.2)
     e. return answer + source citations (doc_id, page_number, chunk preview)
```

---

## Authentication Flow

```
POST /api/auth/login  →  bcrypt check  →  JWT access token (short TTL)
                                       +  refresh token (long TTL)

Every request:  Authorization: Bearer <access_token>
                require_auth decorator validates JWT + role

Token expired?  Frontend interceptor catches 401
                → calls /api/auth/refresh with refresh token
                → queues concurrent requests, replays after new token arrives

Logout:  POST /api/auth/logout  →  token added to Redis blacklist
```

---

## Frontend Routes

| URL | Page | Who can access |
|-----|------|----------------|
| `/login` | Login | Public |
| `/` | Dashboard / Calls | Authenticated |
| `/documents` | Upload + RAG query | Authenticated |
| `/admin` | Jobs, users, system health | Admin role only |

- All non-login routes wrapped in `ProtectedRoute`
- Socket.IO authenticated on connect via `{token: JWT}`

---

## Directory Map

```
pravaah-os/
├── backend/
│   ├── app.py              Flask app factory, Socket.IO init, Redis client
│   ├── auth.py             JWT tokens, bcrypt, require_auth decorator
│   ├── config.py           All config from env vars
│   ├── database.py         SQLAlchemy engine (SQLite WAL or Postgres)
│   ├── models.py           User, Call, Transcript, Document, DocumentChunk, Job
│   ├── socket_handlers.py  audio_chunk → Deepgram, transcript events → browser
│   ├── utils.py            Shared helpers
│   └── routes/
│       ├── auth.py         /api/auth/*
│       ├── calls.py        /api/calls/*
│       ├── documents.py    /api/documents/*  (upload, status, search/RAG)
│       └── jobs.py         /api/jobs/*
│
├── pipeline/
│   ├── deepgram_stt.py     WebSocket client to Deepgram Nova-2
│   ├── deepgram_tts.py     REST client to Deepgram Aura
│   ├── llm_client.py       OpenRouter wrapper (summary, action items)
│   ├── openrouter_client.py Raw OpenRouter HTTP calls
│   ├── embeddings.py       EmbeddingClient — batch embed, retry, backoff
│   ├── document_processor.py  RQ job: extract → chunk → embed → ChromaDB
│   ├── rag_engine.py       RAGEngine.query() — cache → search → synthesize
│   ├── prompt_templates.py All LLM prompts (SYSTEM_RAG etc.)
│   ├── session_manager.py  Per-call state (active Deepgram WS, buffer)
│   └── websocket_bridge.py Socket.IO ↔ Deepgram bridge logic
│
├── frontend/src/
│   ├── App.jsx             Router, all routes, ProtectedRoute wrappers
│   ├── api.js              All axios calls to backend
│   ├── socket.js           Socket.IO singleton
│   ├── hooks/useAuth.js    Login, logout, token refresh, axios interceptors
│   ├── components/
│   │   ├── ProtectedRoute.jsx   Auth + role guard
│   │   └── DocProgressBar.jsx   Live progress via Socket.IO doc_progress events
│   └── pages/
│       ├── Login.jsx       Login form
│       ├── Documents.jsx   Upload + drag-drop + RAG query panel
│       └── AdminPage.jsx   Jobs table, user management, system health
│
├── ARCHITECTURE.md         Full technical spec (single source of truth)
├── PROGRESS.md             Build log — all agents DONE
├── REVIEW.md               QA review — Overall: APPROVED
├── start.sh                Start Redis → RQ worker → Flask → Vite (with cleanup trap)
├── Makefile                dev, test, lint, clean, create-admin targets
├── .env.example            All required env vars
└── launch_pravaah.sh       Tmux 6-pane launcher (one pane per agent role)
```

---

## How to Run

```bash
cp .env.example .env
# fill in: DEEPGRAM_API_KEY, OPENROUTER_API_KEY, JWT_SECRET_KEY, FLASK_SECRET_KEY

make setup      # install Python deps + npm install
./start.sh      # starts Redis → RQ worker → Flask (5000) → Vite (5173)
```

Or use the tmux launcher to see all 6 agent panes:
```bash
./launch_pravaah.sh
# then in pane 0 (Orchestrator): type "begin"
```

---

## Services & Ports

| Service | Port | Notes |
|---------|------|-------|
| Vite (frontend) | 5173 | `npm run dev` |
| Flask (backend) | 5000 | also serves Socket.IO |
| Redis | 6379 | required for RQ, rate limiting, cache |
| RQ worker | — | separate process, queue: `pravaah` |
| RQ dashboard | /admin/rq | protected by ADMIN_TOKEN |

---

## Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `DEEPGRAM_API_KEY` | STT + TTS |
| `OPENROUTER_API_KEY` | LLM + embeddings |
| `JWT_SECRET_KEY` | Token signing |
| `FLASK_SECRET_KEY` | Flask sessions |
| `REDIS_URL` | Redis connection (default: redis://localhost:6379) |
| `CHROMA_PATH` | Where ChromaDB stores vectors |
| `DATABASE_URL` | Leave blank for SQLite, set for Postgres |
| `ADMIN_TOKEN` | Protects /admin/rq dashboard |
| `MAX_UPLOAD_MB` | Max document size (default: 200) |
| `VITE_API_URL` | Frontend → backend base URL |

---

## Build History (how the code was generated)

This repo was built by a **multi-agent system** orchestrated via Claude Code:

```
Phase 1 — Architect     wrote ARCHITECTURE.md
Phase 2 — 3 agents in parallel:
            Pipeline Engineer  → pipeline/
            Backend Engineer   → backend/
            Frontend Engineer  → frontend/
Phase 3 — DevOps Engineer   → start.sh, Makefile, tests, README
Phase 4 — QA Reviewer       → REVIEW.md

Ran twice (v1 → rework → v2) until QA marked Overall: APPROVED.
```

Agent role prompts live in [.claude/agents/](.claude/agents/).
Orchestrator instructions live in [CLAUDE.md](CLAUDE.md).
