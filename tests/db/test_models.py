import pytest
from sqlmodel import Session, create_engine, SQLModel
from oo_automator.db.models import Test, Run, Task, Result, Failure


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def test_create_test(session):
    test = Test(url="https://optionomega.com/test/abc123", name="My Test")
    session.add(test)
    session.commit()
    session.refresh(test)

    assert test.id is not None
    assert test.url == "https://optionomega.com/test/abc123"
    assert test.name == "My Test"
    assert test.run_count == 0


def test_create_run_with_test(session):
    test = Test(url="https://optionomega.com/test/abc123")
    session.add(test)
    session.commit()

    run = Run(
        test_id=test.id,
        mode="sweep",
        config={"parameter": "delta", "start": 5, "end": 50}
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    assert run.id is not None
    assert run.test_id == test.id
    assert run.status == "pending"


def test_create_task_with_run(session):
    test = Test(url="https://optionomega.com/test/abc123")
    session.add(test)
    session.commit()

    run = Run(test_id=test.id, mode="sweep", config={})
    session.add(run)
    session.commit()

    task = Task(run_id=run.id, parameter_values={"delta": 15})
    session.add(task)
    session.commit()
    session.refresh(task)

    assert task.id is not None
    assert task.status == "pending"
    assert task.attempts == 0


def test_create_result_with_task(session):
    test = Test(url="https://optionomega.com/test/abc123")
    session.add(test)
    session.commit()

    run = Run(test_id=test.id, mode="sweep", config={})
    session.add(run)
    session.commit()

    task = Task(run_id=run.id, parameter_values={"delta": 15})
    session.add(task)
    session.commit()

    result = Result(
        task_id=task.id,
        cagr=0.156,
        max_drawdown=-0.08,
        win_percentage=68.2,
        capture_rate=15.4,
        mar=1.95,
        pl=13376.0,
        total_premium=86720.0,
        starting_capital=250000.0,
        ending_capital=263376.0,
        total_trades=652,
        winners=402,
        avg_per_trade=21.0,
        avg_winner=130.0,
        avg_loser=-155.0,
        max_winner=217.0,
        max_loser=-377.0,
        avg_minutes_in_trade=154.1,
    )
    session.add(result)
    session.commit()
    session.refresh(result)

    assert result.id is not None
    assert result.cagr == 0.156
    assert result.total_trades == 652
