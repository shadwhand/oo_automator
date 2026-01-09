"""Tests for analytics API endpoints."""
import os
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from oo_automator.db.connection import init_db, get_engine, get_session
from oo_automator.db.models import Test as TestModel, Run, Task, Result
from oo_automator.web.app import app


@pytest.fixture(scope="module")
def setup_db():
    """Initialize database tables for testing."""
    init_db()


@pytest.fixture
def client(setup_db):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_trade_csv():
    """Create a sample trade log CSV for testing."""
    csv_content = """Date Opened,Time Opened,Date Closed,Time Closed,P/L,P/L %,Premium,Legs,No. of Contracts,Reason For Close,Opening VIX,Closing VIX,Gap,Movement,Opening Price,Closing Price,Max Profit,Max Loss,Margin Req.
2024-01-15,09:30:00,2024-01-15,15:00:00,$500,10%,$5000,PUT 4500/4490,1,Expired,$15.00,$14.50,0.5%,1.2%,$4500.00,$4505.00,$500,-$1000,$2000
2024-01-16,09:30:00,2024-01-16,14:00:00,-$200,-4%,$5000,PUT 4500/4490,1,Stop Loss,$16.00,$17.00,-0.3%,-0.8%,$4495.00,$4490.00,$500,-$1000,$2000
2024-01-17,09:30:00,2024-01-17,15:30:00,$300,6%,$5000,PUT 4500/4490,1,Expired,$14.00,$13.50,0.2%,0.5%,$4510.00,$4515.00,$500,-$1000,$2000
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        f.flush()
        yield f.name
    # Cleanup
    os.unlink(f.name)


@pytest.fixture
def test_with_trade_logs(setup_db, sample_trade_csv):
    """Create a test with runs that have trade log CSVs."""
    engine = get_engine()
    session = get_session(engine)

    # Use unique URL to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]

    try:
        # Create a test
        test = TestModel(
            url=f"https://example.com/test-with-logs-{unique_id}",
            name="Test With Trade Logs",
            run_count=2,
        )
        session.add(test)
        session.commit()
        session.refresh(test)

        # Create two runs with trade logs
        run1 = Run(
            test_id=test.id,
            mode="sweep",
            config={"parameter": "delta", "values": [5, 10, 15]},
            status="completed",
        )
        session.add(run1)
        session.commit()
        session.refresh(run1)

        # Create task and result with trade log
        task1 = Task(
            run_id=run1.id,
            parameter_values={"delta": 10},
            status="completed",
        )
        session.add(task1)
        session.commit()
        session.refresh(task1)

        result1 = Result(
            task_id=task1.id,
            pl=600.0,
            cagr=15.5,
            max_drawdown=8.2,
            trade_log_csv=sample_trade_csv,
        )
        session.add(result1)
        session.commit()

        # Second run
        run2 = Run(
            test_id=test.id,
            mode="sweep",
            config={"parameter": "delta", "values": [5, 10, 15]},
            status="completed",
        )
        session.add(run2)
        session.commit()
        session.refresh(run2)

        task2 = Task(
            run_id=run2.id,
            parameter_values={"delta": 15},
            status="completed",
        )
        session.add(task2)
        session.commit()
        session.refresh(task2)

        result2 = Result(
            task_id=task2.id,
            pl=800.0,
            cagr=18.2,
            max_drawdown=6.5,
            trade_log_csv=sample_trade_csv,
        )
        session.add(result2)
        session.commit()

        yield {
            "test": test,
            "run1": run1,
            "run2": run2,
            "task1": task1,
            "task2": task2,
            "result1": result1,
            "result2": result2,
        }

    finally:
        session.close()


@pytest.fixture
def test_without_trade_logs(setup_db):
    """Create a test with runs that don't have trade log CSVs."""
    engine = get_engine()
    session = get_session(engine)

    # Use unique URL to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]

    try:
        # Create a test
        test = TestModel(
            url=f"https://example.com/test-no-logs-{unique_id}",
            name="Test Without Trade Logs",
            run_count=1,
        )
        session.add(test)
        session.commit()
        session.refresh(test)

        # Create a run without trade logs
        run = Run(
            test_id=test.id,
            mode="sweep",
            config={"parameter": "delta", "values": [5]},
            status="completed",
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        task = Task(
            run_id=run.id,
            parameter_values={"delta": 5},
            status="completed",
        )
        session.add(task)
        session.commit()
        session.refresh(task)

        # Result without trade_log_csv
        result = Result(
            task_id=task.id,
            pl=300.0,
            cagr=10.0,
            max_drawdown=5.0,
            trade_log_csv=None,  # No trade log
        )
        session.add(result)
        session.commit()

        yield {"test": test, "run": run}

    finally:
        session.close()


class TestAnalyticsTestsEndpoint:
    """Tests for GET /api/analytics/tests endpoint."""

    def test_returns_tests_with_trade_logs(self, client, test_with_trade_logs):
        """Should return tests that have results with trade_log_csv."""
        response = client.get("/api/analytics/tests")
        assert response.status_code == 200

        data = response.json()
        assert "tests" in data

        # Find our test in the results
        test_ids = [t["id"] for t in data["tests"]]
        assert test_with_trade_logs["test"].id in test_ids

    def test_does_not_return_tests_without_trade_logs(self, client, test_without_trade_logs):
        """Should not return tests that have no results with trade_log_csv."""
        response = client.get("/api/analytics/tests")
        assert response.status_code == 200

        data = response.json()

        # Our test without trade logs should not be in results
        test_ids = [t["id"] for t in data["tests"]]
        assert test_without_trade_logs["test"].id not in test_ids

    def test_returns_correct_structure(self, client, test_with_trade_logs):
        """Should return correct data structure for each test."""
        response = client.get("/api/analytics/tests")
        assert response.status_code == 200

        data = response.json()

        # Find our test
        test_data = None
        for t in data["tests"]:
            if t["id"] == test_with_trade_logs["test"].id:
                test_data = t
                break

        assert test_data is not None
        assert "id" in test_data
        assert "name" in test_data
        assert "url" in test_data
        assert "run_count" in test_data

    def test_returns_run_count(self, client, test_with_trade_logs):
        """Should return correct run count with trade logs."""
        response = client.get("/api/analytics/tests")
        assert response.status_code == 200

        data = response.json()

        # Find our test
        test_data = None
        for t in data["tests"]:
            if t["id"] == test_with_trade_logs["test"].id:
                test_data = t
                break

        assert test_data is not None
        # Should have 2 runs with trade logs
        assert test_data["run_count"] >= 2


class TestAnalyticsDataEndpoint:
    """Tests for GET /api/analytics/data endpoint."""

    def test_requires_test_id(self, client):
        """Should require test_id parameter."""
        response = client.get("/api/analytics/data")
        assert response.status_code == 422  # Validation error

    def test_returns_404_for_nonexistent_test(self, client, setup_db):
        """Should return 404 for nonexistent test."""
        response = client.get("/api/analytics/data?test_id=99999")
        assert response.status_code == 404

    def test_returns_aggregated_data(self, client, test_with_trade_logs):
        """Should return aggregated chart data."""
        test_id = test_with_trade_logs["test"].id
        response = client.get(f"/api/analytics/data?test_id={test_id}")
        assert response.status_code == 200

        data = response.json()

        # Should contain chart data keys from aggregate_for_charts
        assert "daily_pl" in data
        assert "cumulative" in data
        assert "stop_loss_counts" in data
        assert "reason_counts" in data
        assert "vix_data" in data
        assert "duration_avg" in data

    def test_filters_by_run_ids(self, client, test_with_trade_logs):
        """Should filter by run_ids when provided."""
        test_id = test_with_trade_logs["test"].id
        run_id = test_with_trade_logs["run1"].id

        response = client.get(f"/api/analytics/data?test_id={test_id}&run_ids={run_id}")
        assert response.status_code == 200

        data = response.json()
        assert "daily_pl" in data

    def test_accepts_multiple_run_ids(self, client, test_with_trade_logs):
        """Should accept comma-separated run_ids."""
        test_id = test_with_trade_logs["test"].id
        run_ids = f"{test_with_trade_logs['run1'].id},{test_with_trade_logs['run2'].id}"

        response = client.get(f"/api/analytics/data?test_id={test_id}&run_ids={run_ids}")
        assert response.status_code == 200

    def test_filters_by_date_range(self, client, test_with_trade_logs):
        """Should filter by start_date and end_date."""
        test_id = test_with_trade_logs["test"].id

        response = client.get(
            f"/api/analytics/data?test_id={test_id}&start_date=2024-01-01&end_date=2024-12-31"
        )
        assert response.status_code == 200

        data = response.json()
        assert "daily_pl" in data

    def test_returns_empty_data_for_no_trades(self, client, test_without_trade_logs):
        """Should return empty aggregation if no trade logs found."""
        test_id = test_without_trade_logs["test"].id

        # This test doesn't have trade logs, so should return empty aggregation
        response = client.get(f"/api/analytics/data?test_id={test_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["daily_pl"] == {}
        assert data["cumulative"] == {}
        assert data["vix_data"] == []
