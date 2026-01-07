"""Integration tests for complete run flow."""
import asyncio
import pytest
from sqlmodel import Session, create_engine, SQLModel

from oo_automator.db.models import Test, Run, Task, Result
from oo_automator.db.queries import (
    get_or_create_test,
    create_run,
    create_tasks_for_run,
    update_task_status,
    save_result,
    update_run_status,
)
from oo_automator.parameters import get_parameter, list_parameters
from oo_automator.core.run_manager import generate_combinations
from oo_automator.core.task_queue import TaskQueue


@pytest.fixture
def engine():
    """Create in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Get database session."""
    with Session(engine) as session:
        yield session


class TestCompleteRunFlow:
    """Test complete run flow from test creation to results."""

    def test_create_test_and_run(self, session):
        """Test creating a test and run."""
        # Create test
        test = get_or_create_test(
            session,
            url="https://app.optionomega.com/tests/test123",
            name="Integration Test"
        )
        assert test.id is not None
        assert test.name == "Integration Test"

        # Create run config
        config = {
            "mode": "sweep",
            "parameter": "delta",
            "values": [5, 10, 15, 20],
        }

        # Create run
        run = create_run(session, test.id, "sweep", config)
        assert run.id is not None
        assert run.status == "pending"

        # Create tasks
        combinations = generate_combinations(config)
        tasks = create_tasks_for_run(session, run.id, combinations)
        assert len(tasks) == 4

    def test_task_lifecycle(self, session):
        """Test task status transitions."""
        # Setup
        test = get_or_create_test(session, url="https://example.com/test")
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        tasks = create_tasks_for_run(session, run.id, [{"delta": 10}])
        task = tasks[0]

        # Verify initial state
        assert task.status == "pending"
        assert task.attempts == 0

        # Transition to running
        updated = update_task_status(session, task.id, "running", increment_attempts=True)
        assert updated.status == "running"
        assert updated.attempts == 1

        # Transition to completed
        updated = update_task_status(session, task.id, "completed")
        assert updated.status == "completed"

    def test_save_and_retrieve_results(self, session):
        """Test saving and retrieving results."""
        # Setup
        test = get_or_create_test(session, url="https://example.com/test")
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        tasks = create_tasks_for_run(session, run.id, [{"delta": 10}])
        task = tasks[0]

        # Save result
        result = save_result(session, task.id, {
            "cagr": 25.5,
            "max_drawdown": -15.2,
            "win_percentage": 62.5,
            "pl": 5000.0,
            "mar": 1.68,
            "total_trades": 150,
        })

        assert result.id is not None
        assert result.cagr == 25.5
        assert result.pl == 5000.0

    def test_run_status_lifecycle(self, session):
        """Test run status transitions."""
        # Setup
        test = get_or_create_test(session, url="https://example.com/test")
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})

        # Verify initial state
        assert run.status == "pending"
        assert run.started_at is None

        # Start run
        updated = update_run_status(session, run.id, "running")
        assert updated.status == "running"
        assert updated.started_at is not None

        # Complete run
        updated = update_run_status(session, run.id, "completed")
        assert updated.status == "completed"
        assert updated.completed_at is not None


class TestParameterIntegration:
    """Test parameter system integration."""

    def test_parameter_discovery(self):
        """Test that parameters are discovered correctly."""
        params = list_parameters()
        assert len(params) > 0

        # Check delta parameter exists
        delta = get_parameter("delta")
        assert delta is not None
        assert delta.name == "delta"

    def test_parameter_value_generation(self):
        """Test parameter value generation."""
        delta = get_parameter("delta")
        assert delta is not None

        # Generate values
        values = delta.generate_values({
            "start": 5,
            "end": 20,
            "step": 5,
        })

        assert values == [5, 10, 15, 20]

    def test_parameter_config(self):
        """Test parameter configuration schema."""
        delta = get_parameter("delta")
        assert delta is not None

        config = delta.configure()
        assert len(config.fields) > 0

        # Check defaults
        defaults = config.get_defaults()
        assert "start" in defaults
        assert "end" in defaults


class TestTaskQueueIntegration:
    """Test task queue with database."""

    @pytest.mark.asyncio
    async def test_queue_with_db_tasks(self, session):
        """Test queue operations with database tasks."""
        # Setup
        test = get_or_create_test(session, url="https://example.com/test")
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        db_tasks = create_tasks_for_run(session, run.id, [
            {"delta": 5},
            {"delta": 10},
            {"delta": 15},
        ])

        # Create queue and add tasks
        queue = TaskQueue()
        for task in db_tasks:
            await queue.put({"task_id": task.id, "params": task.parameter_values})

        assert queue.qsize() == 3

        # Process tasks
        task_data = await queue.get()
        assert task_data["task_id"] == db_tasks[0].id

        queue.mark_completed()
        stats = queue.get_stats()
        assert stats["completed"] == 1

    @pytest.mark.asyncio
    async def test_queue_requeue_failed_task(self, session):
        """Test requeuing a failed task."""
        # Setup
        test = get_or_create_test(session, url="https://example.com/test")
        run = create_run(session, test.id, "sweep", {"mode": "sweep"})
        db_tasks = create_tasks_for_run(session, run.id, [{"delta": 5}])

        # Create queue and add task
        queue = TaskQueue()
        task_data = {"task_id": db_tasks[0].id, "params": db_tasks[0].parameter_values, "attempts": 0}
        await queue.put(task_data)

        # Get and requeue
        retrieved = await queue.get()
        retrieved["attempts"] += 1
        await queue.requeue(retrieved, priority=10)

        # Verify task is back in queue
        assert queue.qsize() == 1


class TestRunManagerIntegration:
    """Test run manager with database."""

    def test_generate_sweep_combinations(self):
        """Test sweep mode combination generation."""
        config = {
            "mode": "sweep",
            "parameter": "delta",
            "values": [5, 10, 15],
        }
        combinations = generate_combinations(config)

        assert len(combinations) == 3
        assert combinations[0] == {"delta": 5}
        assert combinations[1] == {"delta": 10}
        assert combinations[2] == {"delta": 15}

    def test_generate_grid_combinations(self):
        """Test grid mode combination generation."""
        config = {
            "mode": "grid",
            "parameters": {
                "delta": [5, 10],
                "profit_target": [50, 100],
            },
        }
        combinations = generate_combinations(config)

        # 2 x 2 = 4 combinations
        assert len(combinations) == 4

        # Verify all combinations exist
        expected = [
            {"delta": 5, "profit_target": 50},
            {"delta": 5, "profit_target": 100},
            {"delta": 10, "profit_target": 50},
            {"delta": 10, "profit_target": 100},
        ]
        for exp in expected:
            assert exp in combinations

    def test_generate_staged_combinations(self):
        """Test staged mode combination generation."""
        config = {
            "mode": "staged",
            "stages": [
                {"parameter": "delta", "values": [5, 10, 15]},
                {"parameter": "profit_target", "values": [50, 100]},
            ],
        }
        combinations = generate_combinations(config)

        # First stage only
        assert len(combinations) == 3
        assert combinations[0] == {"delta": 5}

    def test_generate_empty_combinations(self):
        """Test handling of empty config."""
        config = {"mode": "sweep", "parameter": "delta", "values": []}
        combinations = generate_combinations(config)
        assert combinations == []


class TestEndToEndFlow:
    """Test complete end-to-end flow."""

    def test_full_backtest_workflow(self, session):
        """Test the complete backtest workflow from start to finish."""
        # 1. Create a test
        test = get_or_create_test(
            session,
            url="https://app.optionomega.com/tests/full-workflow",
            name="Full Workflow Test"
        )

        # 2. Create run with sweep config
        config = {
            "mode": "sweep",
            "parameter": "delta",
            "values": [5, 10, 15],
        }
        run = create_run(session, test.id, "sweep", config)

        # 3. Generate and create tasks
        combinations = generate_combinations(config)
        tasks = create_tasks_for_run(session, run.id, combinations)

        # 4. Start the run
        update_run_status(session, run.id, "running")

        # 5. Process each task
        for i, task in enumerate(tasks):
            # Mark as running
            update_task_status(session, task.id, "running", increment_attempts=True)

            # Simulate result
            save_result(session, task.id, {
                "cagr": 20.0 + i * 2,
                "pl": 1000.0 * (i + 1),
                "max_drawdown": -10.0 - i,
            })

            # Mark as completed
            update_task_status(session, task.id, "completed")

        # 6. Complete the run
        update_run_status(session, run.id, "completed")

        # 7. Verify final state
        session.refresh(run)
        assert run.status == "completed"
        assert run.completed_at is not None

        # Verify all tasks completed
        for task in tasks:
            session.refresh(task)
            assert task.status == "completed"
            assert task.result is not None
