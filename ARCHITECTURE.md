# Pravaah OS — Architecture Document

> **Status**: v2.0 — Written by Architect Agent (Enterprise Scale Upgrade)
> **Date**: 2026-04-14
> **This document is the single source of truth for all subagents. Do not deviate without updating this file.**
> **v2 supersedes v1.0. All new agents must read this document entirely before writing any code.**

---

## 1. System Overview

### Full Component Map (v2)

```
Browser (React 18 + Vite)
    │
    │  HTTP REST (JSON)           WebSocket (Socket.IO)
    │  /api/*                     events: audio_chunk, transcript_*, doc_*, etc.
    │  Authorization: Bearer JWT  auth: {token: JWT} on connect
    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Flask Server (Python 3.11 + gevent)              │
│                                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐              │
│  │  Auth Layer │  │ Rate Limiter │  │ Struct Logger │              │
│  │  (JWT/APIKey│  │ (flask-limiter│  │  (structlog)  │              │
│  │   + bcrypt) │  │  via Redis)  │  │               │              │
│  └─────────────┘  └──────────────┘  └───────────────┘              │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     Route Handlers                             │ │
│  │  /api/auth/*  /api/calls/*  /api/documents/*  /api/analytics/* │ │
│  │  /api/jobs/*  /admin/rq                                        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────┐    ┌──────────────────────────────────┐ │
│  │  Socket.IO Handlers    │    │  SQLAlchemy ORM Session Pool     │ │
│  │  (gevent mode)         │    │  SQLite WAL (pool=10) or         │ │
│  └────────────────────────┘    │  PostgreSQL psycopg2 (pool=20)   │ │
│                                └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
    │           │              │
    │           │              └── Redis (localhost:6379)
    │           │                     • Session state (hash: session:{id})
    │           │                     • Rate limit counters
    │           │                     • Analytics cache (TTL 5m)
    │           │                     • Doc search cache (TTL 10m)
    │           │                     • RQ job queue: pravaah
    │           │
    │           └── RQ Workers (separate process: rq worker pravaah)
    │                     • ingest_document job
    │                     • run_end_of_call_llm job
    │                     • generate_analytics_cache job
    │                     │
    │                     ├── pdfminer (PDF text extraction)
    │                     ├── OpenRouter Embedding API
    │                     └── ChromaDB (local vector store, CHROMA_PATH)
    │
    ├── SQLite / PostgreSQL DB
    │      Tables: users, calls, transcripts, summaries, action_items,
    │              documents, document_chunks, jobs
    │
    ├── Deepgram Nova-2 STT (wss://api.deepgram.com/v1/listen)
    │      One WebSocket per active call session
    │
    └── Deepgram Aura TTS (https://api.deepgram.com/v1/speak)
           REST, called per assistant reply
```

### ASCII Data-Flow Diagram (a) — One Complete Voice Call Turn

```
Browser                Flask/SocketIO+gevent    Deepgram STT       OpenRouter         Deepgram TTS
   |                          |                      |                  |                   |
   |--join_call (JWT auth)---->|                      |                  |                   |
   |                          |--open WS (nova-2)---->|                  |                   |
   |                          |<--Connected-----------|                  |                   |
   |--audio_chunk (x N)------->|                      |                  |                   |
   |                          |--send binary--------->|                  |                   |
   |                          |<--interim JSON--------|                  |                   |
   |<--transcript_interim------|                       |                  |                   |
   |                          |<--final JSON----------|                  |                   |
   |<--transcript_final--------|                       |                  |                   |
   |                          |--INSERT transcripts   |                  |                   |
   |                          |--RQ.enqueue(          |                  |                   |
   |                          |   run_end_of_call_llm)|                  |                   |
   |                          |                       |                  |                   |
   |              [RQ Worker picks up job]            |                  |                   |
   |                          |--POST /completions----|----------------->|                   |
   |                          |<--JSON response-------|------------------|                   |
   |                          |--INSERT summaries/action_items           |                   |
   |<--call_summary------------|                       |                  |                   |
   |<--action_items------------|                       |                  |                   |
   |                          |--POST /speak----------|------------------+------------------>|
   |                          |<--audio/mpeg----------|------------------+-------------------|
   |<--tts_audio (b64)---------|                       |                  |                   |
   [plays audio]              |                       |                  |                   |
   |--leave_call-------------->|                       |                  |                   |
   |                          |--close WS------------>|                  |                   |
```

### ASCII Data-Flow Diagram (b) — Document Ingestion Pipeline

```
Browser (DocumentsPage)        Flask (HTTP)           Redis/RQ              RQ Worker
    |                              |                      |                      |
    |--POST /api/documents/upload->|                      |                      |
    |   (multipart, up to 200MB)   |                      |                      |
    |                              |--validate MIME/size  |                      |
    |                              |--INSERT documents    |                      |
    |                              |   (status=queued)    |                      |
    |                              |--RQ.enqueue(-------->|                      |
    |                              |  ingest_document,    |                      |
    |                              |  doc_id)             |                      |
    |<--201 {doc_id, status:queued}|                      |                      |
    |                              |                      |--dequeue job-------->|
    |                              |                      |                      |--pdfminer extract
    |                              |                      |                      |--split into chunks
    |                              |                      |                      |  (512 tok, 100 overlap)
    |<--doc_processing_start (WS)--|<--emit via socketio--|<--emit progress------|
    |                              |                      |                      |  per chunk:
    |                              |                      |                      |--embed chunk via
    |                              |                      |                      |  OpenRouter
    |<--doc_chunk_embedded (WS)----|<--emit via socketio--|<--emit progress------|--store in ChromaDB
    |  {doc_id, progress_pct,      |                      |                      |--INSERT document_chunks
    |   pages_done, pages_total}   |                      |                      |
    |                              |                      |                      | (repeat per chunk)
    |<--doc_processing_done (WS)---|<--emit via socketio--|<--emit progress------|
    |   {doc_id, total_chunks,     |                      |                      |--UPDATE documents
    |    total_pages}              |                      |                      |   status=ready
```

---

## 2. Full Monorepo Folder Structure

Every file that must exist after all agents finish:

```
pravaah-os/
├── ARCHITECTURE.md              ← this file (Architect)
├── PROGRESS.md                  ← build log (all agents append)
├── REVIEW.md                    ← QA output (Reviewer agent)
├── README.md                    ← DevOps
├── Makefile                     ← DevOps
├── start.sh                     ← DevOps (starts Flask + RQ worker + Redis check)
├── .env.example                 ← DevOps
├── requirements.txt             ← Backend
│
├── backend/
│   ├── __init__.py
│   ├── app.py                   ← Flask app factory + SocketIO init (gevent mode)
│   ├── config.py                ← env var loading, all constants
│   ├── database.py              ← SQLAlchemy engine + session factory, schema init
│   ├── models.py                ← SQLAlchemy ORM model classes
│   ├── auth.py                  ← JWT encode/decode, API key check, role decorators
│   ├── limiter.py               ← flask-limiter instance (Redis backend)
│   ├── worker.py                ← RQ job functions: ingest_document, run_end_of_call_llm, generate_analytics_cache
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py              ← /api/auth/login, /api/auth/refresh
│   │   ├── calls.py             ← /api/calls/* routes
│   │   ├── documents.py         ← /api/documents/* routes (upload, get, search, status)
│   │   ├── analytics.py         ← /api/analytics/* routes
│   │   └── jobs.py              ← /api/jobs/<job_id> route
│   ├── socket_handlers.py       ← all Socket.IO event handlers
│   └── utils.py                 ← helpers: pagination, validation, structlog setup
│
├── pipeline/
│   ├── __init__.py
│   ├── deepgram_stt.py          ← Deepgram WebSocket STT client
│   ├── deepgram_tts.py          ← Deepgram Aura REST TTS client
│   ├── openrouter_client.py     ← OpenRouter LLM + embedding HTTP client
│   ├── prompt_templates.py      ← all system/user prompts
│   ├── session_manager.py       ← per-call state: deepgram ws, transcript buffer
│   ├── document_processor.py   ← chunking logic, embedding calls, ChromaDB writes
│   └── chroma_client.py         ← ChromaDB singleton + collection management
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx              ← router, global socket context, auth context
│       ├── socket.js            ← Socket.IO client singleton (sends JWT on connect)
│       ├── api.js               ← axios REST client (attaches Authorization header)
│       ├── auth.js              ← token storage, login/logout helpers
│       ├── components/
│       │   ├── AudioRecorder.jsx
│       │   ├── TranscriptDisplay.jsx
│       │   ├── ActionItemsList.jsx
│       │   ├── CallSummaryCard.jsx
│       │   ├── LanguageBadge.jsx
│       │   ├── NavBar.jsx
│       │   ├── DocumentUploadZone.jsx  ← drag-drop with progress bar
│       │   ├── DocIngestionProgress.jsx ← real-time progress display via Socket.IO
│       │   └── ProtectedRoute.jsx      ← redirects to /login if no JWT
│       └── pages/
│           ├── LoginPage.jsx
│           ├── LiveCallPage.jsx
│           ├── CallHistoryPage.jsx
│           ├── CallDetailPage.jsx
│           ├── DocumentsPage.jsx       ← v2: progress bars, RAG query input, chunk viewer
│           ├── AnalyticsPage.jsx
│           └── AdminPage.jsx           ← v2: job queue link, user management table
│
└── tests/
    ├── test_pipeline.py         ← DevOps
    ├── test_api.py              ← DevOps
    └── test_socket.py           ← DevOps
```

---

## 3. Voice Pipeline Design

### 3.1 Browser Audio Capture

```javascript
// frontend/src/components/AudioRecorder.jsx
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
  ? 'audio/webm;codecs=opus'
  : 'audio/ogg;codecs=opus';   // fallback for Firefox
const recorder = new MediaRecorder(stream, { mimeType });
recorder.ondataavailable = (e) => {
  if (e.data.size > 0) {
    socket.emit('audio_chunk', { session_id, data: e.data });
  }
};
recorder.start(250); // 250ms time slices
```

### 3.2 Flask SocketIO — Audio Reception (gevent mode)

File: `backend/socket_handlers.py`

```python
@socketio.on('audio_chunk')
def handle_audio_chunk(payload):
    session_id = payload['session_id']
    audio_bytes = payload['data']          # bytes
    mgr = session_manager.get(session_id)
    if mgr:
        mgr.send_audio(audio_bytes)        # forward to Deepgram WS via gevent greenlet
```

### 3.3 Deepgram Nova-2 STT WebSocket

File: `pipeline/deepgram_stt.py`

- URL: `wss://api.deepgram.com/v1/listen`
- Auth header: `Authorization: Token {DEEPGRAM_API_KEY}`
- Query params:
  ```
  model=nova-2
  language=hi-en
  punctuate=true
  interim_results=true
  smart_format=true
  endpointing=500
  encoding=webm-opus
  sample_rate=48000
  channels=1
  ```
- One WebSocket connection per active call session (opened on `join_call`, closed on `leave_call`)
- Reconnect logic: exponential backoff up to 5 retries (1s, 2s, 4s, 8s, 16s)

### 3.4 Transcript Routing (interim vs final)

```python
def on_deepgram_message(session_id, message_json):
    data = json.loads(message_json)
    if data['type'] != 'Results':
        return
    alt = data['channel']['alternatives'][0]
    transcript = alt['transcript']
    is_final = data['is_final']
    if not transcript.strip():
        return
    if not is_final:
        socketio.emit('transcript_interim',
                      {'session_id': session_id, 'text': transcript},
                      room=session_id)
    else:
        db_session = get_db_session()
        insert_transcript(db_session, session_id, transcript, is_final=True)
        socketio.emit('transcript_final',
                      {'session_id': session_id, 'text': transcript},
                      room=session_id)
        # Enqueue LLM job in RQ — do NOT run in Flask thread
        q = get_rq_queue()
        q.enqueue(run_end_of_call_llm, session_id, transcript,
                  retry=Retry(max=3, interval=[10, 30, 60]))
```

### 3.5 LLM Pipeline (OpenRouter) — Runs in RQ Worker

File: `backend/worker.py` — function `run_end_of_call_llm(session_id, transcript)`

- Worker runs as separate process: `rq worker pravaah`
- Called after every `is_final=True` transcript
- Uses `claude-sonnet-4-5` for: call summary, action item extraction, sentiment/intent
- Uses `claude-haiku-4-5-20251001` for: language detection, acknowledgement generation, entity tagging

POST to `https://openrouter.ai/api/v1/chat/completions`

Headers:
```
Authorization: Bearer {OPENROUTER_API_KEY}
HTTP-Referer: http://localhost:5000
X-Title: Pravaah OS
Content-Type: application/json
```

Body example:
```json
{
  "model": "anthropic/claude-sonnet-4-5",
  "messages": [
    {"role": "system", "content": "<SYSTEM_PROMPT>"},
    {"role": "user",   "content": "<transcript_context>"}
  ],
  "temperature": 0.3,
  "max_tokens": 1024
}
```

After LLM response:
1. INSERT into summaries/action_items tables
2. Emit Socket.IO events `call_summary` and `action_items` to the session room

### 3.6 Deepgram Aura TTS

File: `pipeline/deepgram_tts.py`

```
POST https://api.deepgram.com/v1/speak?model=aura-asteria-en
Authorization: Token {DEEPGRAM_API_KEY}
Content-Type: application/json
Body: {"text": "<assistant reply text>"}
Response: audio/mpeg binary
```

The binary is base64-encoded and emitted over Socket.IO:
```python
audio_b64 = base64.b64encode(audio_bytes).decode()
socketio.emit('tts_audio', {'session_id': session_id, 'audio': audio_b64}, room=session_id)
```

Browser decodes and plays:
```javascript
socket.on('tts_audio', ({ audio }) => {
  const blob = new Blob([Uint8Array.from(atob(audio), c => c.charCodeAt(0))], { type: 'audio/mpeg' });
  new Audio(URL.createObjectURL(blob)).play();
});
```

---

## 4. Document Ingestion Pipeline (NEW — v2)

### 4.1 Overview

Documents up to 200 MB each (1 GB per batch) are accepted. Processing is fully async via RQ. The pipeline extracts text, splits into 512-token chunks with 100-token overlap, embeds each chunk, stores embeddings in ChromaDB, and emits Socket.IO progress events.

### 4.2 Upload Flow

1. Client POSTs `multipart/form-data` to `POST /api/documents/upload`
2. Flask validates: MIME type must be `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, or `text/plain`; file size ≤ 200 MB (200 × 1024 × 1024 bytes)
3. Flask saves raw file to `{UPLOAD_FOLDER}/{doc_id}/{filename}` on disk
4. Flask INSERTs a row into `documents` table with `status='queued'`, `job_id=None`
5. Flask calls `q.enqueue('backend.worker.ingest_document', doc_id, retry=Retry(max=3, interval=[30, 60, 120]))` → returns RQ job object
6. Flask UPDATEs `documents.job_id = job.id`
7. Flask returns 201:
   ```json
   {
     "doc_id": "uuid4",
     "filename": "report_q4.pdf",
     "mime_type": "application/pdf",
     "size_bytes": 5242880,
     "status": "queued",
     "job_id": "rq-job-uuid",
     "uploaded_at": "2026-04-14T10:00:00Z"
   }
   ```

### 4.3 Chunking Algorithm

File: `pipeline/document_processor.py` — function `chunk_document(text, pages_map)`

`pages_map` is a dict: `{page_num (int): text (str)}` produced by pdfminer page-by-page extraction.

```python
CHUNK_TOKENS = 512
OVERLAP_TOKENS = 100

def chunk_document(pages_map: dict) -> list[dict]:
    """
    Returns list of chunk dicts:
    {
      'chunk_index': int,        # 0-based global index across all pages
      'page_number': int,        # 1-based PDF page number
      'text': str,               # chunk text
      'token_count': int         # approximate token count
    }
    """
    import tiktoken
    enc = tiktoken.get_encoding('cl100k_base')  # works for all claude/openai models

    all_tokens = []   # list of (token_id, page_number)
    for page_num in sorted(pages_map.keys()):
        page_text = pages_map[page_num]
        tokens = enc.encode(page_text)
        all_tokens.extend([(t, page_num) for t in tokens])

    chunks = []
    start = 0
    chunk_index = 0
    total_tokens = len(all_tokens)

    while start < total_tokens:
        end = min(start + CHUNK_TOKENS, total_tokens)
        chunk_token_ids = [t[0] for t in all_tokens[start:end]]
        chunk_pages = [t[1] for t in all_tokens[start:end]]
        chunk_text = enc.decode(chunk_token_ids)
        # The page number is the page where the majority of tokens in this chunk come from
        dominant_page = max(set(chunk_pages), key=chunk_pages.count)
        chunks.append({
            'chunk_index': chunk_index,
            'page_number': dominant_page,
            'text': chunk_text,
            'token_count': len(chunk_token_ids)
        })
        chunk_index += 1
        start += (CHUNK_TOKENS - OVERLAP_TOKENS)  # slide with overlap

    return chunks
```

### 4.4 pdfminer Extraction

File: `pipeline/document_processor.py` — function `extract_pages(filepath) -> dict[int, str]`

```python
from pdfminer.high_level import extract_pages as pm_extract_pages
from pdfminer.layout import LTTextContainer

def extract_pages(filepath: str) -> dict:
    """Returns {page_num (1-based): text_content}"""
    pages_map = {}
    for page_num, page_layout in enumerate(pm_extract_pages(filepath), start=1):
        page_text = ''
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                page_text += element.get_text()
        pages_map[page_num] = page_text.strip()
    return pages_map
```

For DOCX: use `python-docx` to extract paragraphs, assign all text to page_number=1 (DOCX has no true page boundaries).
For TXT: read entire file as a single string, assign to page_number=1.

### 4.5 Embedding Model

Use OpenRouter's embedding endpoint:

```
POST https://openrouter.ai/api/v1/embeddings
Authorization: Bearer {OPENROUTER_API_KEY}
Content-Type: application/json
Body:
{
  "model": "openai/text-embedding-3-small",
  "input": "<chunk text>"
}
Response:
{
  "data": [{"embedding": [0.023, -0.041, ...], "index": 0}],
  "model": "openai/text-embedding-3-small",
  "usage": {"prompt_tokens": 87, "total_tokens": 87}
}
```

- Model: `openai/text-embedding-3-small` (1536-dimensional, supported by OpenRouter, cheap)
- Set via env var: `EMBEDDING_MODEL=openai/text-embedding-3-small`
- Batch: embed one chunk at a time (to avoid token limit issues; batch later as optimization)
- Retry 3 times on HTTP 429/500 with 2s backoff

### 4.6 ChromaDB Collection Schema

File: `pipeline/chroma_client.py`

```python
import chromadb

_client = None

def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=os.getenv('CHROMA_PATH', './chroma_db'))
    return _client

def get_or_create_collection(doc_id: str):
    """One ChromaDB collection per document. Name: doc_{doc_id_no_hyphens}"""
    client = get_chroma_client()
    name = f"doc_{doc_id.replace('-', '')}"
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )
```

Each chunk is added to the collection:
```python
collection.add(
    ids=[f"chunk_{chunk['chunk_index']}"],
    embeddings=[embedding_vector],          # list of 1536 floats
    documents=[chunk['text']],
    metadatas=[{
        "doc_id": doc_id,
        "chunk_index": chunk['chunk_index'],
        "page_number": chunk['page_number'],
        "token_count": chunk['token_count']
    }]
)
```

### 4.7 Worker Job: `ingest_document`

File: `backend/worker.py` — function `ingest_document(doc_id: str)`

Full job pseudocode:
```python
def ingest_document(doc_id: str):
    import structlog
    log = structlog.get_logger()
    db = get_db_session()

    try:
        # 1. Load document record
        doc = db.query(Document).filter_by(doc_id=doc_id).first()
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        doc.status = 'processing'
        db.commit()

        # 2. Emit start event
        emit_doc_event('doc_processing_start', {
            'doc_id': doc_id,
            'progress_pct': 0,
            'pages_done': 0,
            'pages_total': 0
        })

        # 3. Extract text (pdfminer / docx / txt)
        filepath = doc.storage_path
        pages_map = extract_pages(filepath)   # {page_num: text}
        total_pages = len(pages_map)

        # 4. Update total_pages in DB
        doc.total_pages = total_pages
        db.commit()

        # 5. Chunk
        chunks = chunk_document(pages_map)    # list of chunk dicts
        total_chunks = len(chunks)
        log.info("doc_chunked", doc_id=doc_id, total_chunks=total_chunks, total_pages=total_pages)

        # 6. Embed + store each chunk
        collection = get_or_create_collection(doc_id)
        pages_done = set()

        for i, chunk in enumerate(chunks):
            # 6a. Embed
            t0 = time.time()
            embedding = embed_text(chunk['text'])  # calls OpenRouter
            latency_ms = int((time.time() - t0) * 1000)
            log.info("chunk_embedded",
                     doc_id=doc_id, chunk_index=i,
                     embedding_model=EMBEDDING_MODEL, latency_ms=latency_ms)

            # 6b. Store in ChromaDB
            collection.add(
                ids=[f"chunk_{i}"],
                embeddings=[embedding],
                documents=[chunk['text']],
                metadatas=[{
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "page_number": chunk['page_number'],
                    "token_count": chunk['token_count']
                }]
            )

            # 6c. INSERT document_chunks metadata row
            chunk_row = DocumentChunk(
                doc_id=doc_id,
                chunk_index=i,
                page_number=chunk['page_number'],
                text=chunk['text'],
                token_count=chunk['token_count'],
                embedding_model=EMBEDDING_MODEL,
                created_at=datetime.utcnow().isoformat()
            )
            db.add(chunk_row)
            db.commit()

            # 6d. Track pages done
            pages_done.add(chunk['page_number'])
            progress_pct = int((i + 1) / total_chunks * 100)

            # 6e. Emit progress every 10 chunks or on page boundary
            if i % 10 == 0 or chunk['page_number'] not in pages_done:
                emit_doc_event('doc_chunk_embedded', {
                    'doc_id': doc_id,
                    'progress_pct': progress_pct,
                    'pages_done': len(pages_done),
                    'pages_total': total_pages,
                    'chunk_index': i,
                    'total_chunks': total_chunks
                })

        # 7. Finalize
        doc.status = 'ready'
        doc.total_chunks = total_chunks
        db.commit()

        emit_doc_event('doc_processing_done', {
            'doc_id': doc_id,
            'progress_pct': 100,
            'pages_done': total_pages,
            'pages_total': total_pages,
            'total_chunks': total_chunks
        })
        log.info("doc_ingestion_complete", doc_id=doc_id, total_chunks=total_chunks)

    except Exception as e:
        doc.status = 'failed'
        db.commit()
        log.error("doc_ingestion_failed", doc_id=doc_id, error=str(e))
        emit_doc_event('doc_processing_error', {'doc_id': doc_id, 'error': str(e)})
        raise   # RQ will retry
    finally:
        db.close()
```

`emit_doc_event` uses a Redis pub/sub channel that Flask-SocketIO listens to (cross-process socket emission):
```python
def emit_doc_event(event_name: str, payload: dict):
    """Emit Socket.IO event from RQ worker process via Redis pub/sub."""
    redis_client = get_redis_client()
    redis_client.publish('socketio_events', json.dumps({
        'event': event_name,
        'data': payload,
        'room': payload.get('doc_id')   # clients join room by doc_id after upload
    }))
```

In `backend/app.py`, a gevent greenlet subscribes to `socketio_events` channel and forwards to Socket.IO:
```python
def redis_event_relay():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('socketio_events')
    for message in pubsub.listen():
        if message['type'] == 'message':
            payload = json.loads(message['data'])
            socketio.emit(payload['event'], payload['data'], room=payload.get('room'))

gevent.spawn(redis_event_relay)
```

### 4.8 RAG Query Flow

Endpoint: `POST /api/documents/search`

```
Request:
{
  "query": "What is the total revenue for Q4?",
  "doc_ids": ["uuid1", "uuid2"],   // optional filter; omit for all docs in session
  "session_id": "uuid",            // optional: search all docs linked to this call
  "top_k": 5                       // optional, default 5, max 20
}

Response:
{
  "query": "What is the total revenue for Q4?",
  "answer": "Based on the documents, the Q4 revenue was ₹42.3 crore...",
  "sources": [
    {
      "doc_id": "uuid1",
      "filename": "report_q4.pdf",
      "page_number": 7,
      "chunk_index": 23,
      "text": "...Revenue for Q4 FY26 stood at ₹42.3 crore, up 18% YoY...",
      "score": 0.91
    }
  ]
}
```

Server-side flow:
```python
def rag_search(query, doc_ids, session_id, top_k=5):
    # 1. Check Redis cache (key: rag:{sha256(query+doc_ids)}, TTL 10 min)
    cache_key = f"rag:{hashlib.sha256((query + str(sorted(doc_ids))).encode()).hexdigest()}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # 2. Embed the query
    query_embedding = embed_text(query)

    # 3. Query ChromaDB for each doc_id
    all_results = []
    for doc_id in doc_ids:
        collection = get_or_create_collection(doc_id)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        for i, text in enumerate(results['documents'][0]):
            score = 1 - results['distances'][0][i]   # cosine: 1-distance = similarity
            all_results.append({
                'doc_id': doc_id,
                'text': text,
                'score': score,
                **results['metadatas'][0][i]
            })

    # 4. Sort by score, take top_k
    all_results.sort(key=lambda x: x['score'], reverse=True)
    top_chunks = all_results[:top_k]

    # 5. Build context for LLM synthesis
    context = '\n\n'.join([
        f"[Source: {r['filename']}, Page {r['page_number']}]\n{r['text']}"
        for r in top_chunks
    ])
    prompt = f"Answer based only on the following document excerpts:\n\n{context}\n\nQuestion: {query}"

    # 6. LLM synthesis call (claude-sonnet-4-5)
    answer = openrouter_client.complete(
        task='rag_synthesis',
        user_message=prompt,
        max_tokens=512
    )

    result = {'query': query, 'answer': answer, 'sources': top_chunks}

    # 7. Cache result
    redis_client.setex(cache_key, 600, json.dumps(result))

    return result
```

---

## 5. Flask API Contract

### Authentication

All endpoints except `/api/auth/login` and `/api/auth/refresh` require authentication.

Two auth methods are supported:
1. **JWT Bearer token**: `Authorization: Bearer <access_token>`
2. **API key**: `X-API-Key: <api_key>` (stored in users table, `api_key` column)

Socket.IO authentication: pass JWT in the auth payload:
```javascript
const socket = io('http://localhost:5000', {
  auth: { token: localStorage.getItem('access_token') }
});
```

Server validates on `connect` event:
```python
@socketio.on('connect')
def handle_connect(auth):
    token = auth.get('token') if auth else None
    if not token:
        raise ConnectionRefusedError('Authentication required')
    user = verify_jwt(token)
    if not user:
        raise ConnectionRefusedError('Invalid token')
    session['user_id'] = user.id
    session['role'] = user.role
```

### REST Endpoints

---

#### POST /api/auth/login
**Request body:**
```json
{"username": "agent01", "password": "secret"}
```
**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 86400,
  "role": "agent"
}
```
**Errors:** 401 if credentials invalid; 403 if user is_active=false.

---

#### POST /api/auth/refresh
**Request body:**
```json
{"refresh_token": "eyJ..."}
```
**Response (200):**
```json
{"access_token": "eyJ...", "expires_in": 86400}
```
**Errors:** 401 if refresh token invalid or expired.

---

#### POST /api/calls/start
**Auth required**: role `agent` or `admin`
**Rate limit**: 100/min per user
**Request body:**
```json
{
  "agent_id": "string (optional, defaults to JWT username)",
  "language": "string (optional, defaults to 'hi-en')",
  "metadata": {}
}
```
**Response (201):**
```json
{
  "session_id": "uuid4 string",
  "status": "active",
  "created_at": "ISO8601"
}
```

---

#### POST /api/calls/<session_id>/end
**Auth required**: role `agent` or `admin`
**Request body:**
```json
{"agent_id": "string (optional)"}
```
**Response (200):**
```json
{
  "session_id": "string",
  "status": "ended",
  "duration_seconds": 142,
  "transcript_count": 12,
  "ended_at": "ISO8601"
}
```
**Notes:** Updates `calls.status = 'ended'`. Enqueues `run_end_of_call_llm` job for final summary.

---

#### GET /api/calls
**Auth required**: role `agent`, `supervisor`, or `admin`
**Rate limit**: 100/min per user
**Query params:** `page` (int, default 1), `per_page` (int, default 20, max 100), `agent_id` (string), `status` (active|ended), `from` (ISO8601 date), `to` (ISO8601 date)

**Response (200):**
```json
{
  "calls": [
    {
      "session_id": "uuid",
      "agent_id": "string",
      "status": "ended",
      "language": "hi-en",
      "created_at": "ISO8601",
      "ended_at": "ISO8601",
      "duration_seconds": 142,
      "summary_preview": "First 120 chars..."
    }
  ],
  "total": 85,
  "page": 1,
  "per_page": 20
}
```

---

#### GET /api/calls/<session_id>
**Auth required**: any authenticated user
**Response (200):** Full call object with transcripts, summary, action_items arrays.
**Errors:** 404 if not found.

---

#### POST /api/documents/upload
**Auth required**: role `agent` or `admin`
**Rate limit**: 20 uploads/hour per user
**Request:** `multipart/form-data`
- `file`: binary file (PDF/DOCX/TXT — max 200 MB)
- `call_session_id`: string (optional)
- `description`: string (optional)

**Response (201):**
```json
{
  "doc_id": "uuid",
  "filename": "invoice_march.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 204800,
  "status": "queued",
  "job_id": "rq-job-uuid",
  "uploaded_at": "ISO8601"
}
```

---

#### GET /api/documents/<doc_id>
**Auth required**: any authenticated user
**Response (200):**
```json
{
  "doc_id": "uuid",
  "filename": "string",
  "mime_type": "string",
  "size_bytes": 204800,
  "status": "queued|processing|ready|failed",
  "total_pages": 100,
  "total_chunks": 412,
  "job_id": "rq-job-uuid",
  "uploaded_at": "ISO8601"
}
```

---

#### GET /api/documents/<doc_id>/status
**Auth required**: any authenticated user
**Response (200):**
```json
{
  "doc_id": "uuid",
  "status": "processing",
  "job_id": "rq-job-uuid",
  "job_status": "started",
  "progress_pct": 47,
  "pages_done": 47,
  "pages_total": 100,
  "chunks_done": 193,
  "total_chunks": 412
}
```
**Notes:** `progress_pct` is read from Redis key `doc_progress:{doc_id}` (updated by worker).

---

#### POST /api/documents/search
**Auth required**: any authenticated user
**Rate limit**: 100/min per user
**Request body:**
```json
{
  "query": "What is the refund policy?",
  "doc_ids": ["uuid1", "uuid2"],
  "session_id": "uuid (optional)",
  "top_k": 5
}
```
**Response (200):**
```json
{
  "query": "What is the refund policy?",
  "answer": "LLM synthesized answer based on top chunks...",
  "sources": [
    {
      "doc_id": "uuid1",
      "filename": "policy.pdf",
      "page_number": 12,
      "chunk_index": 45,
      "text": "...chunk text...",
      "score": 0.91
    }
  ]
}
```

---

#### GET /api/analytics/summary
**Auth required**: role `supervisor` or `admin`
**Query params:** `from` (ISO8601), `to` (ISO8601)
**Notes:** Result cached in Redis for 5 minutes. Cache key: `analytics:summary:{from}:{to}`

**Response (200):**
```json
{
  "total_calls": 320,
  "total_duration_seconds": 48600,
  "average_duration_seconds": 151,
  "calls_by_status": {"active": 3, "ended": 317},
  "calls_by_language": {"hi-en": 290, "en": 30},
  "action_items_generated": 980,
  "action_items_by_priority": {"high": 120, "medium": 500, "low": 360}
}
```

---

#### GET /api/analytics/agent/<agent_id>
**Auth required**: role `supervisor` or `admin`
**Response (200):** Agent-specific analytics.

---

#### GET /api/jobs/<job_id>
**Auth required**: any authenticated user
**Response (200):**
```json
{
  "job_id": "rq-job-uuid",
  "status": "queued|started|finished|failed|deferred",
  "created_at": "ISO8601",
  "started_at": "ISO8601",
  "ended_at": "ISO8601",
  "result": null,
  "error": null
}
```
**Notes:** Fetches from RQ's job registry via `rq.job.Job.fetch(job_id, connection=redis)`.

---

#### GET /admin/rq
**Auth required**: `X-Admin-Token: {ADMIN_TOKEN}` header (separate from JWT)
**Notes:** Served by `rq-dashboard`. Mount in Flask app factory:
```python
from rq_dashboard import blueprint as rq_blueprint
app.config['RQ_DASHBOARD_REDIS_URL'] = REDIS_URL
app.register_blueprint(rq_blueprint, url_prefix='/admin/rq')
```

---

### Socket.IO Events

#### Client → Server

| Event | Payload | Auth | Description |
|---|---|---|---|
| `connect` | `auth: {token: JWT}` | Required | Authenticate Socket.IO connection |
| `join_call` | `{session_id: str}` | Required | Client joins room, server opens Deepgram WS |
| `audio_chunk` | `{session_id: str, data: Blob/bytes}` | Required | Raw audio chunk from MediaRecorder |
| `leave_call` | `{session_id: str}` | Required | Client leaves, server closes Deepgram WS |
| `join_doc_room` | `{doc_id: str}` | Required | Client subscribes to document ingestion events |

#### Server → Client

| Event | Payload | Description |
|---|---|---|
| `transcript_interim` | `{session_id, text, timestamp}` | Partial transcript from Deepgram |
| `transcript_final` | `{session_id, text, timestamp}` | Final transcript segment |
| `call_summary` | `{session_id, summary}` | LLM-generated summary |
| `action_items` | `{session_id, items: [{text, priority}]}` | Extracted action items |
| `tts_audio` | `{session_id, audio: base64_str}` | TTS response audio |
| `doc_processing_start` | `{doc_id, progress_pct:0, pages_done:0, pages_total:N}` | Document ingestion begun |
| `doc_chunk_embedded` | `{doc_id, progress_pct, pages_done, pages_total, chunk_index, total_chunks}` | Progress update |
| `doc_processing_done` | `{doc_id, progress_pct:100, total_chunks, total_pages}` | Document fully ingested |
| `doc_processing_error` | `{doc_id, error: str}` | Ingestion failed |
| `error` | `{session_id, code, message}` | Error from any pipeline stage |

---

## 6. Frontend Screens

### Screen 0 — Login Page
- **Route**: `/login`
- **Key UI elements**: Username + password fields, "Sign In" button, error message on bad creds
- **REST calls**: `POST /api/auth/login`
- **Behavior**: Stores `access_token` and `refresh_token` in localStorage. Redirects to `/` on success.
- **Note**: All other routes are wrapped in `<ProtectedRoute>` — redirect to `/login` if no token.

### Screen 1 — Live Call Page
- **Route**: `/` (default, also `/call`)
- **Primary user**: Call center agent
- **Key UI elements**:
  - Large "Start Call" / "End Call" button
  - Audio waveform animation (CSS) while recording
  - Live transcript scrolling text area (interim shown in grey, final in black)
  - Language badge (hi-en / en / hi)
  - Action items panel — populates in real time
  - Call summary panel — appears after call ends
  - TTS audio player (auto-plays, volume control)
  - Session ID display (for reference)
- **Socket.IO events consumed**: `transcript_interim`, `transcript_final`, `call_summary`, `action_items`, `tts_audio`, `error`
- **REST calls**: `POST /api/calls/start`, `POST /api/calls/<session_id>/end`

### Screen 2 — Call History Page
- **Route**: `/history`
- **Primary user**: Supervisor / QA reviewer
- **Key UI elements**:
  - Filterable table: date range, agent ID, status dropdown
  - Columns: Session ID, Agent, Date, Duration, Status, Summary preview
  - Pagination (20 per page)
  - Click row → navigate to Call Detail
  - Export CSV button (client-side)
- **REST calls**: `GET /api/calls` with query params

### Screen 3 — Call Detail Page
- **Route**: `/calls/:session_id`
- **Key UI elements**: metadata header, full transcript timeline, summary, action items, related documents list
- **REST calls**: `GET /api/calls/<session_id>`

### Screen 4 — Documents Page (v2 — enhanced)
- **Route**: `/documents`
- **Primary user**: Operations team
- **Key UI elements**:
  - Drag-and-drop upload zone (PDF, DOCX, TXT — up to 200 MB)
  - Per-document ingestion progress bar (animated, shows `pages_done / pages_total` and `progress_pct%`)
  - Documents table: filename, type, size, status badge, upload date, linked call
  - "Ask a Question" RAG input box — text field + "Search" button
  - RAG results section: LLM answer card + source chunk list (filename, page number, score, text excerpt)
  - Chunk viewer modal: click any document → see list of all chunks with page number
- **Socket.IO events consumed**: `doc_processing_start`, `doc_chunk_embedded`, `doc_processing_done`, `doc_processing_error`
  - On mount, emit `join_doc_room` for each doc with status != 'ready'
- **REST calls**: `POST /api/documents/upload`, `GET /api/documents/<doc_id>`, `GET /api/documents/<doc_id>/status`, `POST /api/documents/search`

### Screen 5 — Analytics Page
- **Route**: `/analytics`
- **Primary user**: Management
- **Key UI elements**:
  - Date range picker
  - KPI cards: total calls, avg duration, total action items
  - Bar chart: calls per day (recharts)
  - Pie chart: calls by language
  - Agent performance table (sortable)
- **REST calls**: `GET /api/analytics/summary`, `GET /api/analytics/agent/<agent_id>`

### Screen 6 — Admin Page (v2 — new)
- **Route**: `/admin`
- **Auth**: Only visible/accessible to users with role `admin`
- **Key UI elements**:
  - **Job Queue Dashboard**: Link button → opens `/admin/rq` in new tab (rq-dashboard)
  - **Queue Stats card**: Shows pending/active/failed job counts (poll `GET /api/jobs/stats` every 30s)
  - **User Management table**: columns: username, role, is_active (toggle), created_at, api_key (masked)
    - "Add User" button → modal with username/password/role fields
    - "Deactivate" button per user row
  - **System Health card**: Redis ping, DB connection, ChromaDB collections count
- **REST calls**: `GET /api/admin/users`, `POST /api/admin/users`, `PATCH /api/admin/users/<id>`, `GET /api/admin/health`

---

## 7. Database Schema (v2)

File: `backend/database.py` — SQLAlchemy ORM models, engine creation, session factory.

### Connection Layer

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./pravaah.db')

if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_size=10,
        execution_options={"isolation_level": "SERIALIZABLE"}
    )
    # Enable WAL mode
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
else:
    # PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=10
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### File: `backend/models.py`

All ORM models use the `Base` from `database.py`.

### Table: users
```python
class User(Base):
    __tablename__ = 'users'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    username     = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(128), nullable=False)   # bcrypt hash
    role         = Column(String(16), nullable=False, default='agent')
                   # 'agent' | 'supervisor' | 'admin'
    api_key      = Column(String(64), nullable=True, unique=True)
                   # optional; SHA-256 of random bytes, stored plain for lookup
    is_active    = Column(Boolean, nullable=False, default=True)
    created_at   = Column(String(32), nullable=False)     # ISO8601
```

### Table: calls
```python
class Call(Base):
    __tablename__ = 'calls'
    id               = Column(Integer, primary_key=True, autoincrement=True)
    session_id       = Column(String(36), nullable=False, unique=True)  # UUID4
    agent_id         = Column(String(64), nullable=False, default='unknown')
    user_id          = Column(Integer, ForeignKey('users.id'), nullable=True)
    status           = Column(String(16), nullable=False, default='active')
                       # 'active' | 'ended'
    language         = Column(String(16), nullable=False, default='hi-en')
    metadata_json    = Column(Text, nullable=True)         # JSON string
    created_at       = Column(String(32), nullable=False)  # ISO8601
    ended_at         = Column(String(32), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

Index: idx_calls_agent_id, idx_calls_status, idx_calls_created_at, idx_calls_user_id
```

### Table: transcripts
```python
class Transcript(Base):
    __tablename__ = 'transcripts'
    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey('calls.session_id'), nullable=False)
    text       = Column(Text, nullable=False)
    is_final   = Column(Boolean, nullable=False, default=True)
    speaker    = Column(String(32), nullable=True)
    timestamp  = Column(String(32), nullable=False)  # ISO8601

Index: idx_transcripts_session
```

### Table: summaries
```python
class Summary(Base):
    __tablename__ = 'summaries'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(String(36), ForeignKey('calls.session_id'), nullable=False, unique=True)
    text         = Column(Text, nullable=False)
    model_used   = Column(String(64), nullable=False)
    generated_at = Column(String(32), nullable=False)  # ISO8601
```

### Table: action_items
```python
class ActionItem(Base):
    __tablename__ = 'action_items'
    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey('calls.session_id'), nullable=False)
    text       = Column(Text, nullable=False)
    priority   = Column(String(16), nullable=False, default='medium')
                 # 'high' | 'medium' | 'low'
    assignee   = Column(String(64), nullable=True)
    status     = Column(String(16), nullable=False, default='open')
                 # 'open' | 'done'
    created_at = Column(String(32), nullable=False)

Index: idx_action_items_session, idx_action_items_priority
```

### Table: documents (v2 — updated)
```python
class Document(Base):
    __tablename__ = 'documents'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    doc_id       = Column(String(36), nullable=False, unique=True)  # UUID4
    session_id   = Column(String(36), ForeignKey('calls.session_id'), nullable=True)
    user_id      = Column(Integer, ForeignKey('users.id'), nullable=True)
    filename     = Column(String(256), nullable=False)
    mime_type    = Column(String(64), nullable=False)
    size_bytes   = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)   # absolute path on disk
    description  = Column(Text, nullable=True)
    status       = Column(String(16), nullable=False, default='queued')
                   # 'queued' | 'processing' | 'ready' | 'failed'
    job_id       = Column(String(64), nullable=True)     # RQ job ID
    total_pages  = Column(Integer, nullable=True)        # filled after extraction
    total_chunks = Column(Integer, nullable=True)        # filled after ingestion
    uploaded_at  = Column(String(32), nullable=False)    # ISO8601
    # NOTE: extracted_text column is REMOVED; text lives in document_chunks table
    # NOTE: ChromaDB stores embeddings; document_chunks stores text + metadata

Index: idx_documents_session, idx_documents_user_id, idx_documents_status
```

### Table: document_chunks (NEW)
```python
class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    id              = Column(Integer, primary_key=True, autoincrement=True)
    doc_id          = Column(String(36), ForeignKey('documents.doc_id'), nullable=False)
    chunk_index     = Column(Integer, nullable=False)    # 0-based
    page_number     = Column(Integer, nullable=False)    # 1-based PDF page
    text            = Column(Text, nullable=False)       # raw chunk text
    token_count     = Column(Integer, nullable=False)
    embedding_model = Column(String(64), nullable=False) # e.g. 'openai/text-embedding-3-small'
    created_at      = Column(String(32), nullable=False) # ISO8601
    # NOTE: the actual embedding vector is stored in ChromaDB, keyed by
    #       collection="doc_{doc_id_no_hyphens}", id="chunk_{chunk_index}"

Index: idx_chunks_doc_id, idx_chunks_page_number
UniqueConstraint: (doc_id, chunk_index)
```

### Table: jobs (NEW)
```python
class Job(Base):
    __tablename__ = 'jobs'
    id           = Column(Integer, primary_key=True, autoincrement=True)
    job_id       = Column(String(64), nullable=False, unique=True)  # RQ job ID
    job_type     = Column(String(32), nullable=False)
                   # 'ingest_document' | 'run_end_of_call_llm' | 'generate_analytics_cache'
    status       = Column(String(16), nullable=False, default='queued')
                   # 'queued' | 'started' | 'finished' | 'failed'
    payload_json = Column(Text, nullable=True)   # job input as JSON string
    result_json  = Column(Text, nullable=True)   # job result as JSON string
    error        = Column(Text, nullable=True)   # error message if failed
    retry_count  = Column(Integer, nullable=False, default=0)
    created_at   = Column(String(32), nullable=False)   # ISO8601
    started_at   = Column(String(32), nullable=True)
    completed_at = Column(String(32), nullable=True)

Index: idx_jobs_type, idx_jobs_status
```

---

## 8. Worker Architecture (NEW — v2)

### 8.1 Starting Workers

Workers run as a separate OS process, not inside Flask:

```bash
# Start RQ worker (run in a separate terminal or via start.sh)
rq worker pravaah --url $REDIS_URL --with-scheduler
```

`start.sh` must start:
1. Redis check (ping; start `redis-server` if not running)
2. RQ worker (`rq worker pravaah &`)
3. Flask server (`python -m backend.app`)

### 8.2 Job Types

| Job Function | Module | Trigger | Retry Policy |
|---|---|---|---|
| `ingest_document` | `backend.worker` | `POST /api/documents/upload` | 3 retries, intervals: [30s, 60s, 120s] |
| `run_end_of_call_llm` | `backend.worker` | Deepgram `is_final=True` transcript | 3 retries, intervals: [10s, 30s, 60s] |
| `generate_analytics_cache` | `backend.worker` | Scheduled (every 5 min) via RQ Scheduler | No retry |

### 8.3 Enqueuing Jobs

```python
from redis import Redis
from rq import Queue, Retry

redis_conn = Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
q = Queue('pravaah', connection=redis_conn)

# Document ingestion
job = q.enqueue(
    'backend.worker.ingest_document',
    doc_id,
    retry=Retry(max=3, interval=[30, 60, 120]),
    job_timeout=3600    # 1 hour max for large PDFs
)

# LLM job
job = q.enqueue(
    'backend.worker.run_end_of_call_llm',
    session_id,
    transcript,
    retry=Retry(max=3, interval=[10, 30, 60]),
    job_timeout=120
)
```

After enqueuing, Flask also INSERTs a row into the `jobs` table.

### 8.4 Job Status Polling

Frontend polls `GET /api/jobs/<job_id>` every 2 seconds while a job is in progress.
The endpoint uses `rq.job.Job.fetch(job_id, connection=redis_conn)` to get live status.

Additionally, for document ingestion, the frontend uses Socket.IO events (more efficient than polling).

### 8.5 Failed Job Handling

If all retries are exhausted:
1. RQ moves the job to the `failed` registry
2. The worker's `on_failure` callback fires:
   ```python
   def on_ingest_failure(job, connection, type, value, traceback):
       db = get_db_session()
       doc = db.query(Document).filter_by(job_id=job.id).first()
       if doc:
           doc.status = 'failed'
           db.commit()
       db.query(Job).filter_by(job_id=job.id).update({
           'status': 'failed',
           'error': str(value),
           'completed_at': datetime.utcnow().isoformat()
       })
       db.commit()
   ```
3. Socket.IO `doc_processing_error` event is emitted to the client

---

## 9. Redis Data Structures (NEW — v2)

### Key Naming Conventions

All keys use colon-separated namespaces. No spaces. All TTLs are explicitly set.

### Session State (Voice Calls)

| Key | Type | TTL | Contents |
|---|---|---|---|
| `session:{session_id}` | Hash | 2h | `deepgram_ws_open`, `transcript_buffer`, `agent_id`, `user_id`, `started_at` |
| `session:{session_id}:transcripts` | List | 2h | Ordered list of final transcript strings (for end-of-call summary) |

### Document Ingestion Progress

| Key | Type | TTL | Contents |
|---|---|---|---|
| `doc_progress:{doc_id}` | Hash | 24h | `progress_pct`, `pages_done`, `pages_total`, `chunks_done`, `total_chunks`, `status` |

Worker updates this hash after each chunk; `GET /api/documents/<doc_id>/status` reads it.

### Rate Limiting (flask-limiter)

flask-limiter stores counters in Redis automatically. Keys follow the pattern:
`LIMITER:{user_id}:{endpoint}:{window}` (managed by flask-limiter internals, do not write to directly).

### Analytics Cache

| Key | Type | TTL | Contents |
|---|---|---|---|
| `analytics:summary:{from}:{to}` | String (JSON) | 5min (300s) | Serialized analytics response |
| `analytics:agent:{agent_id}` | String (JSON) | 5min (300s) | Serialized agent analytics |

### Document Search Cache

| Key | Type | TTL | Contents |
|---|---|---|---|
| `rag:{sha256_hash}` | String (JSON) | 10min (600s) | Serialized RAG response (query + answer + sources) |

Hash is `sha256(query + sorted(doc_ids))`.

### RQ Job Queue

RQ manages its own Redis keys:
- `rq:queue:pravaah` — sorted set of queued job IDs
- `rq:job:{job_id}` — hash with job metadata
- `rq:finished:pravaah` — finished job registry
- `rq:failed:pravaah` — failed job registry

Do not write to these keys manually.

### Pub/Sub for Cross-Process Socket.IO

| Channel | Publisher | Subscriber | Message format |
|---|---|---|---|
| `socketio_events` | RQ worker | Flask gevent greenlet | `{event, data, room}` JSON string |

---

## 10. Authentication Implementation

### JWT Token Structure

```python
import jwt   # PyJWT
import bcrypt

ACCESS_TOKEN_EXPIRY = 86400      # 24 hours
REFRESH_TOKEN_EXPIRY = 604800    # 7 days

def create_access_token(user_id: int, role: str) -> str:
    payload = {
        'sub': str(user_id),
        'role': role,
        'type': 'access',
        'exp': datetime.utcnow() + timedelta(seconds=ACCESS_TOKEN_EXPIRY),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

def create_refresh_token(user_id: int) -> str:
    payload = {
        'sub': str(user_id),
        'type': 'refresh',
        'exp': datetime.utcnow() + timedelta(seconds=REFRESH_TOKEN_EXPIRY),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

def verify_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

### Role Decorators

File: `backend/auth.py`

```python
from functools import wraps
from flask import request, jsonify, g

def require_auth(roles=None):
    """Decorator: validates JWT or API key. Sets g.user_id and g.role."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Try JWT Bearer token
            auth_header = request.headers.get('Authorization', '')
            api_key = request.headers.get('X-API-Key', '')

            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                payload = verify_jwt(token)
                if not payload:
                    return jsonify({'error': 'Invalid or expired token'}), 401
                g.user_id = int(payload['sub'])
                g.role = payload['role']
            elif api_key:
                db = get_db_session()
                user = db.query(User).filter_by(api_key=api_key, is_active=True).first()
                if not user:
                    return jsonify({'error': 'Invalid API key'}), 401
                g.user_id = user.id
                g.role = user.role
            else:
                return jsonify({'error': 'Authentication required'}), 401

            if roles and g.role not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator
```

Usage:
```python
@app.route('/api/calls/start', methods=['POST'])
@limiter.limit('100/minute', key_func=lambda: g.user_id)
@require_auth(roles=['agent', 'admin'])
def start_call():
    ...
```

### Password Hashing

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

---

## 11. Structured Logging (NEW — v2)

File: `backend/utils.py` — `setup_logging()` called in `app.py` at startup.

```python
import structlog
import logging

def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True
    )
    logging.basicConfig(format='%(message)s', level=os.getenv('LOG_LEVEL', 'INFO'))
```

### Log Events and Fields

Every Flask request (via `@app.after_request` hook):
```json
{"event": "api_request", "method": "POST", "path": "/api/documents/upload", "status": 201, "duration_ms": 42, "user_id": 7}
```

Every LLM call (in `openrouter_client.py`):
```json
{"event": "llm_call", "model": "anthropic/claude-sonnet-4-5", "task": "summarize", "tokens_in": 312, "tokens_out": 87, "latency_ms": 1240}
```

Every document chunk embedded (in `worker.py`):
```json
{"event": "chunk_embedded", "doc_id": "uuid", "chunk_index": 14, "embedding_model": "openai/text-embedding-3-small", "latency_ms": 220}
```

Every Deepgram event (in `deepgram_stt.py`):
```json
{"event": "deepgram_event", "session_id": "uuid", "event_type": "Results", "is_final": true, "transcript_length": 87}
```

---

## 12. Rate Limiting (NEW — v2)

File: `backend/limiter.py`

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import g

limiter = Limiter(
    key_func=lambda: getattr(g, 'user_id', None) or get_remote_address(),
    storage_uri=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    default_limits=["100 per minute"]
)
```

### Per-Endpoint Limits

| Endpoint | Limit | Key |
|---|---|---|
| `POST /api/auth/login` | 10/minute | IP address |
| All other `/api/*` | 100/minute | user_id |
| `POST /api/documents/upload` | 20/hour | user_id |
| `POST /api/documents/search` | 30/minute | user_id |
| `GET /api/analytics/*` | 20/minute | user_id |

Apply with decorator:
```python
@app.route('/api/documents/upload', methods=['POST'])
@limiter.limit('20 per hour')
@require_auth(roles=['agent', 'admin'])
def upload_document():
    ...
```

---

## 13. Full Monorepo Folder Structure (updated)

See Section 2.

---

## 14. Agent Deliverables Table (v2 — updated)

| Agent | Files to Create | Definition of Done |
|---|---|---|
| **Architect** | `ARCHITECTURE.md`, appends `ARCHITECT_V2: DONE` to `PROGRESS.md` | `ARCHITECTURE.md` exists, >500 lines, all v2 sections present |
| **Pipeline Engineer** | `pipeline/__init__.py`, `pipeline/deepgram_stt.py`, `pipeline/deepgram_tts.py`, `pipeline/openrouter_client.py` (add embedding endpoint), `pipeline/prompt_templates.py`, `pipeline/session_manager.py`, `pipeline/document_processor.py`, `pipeline/chroma_client.py` | All 8 files exist; `openrouter_client.py` supports both chat and embedding calls; `document_processor.py` has `extract_pages()`, `chunk_document()`, `embed_text()`; `chroma_client.py` connects to ChromaDB; `PIPELINE: DONE` in PROGRESS.md |
| **Backend Engineer** | `backend/__init__.py`, `backend/app.py` (gevent mode, redis relay greenlet), `backend/config.py`, `backend/database.py` (SQLAlchemy ORM), `backend/models.py` (all 7 tables), `backend/auth.py`, `backend/limiter.py`, `backend/worker.py` (3 job functions), `backend/routes/__init__.py`, `backend/routes/auth.py`, `backend/routes/calls.py`, `backend/routes/documents.py`, `backend/routes/analytics.py`, `backend/routes/jobs.py`, `backend/socket_handlers.py`, `backend/utils.py`, `requirements.txt` | All 17 files exist; Flask app starts with gevent; all auth endpoints work; doc upload enqueues RQ job; `BACKEND: DONE` in PROGRESS.md |
| **Frontend Engineer** | `frontend/package.json`, `frontend/vite.config.js`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/index.html`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/src/socket.js` (sends JWT), `frontend/src/api.js` (Authorization header), `frontend/src/auth.js`, `frontend/src/components/AudioRecorder.jsx`, `frontend/src/components/TranscriptDisplay.jsx`, `frontend/src/components/ActionItemsList.jsx`, `frontend/src/components/CallSummaryCard.jsx`, `frontend/src/components/LanguageBadge.jsx`, `frontend/src/components/NavBar.jsx`, `frontend/src/components/DocumentUploadZone.jsx`, `frontend/src/components/DocIngestionProgress.jsx`, `frontend/src/components/ProtectedRoute.jsx`, `frontend/src/pages/LoginPage.jsx`, `frontend/src/pages/LiveCallPage.jsx`, `frontend/src/pages/CallHistoryPage.jsx`, `frontend/src/pages/CallDetailPage.jsx`, `frontend/src/pages/DocumentsPage.jsx`, `frontend/src/pages/AnalyticsPage.jsx`, `frontend/src/pages/AdminPage.jsx` | All 26 files exist; `npm run build` succeeds; all 7 routes render; Login redirects unauthenticated users; DocumentsPage shows progress bars and RAG input; `FRONTEND: DONE` in PROGRESS.md |
| **DevOps Engineer** | `Makefile`, `start.sh` (starts Redis check + RQ worker + Flask), `.env.example` (all v2 vars), `README.md`, `tests/test_pipeline.py`, `tests/test_api.py`, `tests/test_socket.py` | All 7 files exist; `make test` runs without import errors; `start.sh` starts all 3 processes; README has Redis + ChromaDB setup instructions; `DEVOPS: DONE` in PROGRESS.md |
| **QA Reviewer** | `REVIEW.md` | `REVIEW.md` exists with Overall Status (APPROVED or BLOCKED) and per-agent checklist; `REVIEWER: DONE` in PROGRESS.md |

---

## 15. Environment Variables (v2 — updated)

| Variable | Description | Required | Default |
|---|---|---|---|
| `DEEPGRAM_API_KEY` | Deepgram API key (STT + TTS) | Yes | — |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM + embedding calls | Yes | — |
| `FLASK_SECRET_KEY` | Flask session secret | Yes | — |
| `JWT_SECRET_KEY` | Secret for signing JWTs (different from Flask secret) | Yes | — |
| `ADMIN_TOKEN` | Token for `/admin/rq` access (rq-dashboard) | Yes | — |
| `REDIS_URL` | Redis connection URL | No | `redis://localhost:6379/0` |
| `DATABASE_URL` | SQLAlchemy DB URL; swap to `postgresql://...` for Postgres | No | `sqlite:///./pravaah.db` |
| `CHROMA_PATH` | Directory path for ChromaDB persistence | No | `./chroma_db` |
| `UPLOAD_FOLDER` | Directory for uploaded raw files | No | `./uploads` |
| `EMBEDDING_MODEL` | OpenRouter model for embeddings | No | `openai/text-embedding-3-small` |
| `OPENROUTER_HEAVY_MODEL` | Heavy LLM model ID | No | `anthropic/claude-sonnet-4-5` |
| `OPENROUTER_LIGHT_MODEL` | Light LLM model ID | No | `anthropic/claude-haiku-4-5-20251001` |
| `DEEPGRAM_STT_MODEL` | Deepgram STT model | No | `nova-2` |
| `DEEPGRAM_TTS_MODEL` | Deepgram TTS voice | No | `aura-asteria-en` |
| `MAX_UPLOAD_MB` | Max file upload size in MB | No | `200` |
| `FLASK_ENV` | `development` or `production` | No | `development` |
| `FLASK_HOST` | Host to bind Flask | No | `0.0.0.0` |
| `FLASK_PORT` | Port for Flask server | No | `5000` |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins | No | `http://localhost:5173` |
| `LOG_LEVEL` | Python logging level | No | `INFO` |

---

## 16. Integration Risks (v2 — updated)

### Risk 1: Deepgram WebSocket drops during long calls
**Severity**: High
**Mitigation**: Automatic reconnection in `deepgram_stt.py` with exponential backoff (max 5 retries: 1s, 2s, 4s, 8s, 16s). Keep `session_id` so transcript insertion resumes correctly. Emit `error` Socket.IO event if all retries fail.

### Risk 2: Audio encoding mismatch
**Severity**: High
**Mitigation**: Always pass `encoding=webm-opus&sample_rate=48000&channels=1` in Deepgram WS URL params. If Deepgram returns 400, log full error body and emit `error` event. Browser fallback: try `audio/ogg;codecs=opus` if webm/opus not supported.

### Risk 3: OpenRouter rate limits during peak volume
**Severity**: Medium
**Mitigation**: Token-bucket rate limiter in `openrouter_client.py` (max 10 req/min per session). Queue LLM requests if limit hit. For embedding calls, implement backoff on 429 response. Log queue depth as a metric.

### Risk 4: SQLite write contention under concurrent calls
**Severity**: Medium
**Mitigation**: WAL mode + SQLAlchemy connection pool (10). For >20 concurrent calls, switch to `DATABASE_URL=postgresql://...` — no code changes required.

### Risk 5: CORS errors (React 5173 ↔ Flask 5000)
**Severity**: Low
**Mitigation**: Flask-CORS with `origins=CORS_ORIGINS`. Vite proxy in `vite.config.js` for `/api/*` and `/socket.io/*`.

### Risk 6: ChromaDB data loss on restart (NEW)
**Severity**: High
**Mitigation**: Always use `chromadb.PersistentClient(path=CHROMA_PATH)` — never `chromadb.Client()` (in-memory). Ensure `CHROMA_PATH` is a persistent directory (not `/tmp`). Add ChromaDB health check in `/admin/health` endpoint: try `client.heartbeat()`. If ChromaDB data is lost (e.g., disk wipe), documents must be re-ingested — provide a `POST /api/documents/<doc_id>/reingest` endpoint that re-enqueues the `ingest_document` job.

### Risk 7: RQ worker not running (NEW)
**Severity**: High
**Mitigation**: On document upload response, warn client if `q.count == q.count` doesn't decrease within 10s (i.e., no worker). Add `/api/admin/health` endpoint that checks `len(rq.Worker.all(connection=redis_conn)) > 0` and returns `{"rq_workers": N, "status": "ok"|"no_workers"}`. `start.sh` must verify Redis is running and start RQ worker before Flask. README must warn: "If documents stay in 'queued' state, ensure `rq worker pravaah` is running."

### Risk 8: Large PDF memory usage in worker (NEW)
**Severity**: Medium
**Mitigation**: pdfminer processes one page at a time (`extract_pages()` is a generator). Do not load the entire PDF text into memory at once. Process page by page and yield chunks. For files >100 MB, log a warning and increase `job_timeout` to 3600s.

### Risk 9: tiktoken not available / token count approximation
**Severity**: Low
**Mitigation**: If `tiktoken` import fails, fall back to word-count approximation: `token_count ≈ len(text.split()) * 1.3`. Log a warning if tiktoken is not installed. Add `tiktoken` to `requirements.txt`.

---

## 17. OpenRouter Model Routing Rules (v2 — updated)

File: `pipeline/openrouter_client.py`

```python
HEAVY_TASKS = {'summarize', 'extract_action_items', 'classify_sentiment', 'rag_synthesis'}
LIGHT_TASKS = {'detect_language', 'generate_ack', 'tag_entities', 'analytics_label'}
EMBEDDING_TASKS = {'embed_chunk', 'embed_query'}

def route_model(task: str) -> str:
    if task in EMBEDDING_TASKS:
        return os.getenv('EMBEDDING_MODEL', 'openai/text-embedding-3-small')
    if task in HEAVY_TASKS:
        return os.getenv('OPENROUTER_HEAVY_MODEL', 'anthropic/claude-sonnet-4-5')
    return os.getenv('OPENROUTER_LIGHT_MODEL', 'anthropic/claude-haiku-4-5-20251001')
```

| Task | Model | Justification |
|---|---|---|
| Call summary generation | `anthropic/claude-sonnet-4-5` | Nuanced hi-en understanding |
| Action item extraction | `anthropic/claude-sonnet-4-5` | Precise extraction + priority classification |
| Sentiment/intent classification | `anthropic/claude-sonnet-4-5` | Subtle emotion cues |
| RAG synthesis (document Q&A) | `anthropic/claude-sonnet-4-5` | Complex multi-source synthesis |
| Language detection | `anthropic/claude-haiku-4-5-20251001` | Simple classification, speed matters |
| Acknowledgement generation (TTS) | `anthropic/claude-haiku-4-5-20251001` | Short output, <500ms latency target |
| Entity tagging (names, amounts) | `anthropic/claude-haiku-4-5-20251001` | Structured extraction |
| Analytics label generation | `anthropic/claude-haiku-4-5-20251001` | Batch offline, cost optimization |
| Chunk embedding | `openai/text-embedding-3-small` | 1536-dim, cheap, fast, supported by OpenRouter |
| Query embedding | `openai/text-embedding-3-small` | Must match chunk embedding model exactly |

---

## 18. Prompt Templates (v2 — updated)

All prompts live in `pipeline/prompt_templates.py`.

### SYSTEM_SUMMARIZE (unchanged from v1)
```
You are an expert call analyst for Indian enterprise customer service operations.
You analyze transcripts from multilingual (Hindi-English code-switched) calls.
Your summaries are concise (3-5 sentences), factual, and written in English.
Focus on: what the customer needed, what was resolved, and what is pending.
```

### SYSTEM_ACTION_ITEMS (unchanged from v1)
```
You are an expert at extracting action items from customer service call transcripts.
Extract all follow-up actions mentioned or implied in the transcript.
Return a JSON array of objects with keys: text (string), priority (high|medium|low), assignee (string or null).
Return ONLY the JSON array, no other text.
```

### SYSTEM_SENTIMENT (unchanged from v1)
```
You classify sentiment and intent for customer service quality assurance.
Given a transcript, return JSON with:
- sentiment: positive | neutral | negative
- intent: inquiry | complaint | order | support | other
- confidence: 0.0 to 1.0
Return ONLY the JSON object.
```

### SYSTEM_ENTITY_TAG (unchanged from v1)
```
Extract named entities from this customer service transcript.
Return JSON with arrays for: names (people), amounts (monetary), dates, product_names, locations.
Return ONLY the JSON object.
```

### SYSTEM_RAG_SYNTHESIS (NEW)
```
You are an enterprise document analyst for Indian businesses.
You are given excerpts from business documents (PDFs, reports, contracts).
Answer the user's question based ONLY on the provided document excerpts.
If the answer is not in the excerpts, say: "I could not find this information in the provided documents."
Always cite which document and page number you are drawing from.
Be concise: 2-4 sentences unless the question requires a list.
```

---

*End of ARCHITECTURE.md — written by Architect Agent v2, Pravaah OS v2.0 — Enterprise Scale*
