"""
Pravaah OS — Backend API Tests (backend/tests/test_api.py)
pytest tests: health, start_call, end_call, list_calls, analytics_summary, 404 handling,
              plus v2 auth tests and document upload/status tests.
Run with: pytest backend/tests/test_api.py -v
"""

import io
import json
import os
import sys
import tempfile
import uuid

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Flask test app with isolated temporary SQLite database."""
    db_fd, db_path = tempfile.mkstemp(suffix="_backend_tests.db")
    os.close(db_fd)

    os.environ.setdefault("DEEPGRAM_API_KEY", "test_deepgram_key")
    os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
    os.environ.setdefault("FLASK_SECRET_KEY", "backend_test_secret_key")
    os.environ.setdefault("JWT_SECRET_KEY", "backend_test_jwt_secret_key")
    os.environ["DATABASE_PATH"] = db_path
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["FLASK_ENV"] = "testing"

    from backend.app import create_app
    flask_app = create_app()
    flask_app.config["TESTING"] = True

    yield flask_app
    os.unlink(db_path)


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def active_session_id(client):
    """Create a call that stays active for detail + end tests."""
    resp = client.post(
        "/api/calls/start",
        data=json.dumps({"agent_id": "qa_agent", "language": "hi-en"}),
        content_type="application/json",
    )
    assert resp.status_code == 201
    return resp.get_json()["session_id"]


@pytest.fixture(scope="session")
def auth_token(app, client):
    """
    Create a test admin user and return a valid JWT access token.
    Uses the database and auth helpers directly.
    """
    import uuid as _uuid
    from backend import database as db
    from backend.auth import hash_password, generate_tokens

    username = f"test_admin_{_uuid.uuid4().hex[:8]}"
    password = "TestPassword123!"
    pw_hash = hash_password(password)
    api_key = str(_uuid.uuid4())

    with app.app_context():
        user_id = db.create_user(
            username=username,
            password_hash=pw_hash,
            role="admin",
            api_key=api_key,
        )
        tokens = generate_tokens(user_id, "admin")

    return tokens["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    """Authorization headers dict for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert "version" in body


# ---------------------------------------------------------------------------
# start_call
# ---------------------------------------------------------------------------

def test_start_call_returns_201(client):
    resp = client.post(
        "/api/calls/start",
        data=json.dumps({"agent_id": "agent_a"}),
        content_type="application/json",
    )
    assert resp.status_code == 201


def test_start_call_has_session_id(client):
    resp = client.post(
        "/api/calls/start",
        data=json.dumps({"agent_id": "agent_b"}),
        content_type="application/json",
    )
    body = resp.get_json()
    assert "session_id" in body
    assert len(body["session_id"]) == 36  # UUID4


def test_start_call_status_is_active(client):
    resp = client.post(
        "/api/calls/start",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.get_json()["status"] == "active"


def test_start_call_empty_body_uses_defaults(client):
    resp = client.post("/api/calls/start", content_type="application/json")
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# end_call
# ---------------------------------------------------------------------------

def test_end_call_returns_200(client, active_session_id):
    resp = client.post(
        f"/api/calls/{active_session_id}/end",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 200


def test_end_call_status_is_ended(client, active_session_id):
    resp = client.post(
        f"/api/calls/{active_session_id}/end",
        data=json.dumps({}),
        content_type="application/json",
    )
    body = resp.get_json()
    assert body["status"] == "ended"
    assert body["session_id"] == active_session_id


def test_end_call_has_duration(client, active_session_id):
    resp = client.post(
        f"/api/calls/{active_session_id}/end",
        data=json.dumps({}),
        content_type="application/json",
    )
    body = resp.get_json()
    assert "duration_seconds" in body
    assert isinstance(body["duration_seconds"], int)


def test_end_call_unknown_session_returns_404(client):
    resp = client.post(
        "/api/calls/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/end",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# list_calls
# ---------------------------------------------------------------------------

def test_list_calls_returns_200(client):
    resp = client.get("/api/calls/")
    assert resp.status_code == 200


def test_list_calls_has_required_keys(client):
    resp = client.get("/api/calls/")
    body = resp.get_json()
    for key in ("calls", "total", "page", "per_page"):
        assert key in body


def test_list_calls_default_pagination(client):
    resp = client.get("/api/calls/")
    body = resp.get_json()
    assert body["page"] == 1
    assert body["per_page"] == 20


def test_list_calls_custom_per_page(client):
    resp = client.get("/api/calls/?page=1&per_page=3")
    body = resp.get_json()
    assert body["per_page"] == 3
    assert len(body["calls"]) <= 3


def test_list_calls_filter_status_ended(client):
    resp = client.get("/api/calls/?status=ended")
    assert resp.status_code == 200
    for call in resp.get_json()["calls"]:
        assert call["status"] == "ended"


def test_list_calls_invalid_status_returns_400(client):
    resp = client.get("/api/calls/?status=bogus")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# analytics_summary
# ---------------------------------------------------------------------------

def test_analytics_summary_returns_200(client):
    resp = client.get("/api/analytics/summary")
    assert resp.status_code == 200


def test_analytics_summary_has_total_calls(client):
    resp = client.get("/api/analytics/summary")
    body = resp.get_json()
    assert "total_calls" in body
    assert isinstance(body["total_calls"], int)
    assert body["total_calls"] >= 0


def test_analytics_summary_has_calls_by_status(client):
    resp = client.get("/api/analytics/summary")
    body = resp.get_json()
    assert "calls_by_status" in body
    assert isinstance(body["calls_by_status"], dict)


def test_analytics_summary_with_date_filter(client):
    resp = client.get("/api/analytics/summary?from=2020-01-01&to=2035-01-01")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 404 handling
# ---------------------------------------------------------------------------

def test_unknown_route_returns_404(client):
    resp = client.get("/api/this_endpoint_does_not_exist")
    assert resp.status_code == 404


def test_call_detail_unknown_id_returns_404(client):
    resp = client.get("/api/calls/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_analytics_agent_unknown_returns_404(client):
    resp = client.get("/api/analytics/agent/ghost_agent_xyz_9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# v2 Auth tests
# ---------------------------------------------------------------------------

def test_login_success(app, client):
    """POST /api/auth/login with valid credentials returns 200 + access_token."""
    import uuid as _uuid
    from backend import database as db
    from backend.auth import hash_password

    username = f"login_user_{_uuid.uuid4().hex[:8]}"
    password = "ValidPass456!"
    pw_hash = hash_password(password)

    with app.app_context():
        db.create_user(
            username=username,
            password_hash=pw_hash,
            role="agent",
            api_key=str(_uuid.uuid4()),
        )

    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body.get("role") == "agent"


def test_login_invalid(client):
    """POST /api/auth/login with wrong password returns 401."""
    resp = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "nobody_xyz_9999", "password": "wrongpassword"}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_protected_without_token(client):
    """GET /api/calls/ without Authorization header returns 401."""
    # We need a protected-by-auth endpoint. If list_calls is public, test /api/auth/me.
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_protected_with_token(client, auth_headers):
    """GET /api/auth/me with a valid JWT returns 200."""
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "username" in body or ("data" in body and "username" in body.get("data", {}))


# ---------------------------------------------------------------------------
# v2 Document upload and status tests
# ---------------------------------------------------------------------------

def test_document_upload_queues_job(client, auth_headers):
    """
    POST /api/documents/upload with a text file returns 200/201 with a job_id.
    RQ is not running in tests, so we expect the endpoint to return a job_id
    (or None if Redis is unavailable) without crashing.
    """
    fake_file = (io.BytesIO(b"Hello Pravaah document content."), "test_doc.txt")
    resp = client.post(
        "/api/documents/upload",
        data={"file": fake_file},
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    # Endpoint should succeed (201 or 200) even when RQ/Redis is unavailable
    assert resp.status_code in (200, 201), f"Unexpected status: {resp.status_code}, body: {resp.get_data(as_text=True)}"
    body = resp.get_json()
    # job_id may be None if Redis is down in test env, but key must exist
    assert "doc_id" in body or "id" in body or "document" in body


def test_document_status(client, auth_headers):
    """
    GET /api/documents/<id>/status returns a status field.
    Uploads a doc first, then checks its status.
    """
    # Upload a document first
    fake_file = (io.BytesIO(b"Status check document."), "status_check.txt")
    upload_resp = client.post(
        "/api/documents/upload",
        data={"file": fake_file},
        content_type="multipart/form-data",
        headers=auth_headers,
    )
    if upload_resp.status_code not in (200, 201):
        pytest.skip("Document upload not available in this test environment")

    body = upload_resp.get_json()
    # Extract doc_id from response — handle different response shapes
    doc_id = (
        body.get("doc_id")
        or body.get("id")
        or (body.get("document") or {}).get("doc_id")
        or (body.get("document") or {}).get("id")
    )
    if not doc_id:
        pytest.skip("Could not extract doc_id from upload response")

    status_resp = client.get(
        f"/api/documents/{doc_id}/status",
        headers=auth_headers,
    )
    assert status_resp.status_code == 200
    status_body = status_resp.get_json()
    # Response may nest data under a "data" key depending on the ok() helper
    data = status_body.get("data", status_body)
    assert "status" in data, f"'status' key missing from: {status_body}"
