"""
Pravaah OS — Embedding Client

Wraps the OpenRouter embeddings API (openai/text-embedding-3-small) for use
by the document ingestion pipeline and RAG engine.
"""

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
_EMBEDDING_MODEL = "openai/text-embedding-3-small"
_BATCH_SIZE = 100
_REQUEST_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1.0


class EmbeddingClient:
    """
    Client for generating text embeddings via the OpenRouter embeddings API.

    Uses ``openai/text-embedding-3-small`` which returns 1536-dimensional
    float vectors.  All network calls respect ``timeout=30s`` and retry up
    to three times with exponential backoff.

    Parameters
    ----------
    api_key : str, optional
        OpenRouter API key.  Falls back to the ``OPENROUTER_API_KEY`` env var.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialise the embedding client with the OpenRouter API key."""
        self._api_key: str = api_key or os.environ["OPENROUTER_API_KEY"]
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "Pravaah OS",
                "Content-Type": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a single batch of up to ``_BATCH_SIZE`` texts.

        Parameters
        ----------
        texts : list[str]
            Texts to embed.  Must contain at most ``_BATCH_SIZE`` items.

        Returns
        -------
        list[list[float]]
            List of 1536-dimensional embedding vectors, one per input text,
            in the same order as *texts*.

        Raises
        ------
        RuntimeError
            If all retry attempts fail.
        """
        payload = {"model": _EMBEDDING_MODEL, "input": texts}
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.debug(
                    "Embedding request attempt %d/%d — %d texts",
                    attempt,
                    _MAX_RETRIES,
                    len(texts),
                )
                response = self._session.post(
                    _EMBEDDING_URL,
                    json=payload,
                    timeout=_REQUEST_TIMEOUT_SECONDS,
                )

                if response.status_code == 200:
                    data = response.json()
                    # OpenAI-compatible response: data.data[i].embedding
                    embeddings = [item["embedding"] for item in data["data"]]
                    logger.debug("Received %d embeddings", len(embeddings))
                    return embeddings

                logger.warning(
                    "Embedding attempt %d returned HTTP %d: %s",
                    attempt,
                    response.status_code,
                    response.text[:300],
                )
                last_exc = RuntimeError(
                    f"Embedding API HTTP {response.status_code}: {response.text[:300]}"
                )

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    logger.info("Rate limited; waiting %ds before retry", retry_after)
                    time.sleep(min(retry_after, 60))
                    continue

            except requests.exceptions.Timeout as exc:
                logger.warning("Embedding attempt %d timed out: %s", attempt, exc)
                last_exc = exc
            except requests.exceptions.RequestException as exc:
                logger.warning("Embedding attempt %d request error: %s", attempt, exc)
                last_exc = exc
            except (KeyError, IndexError) as exc:
                logger.error("Failed to parse embedding response: %s", exc)
                last_exc = exc

            if attempt < _MAX_RETRIES:
                backoff = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.info("Retrying embedding call in %.1fs…", backoff)
                time.sleep(backoff)

        logger.error("All %d embedding attempts failed", _MAX_RETRIES)
        raise RuntimeError(
            f"Embedding call failed after {_MAX_RETRIES} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts, batching into groups of up to 100.

        Parameters
        ----------
        texts : list[str]
            Texts to embed.  May be any length; internally split into batches
            of at most ``_BATCH_SIZE`` items.

        Returns
        -------
        list[list[float]]
            List of 1536-dimensional float vectors, one per input text.
        """
        if not texts:
            return []

        results: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            results.extend(self._embed_batch(batch))
        return results

    def embed_single(self, text: str) -> list[float]:
        """
        Convenience wrapper to embed a single text string.

        Parameters
        ----------
        text : str
            Text to embed.

        Returns
        -------
        list[float]
            1536-dimensional embedding vector.
        """
        return self.embed([text])[0]

    def close(self) -> None:
        """Close the underlying requests Session."""
        self._session.close()
        logger.debug("EmbeddingClient session closed")
