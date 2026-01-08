from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from .models import Test, Run, Task, Result, Failure


def get_or_create_test(session: Session, url: str, name: Optional[str] = None) -> Test:
    """Get existing test by URL or create new one."""
    statement = select(Test).where(Test.url == url)
    test = session.exec(statement).first()

    if test is None:
        test = Test(url=url, name=name)
        session.add(test)
        session.commit()
        session.refresh(test)
    elif name and not test.name:
        test.name = name
        session.commit()
        session.refresh(test)

    return test


def get_recent_tests(session: Session, limit: int = 10) -> list[Test]:
    """Get recently used tests, ordered by last run or creation."""
    statement = (
        select(Test)
        .order_by(Test.last_run_at.desc().nullslast(), Test.created_at.desc())
        .limit(limit)
    )
    return list(session.exec(statement).all())


def find_test_by_name_or_url(session: Session, query: str) -> Optional[Test]:
    """Find a test by partial name or URL match."""
    # Try URL match first
    statement = select(Test).where(Test.url.contains(query))
    test = session.exec(statement).first()
    if test:
        return test

    # Try name match
    statement = select(Test).where(Test.name.contains(query))
    return session.exec(statement).first()


def create_run(session: Session, test_id: int, mode: str, config: dict) -> Run:
    """Create a new run."""
    run = Run(test_id=test_id, mode=mode, config=config)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def create_tasks_for_run(session: Session, run_id: int, parameter_combinations: list[dict]) -> list[Task]:
    """Create tasks for all parameter combinations."""
    tasks = []
    for params in parameter_combinations:
        task = Task(run_id=run_id, parameter_values=params)
        session.add(task)
        tasks.append(task)
    session.commit()
    for task in tasks:
        session.refresh(task)
    return tasks


def get_pending_tasks(session: Session, run_id: int, limit: int = 10) -> list[Task]:
    """Get pending tasks for a run."""
    statement = (
        select(Task)
        .where(Task.run_id == run_id, Task.status == "pending")
        .limit(limit)
    )
    return list(session.exec(statement).all())


def update_task_status(session: Session, task_id: int, status: str, increment_attempts: bool = False) -> Task:
    """Update task status."""
    statement = select(Task).where(Task.id == task_id)
    task = session.exec(statement).one()
    task.status = status
    if increment_attempts:
        task.attempts += 1
    session.commit()
    session.refresh(task)
    return task


def save_result(session: Session, task_id: int, result_data: dict) -> Result:
    """Save test result."""
    result = Result(task_id=task_id, **result_data)
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def save_failure(session: Session, task_id: int, attempt_number: int, failure_type: str,
                 error_message: str, screenshot_path: Optional[str] = None,
                 html_path: Optional[str] = None, console_log: Optional[dict] = None) -> Failure:
    """Save failure artifact."""
    failure = Failure(
        task_id=task_id,
        attempt_number=attempt_number,
        failure_type=failure_type,
        error_message=error_message,
        screenshot_path=screenshot_path,
        html_path=html_path,
        console_log=console_log,
    )
    session.add(failure)
    session.commit()
    session.refresh(failure)
    return failure


def update_run_status(session: Session, run_id: int, status: str) -> Run:
    """Update run status."""
    statement = select(Run).where(Run.id == run_id)
    run = session.exec(statement).one()
    run.status = status
    if status == "running" and run.started_at is None:
        run.started_at = datetime.utcnow()
    if status in ("completed", "failed"):
        run.completed_at = datetime.utcnow()
    session.commit()
    session.refresh(run)
    return run


def increment_test_run_count(session: Session, test_id: int) -> None:
    """Increment run count and update last_run_at for a test."""
    statement = select(Test).where(Test.id == test_id)
    test = session.exec(statement).one()
    test.run_count += 1
    test.last_run_at = datetime.utcnow()
    session.commit()


def get_tests_with_run_summary(session: Session, limit: int = 10) -> list[dict]:
    """Get recent tests with run count and latest run info.

    Returns list of dicts with: test, run_count, latest_run, latest_result
    """
    # Get recent tests
    tests = get_recent_tests(session, limit=limit)

    results = []
    for test in tests:
        # Get latest run for this test
        latest_run_stmt = (
            select(Run)
            .where(Run.test_id == test.id)
            .order_by(Run.created_at.desc())
            .limit(1)
        )
        latest_run = session.exec(latest_run_stmt).first()

        # Get latest result if we have a run
        latest_result = None
        if latest_run:
            # Get the first completed task's result for this run
            result_stmt = (
                select(Result)
                .join(Task, Result.task_id == Task.id)
                .where(Task.run_id == latest_run.id)
                .order_by(Result.created_at.desc())
                .limit(1)
            )
            latest_result = session.exec(result_stmt).first()

        results.append({
            "test": test,
            "run_count": test.run_count,
            "latest_run": latest_run,
            "latest_result": latest_result,
        })

    return results
