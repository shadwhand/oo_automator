"""Tests for recommendations API endpoint."""
import pytest
from fastapi.testclient import TestClient

from oo_automator.db.connection import init_db
from oo_automator.web.app import app


@pytest.fixture(scope="module")
def setup_db():
    """Initialize database tables for testing."""
    init_db()


@pytest.fixture
def client(setup_db):
    """Create test client."""
    return TestClient(app)


class TestRecommendationsAPI:
    def test_get_recommendations_not_found(self, client):
        response = client.get("/api/runs/99999/recommendations")
        assert response.status_code == 404

    def test_get_recommendations_accepts_goal_param(self, client):
        # Should accept goal parameter without error
        response = client.get("/api/runs/1/recommendations?goal=maximize_returns")
        # Either 200 (has data) or 404 (no run) - just shouldn't be 422/500
        assert response.status_code in [200, 404]

    def test_get_recommendations_returns_structure(self, client):
        response = client.get("/api/runs/1/recommendations")
        if response.status_code == 200:
            data = response.json()
            assert "top_pick" in data
            assert "alternatives" in data
            assert "avoid" in data
            assert "goal" in data
