"""
Pravaah OS — Pipeline Package

Exposes STT, TTS, LLM clients, session management, embeddings, and RAG.
"""

from .deepgram_stt import DeepgramSTTClient
from .deepgram_tts import DeepgramTTSClient
from .document_processor import ingest_document
from .embeddings import EmbeddingClient
from .openrouter_client import OpenRouterLLMClient
from .rag_engine import RAGEngine
from .session_manager import SessionManager

__all__ = [
    "DeepgramSTTClient",
    "DeepgramTTSClient",
    "EmbeddingClient",
    "OpenRouterLLMClient",
    "RAGEngine",
    "SessionManager",
    "ingest_document",
]
