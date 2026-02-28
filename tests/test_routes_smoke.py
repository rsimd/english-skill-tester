"""Smoke tests for API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from english_skill_tester.api.routes import router


@pytest.fixture
def mock_settings(tmp_path):
    settings = MagicMock()
    settings.sessions_dir = tmp_path / "sessions"
    settings.sessions_dir.mkdir()
    settings.app_secret = None
    return settings


@pytest.fixture
def client(mock_settings):
    app = FastAPI()
    app.include_router(router)
    with patch("english_skill_tester.api.routes.get_settings", return_value=mock_settings):
        with TestClient(app) as c:
            yield c


class TestHealthCheck:
    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSessionsList:
    def test_sessions_empty_dir(self, client):
        response = client.get("/api/sessions")
        assert response.status_code == 200
        assert response.json() == []

    def test_sessions_history_empty(self, client):
        response = client.get("/api/sessions/history")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_session_not_found(self, client):
        import uuid
        valid_uuid = str(uuid.uuid4())
        response = client.get(f"/api/sessions/{valid_uuid}")
        assert response.status_code == 404

    def test_session_invalid_id(self, client):
        response = client.get("/api/sessions/not-a-uuid")
        assert response.status_code == 400
