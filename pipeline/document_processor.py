"""
Pravaah OS — Document Ingestion Worker

Entry point for the RQ ``ingest_document`` job.  Handles PDF, TXT, and DOCX
files; chunks text by token count; embeds chunks via OpenRouter; stores
vectors in ChromaDB; and updates the SQLite/PostgreSQL database.

This module is intentionally importable as a standalone function — RQ calls
``ingest_document`` directly without going through the Flask app context.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token chunking helpers
# ---------------------------------------------------------------------------

_CHUNK_TARGET_TOKENS = 512
_CHUNK_OVERLAP_TOKENS = 100
_EMBED_BATCH_SIZE = 50
_DOCX_PAGE_PARAGRAPHS = 50


def _count_tokens(text: str, encoder) -> int:
    """
    Return the number of tokens in *text* using the provided tiktoken encoder.

    Parameters
    ----------
    text : str
        Input text.
    encoder : tiktoken.Encoding
        Pre-loaded tiktoken encoding (e.g. cl100k_base).

    Returns
    -------
    int
        Token count.
    """
    return len(encoder.encode(text))


def _chunk_page(
    page_text: str,
    page_number: int,
    doc_id: str,
    start_chunk_index: int,
    encoder,
) -> list[dict[str, Any]]:
    """
    Split *page_text* into overlapping token-bounded chunks.

    Each chunk is a dict with keys:
    ``text``, ``page_number``, ``chunk_index``, ``doc_id``.

    Parameters
    ----------
    page_text : str
        Raw text of a single page (or logical page for TXT/DOCX).
    page_number : int
        1-based page number.
    doc_id : str
        Document identifier from the database.
    start_chunk_index : int
        The global chunk index at which to start numbering from.
    encoder : tiktoken.Encoding
        Pre-loaded cl100k_base encoder.

    Returns
    -------
    list[dict]
        List of chunk dicts.
    """
    tokens = encoder.encode(page_text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        return []

    chunks: list[dict[str, Any]] = []
    chunk_idx = start_chunk_index

    if total_tokens <= _CHUNK_TARGET_TOKENS:
        chunks.append(
            {
                "text": page_text,
                "page_number": page_number,
                "chunk_index": chunk_idx,
                "doc_id": doc_id,
            }
        )
    else:
        pos = 0
        while pos < total_tokens:
            end = min(pos + _CHUNK_TARGET_TOKENS, total_tokens)
            chunk_tokens = tokens[pos:end]
            chunk_text = encoder.decode(chunk_tokens)
            chunks.append(
                {
                    "text": chunk_text,
                    "page_number": page_number,
                    "chunk_index": chunk_idx,
                    "doc_id": doc_id,
                }
            )
            chunk_idx += 1
            if end == total_tokens:
                break
            pos = end - _CHUNK_OVERLAP_TOKENS

    return chunks


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_pdf(file_path: str) -> list[tuple[int, str]]:
    """
    Extract text from a PDF file, one entry per page.

    Parameters
    ----------
    file_path : str
        Absolute path to the PDF file.

    Returns
    -------
    list[tuple[int, str]]
        List of ``(page_number, page_text)`` tuples (1-based page numbers).
    """
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer

    pages: list[tuple[int, str]] = []
    for page_num, page_layout in enumerate(extract_pages(file_path), start=1):
        texts: list[str] = []
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                texts.append(element.get_text())
        pages.append((page_num, "".join(texts)))
    return pages


def _extract_txt(file_path: str) -> list[tuple[int, str]]:
    """
    Read a plain-text file as a single logical page.

    Parameters
    ----------
    file_path : str
        Absolute path to the TXT file.

    Returns
    -------
    list[tuple[int, str]]
        Single-element list: ``[(1, full_text)]``.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    return [(1, content)]


def _extract_docx(file_path: str) -> list[tuple[int, str]]:
    """
    Extract text from a DOCX file, grouping every 50 paragraphs as one page.

    Parameters
    ----------
    file_path : str
        Absolute path to the DOCX file.

    Returns
    -------
    list[tuple[int, str]]
        List of ``(page_number, page_text)`` tuples.
    """
    from docx import Document  # python-docx

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    pages: list[tuple[int, str]] = []
    for page_num, start in enumerate(
        range(0, max(len(paragraphs), 1), _DOCX_PAGE_PARAGRAPHS), start=1
    ):
        batch = paragraphs[start : start + _DOCX_PAGE_PARAGRAPHS]
        pages.append((page_num, "\n".join(batch)))
    return pages


# ---------------------------------------------------------------------------
# Main RQ job
# ---------------------------------------------------------------------------


def ingest_document(
    doc_id: str,
    file_path: str,
    db_url: str,
    redis_url: str,
    chroma_path: str,
    openrouter_api_key: str,
    job_id: str | None = None,
) -> None:
    """
    Ingest a document into ChromaDB and update the database.

    This function is the RQ job entry point.  It:

    1. Extracts text page by page (PDF / TXT / DOCX).
    2. Chunks each page using a 512-token sliding window with 100-token overlap.
    3. Emits progress events via Redis pub/sub.
    4. Embeds chunks in batches of 50 using EmbeddingClient.
    5. Stores embeddings + text in ChromaDB collection ``doc_{doc_id}``.
    6. Updates the ``documents`` and ``document_chunks`` tables in the DB.

    Parameters
    ----------
    doc_id : str
        Document primary key from the ``documents`` table.
    file_path : str
        Absolute path to the uploaded file on disk.
    db_url : str
        SQLAlchemy-compatible database URL (e.g. ``sqlite:///pravaah.db``).
    redis_url : str
        Redis URL (e.g. ``redis://localhost:6379/0``).
    chroma_path : str
        Filesystem path where ChromaDB persists its data.
    openrouter_api_key : str
        OpenRouter API key for the embedding client.
    """
    import tiktoken
    import chromadb
    import redis as redis_lib
    import sqlalchemy as sa

    from .embeddings import EmbeddingClient

    # ------------------------------------------------------------------
    # Setup — resolve job_id from RQ context if not passed explicitly
    # ------------------------------------------------------------------
    if job_id is None:
        try:
            from rq import get_current_job
            rq_job = get_current_job()
            if rq_job:
                job_id = rq_job.id
        except Exception:
            pass

    redis_client = redis_lib.from_url(redis_url)
    channel = f"doc:{doc_id}:progress"

    def _publish(payload: dict) -> None:
        """Publish a progress event to Redis pub/sub."""
        try:
            redis_client.publish(channel, json.dumps(payload))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis publish failed: %s", exc)

    def _update_job_status(status: str, engine, error_msg: str | None = None) -> None:
        """Update the jobs table row for this ingest job."""
        if not job_id:
            return
        try:
            with engine.begin() as conn:
                if status in ("finished", "failed"):
                    conn.execute(
                        sa.text(
                            "UPDATE jobs SET status=:status, completed_at=CURRENT_TIMESTAMP "
                            "WHERE job_id=:job_id"
                        ),
                        {"status": status, "job_id": job_id},
                    )
                else:
                    conn.execute(
                        sa.text("UPDATE jobs SET status=:status WHERE job_id=:job_id"),
                        {"status": status, "job_id": job_id},
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to update job %s status to %s: %s", job_id, status, exc)

    try:
        encoder = tiktoken.get_encoding("cl100k_base")

        # Mark job as started and document as processing
        _engine_early = sa.create_engine(db_url)
        with _engine_early.begin() as conn:
            conn.execute(
                sa.text("UPDATE documents SET status='processing' WHERE doc_id=:doc_id"),
                {"doc_id": doc_id},
            )
        _update_job_status("started", _engine_early)
        _engine_early.dispose()

        # ------------------------------------------------------------------
        # Step 1 — Extract text
        # ------------------------------------------------------------------
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            raw_pages = _extract_pdf(file_path)
        elif ext == ".txt":
            raw_pages = _extract_txt(file_path)
        elif ext in {".docx", ".doc"}:
            raw_pages = _extract_docx(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {ext!r}")

        total_pages = len(raw_pages)
        _publish({"status": "extracting", "event": "extracted", "pages": total_pages})
        logger.info("doc=%s extracted %d pages from %s", doc_id, total_pages, file_path)

        # ------------------------------------------------------------------
        # Step 2 — Chunk pages
        # ------------------------------------------------------------------
        all_chunks: list[dict] = []
        for page_num, page_text in raw_pages:
            if not page_text.strip():
                continue
            page_chunks = _chunk_page(
                page_text, page_num, doc_id, len(all_chunks), encoder
            )
            all_chunks.extend(page_chunks)

        total_chunks = len(all_chunks)
        logger.info("doc=%s produced %d chunks", doc_id, total_chunks)

        # ------------------------------------------------------------------
        # Step 3 — Embed in batches of 50 with progress updates
        # ------------------------------------------------------------------
        embed_client = EmbeddingClient(api_key=openrouter_api_key)
        all_embeddings: list[list[float]] = []

        for batch_start in range(0, total_chunks, _EMBED_BATCH_SIZE):
            batch = all_chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]
            batch_texts = [c["text"] for c in batch]
            batch_vectors = embed_client.embed(batch_texts)
            all_embeddings.extend(batch_vectors)

            # Emit every 10 embedded chunks (batch boundaries may differ)
            done = len(all_embeddings)
            pct = int(done / max(total_chunks, 1) * 100)
            _publish(
                {
                    "status": "embedding",
                    "event": "embedding",
                    "progress": pct,
                    "pct": pct,
                    "chunks_done": done,
                    "total": total_chunks,
                }
            )

        # ------------------------------------------------------------------
        # Step 4 — Store in ChromaDB
        # On retry runs we delete the old collection first to avoid duplicate-id
        # errors from a previous partial ingest.
        # ------------------------------------------------------------------
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection_name = f"doc_{doc_id}"
        try:
            chroma_client.delete_collection(collection_name)
            logger.info("doc=%s deleted stale ChromaDB collection before re-ingest", doc_id)
        except Exception:
            pass  # Collection didn't exist — that's fine

        collection = chroma_client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [f"{doc_id}_chunk_{c['chunk_index']}" for c in all_chunks]
        metadatas = [
            {
                "page_number": c["page_number"],
                "chunk_index": c["chunk_index"],
                "doc_id": c["doc_id"],
            }
            for c in all_chunks
        ]
        documents_texts = [c["text"] for c in all_chunks]

        # ChromaDB add() in one call (it handles batching internally)
        collection.add(
            ids=ids,
            embeddings=all_embeddings,
            metadatas=metadatas,
            documents=documents_texts,
        )
        logger.info("doc=%s stored %d chunks in ChromaDB", doc_id, total_chunks)

        # ------------------------------------------------------------------
        # Step 5 — Update DB (wipe old chunks first, then re-insert cleanly)
        # ------------------------------------------------------------------
        engine = sa.create_engine(db_url)
        with engine.begin() as conn:
            # Remove stale chunk rows from any previous partial ingest
            conn.execute(
                sa.text("DELETE FROM document_chunks WHERE doc_id=:doc_id"),
                {"doc_id": doc_id},
            )

            # Update documents table
            conn.execute(
                sa.text(
                    "UPDATE documents SET status='completed', total_pages=:tp, "
                    "total_chunks=:tc WHERE doc_id=:doc_id"
                ),
                {"tp": total_pages, "tc": total_chunks, "doc_id": doc_id},
            )

            # Insert document_chunks rows
            for chunk in all_chunks:
                conn.execute(
                    sa.text(
                        "INSERT INTO document_chunks "
                        "(doc_id, chunk_index, page_number, text, embedding_model) "
                        "VALUES (:doc_id, :chunk_index, :page_number, :text, :model)"
                    ),
                    {
                        "doc_id": doc_id,
                        "chunk_index": chunk["chunk_index"],
                        "page_number": chunk["page_number"],
                        "text": chunk["text"],
                        "model": "text-embedding-3-small",
                    },
                )

        _update_job_status("finished", engine)
        logger.info("doc=%s DB update complete", doc_id)

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        _publish(
            {"status": "done", "event": "done", "total_chunks": total_chunks, "total_pages": total_pages}
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("doc=%s ingest failed: %s", doc_id, exc, exc_info=True)
        _publish({"status": "failed", "event": "error", "message": str(exc)})

        # Mark document and job as failed in DB
        try:
            _fail_engine = sa.create_engine(db_url)  # type: ignore[possibly-undefined]
            with _fail_engine.begin() as conn:
                conn.execute(
                    sa.text("UPDATE documents SET status='failed' WHERE doc_id=:doc_id"),
                    {"doc_id": doc_id},
                )
            _update_job_status("failed", _fail_engine)
            _fail_engine.dispose()
        except Exception as db_exc:  # noqa: BLE001
            logger.error("doc=%s failed to update DB status to failed: %s", doc_id, db_exc)

        raise
