"""
Pravaah OS — STT Client alias module.

Re-exports ``DeepgramSTTClient`` from ``deepgram_stt`` for backward
compatibility with any code that imports from ``pipeline.stt_client``.
"""

from .deepgram_stt import DeepgramSTTClient  # noqa: F401

__all__ = ["DeepgramSTTClient"]
