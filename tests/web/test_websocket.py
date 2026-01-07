"""Tests for WebSocket functionality."""
import pytest
from fastapi.testclient import TestClient
from oo_automator.web.app import app
from oo_automator.db.connection import init_db


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize database for tests."""
    init_db()


def test_websocket_connection():
    """Test WebSocket connection is accepted."""
    client = TestClient(app)
    # Create a test run first
    # For now, just test that the endpoint exists
    with client.websocket_connect("/ws/runs/1") as websocket:
        data = websocket.receive_json()
        assert "type" in data or "error" in data


def test_websocket_ping_pong():
    """Test WebSocket ping/pong."""
    client = TestClient(app)
    with client.websocket_connect("/ws/runs/1") as websocket:
        websocket.receive_json()  # Skip initial status
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert response == "pong"
