"""
Pravaah OS — Backend API Tests
pytest tests for all REST endpoints: health, calls, analytics, 404 handling.
Run with: pytest tests/test_api.py -v
"""

import json
import os
import sys
import tempfile

import pytest

# Ensure project root is on the path so backend package is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Create a Flask test app with an isolated temporary SQLite database."""
    # Use a temporary DB so tests don't pollute any real database
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    # Set env vars before importing the app
    os.environ.setdefault("DEEPGRAM_API_KEY", "test_deepgram_key")
    os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
    os.environ.setdefault("FLASK_SECRET_KEY", "test_secret_key_for_pytest")
    os.environ["DATABASE_PATH"] = db_path
    os.environ["FLASK_ENV"] = "testing"

    from backend.app import create_app
    flask_app = create_app()
    flask_app.config["TESTING"] = True

    yield flask_app

    # Cleanup temp DB after test session
    os.unlink(db_path)


@pytest.fixture(scope="session")
def client(app):
    """Return a Flask test client."""
    return app.test_client()


@pytest.fixture(scope="session")
def session_id(client):
    """Create a call and return its session_id for reuse across tests."""
    resp = client.post(
        "/api/calls/start",
        data=json.dumps({"agent_id": "test_agent", "language": "hi-en"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    return data["session_id"]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self, client):
        resp = client.get("/health")
        body = resp.get_json()
        assert body["status"] == "ok"
        assert "version" in body


# ---------------------------------------------------------------------------
# POST /api/calls/start
# ---------------------------------------------------------------------------

class TestStartCall:
    def test_start_call_returns_201(self, client):
        resp = client.post(
            "/api/calls/start",
            data=json.dumps({"agent_id": "agent_001", "language": "hi-en"}),
            content_type="application/json",
        )
        assert resp.status_code == 201

    def test_start_call_response_shape(self, client):
        resp = client.post(
            "/api/calls/start",
            data=json.dumps({"agent_id": "agent_001"}),
            content_type="application/json",
        )
        body = resp.get_json()
        assert "session_id" in body
        assert body["status"] == "active"
        assert "created_at" in body
        assert len(body["session_id"]) == 36  # UUID4 length

    def test_start_call_no_body(self, client):
        """Should succeed even with empty body — defaults kick in."""
        resp = client.post("/api/calls/start", content_type="application/json")
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["status"] == "active"

    def test_start_call_with_metadata(self, client):
        resp = client.post(
            "/api/calls/start",
            data=json.dumps({
                "agent_id": "agent_meta",
                "language": "en",
                "metadata": {"queue": "billing", "priority": 2},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# POST /api/calls/<session_id>/end
# ---------------------------------------------------------------------------

class TestEndCall:
    def test_end_call_returns_200(self, client, session_id):
        resp = client.post(
            f"/api/calls/{session_id}/end",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_end_call_response_shape(self, client, session_id):
        resp = client.post(
            f"/api/calls/{session_id}/end",
            data=json.dumps({}),
            content_type="application/json",
        )
        body = resp.get_json()
        assert body["session_id"] == session_id
        assert body["status"] == "ended"
        assert "duration_seconds" in body
        assert "ended_at" in body

    def test_end_call_twice_is_idempotent(self, client, session_id):
        """Ending an already-ended call should not raise an error."""
        resp = client.post(
            f"/api/calls/{session_id}/end",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_end_call_unknown_session_returns_404(self, client):
        resp = client.post(
            "/api/calls/00000000-0000-0000-0000-000000000000/end",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/calls
# ---------------------------------------------------------------------------

class TestListCalls:
    def test_list_calls_returns_200(self, client):
        resp = client.get("/api/calls/")
        assert resp.status_code == 200

    def test_list_calls_response_shape(self, client):
        resp = client.get("/api/calls/")
        body = resp.get_json()
        assert "calls" in body
        assert "total" in body
        assert "page" in body
        assert "per_page" in body
        assert isinstance(body["calls"], list)

    def test_list_calls_pagination_defaults(self, client):
        resp = client.get("/api/calls/")
        body = resp.get_json()
        assert body["page"] == 1
        assert body["per_page"] == 20

    def test_list_calls_pagination_params(self, client):
        resp = client.get("/api/calls/?page=1&per_page=5")
        body = resp.get_json()
        assert body["per_page"] == 5
        assert len(body["calls"]) <= 5

    def test_list_calls_filter_by_status(self, client):
        resp = client.get("/api/calls/?status=ended")
        assert resp.status_code == 200
        body = resp.get_json()
        for call in body["calls"]:
            assert call["status"] == "ended"

    def test_list_calls_filter_invalid_status(self, client):
        resp = client.get("/api/calls/?status=invalid_status")
        assert resp.status_code == 400

    def test_list_calls_filter_by_agent(self, client):
        resp = client.get("/api/calls/?agent_id=test_agent")
        assert resp.status_code == 200
        body = resp.get_json()
        for call in body["calls"]:
            assert call["agent_id"] == "test_agent"


# ---------------------------------------------------------------------------
# GET /api/calls/<session_id>  (detail)
# ---------------------------------------------------------------------------

class TestGetCallDetail:
    def test_get_call_detail_returns_200(self, client, session_id):
        resp = client.get(f"/api/calls/{session_id}")
        assert resp.status_code == 200

    def test_get_call_detail_shape(self, client, session_id):
        resp = client.get(f"/api/calls/{session_id}")
        body = resp.get_json()
        assert body["session_id"] == session_id
        assert "status" in body
        assert "transcripts" in body
        assert isinstance(body["transcripts"], list)
        assert "action_items" in body
        assert isinstance(body["action_items"], list)

    def test_get_call_detail_unknown_returns_404(self, client):
        resp = client.get("/api/calls/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/analytics/summary
# ---------------------------------------------------------------------------

class TestAnalyticsSummary:
    def test_analytics_summary_returns_200(self, client):
        resp = client.get("/api/analytics/summary")
        assert resp.status_code == 200

    def test_analytics_summary_shape(self, client):
        resp = client.get("/api/analytics/summary")
        body = resp.get_json()
        required_keys = [
            "total_calls",
            "total_duration_seconds",
            "average_duration_seconds",
            "calls_by_status",
            "calls_by_language",
            "action_items_generated",
        ]
        for key in required_keys:
            assert key in body, f"Missing key: {key}"

    def test_analytics_summary_total_calls_is_int(self, client):
        resp = client.get("/api/analytics/summary")
        body = resp.get_json()
        assert isinstance(body["total_calls"], int)
        assert body["total_calls"] >= 0

    def test_analytics_summary_with_date_range(self, client):
        resp = client.get("/api/analytics/summary?from=2020-01-01&to=2030-12-31")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 404 handling
# ---------------------------------------------------------------------------

class TestNotFound:
    def test_unknown_route_returns_404(self, client):
        resp = client.get("/api/does_not_exist")
        assert resp.status_code == 404

    def test_unknown_call_endpoint_returns_404(self, client):
        resp = client.get("/api/calls/nonexistent-session-id-xyz")
        assert resp.status_code == 404

    def test_unknown_analytics_agent_returns_404(self, client):
        resp = client.get("/api/analytics/agent/no_such_agent_xyz_123")
        assert resp.status_code == 404
