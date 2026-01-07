import pytest
from sqlmodel import Session, create_engine, SQLModel
from oo_automator.db.models import Test, Run, Task, Result
from oo_automator.db.queries import (
    get_or_create_test,
    get_recent_tests,
    find_test_by_name_or_url,
    create_run,
    create_tasks_for_run,
    get_pending_tasks,
    update_task_status,
    save_result,
)


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def test_get_or_create_test_new(session):
    test = get_or_create_test(session, "https://optionomega.com/test/abc123", "My Test")
    assert test.id is not None
    assert test.url == "https://optionomega.com/test/abc123"
    assert test.name == "My Test"


def test_get_or_create_test_existing(session):
    test1 = get_or_create_test(session, "https://optionomega.com/test/abc123", "My Test")
    test2 = get_or_create_test(session, "https://optionomega.com/test/abc123")
    assert test1.id == test2.id


def test_get_recent_tests(session):
    get_or_create_test(session, "https://optionomega.com/test/abc123", "Test 1")
    get_or_create_test(session, "https://optionomega.com/test/def456", "Test 2")

    tests = get_recent_tests(session, limit=10)
    assert len(tests) == 2


def test_find_test_by_name_or_url(session):
    get_or_create_test(session, "https://optionomega.com/test/abc123", "My Strategy")

    test = find_test_by_name_or_url(session, "Strategy")
    assert test is not None
    assert test.name == "My Strategy"

    test = find_test_by_name_or_url(session, "abc123")
    assert test is not None


def test_create_run(session):
    test = get_or_create_test(session, "https://optionomega.com/test/abc123")
    run = create_run(session, test.id, "sweep", {"parameter": "delta"})

    assert run.id is not None
    assert run.mode == "sweep"
    assert run.status == "pending"


def test_create_tasks_for_run(session):
    test = get_or_create_test(session, "https://optionomega.com/test/abc123")
    run = create_run(session, test.id, "sweep", {})

    param_combinations = [{"delta": 5}, {"delta": 10}, {"delta": 15}]
    tasks = create_tasks_for_run(session, run.id, param_combinations)

    assert len(tasks) == 3
    assert tasks[0].parameter_values == {"delta": 5}


def test_get_pending_tasks(session):
    test = get_or_create_test(session, "https://optionomega.com/test/abc123")
    run = create_run(session, test.id, "sweep", {})
    create_tasks_for_run(session, run.id, [{"delta": 5}, {"delta": 10}])

    pending = get_pending_tasks(session, run.id, limit=10)
    assert len(pending) == 2


def test_update_task_status(session):
    test = get_or_create_test(session, "https://optionomega.com/test/abc123")
    run = create_run(session, test.id, "sweep", {})
    tasks = create_tasks_for_run(session, run.id, [{"delta": 5}])

    update_task_status(session, tasks[0].id, "running")
    session.refresh(tasks[0])
    assert tasks[0].status == "running"


def test_save_result(session):
    test = get_or_create_test(session, "https://optionomega.com/test/abc123")
    run = create_run(session, test.id, "sweep", {})
    tasks = create_tasks_for_run(session, run.id, [{"delta": 5}])

    result_data = {
        "cagr": 0.156,
        "max_drawdown": -0.08,
        "win_percentage": 68.2,
        "pl": 13376.0,
    }
    result = save_result(session, tasks[0].id, result_data)

    assert result.id is not None
    assert result.cagr == 0.156
