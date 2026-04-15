"""
Pravaah OS — LLM Client alias module.

Re-exports ``OpenRouterLLMClient`` from ``openrouter_client`` for backward
compatibility with any code that imports from ``pipeline.llm_client``.
"""

from .openrouter_client import OpenRouterLLMClient  # noqa: F401

__all__ = ["OpenRouterLLMClient"]
