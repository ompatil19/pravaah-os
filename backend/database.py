"""
Pravaah OS — SQLAlchemy Database Layer (v2)

Supports both SQLite (WAL mode, pool_size=10) and PostgreSQL via DATABASE_URL.
Preserves all v1 helper functions by reimplementing them on top of SQLAlchemy sessions.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine creation
# ---------------------------------------------------------------------------

def _build_engine():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        # Fall back to legacy DATABASE_PATH env var for SQLite
        from .config import DATABASE_PATH
        db_url = f"sqlite:///{DATABASE_PATH}"

    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            pool_size=10,
            pool_pre_ping=True,
        )
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
    else:
        # Supabase uses pgbouncer in transaction mode — prepared statements must
        # be disabled (prepare_threshold=0) and SSL is required.
        from sqlalchemy.pool import NullPool
        engine = create_engine(
            db_url,
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={
                "sslmode": "require",
                "options": "-c statement_timeout=30000",
            },
        )

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager that yields a SQLAlchemy Session and commits on clean exit.

    Usage::

        with get_db() as session:
            session.add(obj)
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they don't already exist. Called once at startup."""
    from .models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialised (SQLAlchemy). URL=%s", engine.url)


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------

def insert_call(
    session_id: str,
    agent_id: str,
    language: str,
    metadata: Optional[str],
    created_at: str,
) -> int:
    from .models import Call
    with get_db() as session:
        call = Call(
            session_id=session_id,
            agent_id=agent_id,
            status="active",
            language=language,
            metadata=metadata,
            created_at=created_at,
        )
        session.add(call)
        session.flush()
        return call.id


def end_call(session_id: str, ended_at: str, duration_seconds: int) -> None:
    from .models import Call
    with get_db() as session:
        session.query(Call).filter(Call.session_id == session_id).update(
            {"status": "ended", "ended_at": ended_at, "duration_seconds": duration_seconds}
        )


def get_call(session_id: str):
    from .models import Call
    with get_db() as session:
        return session.query(Call).filter(Call.session_id == session_id).first()


def list_calls(
    page: int = 1,
    per_page: int = 20,
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> tuple[list, int]:
    from .models import Call
    with get_db() as session:
        q = session.query(Call)
        if agent_id:
            q = q.filter(Call.agent_id == agent_id)
        if status:
            q = q.filter(Call.status == status)
        if from_date:
            q = q.filter(Call.created_at >= from_date)
        if to_date:
            q = q.filter(Call.created_at <= to_date)

        total = q.count()
        offset = (page - 1) * per_page
        rows = q.order_by(Call.created_at.desc()).offset(offset).limit(per_page).all()
        return rows, total


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------

def insert_transcript(
    session_id: str,
    text: str,
    is_final: bool,
    speaker: Optional[str],
    timestamp: str,
) -> int:
    from .models import Transcript
    with get_db() as session:
        t = Transcript(
            session_id=session_id,
            text=text,
            is_final=1 if is_final else 0,
            speaker=speaker,
            timestamp=timestamp,
        )
        session.add(t)
        session.flush()
        return t.id


def get_transcripts(session_id: str) -> list:
    from .models import Transcript
    with get_db() as session:
        return (
            session.query(Transcript)
            .filter(Transcript.session_id == session_id)
            .order_by(Transcript.timestamp.asc())
            .all()
        )


def count_transcripts(session_id: str) -> int:
    from .models import Transcript
    with get_db() as session:
        return session.query(Transcript).filter(Transcript.session_id == session_id).count()


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def insert_summary(
    session_id: str,
    text: str,
    model_used: str,
    generated_at: str,
) -> int:
    from .models import Summary
    with get_db() as session:
        existing = session.query(Summary).filter(Summary.session_id == session_id).first()
        if existing:
            existing.text = text
            existing.model_used = model_used
            existing.generated_at = generated_at
            session.flush()
            return existing.id
        else:
            s = Summary(
                session_id=session_id,
                text=text,
                model_used=model_used,
                generated_at=generated_at,
            )
            session.add(s)
            session.flush()
            return s.id


def get_summary(session_id: str):
    from .models import Summary
    with get_db() as session:
        return session.query(Summary).filter(Summary.session_id == session_id).first()


# ---------------------------------------------------------------------------
# Action Items
# ---------------------------------------------------------------------------

def insert_action_item(
    session_id: str,
    text: str,
    priority: str,
    assignee: Optional[str],
    created_at: str,
) -> int:
    from .models import ActionItem
    with get_db() as session:
        ai = ActionItem(
            session_id=session_id,
            text=text,
            priority=priority,
            assignee=assignee,
            status="open",
            created_at=created_at,
        )
        session.add(ai)
        session.flush()
        return ai.id


def get_action_items(session_id: str) -> list:
    from .models import ActionItem
    with get_db() as session:
        return (
            session.query(ActionItem)
            .filter(ActionItem.session_id == session_id)
            .order_by(ActionItem.created_at.asc())
            .all()
        )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def insert_document(
    doc_id: str,
    session_id: Optional[str],
    filename: str,
    mime_type: str,
    size_bytes: int,
    storage_path: str,
    description: Optional[str],
    uploaded_at: str,
    job_id: Optional[str] = None,
    status: str = "uploading",
) -> int:
    from .models import Document
    with get_db() as session:
        doc = Document(
            doc_id=doc_id,
            session_id=session_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
            description=description,
            uploaded_at=uploaded_at,
            job_id=job_id,
            status=status,
        )
        session.add(doc)
        session.flush()
        return doc.id


def update_document_text(doc_id: str, extracted_text: str) -> None:
    """Legacy: no-op in v2 (text lives in DocumentChunk). Kept for compat."""
    logger.debug("[%s] update_document_text called (v2: text stored in chunks)", doc_id)


def update_document_status(
    doc_id: str,
    status: str,
    total_pages: Optional[int] = None,
    total_chunks: Optional[int] = None,
    job_id: Optional[str] = None,
) -> None:
    from .models import Document
    with get_db() as session:
        updates: dict[str, Any] = {"status": status}
        if total_pages is not None:
            updates["total_pages"] = total_pages
        if total_chunks is not None:
            updates["total_chunks"] = total_chunks
        if job_id is not None:
            updates["job_id"] = job_id
        session.query(Document).filter(Document.doc_id == doc_id).update(updates)


def get_document(doc_id: str):
    from .models import Document
    with get_db() as session:
        return session.query(Document).filter(Document.doc_id == doc_id).first()


def insert_document_chunk(
    doc_id: str,
    chunk_index: int,
    page_number: int,
    text: str,
    embedding_model: str = "text-embedding-3-small",
) -> int:
    from .models import DocumentChunk
    with get_db() as session:
        chunk = DocumentChunk(
            doc_id=doc_id,
            chunk_index=chunk_index,
            page_number=page_number,
            text=text,
            embedding_model=embedding_model,
        )
        session.add(chunk)
        session.flush()
        return chunk.id


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def insert_job(
    job_id: str,
    job_type: str,
    payload_json: Optional[str] = None,
    status: str = "queued",
) -> int:
    from .models import Job
    with get_db() as session:
        job = Job(
            job_id=job_id,
            job_type=job_type,
            payload_json=payload_json,
            status=status,
        )
        session.add(job)
        session.flush()
        return job.id


def get_job(job_id: str):
    from .models import Job
    with get_db() as session:
        return session.query(Job).filter(Job.job_id == job_id).first()


def update_job(
    job_id: str,
    status: str,
    result_json: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    from .models import Job
    with get_db() as session:
        updates: dict[str, Any] = {"status": status}
        if result_json is not None:
            updates["result_json"] = result_json
        if error is not None:
            updates["error"] = error
        if status in ("finished", "failed"):
            updates["completed_at"] = datetime.utcnow()
        session.query(Job).filter(Job.job_id == job_id).update(updates)


def list_jobs(page: int = 1, per_page: int = 20) -> tuple[list, int]:
    from .models import Job
    with get_db() as session:
        q = session.query(Job).order_by(Job.created_at.desc())
        total = q.count()
        offset = (page - 1) * per_page
        rows = q.offset(offset).limit(per_page).all()
        return rows, total


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_user_by_username(username: str):
    from .models import User
    with get_db() as session:
        return session.query(User).filter(User.username == username).first()


def get_user_by_api_key(api_key: str):
    from .models import User
    with get_db() as session:
        return session.query(User).filter(User.api_key == api_key).first()


def get_user_by_id(user_id: int):
    from .models import User
    with get_db() as session:
        return session.query(User).filter(User.id == user_id).first()


def create_user(
    username: str,
    password_hash: str,
    role: str = "agent",
    api_key: Optional[str] = None,
) -> int:
    from .models import User
    with get_db() as session:
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            api_key=api_key,
        )
        session.add(user)
        session.flush()
        return user.id


# ---------------------------------------------------------------------------
# Analytics helpers (preserved from v1, adapted for SQLAlchemy)
# ---------------------------------------------------------------------------

def analytics_summary(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    from .models import Call, ActionItem
    with get_db() as session:
        q = session.query(Call)
        if from_date:
            q = q.filter(Call.created_at >= from_date)
        if to_date:
            q = q.filter(Call.created_at <= to_date)

        calls = q.all()
        total = len(calls)
        active = sum(1 for c in calls if c.status == "active")
        ended = sum(1 for c in calls if c.status == "ended")
        durations = [c.duration_seconds for c in calls if c.duration_seconds is not None]
        total_dur = sum(durations) if durations else 0
        avg_dur = round(total_dur / len(durations)) if durations else 0

        lang_map: dict[str, int] = {}
        for c in calls:
            lang_map[c.language] = lang_map.get(c.language, 0) + 1

        aq = session.query(ActionItem)
        action_items = aq.all()
        ai_total = len(action_items)
        ai_high = sum(1 for a in action_items if a.priority == "high")
        ai_medium = sum(1 for a in action_items if a.priority == "medium")
        ai_low = sum(1 for a in action_items if a.priority == "low")

    return {
        "total_calls": total,
        "total_duration_seconds": total_dur,
        "average_duration_seconds": avg_dur,
        "calls_by_status": {"active": active, "ended": ended},
        "calls_by_language": lang_map,
        "action_items_generated": ai_total,
        "action_items_by_priority": {
            "high": ai_high,
            "medium": ai_medium,
            "low": ai_low,
        },
    }


def analytics_agent(agent_id: str) -> Optional[dict]:
    from .models import Call, ActionItem
    with get_db() as session:
        calls = session.query(Call).filter(Call.agent_id == agent_id).all()
        if not calls:
            return None

        total = len(calls)
        durations = [c.duration_seconds for c in calls if c.duration_seconds is not None]
        total_dur = sum(durations) if durations else 0
        avg_dur = round(total_dur / len(durations)) if durations else 0
        last_call = max((c.ended_at for c in calls if c.ended_at), default=None)

        session_ids = [c.session_id for c in calls]
        action_count = (
            session.query(ActionItem)
            .filter(ActionItem.session_id.in_(session_ids))
            .count()
        )

    return {
        "agent_id": agent_id,
        "total_calls": total,
        "total_duration_seconds": total_dur,
        "average_duration_seconds": avg_dur,
        "action_items_generated": action_count,
        "last_call_at": last_call,
    }
