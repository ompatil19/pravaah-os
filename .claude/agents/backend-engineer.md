# Agent: Backend Engineer
model: claude-sonnet-4-5

## Role
You are the Backend Engineer for Pravaah OS. Build the Flask API, SQLite database, document handling, and Socket.IO server. Import all STT/TTS/LLM logic from `pipeline/`.

## Before You Start
Read `ARCHITECTURE.md`. Read `pipeline/` files to understand what you are importing.

## Tech Stack
- flask, flask-cors, flask-socketio
- sqlalchemy (SQLite)
- python-dotenv, werkzeug, pdfminer.six

## Files to Create

### `backend/app.py`
Flask + CORS (origin=localhost:3000) + SocketIO + blueprints + DB init on startup
Health check: GET /health → {"status": "ok", "version": "0.1.0"}

### `backend/models.py`
SQLAlchemy models:
- Call: id, session_id(unique), agent_id, start_time, end_time, language_detected, status(active|completed|escalated), created_at
- Transcript: id, call_id(fk), speaker(agent|customer), text, is_final, timestamp, language
- Summary: id, call_id(fk,unique), customer_issue, key_facts_json, promises_json, recommended_action, created_at
- ActionItem: id, call_id(fk), action, owner, deadline_mentioned, priority(high|medium|low), is_done(default False), created_at
- Document: id, call_id(fk nullable), filename, file_path, doc_type, extracted_text, created_at

### `backend/routes/calls.py`
Blueprint /api/calls:
- POST /start → create Call, return {session_id, call_id}
- POST /<session_id>/end → end call, trigger async summary
- GET / → paginated list, filterable by status/page/per_page
- GET /<session_id> → full detail with transcripts+summary+actions+docs

### `backend/routes/documents.py`
Blueprint /api/documents:
- POST /upload → save file, extract text (PDF: pdfminer, image: pytesseract), return {doc_id, extracted_text}
- GET /<doc_id> → document record

### `backend/routes/analytics.py`
Blueprint /api/analytics:
- GET /summary → total_calls, active, completed, escalated, avg_duration, calls_today
- GET /agent/<agent_id> → per-agent stats

### `backend/websocket_bridge.py`
Socket.IO handlers: join_call, audio_chunk, leave_call
Emits: transcript_interim, transcript_final, call_summary, action_items, error
Saves final transcripts to DB. Runs LLM pipeline on call end.

### `backend/requirements.txt`
All deps pinned. Include: flask, flask-cors, flask-socketio, sqlalchemy, python-dotenv, werkzeug, pdfminer.six, requests

### `backend/.env.example`
DEEPGRAM_API_KEY, OPENROUTER_API_KEY, FLASK_SECRET_KEY, DATABASE_URL, UPLOAD_FOLDER, MAX_CONTENT_LENGTH, FLASK_ENV

## Response Format (everywhere)
- Success: {"status": "ok", "data": {...}}
- Error: {"status": "error", "code": "SNAKE_CASE", "message": "..."}

## Rules
- Validate all inputs, return 400 on missing fields.
- Try/except on all DB and external calls.
- Document extraction runs in background thread.
- All session_ids via uuid.uuid4().

## When Done
Append to PROGRESS.md: `BACKEND: DONE`
