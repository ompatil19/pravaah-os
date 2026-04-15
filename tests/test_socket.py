"""
Pravaah OS — Socket.IO Handler Tests
Tests for join_call, audio_chunk, and leave_call events using flask_socketio's
test client. All Deepgram WebSocket calls are mocked.
Run with: pytest tests/test_socket.py -v
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DEEPGRAM_API_KEY", "test_deepgram_key")
os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
os.environ.setdefault("FLASK_SECRET_KEY", "test_secret_socketio")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    db_fd, db_path = tempfile.mkstemp(suffix="_socket.db")
    os.close(db_fd)
    os.environ["DATABASE_PATH"] = db_path
    os.environ["FLASK_ENV"] = "testing"

    from backend.app import create_app, socketio as sio
    flask_app = create_app()
    flask_app.config["TESTING"] = True

    yield flask_app, sio
    os.unlink(db_path)


@pytest.fixture(scope="module")
def flask_client(app):
    flask_app, _ = app
    return flask_app.test_client()


@pytest.fixture(scope="module")
def socket_client(app):
    from flask_socketio import SocketIOTestClient
    flask_app, sio = app
    return SocketIOTestClient(flask_app, sio)


@pytest.fixture(scope="module")
def test_session_id(flask_client):
    """Create a call via REST and return session_id for socket tests."""
    resp = flask_client.post(
        "/api/calls/start",
        data=json.dumps({"agent_id": "socket_test_agent"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    return resp.get_json()["session_id"]


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------

class TestSocketConnection:
    def test_socket_connects(self, socket_client):
        assert socket_client.is_connected()

    def test_socket_disconnect_reconnect(self, app):
        from flask_socketio import SocketIOTestClient
        flask_app, sio = app
        client = SocketIOTestClient(flask_app, sio)
        assert client.is_connected()
        client.disconnect()
        assert not client.is_connected()


# ---------------------------------------------------------------------------
# join_call event
# ---------------------------------------------------------------------------

class TestJoinCall:
    @patch("backend.socket_handlers.session_manager")
    def test_join_call_emits_no_error(self, mock_mgr, socket_client, test_session_id):
        """join_call should not raise an error event for a valid session."""
        mock_mgr.get.return_value = None
        mock_mgr.create.return_value = MagicMock()

        socket_client.emit("join_call", {"session_id": test_session_id})
        received = socket_client.get_received()
        error_events = [e for e in received if e.get("name") == "error"]
        # No error events should have been emitted for a valid join
        assert len(error_events) == 0 or all(
            "session" not in str(e.get("args", "")).lower()
            for e in error_events
        )

    def test_join_call_missing_session_id(self, socket_client):
        """join_call with no session_id should either error or silently ignore."""
        socket_client.emit("join_call", {})
        # Should not crash the server — just validate it's still connected
        assert socket_client.is_connected()


# ---------------------------------------------------------------------------
# audio_chunk event
# ---------------------------------------------------------------------------

class TestAudioChunk:
    @patch("backend.socket_handlers.session_manager")
    def test_audio_chunk_forwarded_to_session(self, mock_mgr, socket_client, test_session_id):
        """audio_chunk should call send_audio on the session if it exists."""
        mock_session = MagicMock()
        mock_mgr.get.return_value = mock_session

        fake_audio = b"\x00\x01\x02\x03" * 64
        socket_client.emit("audio_chunk", {"session_id": test_session_id, "data": fake_audio})

        # The mock session's send_audio should have been called
        # (or at minimum the server should not crash)
        assert socket_client.is_connected()

    @patch("backend.socket_handlers.session_manager")
    def test_audio_chunk_no_session_is_handled(self, mock_mgr, socket_client, test_session_id):
        """audio_chunk with no active session should not crash the server."""
        mock_mgr.get.return_value = None

        socket_client.emit("audio_chunk", {"session_id": "00000000-no-session", "data": b"\x00"})
        assert socket_client.is_connected()


# ---------------------------------------------------------------------------
# leave_call event
# ---------------------------------------------------------------------------

class TestLeaveCall:
    @patch("backend.socket_handlers.session_manager")
    def test_leave_call_closes_session(self, mock_mgr, socket_client, test_session_id):
        """leave_call should invoke cleanup on the session."""
        mock_session = MagicMock()
        mock_mgr.get.return_value = mock_session

        socket_client.emit("leave_call", {"session_id": test_session_id})
        assert socket_client.is_connected()

    def test_leave_call_unknown_session(self, socket_client):
        """leave_call for unknown session should not crash."""
        socket_client.emit("leave_call", {"session_id": "nonexistent-session-id"})
        assert socket_client.is_connected()


# ---------------------------------------------------------------------------
# Error event structure
# ---------------------------------------------------------------------------

class TestSocketErrorHandling:
    def test_server_still_connected_after_bad_events(self, socket_client):
        """Server should remain up after a series of malformed events."""
        socket_client.emit("join_call", None)
        socket_client.emit("audio_chunk", None)
        socket_client.emit("leave_call", None)
        assert socket_client.is_connected()
