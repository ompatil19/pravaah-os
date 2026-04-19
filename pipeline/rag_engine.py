"""
Pravaah OS — RAG Engine

Retrieval-Augmented Generation over ingested documents stored in ChromaDB.
Results are cached in Redis (TTL 10 min) to avoid redundant embedding calls
and LLM invocations for identical queries.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600  # 10 minutes
_DEFAULT_TOP_K = 5


class RAGEngine:
    """
    Retrieval-Augmented Generation engine for Pravaah OS documents.

    Embeds user questions, retrieves the most relevant chunks from ChromaDB,
    builds a grounded context, and calls the OpenRouter heavy model to
    produce a cited answer.

    Parameters
    ----------
    chroma_path : str
        Filesystem path where ChromaDB stores its data.
    openrouter_api_key : str
        OpenRouter API key for embedding and LLM calls.
    redis_client : redis.Redis
        Pre-initialised Redis client for result caching.
    """

    def __init__(
        self,
        chroma_path: str,
        openrouter_api_key: str,
        redis_client: Any,
    ) -> None:
        """Initialise the RAG engine, connecting to ChromaDB and loading clients."""
        import chromadb

        from .embeddings import EmbeddingClient
        from .openrouter_client import OpenRouterLLMClient

        self._chroma = chromadb.PersistentClient(path=chroma_path)
        self._embed_client = EmbeddingClient(api_key=openrouter_api_key)
        self._llm_client = OpenRouterLLMClient(api_key=openrouter_api_key)
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(question: str, doc_ids: Optional[list[str]]) -> str:
        """
        Build a short, deterministic Redis cache key for a (question, doc_ids) pair.

        Parameters
        ----------
        question : str
            User question text.
        doc_ids : list[str] or None
            Optional list of document IDs to restrict the search.

        Returns
        -------
        str
            Redis key of the form ``rag_cache:<16-char hex>``.
        """
        raw = question + str(sorted(doc_ids) if doc_ids else "")
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"rag_cache:{digest}"

    def _get_cache(self, key: str) -> Optional[dict]:
        """
        Retrieve a cached RAG result from Redis.

        Parameters
        ----------
        key : str
            Redis cache key.

        Returns
        -------
        dict or None
            Cached result dict, or ``None`` if not found / expired.
        """
        try:
            value = self._redis.get(key)
            if value is not None:
                return json.loads(value)
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG cache get failed: %s", exc)
        return None

    def _set_cache(self, key: str, value: dict) -> None:
        """
        Store a RAG result in Redis with a 10-minute TTL.

        Parameters
        ----------
        key : str
            Redis cache key.
        value : dict
            Result dict to serialise and store.
        """
        try:
            self._redis.setex(key, _CACHE_TTL_SECONDS, json.dumps(value))
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG cache set failed: %s", exc)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        doc_ids: Optional[list[str]] = None,
        top_k: int = _DEFAULT_TOP_K,
    ) -> dict:
        """
        Answer *question* using document chunks stored in ChromaDB.

        Workflow:
        1. Check Redis cache; return cached result if present.
        2. Embed *question* via ``EmbeddingClient``.
        3. Query ChromaDB — either across specified ``doc_ids`` or all
           collections whose names start with ``doc_``.
        4. Build a grounded context string from the top-*k* chunks.
        5. Call the OpenRouter heavy model with the RAG system prompt.
        6. Cache and return the structured result.

        Parameters
        ----------
        question : str
            Natural-language question to answer.
        doc_ids : list[str] or None
            If supplied, restrict retrieval to these document IDs only.
        top_k : int
            Number of chunks to retrieve (default 5).

        Returns
        -------
        dict
            Keys:
            - ``answer`` (str): LLM-generated answer grounded in the context.
            - ``sources`` (list[dict]): Each source has ``doc_id``,
              ``page_number``, and ``chunk_text_preview`` (first 200 chars).
            - ``cached`` (bool): ``True`` if the result came from cache.
        """
        cache_key = self._cache_key(question, doc_ids)

        # 1. Cache check
        cached = self._get_cache(cache_key)
        if cached is not None:
            cached["cached"] = True
            logger.debug("RAG cache hit for key %s", cache_key)
            return cached

        # 2. Embed question
        question_vector = self._embed_client.embed_single(question)

        # 3. Retrieve chunks
        results = self._retrieve(question_vector, doc_ids=doc_ids, top_k=top_k)

        if not results:
            answer_dict: dict = {
                "answer": "Not found in the provided documents.",
                "sources": [],
                "cached": False,
            }
            self._set_cache(cache_key, {k: v for k, v in answer_dict.items() if k != "cached"})
            return answer_dict

        # 4. Build context
        context_parts: list[str] = []
        sources: list[dict] = []
        for text, metadata in results:
            page = metadata.get("page_number", "?")
            context_parts.append(f"[Page {page}] {text}")
            sources.append(
                {
                    "doc_id": metadata.get("doc_id", ""),
                    "page_number": page,
                    "chunk_text_preview": text[:200],
                }
            )

        context = "\n\n---\n\n".join(context_parts)

        # 5. Call LLM
        answer = self._llm_client.answer_from_context(question, context)

        # 6. Build, cache, and return result
        result: dict = {"answer": answer, "sources": sources, "cached": False}
        self._set_cache(cache_key, {"answer": answer, "sources": sources})
        return result

    # ------------------------------------------------------------------
    # Internal retrieval
    # ------------------------------------------------------------------

    def _retrieve(
        self,
        query_vector: list[float],
        doc_ids: Optional[list[str]],
        top_k: int,
    ) -> list[tuple[str, dict]]:
        """
        Query ChromaDB for the top-*k* chunks closest to *query_vector*.

        Parameters
        ----------
        query_vector : list[float]
            Embedding vector for the user question.
        doc_ids : list[str] or None
            Restrict to these document collections; if ``None`` search all.
        top_k : int
            Number of results to return.

        Returns
        -------
        list[tuple[str, dict]]
            List of ``(chunk_text, metadata_dict)`` tuples ordered by
            similarity (most similar first).
        """
        # Determine which collections to query
        if doc_ids:
            collection_names = [f"doc_{did}" for did in doc_ids]
        else:
            all_collections = self._chroma.list_collections()
            collection_names = [
                c.name for c in all_collections if c.name.startswith("doc_")
            ]

        if not collection_names:
            logger.warning("No ChromaDB collections found to query")
            return []

        # Query each collection and aggregate
        combined: list[tuple[float, str, dict]] = []  # (distance, text, metadata)

        for name in collection_names:
            try:
                collection = self._chroma.get_collection(name)
                count = collection.count()
                if count == 0:
                    logger.debug("Collection %s is empty — skipping", name)
                    continue
                res = collection.query(
                    query_embeddings=[query_vector],
                    n_results=min(top_k, count),
                    include=["documents", "metadatas", "distances"],
                )
                docs = res.get("documents", [[]])[0]
                metas = res.get("metadatas", [[]])[0]
                distances = res.get("distances", [[]])[0]
                for dist, text, meta in zip(distances, docs, metas):
                    combined.append((dist, text, meta))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error querying collection %s: %s", name, exc)

        # Sort by distance (ascending = most similar) and take top_k
        combined.sort(key=lambda x: x[0])
        return [(text, meta) for _, text, meta in combined[:top_k]]

    def close(self) -> None:
        """Close underlying client sessions."""
        self._embed_client.close()
        self._llm_client.close()
        logger.debug("RAGEngine closed")
