import pytest
from oo_automator.core.run_manager import RunManager, generate_combinations, RunStatus


def test_generate_combinations_sweep():
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


def test_generate_combinations_grid():
    config = {
        "mode": "grid",
        "parameters": {
            "delta": [5, 10],
            "profit_target": [20, 40],
        }
    }
    combinations = generate_combinations(config)

    assert len(combinations) == 4
    assert {"delta": 5, "profit_target": 20} in combinations
    assert {"delta": 5, "profit_target": 40} in combinations
    assert {"delta": 10, "profit_target": 20} in combinations
    assert {"delta": 10, "profit_target": 40} in combinations


def test_run_manager_creation():
    manager = RunManager(max_browsers=2)
    assert manager.max_browsers == 2
    assert manager.active_browsers == 0


def test_run_manager_stats():
    manager = RunManager(max_browsers=2)
    stats = manager.get_stats()

    assert "status" in stats
    assert "total_tasks" in stats
    assert "completed" in stats
    assert "failed" in stats
    assert "active_browsers" in stats


def test_run_status_enum():
    assert RunStatus.PENDING.value == "pending"
    assert RunStatus.RUNNING.value == "running"
    assert RunStatus.COMPLETED.value == "completed"
