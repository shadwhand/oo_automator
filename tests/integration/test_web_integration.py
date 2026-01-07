"""Integration tests for web dashboard with database."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel

from oo_automator.web.app import app
from oo_automator.db.connection import init_db, get_engine, get_session
from oo_automator.db.queries import (
    get_or_create_test,
    create_run,
    create_tasks_for_run,
    save_result,
    update_task_status,
)


@pytest.fixture(scope="module")
def setup_db():
    """Initialize database for testing."""
    engine = init_db()
    yield engine


@pytest.fixture
def session(setup_db):
    """Get database session using the same engine as the app."""
    engine = get_engine()
    session = get_session(engine)
    yield session
    session.close()


@pytest.fixture
def client(setup_db):
    """Create test client."""
    return TestClient(app)


class TestDashboardWithData:
    """Test dashboard pages with actual data."""

    def test_home_shows_tests(self, client, session):
        """Test home page shows created tests."""
        # Create a test
        test = get_or_create_test(
            session,
            url="https://app.optionomega.com/test/web-test-abc",
            name="My Test Strategy"
        )

        # Load home page
        response = client.get("/")
        assert response.status_code == 200
        assert "My Test Strategy" in response.text

    def test_home_shows_empty_state(self, client):
        """Test home page handles empty state."""
        response = client.get("/")
        assert response.status_code == 200
        # Should show either tests or empty state message
        assert response.status_code == 200

    def test_api_returns_runs(self, client, session):
        """Test API returns created runs."""
        # Create test and run
        test = get_or_create_test(
            session,
            url="https://example.com/test/api-runs-test"
        )
        run = create_run(session, test.id, "sweep", {"mode": "sweep", "parameter": "delta"})

        # Query API
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        # Find our run in the response
        run_ids = [r["id"] for r in data["runs"]]
        assert run.id in run_ids

    def test_api_returns_run_details(self, client, session):
        """Test API returns run details."""
        # Create test and run
        test = get_or_create_test(
            session,
            url="https://example.com/test/api-details-test"
        )
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})

        # Query API
        response = client.get(f"/api/runs/{run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run.id
        assert data["mode"] == "sweep"

    def test_api_returns_tasks(self, client, session):
        """Test API returns tasks for a run."""
        # Setup
        test = get_or_create_test(
            session,
            url="https://example.com/test/api-tasks-test"
        )
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        create_tasks_for_run(session, run.id, [{"delta": 10}, {"delta": 15}])

        # Query API
        response = client.get(f"/api/runs/{run.id}/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) == 2

    def test_api_returns_results(self, client, session):
        """Test API returns results for a run."""
        # Setup
        test = get_or_create_test(
            session,
            url="https://example.com/test/api-results-test"
        )
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        tasks = create_tasks_for_run(session, run.id, [{"delta": 10}])
        update_task_status(session, tasks[0].id, "completed")
        save_result(session, tasks[0].id, {
            "cagr": 20.0,
            "pl": 1000.0,
            "max_drawdown": -5.0,
        })

        # Query API
        response = client.get(f"/api/runs/{run.id}/results")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["cagr"] == 20.0

    def test_api_run_not_found(self, client):
        """Test API returns 404 for non-existent run."""
        response = client.get("/api/runs/99999")
        assert response.status_code == 404

    def test_api_filter_runs_by_status(self, client, session):
        """Test filtering runs by status."""
        # Create test with different status runs
        test = get_or_create_test(
            session,
            url="https://example.com/test/filter-status-test"
        )
        run1 = create_run(session, test.id, "sweep", {"mode": "sweep"})
        run2 = create_run(session, test.id, "sweep", {"mode": "sweep"})

        # Update one run to running
        from oo_automator.db.queries import update_run_status
        update_run_status(session, run2.id, "running")

        # Query for running runs
        response = client.get("/api/runs?status=running")
        assert response.status_code == 200
        data = response.json()
        # All returned runs should be running
        for run in data["runs"]:
            assert run["status"] == "running"


class TestHtmxPartials:
    """Test htmx partial responses."""

    def test_runs_list_htmx(self, client, session):
        """Test runs list returns HTML for htmx requests."""
        # Create a run
        test = get_or_create_test(
            session,
            url="https://example.com/test/htmx-test"
        )
        create_run(session, test.id, "sweep", {"mode": "sweep"})

        # Request with htmx headers
        response = client.get(
            "/api/runs",
            headers={"Accept": "text/html"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_tasks_table_htmx(self, client, session):
        """Test tasks table returns HTML for htmx requests."""
        # Setup
        test = get_or_create_test(
            session,
            url="https://example.com/test/htmx-tasks-test"
        )
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        create_tasks_for_run(session, run.id, [{"delta": 10}])

        # Request with htmx headers
        response = client.get(
            f"/api/runs/{run.id}/tasks",
            headers={"Accept": "text/html"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_results_table_htmx(self, client, session):
        """Test results table returns HTML for htmx requests."""
        # Setup
        test = get_or_create_test(
            session,
            url="https://example.com/test/htmx-results-test"
        )
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        tasks = create_tasks_for_run(session, run.id, [{"delta": 10}])
        update_task_status(session, tasks[0].id, "completed")
        save_result(session, tasks[0].id, {"cagr": 15.0, "pl": 500.0})

        # Request with htmx headers
        response = client.get(
            f"/api/runs/{run.id}/results",
            headers={"Accept": "text/html"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestRunDetailPage:
    """Test run detail page."""

    def test_run_detail_page_loads(self, client, session):
        """Test run detail page loads."""
        # Create a run
        test = get_or_create_test(
            session,
            url="https://example.com/test/detail-page-test"
        )
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})

        # Load run detail page
        response = client.get(f"/runs/{run.id}")
        assert response.status_code == 200


class TestWebDatabaseIntegration:
    """Test web routes properly integrate with database."""

    def test_create_and_view_complete_run(self, client, session):
        """Test complete workflow of creating and viewing a run."""
        # 1. Create test
        test = get_or_create_test(
            session,
            url="https://app.optionomega.com/test/complete-flow",
            name="Complete Flow Test"
        )

        # 2. Create run with tasks
        run = create_run(session, test.id, "sweep", {
            "mode": "sweep",
            "parameter": "delta",
            "values": [5, 10, 15],
        })
        tasks = create_tasks_for_run(session, run.id, [
            {"delta": 5},
            {"delta": 10},
            {"delta": 15},
        ])

        # 3. Add results
        for i, task in enumerate(tasks):
            update_task_status(session, task.id, "completed")
            save_result(session, task.id, {
                "cagr": 15.0 + i * 5,
                "pl": 1000.0 * (i + 1),
            })

        # 4. Verify via API
        # Check run details
        response = client.get(f"/api/runs/{run.id}")
        assert response.status_code == 200
        run_data = response.json()
        assert run_data["id"] == run.id

        # Check tasks
        response = client.get(f"/api/runs/{run.id}/tasks")
        assert response.status_code == 200
        tasks_data = response.json()
        assert len(tasks_data["tasks"]) == 3

        # Check results
        response = client.get(f"/api/runs/{run.id}/results")
        assert response.status_code == 200
        results_data = response.json()
        assert len(results_data["results"]) == 3

        # Verify CAGR values
        cagrs = [r["cagr"] for r in results_data["results"]]
        assert 15.0 in cagrs
        assert 20.0 in cagrs
        assert 25.0 in cagrs

    def test_home_page_shows_recent_test(self, client, session):
        """Test home page shows recently added test."""
        # Create a test with unique name
        test = get_or_create_test(
            session,
            url="https://app.optionomega.com/test/unique-home-test",
            name="Unique Home Test Strategy"
        )

        # Check home page
        response = client.get("/")
        assert response.status_code == 200
        assert "Unique Home Test Strategy" in response.text
