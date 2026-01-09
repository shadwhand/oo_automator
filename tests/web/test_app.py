"""Tests for FastAPI web application."""
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


def test_home_page(client):
    """Test home page loads."""
    response = client.get("/")
    assert response.status_code == 200
    assert "OO Automator" in response.text


def test_api_list_runs(client):
    """Test list runs API."""
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert "runs" in response.json()


def test_analytics_page(client):
    """Test analytics page loads."""
    response = client.get("/analytics")
    assert response.status_code == 200
