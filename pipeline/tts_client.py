"""
Pravaah OS — TTS Client alias module.

Re-exports ``DeepgramTTSClient`` from ``deepgram_tts`` for backward
compatibility with any code that imports from ``pipeline.tts_client``.
"""

from .deepgram_tts import DeepgramTTSClient  # noqa: F401

__all__ = ["DeepgramTTSClient"]
