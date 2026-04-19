"""
Pravaah OS — OpenRouter LLM Client

Provides synchronous wrappers for OpenRouter's OpenAI-compatible chat
completions API. Routes tasks to the correct model (heavy/light) and
implements retry + exponential backoff on all network calls.
"""

import json
import logging
import os
import time
from typing import Any, Optional

import requests

from .prompt_templates import (
    ACTION_ITEMS_PROMPT,
    INTENT_PROMPT,
    LANGUAGE_PROMPT,
    SUMMARIZE_PROMPT,
    SYSTEM_ACTION_ITEMS,
    SYSTEM_LANGUAGE,
    SYSTEM_RAG,
    SYSTEM_SENTIMENT,
    SYSTEM_SUMMARIZE,
)

logger = logging.getLogger(__name__)

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_COMPLETIONS_PATH = "/chat/completions"
_REQUEST_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1.0

# Model routing (see ARCHITECTURE.md §11)
HEAVY_TASKS = {"summarize", "extract_action_items", "classify_sentiment"}
LIGHT_TASKS = {"detect_language", "generate_ack", "tag_entities", "analytics_label"}


def route_model(task: str) -> str:
    """
    Return the appropriate OpenRouter model ID for the given task.

    Parameters
    ----------
    task : str
        Task identifier, e.g. ``'summarize'`` or ``'detect_language'``.

    Returns
    -------
    str
        Full model ID string for the OpenRouter API.
    """
    if task in HEAVY_TASKS:
        return os.getenv("OPENROUTER_HEAVY_MODEL", "anthropic/claude-sonnet-4-5")
    return os.getenv("OPENROUTER_LIGHT_MODEL", "meta-llama/llama-3.1-8b-instruct:free")


class OpenRouterLLMClient:
    """
    Synchronous OpenRouter LLM client with task-aware model routing.

    All public methods implement retry with exponential backoff and honour
    ``timeout=30s`` on every network call.

    Parameters
    ----------
    api_key : str, optional
        OpenRouter API key.  Falls back to the ``OPENROUTER_API_KEY`` env var.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialise the LLM client with the OpenRouter API key."""
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
        self._url = f"{_OPENROUTER_BASE}{_COMPLETIONS_PATH}"

    # ------------------------------------------------------------------
    # Base call method
    # ------------------------------------------------------------------

    def _call(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a chat completion request to OpenRouter and return the response text.

        Retries up to ``_MAX_RETRIES`` times with exponential backoff.

        Parameters
        ----------
        messages : list[dict]
            OpenAI-format messages list with ``role`` and ``content`` keys.
        model : str
            Full model ID for OpenRouter, e.g. ``'anthropic/claude-sonnet-4-5'``.
        temperature : float
            Sampling temperature (default 0.3 for deterministic outputs).
        max_tokens : int
            Maximum tokens in the response (default 1024).

        Returns
        -------
        str
            The assistant's reply text.

        Raises
        ------
        RuntimeError
            If all retries are exhausted or the response cannot be parsed.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.debug("OpenRouter request attempt %d/%d model=%s", attempt, _MAX_RETRIES, model)
                response = self._session.post(
                    self._url,
                    json=payload,
                    timeout=_REQUEST_TIMEOUT_SECONDS,
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.debug("OpenRouter response: %r", content[:200])
                    return content

                logger.warning(
                    "OpenRouter attempt %d returned HTTP %d: %s",
                    attempt,
                    response.status_code,
                    response.text[:300],
                )
                last_exc = RuntimeError(
                    f"OpenRouter HTTP {response.status_code}: {response.text[:300]}"
                )

                # 429 rate-limit: use longer backoff
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    logger.info("Rate limited; waiting %ds before retry", retry_after)
                    time.sleep(min(retry_after, 60))
                    continue

            except requests.exceptions.Timeout as exc:
                logger.warning("OpenRouter attempt %d timed out: %s", attempt, exc)
                last_exc = exc
            except requests.exceptions.RequestException as exc:
                logger.warning("OpenRouter attempt %d request error: %s", attempt, exc)
                last_exc = exc
            except (KeyError, IndexError, json.JSONDecodeError) as exc:
                logger.error("Failed to parse OpenRouter response: %s", exc)
                last_exc = exc

            if attempt < _MAX_RETRIES:
                backoff = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.info("Retrying OpenRouter call in %.1fs…", backoff)
                time.sleep(backoff)

        logger.error("All %d OpenRouter attempts failed", _MAX_RETRIES)
        raise RuntimeError(f"OpenRouter call failed after {_MAX_RETRIES} attempts") from last_exc

    # ------------------------------------------------------------------
    # High-level task methods
    # ------------------------------------------------------------------

    def summarize_transcript(self, transcript: str) -> str:
        """
        Generate a structured call summary from a transcript using the heavy model.

        The summary covers: Issue, Key Facts, Promises Made, and Next Action.

        Parameters
        ----------
        transcript : str
            Full transcript text from the call.

        Returns
        -------
        str
            Structured summary in plain English.
        """
        model = route_model("summarize")
        messages = [
            {"role": "system", "content": SYSTEM_SUMMARIZE},
            {"role": "user", "content": SUMMARIZE_PROMPT.format(transcript=transcript)},
        ]
        return self._call(messages, model, temperature=0.3, max_tokens=512)

    def extract_action_items(self, transcript: str) -> list[dict]:
        """
        Extract structured action items from a transcript using the heavy model.

        Returns a list of dicts with keys: ``action``, ``owner``,
        ``deadline_mentioned``, ``priority``.

        Parameters
        ----------
        transcript : str
            Full transcript text from the call.

        Returns
        -------
        list[dict]
            Parsed JSON array of action items.  Returns an empty list if the
            LLM returns unparseable output.
        """
        model = route_model("extract_action_items")
        messages = [
            {"role": "system", "content": SYSTEM_ACTION_ITEMS},
            {"role": "user", "content": ACTION_ITEMS_PROMPT.format(transcript=transcript)},
        ]
        raw = self._call(messages, model, temperature=0.1, max_tokens=1024)

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            items = json.loads(cleaned)
            if not isinstance(items, list):
                raise ValueError("Expected a JSON array")
            return items
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse action items JSON: %s\nRaw: %r", exc, raw[:500])
            return []

    def classify_intent(self, text: str) -> dict:
        """
        Classify the intent (and confidence) of a short text using the light model.

        Parameters
        ----------
        text : str
            Text snippet to classify (typically a single turn or short segment).

        Returns
        -------
        dict
            Parsed JSON with ``intent`` and ``confidence`` keys.  Falls back to
            ``{"intent": "other", "confidence": 0.0}`` on parse error.
        """
        model = route_model("classify_sentiment")  # heavy model (sonnet)
        messages = [
            {"role": "system", "content": SYSTEM_SENTIMENT},
            {"role": "user", "content": INTENT_PROMPT.format(text=text)},
        ]
        raw = self._call(messages, model, temperature=0.1, max_tokens=128)

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            result = json.loads(cleaned)
            if not isinstance(result, dict):
                raise ValueError("Expected a JSON object")
            return result
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse intent JSON: %s\nRaw: %r", exc, raw[:300])
            return {"intent": "other", "confidence": 0.0}

    def detect_language(self, text: str) -> str:
        """
        Detect the primary language of a text snippet using the light model.

        Parameters
        ----------
        text : str
            Text to classify (transcript segment or full transcript).

        Returns
        -------
        str
            One of ``"hi"``, ``"en"``, or ``"hi-en"``.
            Defaults to ``"hi-en"`` on error.
        """
        model = route_model("detect_language")
        messages = [
            {"role": "system", "content": SYSTEM_LANGUAGE},
            {"role": "user", "content": LANGUAGE_PROMPT.format(text=text)},
        ]
        raw = self._call(messages, model, temperature=0.0, max_tokens=10)
        result = raw.strip().strip('"').lower()
        if result not in {"hi", "en", "hi-en"}:
            logger.warning("Unexpected language label %r; defaulting to 'hi-en'", result)
            return "hi-en"
        return result

    def answer_from_context(self, question: str, context: str) -> str:
        """
        Answer *question* using only the provided document *context* (RAG).

        Uses the heavy model (claude-sonnet-4-5) and the ``SYSTEM_RAG`` system
        prompt which instructs the model to cite page numbers and refuse to
        answer if the information is not present in the context.

        Parameters
        ----------
        question : str
            Natural-language question from the user.
        context : str
            Grounded document context assembled by the RAG engine, consisting
            of labelled page excerpts separated by ``---``.

        Returns
        -------
        str
            Grounded answer text from the LLM.
        """
        model = route_model("summarize")  # heavy model
        messages = [
            {"role": "system", "content": SYSTEM_RAG},
            {
                "role": "user",
                "content": (
                    f"Document context:\n\n{context}\n\n"
                    f"Question: {question}"
                ),
            },
        ]
        return self._call(messages, model, temperature=0.2, max_tokens=1024)

    def close(self) -> None:
        """Close the underlying requests Session."""
        self._session.close()
        logger.debug("OpenRouterLLMClient session closed")
