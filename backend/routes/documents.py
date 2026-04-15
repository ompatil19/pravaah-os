"""
Pravaah OS — /api/documents Blueprint (v2)

Endpoints:
  POST /api/documents/upload           → upload file, enqueue ingest_document RQ job
  GET  /api/documents/<doc_id>         → fetch document record
  GET  /api/documents/<doc_id>/status  → doc + job processing status
  POST /api/documents/search           → RAG semantic search (requires auth)
"""

from __future__ import annotations

import json
import logging
import os
import uuid

from flask import Blueprint, g, request

from .. import database as db
from ..auth import require_auth
from ..models import document_to_dict
from ..utils import (
    allowed_file,
    ensure_upload_folder,
    error,
    now_iso,
    ok,
    safe_filename,
)

logger = logging.getLogger(__name__)
documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _get_max_upload_bytes() -> int:
    """Return max upload size in bytes from MAX_UPLOAD_MB env var (default 200)."""
    try:
        mb = int(os.environ.get("MAX_UPLOAD_MB", "200"))
    except (ValueError, TypeError):
        mb = 200
    return mb * 1024 * 1024


def _guess_mime(ext: str) -> str:
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "txt": "text/plain",
    }.get(ext, "application/octet-stream")


def _enqueue_ingest(doc_id: str, storage_path: str, mime_type: str) -> str | None:
    """
    Enqueue the ingest_document RQ job. Returns the RQ job_id or None on failure.
    Falls back to synchronous inline text extraction if Redis/RQ unavailable.
    """
    try:
        import redis as _redis
        from rq import Queue
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        r = _redis.Redis.from_url(redis_url)
        q = Queue("pravaah", connection=r)

        # Try to import the worker task
        try:
            from pipeline.workers import ingest_document
        except ImportError:
            # Fallback: define a minimal inline task reference
            ingest_document = _inline_ingest

        job = q.enqueue(
            ingest_document,
            doc_id=doc_id,
            storage_path=storage_path,
            mime_type=mime_type,
            job_timeout=600,
        )
        return job.id
    except Exception as exc:
        logger.warning("RQ enqueue failed (%s), using inline extraction.", exc)
        _inline_ingest(doc_id=doc_id, storage_path=storage_path, mime_type=mime_type)
        return None


def _inline_ingest(doc_id: str, storage_path: str, mime_type: str, **kwargs) -> None:
    """
    Inline (synchronous) document ingestion fallback when RQ is unavailable.
    Extracts text and updates document status.
    """
    import threading
    threading.Thread(
        target=_extract_text_sync,
        args=(doc_id, storage_path, mime_type),
        daemon=True,
        name=f"extract-{doc_id}",
    ).start()


def _extract_text_sync(doc_id: str, storage_path: str, mime_type: str) -> None:
    """Background text extraction (inline fallback, no RQ)."""
    try:
        db.update_document_status(doc_id, "processing")
        text = ""

        if mime_type == "application/pdf" or storage_path.lower().endswith(".pdf"):
            text = _extract_pdf(storage_path)
        elif mime_type == "text/plain" or storage_path.lower().endswith(".txt"):
            with open(storage_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        elif "wordprocessingml" in mime_type or storage_path.lower().endswith(".docx"):
            text = _extract_docx(storage_path)
        else:
            try:
                with open(storage_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                text = ""

        # Chunk text and insert chunks
        chunks = _chunk_text(text)
        for idx, chunk_text in enumerate(chunks):
            db.insert_document_chunk(
                doc_id=doc_id,
                chunk_index=idx,
                page_number=1,  # page tracking requires deeper PDF parsing
                text=chunk_text,
            )

        db.update_document_status(
            doc_id=doc_id,
            status="completed",
            total_pages=1,
            total_chunks=len(chunks),
        )
        logger.info("[%s] Inline ingest complete: %d chunks.", doc_id, len(chunks))

        # Publish progress event to Redis if available
        _publish_progress(doc_id, {"status": "completed", "total_chunks": len(chunks)})

    except Exception as exc:
        logger.error("[%s] Inline ingest failed: %s", doc_id, exc)
        db.update_document_status(doc_id, "failed")
        _publish_progress(doc_id, {"status": "failed", "error": str(exc)})


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks of ~chunk_size chars."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def _extract_pdf(path: str) -> str:
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        return pdfminer_extract(path) or ""
    except ImportError:
        logger.warning("pdfminer.six not installed; PDF extraction skipped.")
        return ""
    except Exception as exc:
        logger.error("PDF extraction error: %s", exc)
        return ""


def _extract_docx(path: str) -> str:
    try:
        import docx
        doc = docx.Document(path)
        return "\n".join(para.text for para in doc.paragraphs)
    except ImportError:
        logger.warning("python-docx not installed; DOCX extraction skipped.")
        return ""
    except Exception as exc:
        logger.error("DOCX extraction error: %s", exc)
        return ""


def _publish_progress(doc_id: str, data: dict) -> None:
    """Publish a doc progress event to Redis pub/sub."""
    try:
        import redis as _redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        r = _redis.Redis.from_url(redis_url)
        r.publish(f"doc:{doc_id}:progress", json.dumps(data))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# POST /api/documents/upload
# ---------------------------------------------------------------------------

@documents_bp.route("/upload", methods=["POST"])
@require_auth()
def upload_document():
    """
    Accept a multipart file upload, save to disk, and enqueue an RQ ingest job.

    Form fields:
        file             (required) — binary file (PDF, DOCX, TXT, max MAX_UPLOAD_MB)
        call_session_id  (optional) — associate with a call
        description      (optional) — free-text description
    """
    try:
        if "file" not in request.files:
            return error("MISSING_FILE", "No file field in request.", 400)

        file = request.files["file"]
        if not file or not file.filename:
            return error("EMPTY_FILE", "No file selected.", 400)

        filename = safe_filename(file.filename)
        if not filename:
            return error("INVALID_FILENAME", "Could not derive a safe filename.", 400)

        if not allowed_file(filename):
            return error("UNSUPPORTED_FILE_TYPE", "Allowed: pdf, docx, doc, txt.", 400)

        max_bytes = _get_max_upload_bytes()
        content = file.read()
        if len(content) > max_bytes:
            return error(
                "FILE_TOO_LARGE",
                f"Max size is {max_bytes // (1024 * 1024)} MB.",
                400,
            )

        call_session_id = request.form.get("call_session_id") or None
        description = request.form.get("description") or None

        if call_session_id:
            call_row = db.get_call(call_session_id)
            if not call_row:
                return error("CALL_NOT_FOUND", f"Session {call_session_id} not found.", 404)

        doc_id = str(uuid.uuid4())
        upload_folder = ensure_upload_folder()
        ext = filename.rsplit(".", 1)[-1].lower()
        storage_filename = f"{doc_id}.{ext}"
        storage_path = os.path.join(upload_folder, storage_filename)

        with open(storage_path, "wb") as f:
            f.write(content)

        mime_type = file.content_type or _guess_mime(ext)
        uploaded_at = now_iso()

        # Create a DB Job record first
        rq_job_id_placeholder = str(uuid.uuid4())
        db.insert_job(
            job_id=rq_job_id_placeholder,
            job_type="ingest_document",
            payload_json=json.dumps({"doc_id": doc_id, "storage_path": storage_path}),
            status="queued",
        )

        db.insert_document(
            doc_id=doc_id,
            session_id=call_session_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
            storage_path=storage_path,
            description=description,
            uploaded_at=uploaded_at,
            job_id=rq_job_id_placeholder,
            status="processing",
        )

        # Enqueue RQ job (may update job_id to actual RQ id)
        actual_rq_job_id = _enqueue_ingest(doc_id, storage_path, mime_type)
        if actual_rq_job_id and actual_rq_job_id != rq_job_id_placeholder:
            db.update_document_status(doc_id, "processing", job_id=actual_rq_job_id)
            db.update_job(rq_job_id_placeholder, "finished")
            db.insert_job(
                job_id=actual_rq_job_id,
                job_type="ingest_document",
                payload_json=json.dumps({"doc_id": doc_id, "storage_path": storage_path}),
                status="queued",
            )

        final_job_id = actual_rq_job_id or rq_job_id_placeholder

        # Subscribe Socket.IO room to Redis pub/sub for progress (best-effort)
        try:
            from ..app import socketio
            # Emit initial status to any listening client
            socketio.emit(
                "doc_progress",
                {"doc_id": doc_id, "status": "processing", "job_id": final_job_id},
                room=f"doc:{doc_id}",
            )
        except Exception:
            pass

        return ok(
            {
                "doc_id": doc_id,
                "job_id": final_job_id,
                "status": "processing",
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": len(content),
                "uploaded_at": uploaded_at,
            },
            201,
        )
    except Exception as exc:
        logger.exception("Error uploading document: %s", exc)
        return error("UPLOAD_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/documents/<doc_id>
# ---------------------------------------------------------------------------

@documents_bp.route("/<doc_id>", methods=["GET"])
@require_auth()
def get_document(doc_id: str):
    """Return the document record."""
    try:
        doc = db.get_document(doc_id)
        if not doc:
            return error("DOCUMENT_NOT_FOUND", f"Document {doc_id} not found.", 404)
        return ok(doc.to_dict())
    except Exception as exc:
        logger.exception("Error fetching document %s: %s", doc_id, exc)
        return error("GET_DOCUMENT_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# GET /api/documents/<doc_id>/status
# ---------------------------------------------------------------------------

@documents_bp.route("/<doc_id>/status", methods=["GET"])
@require_auth()
def get_document_status(doc_id: str):
    """Return document processing status plus job status."""
    try:
        doc = db.get_document(doc_id)
        if not doc:
            return error("DOCUMENT_NOT_FOUND", f"Document {doc_id} not found.", 404)

        job_status = None
        if doc.job_id:
            job = db.get_job(doc.job_id)
            if job:
                job_status = job.status

        return ok(
            {
                "doc_id": doc.doc_id,
                "status": doc.status,
                "total_pages": doc.total_pages,
                "total_chunks": doc.total_chunks,
                "job_id": doc.job_id,
                "job_status": job_status,
            }
        )
    except Exception as exc:
        logger.exception("Error fetching status for %s: %s", doc_id, exc)
        return error("GET_STATUS_FAILED", str(exc), 500)


# ---------------------------------------------------------------------------
# POST /api/documents/search
# ---------------------------------------------------------------------------

@documents_bp.route("/search", methods=["POST"])
@require_auth()
def search_documents():
    """
    Semantic search via RAGEngine.

    Body:
        query    : str  (required)
        doc_ids  : list (optional) — filter to these documents
        top_k    : int  (optional, default 5)
    """
    try:
        body = request.get_json(silent=True) or {}
        query = str(body.get("query", "")).strip()
        doc_ids = body.get("doc_ids") or None
        try:
            top_k = int(body.get("top_k", 5))
        except (ValueError, TypeError):
            top_k = 5

        if not query:
            return error("MISSING_QUERY", "query is required.", 400)

        # Attempt RAGEngine query
        try:
            import redis as _redis
            from flask import current_app
            from pipeline.rag_engine import RAGEngine
            _chroma_path = os.getenv("CHROMA_PATH", "./chroma_store")
            _openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
            _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            try:
                _rc = _redis.Redis.from_url(_redis_url, decode_responses=True)
                _rc.ping()
            except Exception:
                _rc = None
            rag = RAGEngine(chroma_path=_chroma_path, openrouter_api_key=_openrouter_key, redis_client=_rc)
            results = rag.query(query=query, doc_ids=doc_ids, top_k=top_k)
        except ImportError:
            # RAGEngine not yet implemented — return empty results gracefully
            results = []
            logger.warning("RAGEngine not available; returning empty search results.")
        except Exception as exc:
            logger.error("RAGEngine query failed: %s", exc)
            return error("RAG_QUERY_FAILED", str(exc), 500)

        return ok(
            {
                "query": query,
                "results": results,
                "count": len(results),
            }
        )
    except Exception as exc:
        logger.exception("Search error: %s", exc)
        return error("SEARCH_FAILED", str(exc), 500)
