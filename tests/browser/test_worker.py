import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from oo_automator.browser.worker import BrowserWorker, WorkerState, TaskResult


def test_worker_initial_state():
    worker = BrowserWorker(worker_id=1)
    assert worker.worker_id == 1
    assert worker.state == WorkerState.IDLE
    assert worker.current_task is None


def test_worker_state_transitions():
    worker = BrowserWorker(worker_id=1)

    worker.state = WorkerState.RUNNING
    assert worker.state == WorkerState.RUNNING

    worker.state = WorkerState.ERROR
    assert worker.state == WorkerState.ERROR


def test_task_result_success():
    result = TaskResult(
        success=True,
        task_id=1,
        parameter_values={"delta": 15},
        results={"cagr": 0.156}
    )
    assert result.success is True
    assert result.task_id == 1
    assert result.results["cagr"] == 0.156


def test_task_result_failure():
    result = TaskResult(
        success=False,
        task_id=1,
        parameter_values={"delta": 15},
        error_message="Failed to log in",
        failure_type="session"
    )
    assert result.success is False
    assert result.failure_type == "session"
