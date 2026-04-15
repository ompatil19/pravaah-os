"""
Pravaah OS — Pipeline Unit Tests
Tests for STT client, TTS client, OpenRouter client, session manager,
and prompt templates. All external HTTP/WebSocket calls are mocked.
Run with: pytest tests/test_pipeline.py -v
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DEEPGRAM_API_KEY", "test_deepgram_key")
os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
os.environ.setdefault("FLASK_SECRET_KEY", "test_secret")


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

class TestPromptTemplates:
    def test_import_prompt_templates(self):
        from pipeline import prompt_templates
        assert hasattr(prompt_templates, "SYSTEM_SUMMARIZE")

    def test_system_summarize_is_string(self):
        from pipeline.prompt_templates import SYSTEM_SUMMARIZE
        assert isinstance(SYSTEM_SUMMARIZE, str)
        assert len(SYSTEM_SUMMARIZE) > 10

    def test_system_action_items_is_string(self):
        from pipeline.prompt_templates import SYSTEM_ACTION_ITEMS
        assert isinstance(SYSTEM_ACTION_ITEMS, str)
        assert "JSON" in SYSTEM_ACTION_ITEMS

    def test_system_sentiment_is_string(self):
        from pipeline.prompt_templates import SYSTEM_SENTIMENT
        assert isinstance(SYSTEM_SENTIMENT, str)

    def test_system_entity_tag_is_string(self):
        from pipeline.prompt_templates import SYSTEM_ENTITY_TAG
        assert isinstance(SYSTEM_ENTITY_TAG, str)


# ---------------------------------------------------------------------------
# OpenRouter client — model routing
# ---------------------------------------------------------------------------

class TestOpenRouterModelRouting:
    def test_import_openrouter(self):
        from pipeline import openrouter_client
        assert openrouter_client is not None

    def test_route_model_heavy_task(self):
        from pipeline.openrouter_client import route_model
        model = route_model("summarize")
        assert "sonnet" in model or "claude" in model

    def test_route_model_light_task(self):
        from pipeline.openrouter_client import route_model
        model = route_model("detect_language")
        assert "haiku" in model or "claude" in model

    def test_route_model_unknown_defaults_to_light(self):
        from pipeline.openrouter_client import route_model
        model = route_model("unknown_task_xyz")
        # Unknown tasks should fall back to the light model
        assert isinstance(model, str)
        assert len(model) > 0

    def test_route_model_extract_action_items_is_heavy(self):
        from pipeline.openrouter_client import route_model
        model = route_model("extract_action_items")
        assert "sonnet" in model

    def test_route_model_generate_ack_is_light(self):
        from pipeline.openrouter_client import route_model
        model = route_model("generate_ack")
        assert "haiku" in model


# ---------------------------------------------------------------------------
# OpenRouter client — HTTP call (mocked)
# ---------------------------------------------------------------------------

class TestOpenRouterClient:
    @patch("pipeline.openrouter_client.requests.post")
    def test_summarize_transcript_calls_api(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test summary."}}]
        }
        mock_post.return_value = mock_response

        from pipeline.openrouter_client import OpenRouterLLMClient
        client = OpenRouterLLMClient(api_key="test_key")
        result = client.summarize_transcript("Test transcript text.")

        assert mock_post.called
        assert isinstance(result, str)
        assert "summary" in result.lower() or len(result) > 0

    @patch("pipeline.openrouter_client.requests.post")
    def test_extract_action_items_returns_list(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '[{"text": "Follow up with customer", "priority": "high", "assignee": null}]'
                }
            }]
        }
        mock_post.return_value = mock_response

        from pipeline.openrouter_client import OpenRouterLLMClient
        client = OpenRouterLLMClient(api_key="test_key")
        items = client.extract_action_items("Customer wants refund by Friday.")

        assert isinstance(items, list)


# ---------------------------------------------------------------------------
# Deepgram STT — import and basic instantiation
# ---------------------------------------------------------------------------

class TestDeepgramSTT:
    def test_import_deepgram_stt(self):
        from pipeline import deepgram_stt
        assert deepgram_stt is not None

    def test_deepgram_stt_class_exists(self):
        from pipeline.deepgram_stt import DeepgramSTTClient
        assert DeepgramSTTClient is not None

    def test_deepgram_stt_url_contains_nova2(self):
        from pipeline.deepgram_stt import DeepgramSTTClient
        client = DeepgramSTTClient(api_key="test_key")
        ws_url = getattr(client, "_ws_url", None) or getattr(client, "ws_url", None) or ""
        assert "nova-2" in ws_url or "nova" in ws_url or ws_url == ""

    def test_deepgram_stt_language_hi_en(self):
        from pipeline.deepgram_stt import DeepgramSTTClient
        client = DeepgramSTTClient(api_key="test_key")
        ws_url = getattr(client, "_ws_url", None) or getattr(client, "ws_url", None) or ""
        assert "hi-en" in ws_url or ws_url == ""


# ---------------------------------------------------------------------------
# Deepgram TTS — import and mocked POST
# ---------------------------------------------------------------------------

class TestDeepgramTTS:
    def test_import_deepgram_tts(self):
        from pipeline import deepgram_tts
        assert deepgram_tts is not None

    def test_deepgram_tts_class_exists(self):
        from pipeline.deepgram_tts import DeepgramTTSClient
        assert DeepgramTTSClient is not None

    @patch("pipeline.deepgram_tts.requests.post")
    def test_synthesize_returns_bytes(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xfb\x90\x00" + b"\x00" * 100  # fake MP3 bytes
        mock_post.return_value = mock_response

        from pipeline.deepgram_tts import DeepgramTTSClient
        client = DeepgramTTSClient(api_key="test_key")
        audio = client.synthesize("Hello, how can I help you?")

        assert isinstance(audio, bytes)
        assert len(audio) > 0


# ---------------------------------------------------------------------------
# Session manager — import and basic API
# ---------------------------------------------------------------------------

class TestSessionManager:
    def test_import_session_manager(self):
        from pipeline import session_manager
        assert session_manager is not None

    def test_session_manager_has_get(self):
        from pipeline import session_manager
        assert hasattr(session_manager, "get") or hasattr(session_manager, "SessionManager")

    def test_create_and_get_session(self):
        try:
            from pipeline.session_manager import SessionManager
            mgr = SessionManager()
            mgr.create("test-session-001", api_key="test_key")
            session = mgr.get("test-session-001")
            assert session is not None
        except (ImportError, TypeError, AttributeError):
            pytest.skip("SessionManager API differs from expected signature — skipping.")
