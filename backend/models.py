"""
Pravaah OS — SQLAlchemy ORM Models (v2)

Defines all database tables using declarative_base().
Backward-compatible: legacy dict serialisers are preserved at the bottom.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)  # bcrypt
    role = Column(String, nullable=False, default="agent")  # agent|supervisor|admin
    api_key = Column(String, unique=True, nullable=True)  # UUID4, optional
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "api_key": self.api_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, unique=True, nullable=False)  # RQ job ID
    job_type = Column(String, nullable=False)  # ingest_document|run_end_of_call_llm|...
    status = Column(String, default="queued")  # queued|started|finished|failed
    payload_json = Column(Text)
    result_json = Column(Text)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "payload_json": self.payload_json,
            "result_json": self.result_json,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, unique=True, nullable=False)
    agent_id = Column(String, nullable=False, default="unknown")
    status = Column(String, nullable=False, default="active")
    language = Column(String, nullable=False, default="hi-en")
    call_metadata = Column(Text)
    created_at = Column(String, nullable=False)
    ended_at = Column(String)
    duration_seconds = Column(Integer)

    transcripts = relationship("Transcript", back_populates="call", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="call", cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="call", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "language": self.language,
            "metadata": self.call_metadata,
            "created_at": self.created_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
        }


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("calls.session_id"), nullable=False)
    text = Column(Text, nullable=False)
    is_final = Column(Integer, nullable=False, default=1)
    speaker = Column(String)
    timestamp = Column(String, nullable=False)

    call = relationship("Call", back_populates="transcripts")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "text": self.text,
            "is_final": bool(self.is_final),
            "speaker": self.speaker,
            "timestamp": self.timestamp,
        }


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("calls.session_id"), nullable=False, unique=True)
    text = Column(Text, nullable=False)
    model_used = Column(String, nullable=False)
    generated_at = Column(String, nullable=False)

    call = relationship("Call", back_populates="summaries")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "text": self.text,
            "model_used": self.model_used,
            "generated_at": self.generated_at,
        }


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("calls.session_id"), nullable=False)
    text = Column(Text, nullable=False)
    priority = Column(String, nullable=False, default="medium")
    assignee = Column(String)
    status = Column(String, nullable=False, default="open")
    created_at = Column(String, nullable=False)

    call = relationship("Call", back_populates="action_items")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "text": self.text,
            "priority": self.priority,
            "assignee": self.assignee,
            "status": self.status,
            "created_at": self.created_at,
        }


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String, unique=True, nullable=False)
    session_id = Column(String, ForeignKey("calls.session_id"), nullable=True)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False)
    description = Column(Text)
    uploaded_at = Column(String, nullable=False)
    # v2 additions
    job_id = Column(String, ForeignKey("jobs.job_id"), nullable=True)
    total_pages = Column(Integer, nullable=True)
    total_chunks = Column(Integer, nullable=True)
    status = Column(String, default="uploading")  # uploading|processing|completed|failed

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self, include_text: bool = False) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "session_id": self.session_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "description": self.description,
            "uploaded_at": self.uploaded_at,
            "job_id": self.job_id,
            "total_pages": self.total_pages,
            "total_chunks": self.total_chunks,
            "status": self.status,
        }


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding_model = Column(String, default="text-embedding-3-small")
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "text": self.text,
            "embedding_model": self.embedding_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Legacy dict serialisers (preserved for backward compatibility with v1 routes)
# These accept either sqlite3.Row objects or ORM model instances.
# ---------------------------------------------------------------------------

def _get(obj, key: str, default=None):
    """Get attribute from either a dict-like row or an ORM instance."""
    try:
        return obj[key]
    except (TypeError, KeyError):
        return getattr(obj, key, default)


def call_to_dict(row) -> dict[str, Any]:
    return {
        "id": _get(row, "id"),
        "session_id": _get(row, "session_id"),
        "agent_id": _get(row, "agent_id"),
        "status": _get(row, "status"),
        "language": _get(row, "language"),
        "metadata": _get(row, "call_metadata"),
        "created_at": _get(row, "created_at"),
        "ended_at": _get(row, "ended_at"),
        "duration_seconds": _get(row, "duration_seconds"),
    }


def call_list_item(row, summary_preview: Optional[str] = None) -> dict[str, Any]:
    return {
        "session_id": _get(row, "session_id"),
        "agent_id": _get(row, "agent_id"),
        "status": _get(row, "status"),
        "language": _get(row, "language"),
        "created_at": _get(row, "created_at"),
        "ended_at": _get(row, "ended_at"),
        "duration_seconds": _get(row, "duration_seconds"),
        "summary_preview": summary_preview,
    }


def transcript_to_dict(row) -> dict[str, Any]:
    return {
        "id": _get(row, "id"),
        "session_id": _get(row, "session_id"),
        "text": _get(row, "text"),
        "is_final": bool(_get(row, "is_final")),
        "speaker": _get(row, "speaker"),
        "timestamp": _get(row, "timestamp"),
    }


def summary_to_dict(row) -> dict[str, Any]:
    return {
        "id": _get(row, "id"),
        "session_id": _get(row, "session_id"),
        "text": _get(row, "text"),
        "model_used": _get(row, "model_used"),
        "generated_at": _get(row, "generated_at"),
    }


def action_item_to_dict(row) -> dict[str, Any]:
    return {
        "id": _get(row, "id"),
        "session_id": _get(row, "session_id"),
        "text": _get(row, "text"),
        "priority": _get(row, "priority"),
        "assignee": _get(row, "assignee"),
        "status": _get(row, "status"),
        "created_at": _get(row, "created_at"),
    }


def document_to_dict(row, include_text: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {
        "doc_id": _get(row, "doc_id"),
        "session_id": _get(row, "session_id"),
        "filename": _get(row, "filename"),
        "mime_type": _get(row, "mime_type"),
        "size_bytes": _get(row, "size_bytes"),
        "storage_path": _get(row, "storage_path"),
        "description": _get(row, "description"),
        "uploaded_at": _get(row, "uploaded_at"),
        "job_id": _get(row, "job_id"),
        "total_pages": _get(row, "total_pages"),
        "total_chunks": _get(row, "total_chunks"),
        "status": _get(row, "status"),
    }
    return d
