# Pravaah OS QA Review v2
Date: 2026-04-14

---

## Pipeline Engineer v2
Status: APPROVED

### Passed ✅
- `pipeline/embeddings.py` — EmbeddingClient present with `embed()` and `embed_single()`, batch support (100-item batches), retry with exponential backoff (3 attempts, 429 handling with Retry-After), proper session management and `close()`.
- `pipeline/document_processor.py` — `ingest_document()` function exists as RQ job entry point; handles PDF (pdfminer), TXT, and DOCX; 512-token chunks with 100-token overlap using tiktoken cl100k_base; page metadata (`page_number`, `chunk_index`, `doc_id`) preserved in ChromaDB metadatas; ChromaDB storage via PersistentClient; Redis pub/sub progress events published at each embedding batch and completion.
- `pipeline/rag_engine.py` — `RAGEngine.query()` implemented with Redis cache (TTL 600s = 10 min), ChromaDB cosine-similarity search across single or all `doc_*` collections, LLM synthesis via `answer_from_context()`, and sources returned with `doc_id`, `page_number`, `chunk_text_preview`.
- `SYSTEM_RAG` prompt added to `prompt_templates.py` — instructs model to use only context, cite page numbers, refuse if not found.
- `answer_from_context()` method on `OpenRouterLLMClient` — uses SYSTEM_RAG prompt and heavy model (claude-sonnet-4-5) with 0.2 temperature.
- Zero hardcoded API keys — all keys read from environment variables via `os.environ["OPENROUTER_API_KEY"]` with optional constructor override.

### Failed ❌
None.

---

## Backend Engineer v2
Status: APPROVED

### Passed ✅
- SQLAlchemy ORM in `models.py` — `User`, `Job`, `Document`, `DocumentChunk` models present with correct columns including v2 additions (`status`, `total_pages`, `total_chunks`, `job_id` on Document; all DocumentChunk fields).
- `database.py` supports both SQLite (WAL mode via PRAGMA, pool_size=10) and PostgreSQL via `DATABASE_URL` env var (pool_size=20).
- `backend/auth.py` — JWT generation (`generate_tokens()`), `require_auth` decorator with role checking, bcrypt hashing (`hash_password` / `check_password`), token blacklisting via Redis.
- `backend/routes/auth.py` — login, refresh, logout, me, and create user (admin-only) endpoints all implemented correctly.
- `backend/routes/documents.py` — upload enqueues RQ job and returns `job_id`; `/status` endpoint returns document + job processing status; `/search` RAG endpoint present.
- `backend/routes/jobs.py` — job status and list (admin-only) endpoints implemented with live RQ status augmentation.
- Redis client in `app.py` — module-level `redis_client` initialised at startup, graceful degradation if Redis unavailable.
- `flask-limiter` configured with Redis backend (falls back to memory:// if Redis unavailable).
- `structlog` configured with JSON renderer in production, ConsoleRenderer in development.
- `rq-dashboard` registered at `/admin/rq` with `ADMIN_TOKEN` protection via `before_request` hook.
- `gevent` async_mode for Socket.IO when Redis is available (falls back to threading).
- `require_auth` applied to all routes in `calls.py`, `documents.py`, `jobs.py`, and `auth.py` (logout, me, create_user).
- `requirements.txt` includes all new deps: `rq`, `rq-dashboard`, `bcrypt`, `structlog`, `chromadb`, `tiktoken`, `pdfminer.six`, `python-docx`, `flask-limiter`, `PyJWT`.
- **RAGEngine instantiation fix (spot check v2)** — `backend/routes/documents.py` line 413 now correctly instantiates `RAGEngine(chroma_path=_chroma_path, openrouter_api_key=_openrouter_key, redis_client=_rc)` with all three required arguments; Redis fallback to `None` on connection failure is handled correctly.

### Failed ❌
None.

---

## Frontend Engineer v2
Status: APPROVED

### Passed ✅
- `frontend/src/hooks/useAuth.js` — `login()`, `logout()`, `refreshToken()` all implemented; axios request interceptor attaches `Authorization: Bearer` header from localStorage; response interceptor handles 401 with single-retry token refresh using a subscriber queue pattern to queue concurrent requests; `_doLogout()` clears all localStorage keys and redirects to `/login`.
- `frontend/src/components/ProtectedRoute.jsx` — redirects unauthenticated users to `/login`; optionally enforces role matching, redirecting to `/` on role mismatch.
- `frontend/src/pages/Login.jsx` — dark UI using CSS variables (`var(--bg)`, `var(--accent)`, `var(--border)`, `var(--text)`, `var(--muted)`, `var(--danger)`); calls `/api/auth/login` via `useAuth`; handles loading state with spinner animation.
- `frontend/src/pages/Documents.jsx` — upload zone with drag-and-drop and progress bar; document list with per-document `DocProgressBar`; RAG query panel with multi-doc selection, question textarea, and answer/source accordion display.
- `frontend/src/components/DocProgressBar.jsx` — subscribes to `doc_progress` Socket.IO events filtered by `docId`; animated progress bar; handles QUEUED / EXTRACTING / EMBEDDING (with dynamic percentage) / DONE / FAILED states; pulse animation on active states.
- `frontend/src/pages/AdminPage.jsx` — job table with auto-refresh every 10 seconds via `setInterval`; user management table with add-user form; system health card; role guard redirects non-admins.
- `frontend/src/App.jsx` — all routes wrapped in `ProtectedRoute`; `/login` is public; `/admin` added with `role="admin"` restriction.
- `frontend/src/api.js` — `searchDocuments`, `getDocumentStatus`, `listJobs`, `createUser` all added and exported; uses `import.meta.env.VITE_API_URL` (env-overridable fallback to localhost, not a true hardcode).
- No hardcoded hex colors in v2-scope files (Login, Documents, AdminPage, DocProgressBar, App); all styling uses CSS custom properties.

### Failed ❌
None.

---

## DevOps Engineer v2
Status: APPROVED

### Passed ✅
- `start.sh` — starts Redis (daemonize), then RQ worker (`pravaah` queue with `--with-scheduler`), then Flask (port 5000), then Vite (port 3000) in correct order; `cleanup()` trap on INT/TERM kills all 4 processes in reverse order (Vite → Flask → RQ → Redis); health polling waits up to 30 seconds per service.
- `Makefile` — has `worker` target (`rq worker pravaah`); uses tabs not spaces; includes `setup`, `dev`, `test`, `test-pipeline`, `lint`, `clean`, `create-admin` targets.
- `.env.example` — has `REDIS_URL`, `CHROMA_PATH`, `JWT_SECRET_KEY`, `ADMIN_TOKEN`, `EMBEDDING_MODEL`, `MAX_UPLOAD_MB=200`, plus all other required variables (`DEEPGRAM_API_KEY`, `OPENROUTER_API_KEY`, `FLASK_SECRET_KEY`, `DATABASE_URL`, `VITE_API_URL`).
- `README.md` — Redis listed as a prerequisite in the Prerequisites table with install instructions; RAG query feature documented in "Document Ingestion (RAG)" and "Asking Questions Across Documents (RAG)" sections.
- `backend/tests/test_api.py` — auth tests present: `test_login_success`, `test_login_invalid`, `test_protected_without_token`, `test_protected_with_token`; document upload job test present: `test_document_upload_queues_job`, `test_document_status`.

### Failed ❌
None.

---

## Overall Status: APPROVED

All agents have passed QA. The single blocker (RAGEngine instantiation with zero arguments in `backend/routes/documents.py`) has been correctly resolved. The fix passes all three checks:

1. `RAGEngine` is now called with all three required keyword arguments: `chroma_path`, `openrouter_api_key`, `redis_client`.
2. `RAGEngine.__init__` signature (`chroma_path: str`, `openrouter_api_key: str`, `redis_client: Any`) matches exactly.
3. Redis fallback (`_rc = None` on connection failure) is handled before the call, so the `redis_client` argument is always provided.

Pravaah OS v2 MVP is ready to run.
