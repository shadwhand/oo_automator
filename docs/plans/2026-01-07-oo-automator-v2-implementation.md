# OO Automator V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reliable, fire-and-forget OptionOmega backtesting automation system with live dashboard monitoring.

**Architecture:** Monolithic Python app using Playwright for browser automation, FastAPI for web dashboard, SQLite for persistence, and Typer for CLI. Auto-discovered parameter plugin system for extensibility.

**Tech Stack:** Python 3.11+, Playwright, FastAPI, SQLite (via SQLModel), Typer, htmx, Jinja2

**Reference Documents:**
- Design: `docs/plans/2026-01-07-oo-automator-v2-design.md`
- Selectors: `recordings/selectors_expanded.json`
- Flow: `recordings/backtest_flow.json`

---

## Phase 1: Project Setup & Core Infrastructure

### Task 1.1: Initialize Project Structure

**Files:**
- Create: `pyproject.toml`
- Create: `oo_automator/__init__.py`
- Create: `oo_automator/main.py`
- Create: `tests/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "oo-automator"
version = "2.0.0"
description = "OptionOmega backtesting automation with live dashboard"
requires-python = ">=3.11"

dependencies = [
    "playwright>=1.40.0",
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
    "sqlmodel>=0.0.14",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.6",
    "websockets>=12.0",
    "httpx>=0.26.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
]

[project.scripts]
oo-automator = "oo_automator.main:app"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create package init**

```python
# oo_automator/__init__.py
"""OO Automator - OptionOmega backtesting automation."""
__version__ = "2.0.0"
```

**Step 3: Create main entry point**

```python
# oo_automator/main.py
import typer

app = typer.Typer(
    name="oo-automator",
    help="OptionOmega backtesting automation with live dashboard",
    add_completion=False,
)


@app.command()
def version():
    """Show version information."""
    from . import __version__
    typer.echo(f"OO Automator v{__version__}")


if __name__ == "__main__":
    app()
```

**Step 4: Create tests init**

```python
# tests/__init__.py
"""Test suite for OO Automator."""
```

**Step 5: Verify installation**

Run: `pip install -e ".[dev]"`
Expected: Successfully installed oo-automator

Run: `oo-automator version`
Expected: `OO Automator v2.0.0`

**Step 6: Commit**

```bash
git init
git add .
git commit -m "feat: initialize project structure with pyproject.toml

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 1.2: Install Playwright and Verify Browser

**Files:**
- None (system setup)

**Step 1: Install Playwright browsers**

Run: `playwright install chromium`
Expected: Chromium browser downloaded

**Step 2: Verify Playwright works**

Run: `python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); b.close(); p.stop(); print('OK')"`
Expected: `OK`

**Step 3: Commit (no files changed, skip)**

---

### Task 1.3: Create Directory Structure

**Files:**
- Create: Multiple `__init__.py` files for package structure

**Step 1: Create all package directories**

```bash
mkdir -p oo_automator/{cli,web,web/routes,web/templates,web/static,core,browser,parameters,analysis,db}
mkdir -p tests/{cli,web,core,browser,parameters}
mkdir -p data/artifacts/failures
```

**Step 2: Create __init__.py files**

Create empty `__init__.py` in each package directory:
- `oo_automator/cli/__init__.py`
- `oo_automator/web/__init__.py`
- `oo_automator/web/routes/__init__.py`
- `oo_automator/core/__init__.py`
- `oo_automator/browser/__init__.py`
- `oo_automator/parameters/__init__.py`
- `oo_automator/analysis/__init__.py`
- `oo_automator/db/__init__.py`

**Step 3: Commit**

```bash
git add .
git commit -m "feat: add package directory structure

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 2: Database Layer

### Task 2.1: Create Database Models

**Files:**
- Create: `oo_automator/db/models.py`
- Test: `tests/db/test_models.py`

**Step 1: Write the failing test**

```python
# tests/db/test_models.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/db/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'oo_automator.db.models'"

**Step 3: Write the implementation**

```python
# oo_automator/db/models.py
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
import json


class Test(SQLModel, table=True):
    """OptionOmega test configurations - grows over time as user adds tests."""
    __tablename__ = "tests"

    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    name: Optional[str] = Field(default=None, index=True)
    last_run_at: Optional[datetime] = Field(default=None, index=True)
    run_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    runs: list["Run"] = Relationship(back_populates="test")


class Run(SQLModel, table=True):
    """Automation runs."""
    __tablename__ = "runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    test_id: int = Field(foreign_key="tests.id")
    mode: str  # sweep | grid | staged
    config: dict = Field(default_factory=dict, sa_type_kwargs={"astext_type": None})
    status: str = Field(default="pending")  # pending | running | paused | completed | failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    test: Optional[Test] = Relationship(back_populates="runs")
    tasks: list["Task"] = Relationship(back_populates="run")

    class Config:
        arbitrary_types_allowed = True


class Task(SQLModel, table=True):
    """Individual test tasks."""
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id", index=True)
    parameter_values: dict = Field(default_factory=dict)
    status: str = Field(default="pending", index=True)  # pending | running | completed | failed | skipped
    attempts: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    run: Optional[Run] = Relationship(back_populates="tasks")
    result: Optional["Result"] = Relationship(back_populates="task")
    failures: list["Failure"] = Relationship(back_populates="task")


class Result(SQLModel, table=True):
    """Test results with all metrics from OptionOmega."""
    __tablename__ = "results"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id", unique=True, index=True)

    # Primary metrics
    pl: Optional[float] = None
    cagr: Optional[float] = None
    max_drawdown: Optional[float] = None
    mar: Optional[float] = None
    win_percentage: Optional[float] = None

    # Premium metrics
    total_premium: Optional[float] = None
    capture_rate: Optional[float] = None

    # Capital metrics
    starting_capital: Optional[float] = None
    ending_capital: Optional[float] = None

    # Trade metrics
    total_trades: Optional[int] = None
    winners: Optional[int] = None
    avg_per_trade: Optional[float] = None
    avg_winner: Optional[float] = None
    avg_loser: Optional[float] = None
    max_winner: Optional[float] = None
    max_loser: Optional[float] = None
    avg_minutes_in_trade: Optional[float] = None

    # Raw data storage
    raw_data: Optional[dict] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    task: Optional[Task] = Relationship(back_populates="result")


class Failure(SQLModel, table=True):
    """Failure artifacts for debugging."""
    __tablename__ = "failures"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id", index=True)
    attempt_number: int
    failure_type: str  # timing | modal | session | browser | permanent
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    html_path: Optional[str] = None
    console_log: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    task: Optional[Task] = Relationship(back_populates="failures")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/db/test_models.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/db/models.py tests/db/test_models.py
git commit -m "feat: add database models for tests, runs, tasks, results, failures

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2.2: Create Database Connection and Queries

**Files:**
- Create: `oo_automator/db/connection.py`
- Create: `oo_automator/db/queries.py`
- Test: `tests/db/test_queries.py`

**Step 1: Write the failing test**

```python
# tests/db/test_queries.py
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/db/test_queries.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write the implementation**

```python
# oo_automator/db/connection.py
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

DATABASE_PATH = Path("data/oo_automator.db")


def get_engine(db_path: Path = DATABASE_PATH):
    """Get or create database engine."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    return engine


def init_db(engine=None):
    """Initialize database tables."""
    if engine is None:
        engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine


def get_session(engine=None):
    """Get a database session."""
    if engine is None:
        engine = get_engine()
    return Session(engine)
```

```python
# oo_automator/db/queries.py
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from .models import Test, Run, Task, Result, Failure


def get_or_create_test(
    session: Session,
    url: str,
    name: Optional[str] = None
) -> Test:
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
    # Try exact URL match first
    statement = select(Test).where(Test.url.contains(query))
    test = session.exec(statement).first()
    if test:
        return test

    # Try name match
    statement = select(Test).where(Test.name.contains(query))
    return session.exec(statement).first()


def create_run(
    session: Session,
    test_id: int,
    mode: str,
    config: dict
) -> Run:
    """Create a new run."""
    run = Run(test_id=test_id, mode=mode, config=config)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def create_tasks_for_run(
    session: Session,
    run_id: int,
    parameter_combinations: list[dict]
) -> list[Task]:
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


def get_pending_tasks(
    session: Session,
    run_id: int,
    limit: int = 10
) -> list[Task]:
    """Get pending tasks for a run."""
    statement = (
        select(Task)
        .where(Task.run_id == run_id, Task.status == "pending")
        .limit(limit)
    )
    return list(session.exec(statement).all())


def update_task_status(
    session: Session,
    task_id: int,
    status: str,
    increment_attempts: bool = False
) -> Task:
    """Update task status."""
    statement = select(Task).where(Task.id == task_id)
    task = session.exec(statement).one()
    task.status = status
    if increment_attempts:
        task.attempts += 1
    session.commit()
    session.refresh(task)
    return task


def save_result(
    session: Session,
    task_id: int,
    result_data: dict
) -> Result:
    """Save test result."""
    result = Result(task_id=task_id, **result_data)
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def save_failure(
    session: Session,
    task_id: int,
    attempt_number: int,
    failure_type: str,
    error_message: str,
    screenshot_path: Optional[str] = None,
    html_path: Optional[str] = None,
    console_log: Optional[dict] = None
) -> Failure:
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


def update_run_status(
    session: Session,
    run_id: int,
    status: str
) -> Run:
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/db/test_queries.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/db/ tests/db/
git commit -m "feat: add database connection and query functions

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 3: Parameter Plugin System

### Task 3.1: Create Base Parameter Class

**Files:**
- Create: `oo_automator/parameters/base.py`
- Test: `tests/parameters/test_base.py`

**Step 1: Write the failing test**

```python
# tests/parameters/test_base.py
import pytest
from dataclasses import dataclass
from oo_automator.parameters.base import (
    Parameter,
    ParameterConfig,
    IntField,
    FloatField,
    ChoiceField,
    TimeField,
)


class MockParameter(Parameter):
    name = "mock"
    display_name = "Mock Parameter"
    description = "A mock parameter for testing"
    selectors = {"input": "input#mock"}

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField("start", label="Start", default=0, min_val=0, max_val=100),
                IntField("end", label="End", default=10, min_val=0, max_val=100),
            ]
        )

    def generate_values(self, config: dict) -> list:
        return list(range(config["start"], config["end"] + 1))

    async def set_value(self, page, value) -> bool:
        return True

    async def verify_value(self, page, value) -> bool:
        return True


def test_parameter_config_fields():
    param = MockParameter()
    config = param.configure()

    assert len(config.fields) == 2
    assert config.fields[0].name == "start"
    assert config.fields[1].name == "end"


def test_parameter_generate_values():
    param = MockParameter()
    values = param.generate_values({"start": 5, "end": 10})

    assert values == [5, 6, 7, 8, 9, 10]


def test_int_field():
    field = IntField("delta", label="Delta", default=15, min_val=1, max_val=100)
    assert field.name == "delta"
    assert field.default == 15
    assert field.validate(50) is True
    assert field.validate(0) is False
    assert field.validate(101) is False


def test_float_field():
    field = FloatField("ratio", label="Ratio", default=0.5, min_val=0.0, max_val=1.0)
    assert field.validate(0.5) is True
    assert field.validate(-0.1) is False


def test_choice_field():
    field = ChoiceField(
        "apply_to",
        label="Apply To",
        choices=["both", "put_only", "call_only"],
        default="both"
    )
    assert field.validate("both") is True
    assert field.validate("invalid") is False


def test_time_field():
    field = TimeField("entry_time", label="Entry Time", default="09:30")
    assert field.validate("09:30") is True
    assert field.validate("25:00") is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/parameters/test_base.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write the implementation**

```python
# oo_automator/parameters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from playwright.async_api import Page
import re


@dataclass
class FieldBase:
    """Base class for configuration fields."""
    name: str
    label: str
    description: str = ""
    required: bool = True

    def validate(self, value: Any) -> bool:
        """Validate field value. Override in subclasses."""
        return True


@dataclass
class IntField(FieldBase):
    """Integer input field."""
    default: int = 0
    min_val: int = 0
    max_val: int = 100
    step: int = 1

    def validate(self, value: Any) -> bool:
        try:
            val = int(value)
            return self.min_val <= val <= self.max_val
        except (TypeError, ValueError):
            return False


@dataclass
class FloatField(FieldBase):
    """Float input field."""
    default: float = 0.0
    min_val: float = 0.0
    max_val: float = 100.0
    step: float = 0.1

    def validate(self, value: Any) -> bool:
        try:
            val = float(value)
            return self.min_val <= val <= self.max_val
        except (TypeError, ValueError):
            return False


@dataclass
class ChoiceField(FieldBase):
    """Choice/dropdown field."""
    choices: list[str] = field(default_factory=list)
    default: str = ""

    def validate(self, value: Any) -> bool:
        return value in self.choices


@dataclass
class TimeField(FieldBase):
    """Time input field (HH:MM format)."""
    default: str = "09:30"

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, value))


@dataclass
class BoolField(FieldBase):
    """Boolean toggle field."""
    default: bool = False

    def validate(self, value: Any) -> bool:
        return isinstance(value, bool)


@dataclass
class ParameterConfig:
    """Configuration schema for a parameter."""
    fields: list[FieldBase] = field(default_factory=list)

    def get_defaults(self) -> dict:
        """Get default values for all fields."""
        return {f.name: f.default for f in self.fields}

    def validate(self, values: dict) -> tuple[bool, list[str]]:
        """Validate all field values. Returns (is_valid, error_messages)."""
        errors = []
        for f in self.fields:
            if f.name in values:
                if not f.validate(values[f.name]):
                    errors.append(f"Invalid value for {f.label}")
            elif f.required:
                errors.append(f"{f.label} is required")
        return len(errors) == 0, errors


class Parameter(ABC):
    """Base class for all parameters."""

    name: str  # Internal identifier
    display_name: str  # Human-readable name
    description: str  # Help text
    selectors: dict  # UI element selectors

    # Optional: Toggle that must be enabled before this parameter is visible
    requires_toggle: Optional[str] = None
    toggle_selector: Optional[str] = None

    def __init__(self):
        self._config: Optional[dict] = None

    @property
    def config(self) -> dict:
        """Get current configuration."""
        return self._config or {}

    def set_config(self, config: dict) -> None:
        """Set configuration for this parameter."""
        self._config = config

    @abstractmethod
    def configure(self) -> ParameterConfig:
        """Return config schema for CLI/dashboard UI."""
        pass

    @abstractmethod
    def generate_values(self, config: dict) -> list:
        """Generate the list of values to test."""
        pass

    @abstractmethod
    async def set_value(self, page: Page, value: Any) -> bool:
        """Set the parameter value in the UI."""
        pass

    @abstractmethod
    async def verify_value(self, page: Page, value: Any) -> bool:
        """Verify the value was set correctly."""
        pass

    async def ensure_visible(self, page: Page) -> bool:
        """Enable parent toggle if this parameter requires it."""
        if not self.requires_toggle or not self.toggle_selector:
            return True

        toggle = page.locator(self.toggle_selector)
        try:
            is_checked = await toggle.get_attribute("aria-checked")
            if is_checked != "true":
                await toggle.click()
                await page.wait_for_timeout(300)  # Wait for reveal animation
        except Exception:
            return False
        return True

    async def _fill_input(self, page: Page, selector: str, value: Any) -> bool:
        """Helper to fill an input field with retry logic."""
        try:
            locator = page.locator(selector)
            await locator.wait_for(state="visible", timeout=5000)
            await locator.clear()
            await locator.fill(str(value))
            return True
        except Exception:
            return False

    async def _get_input_value(self, page: Page, selector: str) -> Optional[str]:
        """Helper to get current input value."""
        try:
            locator = page.locator(selector)
            return await locator.input_value()
        except Exception:
            return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/parameters/test_base.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/parameters/base.py tests/parameters/test_base.py
git commit -m "feat: add base parameter class with field types

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3.2: Create Delta Parameter Implementation

**Files:**
- Create: `oo_automator/parameters/delta.py`
- Test: `tests/parameters/test_delta.py`

**Step 1: Write the failing test**

```python
# tests/parameters/test_delta.py
import pytest
from oo_automator.parameters.delta import DeltaParameter


def test_delta_parameter_metadata():
    param = DeltaParameter()
    assert param.name == "delta"
    assert param.display_name == "Delta"
    assert "put" in param.selectors
    assert "call" in param.selectors


def test_delta_configure():
    param = DeltaParameter()
    config = param.configure()

    field_names = [f.name for f in config.fields]
    assert "start" in field_names
    assert "end" in field_names
    assert "step" in field_names
    assert "apply_to" in field_names


def test_delta_generate_values_range():
    param = DeltaParameter()
    values = param.generate_values({"start": 5, "end": 15, "step": 5})

    assert values == [5, 10, 15]


def test_delta_generate_values_single():
    param = DeltaParameter()
    values = param.generate_values({"start": 10, "end": 10, "step": 1})

    assert values == [10]


def test_delta_generate_values_default_step():
    param = DeltaParameter()
    config = param.configure()
    defaults = config.get_defaults()
    values = param.generate_values({**defaults, "start": 5, "end": 8})

    assert values == [5, 6, 7, 8]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/parameters/test_delta.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write the implementation**

```python
# oo_automator/parameters/delta.py
from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField, ChoiceField


class DeltaParameter(Parameter):
    """Delta parameter for options selection."""

    name = "delta"
    display_name = "Delta"
    description = "Options delta value for put/call leg selection"

    selectors = {
        "put": [
            "div.inline-flex:has(div.append-label:has-text('±')) input",
            "input[placeholder*='delta']",
        ],
        "call": [
            "div.inline-flex:has(div.append-label:has-text('±')) input",
        ],
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField(
                    "start",
                    label="Start Delta",
                    description="Starting delta value",
                    default=5,
                    min_val=1,
                    max_val=100
                ),
                IntField(
                    "end",
                    label="End Delta",
                    description="Ending delta value",
                    default=50,
                    min_val=1,
                    max_val=100
                ),
                IntField(
                    "step",
                    label="Step",
                    description="Increment between values",
                    default=1,
                    min_val=1,
                    max_val=50
                ),
                ChoiceField(
                    "apply_to",
                    label="Apply To",
                    description="Which legs to apply delta changes",
                    choices=["both", "put_only", "call_only"],
                    default="both"
                ),
            ]
        )

    def generate_values(self, config: dict) -> list:
        """Generate list of delta values to test."""
        start = config.get("start", 5)
        end = config.get("end", 50)
        step = config.get("step", 1)

        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step

        return values

    async def set_value(self, page: Page, value: int) -> bool:
        """Set delta value in the UI."""
        await self.ensure_visible(page)

        apply_to = self.config.get("apply_to", "both")
        success = True

        # Find all delta inputs (legs with ± unit selector)
        delta_inputs = page.locator("div.inline-flex:has(button span:text-is('±')) input")
        count = await delta_inputs.count()

        if count == 0:
            return False

        # Typically: first input is short leg (negative delta), second is long leg (positive offset)
        if apply_to in ["both", "put_only"] and count >= 1:
            success = success and await self._fill_input(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=0",
                value
            )

        if apply_to in ["both", "call_only"] and count >= 2:
            success = success and await self._fill_input(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=1",
                value
            )

        return success

    async def verify_value(self, page: Page, value: int) -> bool:
        """Verify delta value was set correctly."""
        apply_to = self.config.get("apply_to", "both")

        delta_inputs = page.locator("div.inline-flex:has(button span:text-is('±')) input")
        count = await delta_inputs.count()

        if apply_to in ["both", "put_only"] and count >= 1:
            actual = await self._get_input_value(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=0"
            )
            if actual != str(value):
                return False

        if apply_to in ["both", "call_only"] and count >= 2:
            actual = await self._get_input_value(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=1"
            )
            if actual != str(value):
                return False

        return True
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/parameters/test_delta.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/parameters/delta.py tests/parameters/test_delta.py
git commit -m "feat: add delta parameter implementation

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3.3: Create Parameter Auto-Discovery

**Files:**
- Modify: `oo_automator/parameters/__init__.py`
- Test: `tests/parameters/test_discovery.py`

**Step 1: Write the failing test**

```python
# tests/parameters/test_discovery.py
import pytest
from oo_automator.parameters import discover_parameters, get_parameter, PARAMETERS


def test_discover_finds_delta():
    params = discover_parameters()
    assert "delta" in params
    assert params["delta"].name == "delta"


def test_parameters_global_populated():
    assert "delta" in PARAMETERS


def test_get_parameter_by_name():
    param = get_parameter("delta")
    assert param is not None
    assert param.name == "delta"


def test_get_parameter_unknown():
    param = get_parameter("nonexistent")
    assert param is None


def test_all_parameters_have_required_attributes():
    for name, param_class in PARAMETERS.items():
        param = param_class()
        assert hasattr(param, "name")
        assert hasattr(param, "display_name")
        assert hasattr(param, "description")
        assert hasattr(param, "selectors")
        assert callable(getattr(param, "configure"))
        assert callable(getattr(param, "generate_values"))
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/parameters/test_discovery.py -v`
Expected: FAIL with "ImportError"

**Step 3: Write the implementation**

```python
# oo_automator/parameters/__init__.py
"""Parameter plugin system with auto-discovery."""
import importlib
import pkgutil
from pathlib import Path
from typing import Optional

from .base import Parameter, ParameterConfig


def discover_parameters() -> dict[str, type[Parameter]]:
    """Auto-discover all parameter classes in this package."""
    parameters = {}
    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name in ("__init__", "base"):
            continue

        try:
            module = importlib.import_module(f".{module_info.name}", __package__)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, Parameter) and
                    attr is not Parameter and
                    hasattr(attr, "name")):
                    parameters[attr.name] = attr
        except Exception as e:
            print(f"Warning: Failed to load parameter module {module_info.name}: {e}")

    return parameters


def get_parameter(name: str) -> Optional[Parameter]:
    """Get a parameter instance by name."""
    param_class = PARAMETERS.get(name)
    if param_class:
        return param_class()
    return None


def list_parameters() -> list[dict]:
    """List all available parameters with metadata."""
    result = []
    for name, param_class in PARAMETERS.items():
        param = param_class()
        result.append({
            "name": param.name,
            "display_name": param.display_name,
            "description": param.description,
        })
    return result


# Auto-discover on import
PARAMETERS = discover_parameters()

__all__ = [
    "Parameter",
    "ParameterConfig",
    "discover_parameters",
    "get_parameter",
    "list_parameters",
    "PARAMETERS",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/parameters/test_discovery.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/parameters/__init__.py tests/parameters/test_discovery.py
git commit -m "feat: add parameter auto-discovery system

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3.4: Create Additional Core Parameters

**Files:**
- Create: `oo_automator/parameters/profit_target.py`
- Create: `oo_automator/parameters/stop_loss.py`
- Create: `oo_automator/parameters/entry_time.py`
- Test: `tests/parameters/test_core_params.py`

**Step 1: Write the failing test**

```python
# tests/parameters/test_core_params.py
import pytest
from oo_automator.parameters import get_parameter, PARAMETERS


def test_profit_target_exists():
    assert "profit_target" in PARAMETERS
    param = get_parameter("profit_target")
    assert param.display_name == "Profit Target"


def test_profit_target_generate_values():
    param = get_parameter("profit_target")
    values = param.generate_values({"start": 10, "end": 50, "step": 10})
    assert values == [10, 20, 30, 40, 50]


def test_stop_loss_exists():
    assert "stop_loss" in PARAMETERS
    param = get_parameter("stop_loss")
    assert param.display_name == "Stop Loss"


def test_stop_loss_generate_values():
    param = get_parameter("stop_loss")
    values = param.generate_values({"start": 50, "end": 200, "step": 50})
    assert values == [50, 100, 150, 200]


def test_entry_time_exists():
    assert "entry_time" in PARAMETERS
    param = get_parameter("entry_time")
    assert param.display_name == "Entry Time"


def test_entry_time_generate_values():
    param = get_parameter("entry_time")
    values = param.generate_values({
        "start_hour": 9,
        "start_minute": 30,
        "end_hour": 10,
        "end_minute": 30,
        "interval_minutes": 30
    })
    assert "09:30" in values
    assert "10:00" in values
    assert "10:30" in values
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/parameters/test_core_params.py -v`
Expected: FAIL

**Step 3: Write the implementations**

```python
# oo_automator/parameters/profit_target.py
from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField, ChoiceField


class ProfitTargetParameter(Parameter):
    """Profit target percentage parameter."""

    name = "profit_target"
    display_name = "Profit Target"
    description = "Profit target percentage for closing positions"

    selectors = {
        "input": "h3:has-text('Profit & Loss') ~ div label:has-text('Profit Target') ~ div input",
        "unit": "h3:has-text('Profit & Loss') ~ div label:has-text('Profit Target') ~ div button.selectInput--nested",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField(
                    "start",
                    label="Start %",
                    description="Starting profit target percentage",
                    default=10,
                    min_val=1,
                    max_val=500
                ),
                IntField(
                    "end",
                    label="End %",
                    description="Ending profit target percentage",
                    default=100,
                    min_val=1,
                    max_val=500
                ),
                IntField(
                    "step",
                    label="Step",
                    description="Increment between values",
                    default=10,
                    min_val=1,
                    max_val=100
                ),
                ChoiceField(
                    "unit",
                    label="Unit",
                    description="Profit target unit type",
                    choices=["%", "$"],
                    default="%"
                ),
            ]
        )

    def generate_values(self, config: dict) -> list:
        start = config.get("start", 10)
        end = config.get("end", 100)
        step = config.get("step", 10)

        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step
        return values

    async def set_value(self, page: Page, value: int) -> bool:
        return await self._fill_input(page, self.selectors["input"], value)

    async def verify_value(self, page: Page, value: int) -> bool:
        actual = await self._get_input_value(page, self.selectors["input"])
        return actual == str(value)
```

```python
# oo_automator/parameters/stop_loss.py
from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField, ChoiceField


class StopLossParameter(Parameter):
    """Stop loss percentage parameter."""

    name = "stop_loss"
    display_name = "Stop Loss"
    description = "Stop loss percentage for limiting losses"

    selectors = {
        "input": "h3:has-text('Profit & Loss') ~ div label:has-text('Stop Loss') ~ div input",
        "unit": "h3:has-text('Profit & Loss') ~ div label:has-text('Stop Loss') ~ div button.selectInput--nested",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField(
                    "start",
                    label="Start %",
                    description="Starting stop loss percentage",
                    default=50,
                    min_val=1,
                    max_val=1000
                ),
                IntField(
                    "end",
                    label="End %",
                    description="Ending stop loss percentage",
                    default=200,
                    min_val=1,
                    max_val=1000
                ),
                IntField(
                    "step",
                    label="Step",
                    description="Increment between values",
                    default=25,
                    min_val=1,
                    max_val=100
                ),
                ChoiceField(
                    "unit",
                    label="Unit",
                    description="Stop loss unit type",
                    choices=["%", "$"],
                    default="%"
                ),
            ]
        )

    def generate_values(self, config: dict) -> list:
        start = config.get("start", 50)
        end = config.get("end", 200)
        step = config.get("step", 25)

        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step
        return values

    async def set_value(self, page: Page, value: int) -> bool:
        return await self._fill_input(page, self.selectors["input"], value)

    async def verify_value(self, page: Page, value: int) -> bool:
        actual = await self._get_input_value(page, self.selectors["input"])
        return actual == str(value)
```

```python
# oo_automator/parameters/entry_time.py
from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField


class EntryTimeParameter(Parameter):
    """Entry time parameter for trade entry timing."""

    name = "entry_time"
    display_name = "Entry Time"
    description = "Time of day to enter trades"

    selectors = {
        "input": "label:has-text('Entry Time') ~ div input[type='time']",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField(
                    "start_hour",
                    label="Start Hour",
                    description="Starting hour (0-23)",
                    default=9,
                    min_val=0,
                    max_val=23
                ),
                IntField(
                    "start_minute",
                    label="Start Minute",
                    description="Starting minute (0-59)",
                    default=30,
                    min_val=0,
                    max_val=59
                ),
                IntField(
                    "end_hour",
                    label="End Hour",
                    description="Ending hour (0-23)",
                    default=15,
                    min_val=0,
                    max_val=23
                ),
                IntField(
                    "end_minute",
                    label="End Minute",
                    description="Ending minute (0-59)",
                    default=0,
                    min_val=0,
                    max_val=59
                ),
                IntField(
                    "interval_minutes",
                    label="Interval (minutes)",
                    description="Time interval between tests",
                    default=30,
                    min_val=5,
                    max_val=120
                ),
            ]
        )

    def generate_values(self, config: dict) -> list:
        start_hour = config.get("start_hour", 9)
        start_minute = config.get("start_minute", 30)
        end_hour = config.get("end_hour", 15)
        end_minute = config.get("end_minute", 0)
        interval = config.get("interval_minutes", 30)

        values = []
        current_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute

        while current_minutes <= end_minutes:
            hour = current_minutes // 60
            minute = current_minutes % 60
            values.append(f"{hour:02d}:{minute:02d}")
            current_minutes += interval

        return values

    async def set_value(self, page: Page, value: str) -> bool:
        return await self._fill_input(page, self.selectors["input"], value)

    async def verify_value(self, page: Page, value: str) -> bool:
        actual = await self._get_input_value(page, self.selectors["input"])
        return actual == value
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/parameters/test_core_params.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/parameters/*.py tests/parameters/test_core_params.py
git commit -m "feat: add profit_target, stop_loss, entry_time parameters

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 4: Browser Automation

### Task 4.1: Create Selectors Module

**Files:**
- Create: `oo_automator/browser/selectors.py`
- Test: `tests/browser/test_selectors.py`

**Step 1: Write the failing test**

```python
# tests/browser/test_selectors.py
import pytest
from oo_automator.browser.selectors import (
    Selectors,
    get_selector,
    get_result_selectors,
)


def test_selectors_login():
    assert Selectors.LOGIN_EMAIL is not None
    assert Selectors.LOGIN_PASSWORD is not None
    assert Selectors.LOGIN_SUBMIT is not None


def test_selectors_modal():
    assert Selectors.NEW_BACKTEST_BUTTON is not None
    assert Selectors.MODAL_DIALOG is not None
    assert Selectors.RUN_BUTTON is not None


def test_get_selector_by_name():
    selector = get_selector("login_email")
    assert selector is not None


def test_get_result_selectors():
    results = get_result_selectors()
    assert "pl" in results
    assert "cagr" in results
    assert "max_drawdown" in results
    assert "win_percentage" in results
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/browser/test_selectors.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# oo_automator/browser/selectors.py
"""UI selectors for OptionOmega automation.

Selectors are derived from recordings/selectors_expanded.json.
Update this file when OptionOmega UI changes.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Selectors:
    """Static selectors for OptionOmega UI elements."""

    # Login
    LOGIN_EMAIL = "input[type='email'], form div:nth-of-type(1) > input"
    LOGIN_PASSWORD = "input[type='password']"
    LOGIN_SUBMIT = "form button[type='submit'], button:has-text('Sign in')"
    SIGN_IN_BUTTON = "span.btn-primary, text=Sign in"

    # Navigation
    TEST_ROW = "table tbody tr td a"

    # New Backtest Modal
    NEW_BACKTEST_BUTTON = "button:has-text('New Backtest')"
    MODAL_DIALOG = "[id^='headlessui-dialog'], [role='dialog']"
    RUN_BUTTON = "button:has-text('Run')"

    # Date Presets
    DATE_START = "label:has-text('Start Date') ~ input.input"
    DATE_END = "label:has-text('End Date') ~ div input.input"

    # Strategy
    TICKER = "label:has-text('Ticker') ~ div button.selectInput"
    COMMON_STRATEGIES = "label:has-text('Common Strategies') ~ div button.selectInput"

    # Funds
    STARTING_FUNDS = "label:has-text('Starting Funds') ~ div input"
    MARGIN_ALLOCATION = "label:has-text('Margin Allocation % Per Trade') ~ div input"
    MAX_CONTRACTS = "label:has-text('Max Contracts Per Trade') ~ div input"

    # Entry Conditions
    ENTRY_TIME = "label:has-text('Entry Time') ~ div input[type='time']"
    FREQUENCY = "label:has-text('Frequency') ~ div button.selectInput"

    # Profit & Loss
    PROFIT_TARGET = "h3:has-text('Profit & Loss') ~ div label:has-text('Profit Target') ~ div input"
    STOP_LOSS = "h3:has-text('Profit & Loss') ~ div label:has-text('Stop Loss') ~ div input"

    # Misc
    OPENING_COMMISSIONS = "label:has-text('Per Contract Opening Commissions') ~ div input"
    CLOSING_COMMISSIONS = "label:has-text('Per Contract Closing Commissions') ~ div input"
    ENTRY_SLIPPAGE = "label:has-text('Entry Slippage') ~ div input"
    EXIT_SLIPPAGE = "label:has-text('Exit Slippage') ~ div input"


# Result page selectors
RESULT_SELECTORS = {
    "pl": "dt:has-text('P/L') ~ dd",
    "cagr": "dt:has-text('CAGR') ~ dd",
    "max_drawdown": "dt:has-text('Max Drawdown') ~ dd",
    "mar": "dt:has-text('MAR Ratio') ~ dd",
    "win_percentage": "dt:has-text('Win Percentage') ~ dd",
    "total_premium": "dt:has-text('Total Premium') ~ dd",
    "capture_rate": "dt:has-text('Capture Rate') ~ dd",
    "starting_capital": "dt:has-text('Starting Capital') ~ dd",
    "ending_capital": "dt:has-text('Ending Capital') ~ dd",
    "total_trades": "div:has(dt:text-is('Trades')) dd",
    "winners": "dt:has-text('Winners') ~ dd",
    "avg_per_trade": "dt:has-text('Avg Per Trade') ~ dd",
    "avg_winner": "dt:has-text('Avg Winner') ~ dd",
    "avg_loser": "dt:has-text('Avg Loser') ~ dd",
    "max_winner": "dt:has-text('Max Winner') ~ dd",
    "max_loser": "dt:has-text('Max Loser') ~ dd",
    "avg_minutes_in_trade": "dt:has-text('Avg Minutes In Trade') ~ dd",
}

# Toggle selectors for conditional fields
TOGGLE_SELECTORS = {
    "use_vix": "h3:has-text('Entry Conditions') ~ div span:has-text('Use VIX')",
    "use_technical_indicators": "h3:has-text('Entry Conditions') ~ div span:has-text('Use Technical Indicators')",
    "use_gaps": "span:has-text('Use Gaps')",
    "use_intraday_movement": "span:has-text('Use Intraday Movement')",
    "use_early_exit": "span:has-text('Use Early Exit')",
    "use_commissions": "span:has-text('Use Commissions & Fees')",
    "use_slippage": "span:has-text('Use Slippage')",
}


def get_selector(name: str) -> Optional[str]:
    """Get a selector by name."""
    # Check Selectors class first
    attr = name.upper()
    if hasattr(Selectors, attr):
        return getattr(Selectors, attr)

    # Check result selectors
    if name in RESULT_SELECTORS:
        return RESULT_SELECTORS[name]

    # Check toggle selectors
    if name in TOGGLE_SELECTORS:
        return TOGGLE_SELECTORS[name]

    return None


def get_result_selectors() -> dict[str, str]:
    """Get all result page selectors."""
    return RESULT_SELECTORS.copy()


def get_toggle_selectors() -> dict[str, str]:
    """Get all toggle selectors."""
    return TOGGLE_SELECTORS.copy()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/browser/test_selectors.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/browser/selectors.py tests/browser/test_selectors.py
git commit -m "feat: add UI selectors module for OptionOmega

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4.2: Create Browser Actions Module

**Files:**
- Create: `oo_automator/browser/actions.py`
- Test: `tests/browser/test_actions.py`

**Step 1: Write the failing test**

```python
# tests/browser/test_actions.py
import pytest
from oo_automator.browser.actions import (
    parse_currency,
    parse_percentage,
    parse_result_value,
    ResultParser,
)


def test_parse_currency_positive():
    assert parse_currency("$13,376") == 13376.0
    assert parse_currency("$250,000") == 250000.0


def test_parse_currency_negative():
    assert parse_currency("-$155") == -155.0


def test_parse_percentage():
    assert parse_percentage("68.2%") == 68.2
    assert parse_percentage("-1%") == -1.0
    assert parse_percentage("0.9%") == 0.9


def test_parse_result_value_with_lot():
    assert parse_result_value("$21 / lot") == 21.0
    assert parse_result_value("-$155 / lot") == -155.0


def test_parse_result_value_plain():
    assert parse_result_value("652") == 652.0
    assert parse_result_value("154.1") == 154.1


def test_result_parser_all_metrics():
    raw_data = {
        "pl": "$13,376",
        "cagr": "0.9%",
        "max_drawdown": "-1%",
        "mar": "1",
        "win_percentage": "61.7%",
        "total_premium": "$86,720",
        "capture_rate": "15.4%",
        "starting_capital": "$250,000",
        "ending_capital": "$263,376",
        "total_trades": "652",
        "winners": "402",
        "avg_per_trade": "$21 / lot",
        "avg_winner": "$130 / lot",
        "avg_loser": "-$155 / lot",
        "max_winner": "$217 / lot",
        "max_loser": "-$377 / lot",
        "avg_minutes_in_trade": "154.1",
    }

    parsed = ResultParser.parse_all(raw_data)

    assert parsed["pl"] == 13376.0
    assert parsed["cagr"] == 0.9
    assert parsed["max_drawdown"] == -1.0
    assert parsed["total_trades"] == 652
    assert parsed["avg_loser"] == -155.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/browser/test_actions.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# oo_automator/browser/actions.py
"""Browser automation actions for OptionOmega."""
import re
from typing import Any, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .selectors import Selectors, get_result_selectors


def parse_currency(value: str) -> float:
    """Parse currency string like '$13,376' or '-$155' to float."""
    if not value:
        return 0.0
    # Remove currency symbol and commas
    cleaned = re.sub(r'[,$]', '', value.strip())
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_percentage(value: str) -> float:
    """Parse percentage string like '68.2%' to float."""
    if not value:
        return 0.0
    cleaned = value.replace('%', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_result_value(value: str) -> float:
    """Parse result value, handling formats like '$21 / lot' or plain numbers."""
    if not value:
        return 0.0

    # Handle "X / lot" format
    if '/' in value:
        value = value.split('/')[0].strip()

    # Handle currency
    if '$' in value:
        return parse_currency(value)

    # Handle percentage
    if '%' in value:
        return parse_percentage(value)

    # Plain number
    try:
        return float(value.replace(',', '').strip())
    except ValueError:
        return 0.0


class ResultParser:
    """Parse backtest results from OptionOmega."""

    CURRENCY_FIELDS = {
        "pl", "total_premium", "starting_capital", "ending_capital",
        "avg_per_trade", "avg_winner", "avg_loser", "max_winner", "max_loser"
    }

    PERCENTAGE_FIELDS = {
        "cagr", "max_drawdown", "win_percentage", "capture_rate"
    }

    INTEGER_FIELDS = {
        "total_trades", "winners"
    }

    @classmethod
    def parse_all(cls, raw_data: dict[str, str]) -> dict[str, Any]:
        """Parse all result fields from raw string data."""
        parsed = {}

        for key, value in raw_data.items():
            if key in cls.CURRENCY_FIELDS:
                parsed[key] = parse_result_value(value)
            elif key in cls.PERCENTAGE_FIELDS:
                parsed[key] = parse_percentage(value)
            elif key in cls.INTEGER_FIELDS:
                parsed[key] = int(parse_result_value(value))
            else:
                parsed[key] = parse_result_value(value)

        return parsed


async def login(page: Page, email: str, password: str) -> bool:
    """Log in to OptionOmega."""
    try:
        # Click sign in button if on landing page
        sign_in = page.locator(Selectors.SIGN_IN_BUTTON)
        if await sign_in.is_visible():
            await sign_in.click()
            await page.wait_for_load_state("networkidle")

        # Fill credentials
        await page.fill(Selectors.LOGIN_EMAIL, email)
        await page.fill(Selectors.LOGIN_PASSWORD, password)
        await page.click(Selectors.LOGIN_SUBMIT)

        # Wait for navigation
        await page.wait_for_load_state("networkidle")
        return True
    except PlaywrightTimeout:
        return False


async def navigate_to_test(page: Page, url: str) -> bool:
    """Navigate to a specific test URL."""
    try:
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        return True
    except PlaywrightTimeout:
        return False


async def open_new_backtest_modal(page: Page) -> bool:
    """Open the New Backtest modal."""
    try:
        await page.click(Selectors.NEW_BACKTEST_BUTTON)
        await page.wait_for_selector(Selectors.MODAL_DIALOG, timeout=5000)
        await page.wait_for_timeout(300)  # Wait for animation
        return True
    except PlaywrightTimeout:
        return False


async def run_backtest(page: Page) -> bool:
    """Click the Run button and wait for results."""
    try:
        await page.click(Selectors.RUN_BUTTON)
        # Wait for modal to close
        await page.wait_for_selector(Selectors.MODAL_DIALOG, state="hidden", timeout=10000)
        # Wait for results to appear (CAGR metric as indicator)
        await page.wait_for_selector("dt:has-text('CAGR')", timeout=300000)
        return True
    except PlaywrightTimeout:
        return False


async def extract_results(page: Page) -> dict[str, Any]:
    """Extract backtest results from the results page."""
    result_selectors = get_result_selectors()
    raw_data = {}

    for key, selector in result_selectors.items():
        try:
            element = page.locator(selector)
            if await element.is_visible():
                raw_data[key] = await element.text_content()
        except Exception:
            raw_data[key] = None

    return ResultParser.parse_all(raw_data)


async def capture_failure_artifacts(
    page: Page,
    screenshot_path: str,
    html_path: str
) -> dict:
    """Capture screenshot, HTML, and console logs for debugging."""
    artifacts = {}

    try:
        await page.screenshot(path=screenshot_path, full_page=True)
        artifacts["screenshot_path"] = screenshot_path
    except Exception:
        pass

    try:
        html_content = await page.content()
        with open(html_path, "w") as f:
            f.write(html_content)
        artifacts["html_path"] = html_path
    except Exception:
        pass

    return artifacts
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/browser/test_actions.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/browser/actions.py tests/browser/test_actions.py
git commit -m "feat: add browser actions with result parsing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4.3: Create Browser Worker

**Files:**
- Create: `oo_automator/browser/worker.py`
- Test: `tests/browser/test_worker.py`

**Step 1: Write the failing test**

```python
# tests/browser/test_worker.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from oo_automator.browser.worker import BrowserWorker, WorkerState


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


@pytest.mark.asyncio
async def test_worker_context_manager():
    worker = BrowserWorker(worker_id=1, headless=True)

    # Mock playwright
    with patch("oo_automator.browser.worker.async_playwright") as mock_pw:
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_context = AsyncMock()

        mock_pw.return_value.__aenter__.return_value.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        async with worker:
            assert worker.state == WorkerState.IDLE

        # Browser should be closed after context exit
        mock_browser.close.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/browser/test_worker.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# oo_automator/browser/worker.py
"""Browser worker for executing backtest tasks."""
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from .actions import (
    login,
    navigate_to_test,
    open_new_backtest_modal,
    run_backtest,
    extract_results,
    capture_failure_artifacts,
)
from ..parameters import get_parameter


class WorkerState(Enum):
    """Browser worker states."""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class TaskResult:
    """Result of executing a task."""
    success: bool
    task_id: int
    parameter_values: dict
    results: Optional[dict] = None
    error_message: Optional[str] = None
    failure_type: Optional[str] = None
    artifacts: dict = field(default_factory=dict)


class BrowserWorker:
    """Browser worker that executes backtest tasks."""

    def __init__(
        self,
        worker_id: int,
        headless: bool = False,
        base_delay: float = 0.5,
    ):
        self.worker_id = worker_id
        self.headless = headless
        self.base_delay = base_delay

        self.state = WorkerState.IDLE
        self.current_task: Optional[int] = None

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._is_logged_in = False
        self._current_test_url: Optional[str] = None

    async def __aenter__(self):
        """Start browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close browser."""
        self.state = WorkerState.STOPPED
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def page(self) -> Optional[Page]:
        return self._page

    async def ensure_logged_in(self, email: str, password: str, base_url: str) -> bool:
        """Ensure worker is logged in."""
        if self._is_logged_in:
            return True

        await self._page.goto(base_url)
        success = await login(self._page, email, password)
        self._is_logged_in = success
        return success

    async def ensure_on_test(self, test_url: str) -> bool:
        """Ensure worker is on the correct test page."""
        if self._current_test_url == test_url:
            return True

        success = await navigate_to_test(self._page, test_url)
        if success:
            self._current_test_url = test_url
        return success

    async def execute_task(
        self,
        task_id: int,
        test_url: str,
        parameter_values: dict,
        credentials: dict,
        artifacts_dir: str,
    ) -> TaskResult:
        """Execute a single backtest task."""
        self.state = WorkerState.RUNNING
        self.current_task = task_id

        try:
            # Ensure logged in
            if not await self.ensure_logged_in(
                credentials["email"],
                credentials["password"],
                credentials.get("base_url", "https://optionomega.com")
            ):
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Failed to log in",
                    failure_type="session",
                )

            # Navigate to test
            if not await self.ensure_on_test(test_url):
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Failed to navigate to test",
                    failure_type="timing",
                )

            # Open new backtest modal
            if not await open_new_backtest_modal(self._page):
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Failed to open backtest modal",
                    failure_type="modal",
                )

            # Set parameter values
            for param_name, value in parameter_values.items():
                param = get_parameter(param_name)
                if param:
                    if not await param.set_value(self._page, value):
                        return TaskResult(
                            success=False,
                            task_id=task_id,
                            parameter_values=parameter_values,
                            error_message=f"Failed to set {param_name}",
                            failure_type="timing",
                        )
                    await asyncio.sleep(self.base_delay)

            # Run backtest
            if not await run_backtest(self._page):
                artifacts = await capture_failure_artifacts(
                    self._page,
                    f"{artifacts_dir}/task_{task_id}_screenshot.png",
                    f"{artifacts_dir}/task_{task_id}_page.html",
                )
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Backtest timed out",
                    failure_type="timing",
                    artifacts=artifacts,
                )

            # Extract results
            results = await extract_results(self._page)

            self.state = WorkerState.IDLE
            self.current_task = None

            return TaskResult(
                success=True,
                task_id=task_id,
                parameter_values=parameter_values,
                results=results,
            )

        except Exception as e:
            self.state = WorkerState.ERROR

            # Capture failure artifacts
            try:
                artifacts = await capture_failure_artifacts(
                    self._page,
                    f"{artifacts_dir}/task_{task_id}_screenshot.png",
                    f"{artifacts_dir}/task_{task_id}_page.html",
                )
            except Exception:
                artifacts = {}

            return TaskResult(
                success=False,
                task_id=task_id,
                parameter_values=parameter_values,
                error_message=str(e),
                failure_type="browser",
                artifacts=artifacts,
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/browser/test_worker.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/browser/worker.py tests/browser/test_worker.py
git commit -m "feat: add browser worker for task execution

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 5: Run Manager & Orchestration

### Task 5.1: Create Task Queue

**Files:**
- Create: `oo_automator/core/task_queue.py`
- Test: `tests/core/test_task_queue.py`

**Step 1: Write the failing test**

```python
# tests/core/test_task_queue.py
import pytest
import asyncio
from oo_automator.core.task_queue import TaskQueue


@pytest.mark.asyncio
async def test_task_queue_basic():
    queue = TaskQueue()

    await queue.put({"id": 1, "value": "a"})
    await queue.put({"id": 2, "value": "b"})

    assert queue.qsize() == 2

    task1 = await queue.get()
    assert task1["id"] == 1

    task2 = await queue.get()
    assert task2["id"] == 2


@pytest.mark.asyncio
async def test_task_queue_priority():
    queue = TaskQueue()

    await queue.put({"id": 1}, priority=2)
    await queue.put({"id": 2}, priority=1)  # Higher priority (lower number)
    await queue.put({"id": 3}, priority=3)

    task = await queue.get()
    assert task["id"] == 2  # Should get highest priority first


@pytest.mark.asyncio
async def test_task_queue_requeue():
    queue = TaskQueue()

    await queue.put({"id": 1, "attempts": 0})
    task = await queue.get()

    # Requeue with incremented attempts
    task["attempts"] += 1
    await queue.requeue(task)

    requeued = await queue.get()
    assert requeued["attempts"] == 1


def test_task_queue_stats():
    queue = TaskQueue()
    stats = queue.get_stats()

    assert "pending" in stats
    assert "completed" in stats
    assert "failed" in stats
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_task_queue.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# oo_automator/core/task_queue.py
"""Async task queue for managing backtest tasks."""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
import heapq


@dataclass(order=True)
class PrioritizedTask:
    """Task wrapper with priority for heap queue."""
    priority: int
    sequence: int  # For FIFO ordering within same priority
    task: Any = field(compare=False)


class TaskQueue:
    """Async priority queue for backtest tasks."""

    def __init__(self, max_retries: int = 3):
        self._heap: list[PrioritizedTask] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._sequence = 0
        self.max_retries = max_retries

        # Stats
        self._completed = 0
        self._failed = 0

    async def put(self, task: dict, priority: int = 5) -> None:
        """Add a task to the queue."""
        async with self._lock:
            self._sequence += 1
            heapq.heappush(
                self._heap,
                PrioritizedTask(priority, self._sequence, task)
            )
            self._not_empty.notify()

    async def get(self, timeout: Optional[float] = None) -> dict:
        """Get the highest priority task."""
        async with self._not_empty:
            while not self._heap:
                try:
                    await asyncio.wait_for(
                        self._not_empty.wait(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    raise asyncio.QueueEmpty()

            item = heapq.heappop(self._heap)
            return item.task

    async def requeue(self, task: dict, priority: int = 10) -> None:
        """Requeue a failed task with lower priority."""
        attempts = task.get("attempts", 0)
        if attempts < self.max_retries:
            await self.put(task, priority=priority)
        else:
            self._failed += 1

    def qsize(self) -> int:
        """Return number of pending tasks."""
        return len(self._heap)

    def empty(self) -> bool:
        """Return True if queue is empty."""
        return len(self._heap) == 0

    def mark_completed(self) -> None:
        """Mark a task as completed."""
        self._completed += 1

    def mark_failed(self) -> None:
        """Mark a task as permanently failed."""
        self._failed += 1

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            "pending": len(self._heap),
            "completed": self._completed,
            "failed": self._failed,
        }

    async def clear(self) -> None:
        """Clear all pending tasks."""
        async with self._lock:
            self._heap.clear()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_task_queue.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/core/task_queue.py tests/core/test_task_queue.py
git commit -m "feat: add async priority task queue

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5.2: Create Run Manager

**Files:**
- Create: `oo_automator/core/run_manager.py`
- Test: `tests/core/test_run_manager.py`

**Step 1: Write the failing test**

```python
# tests/core/test_run_manager.py
import pytest
from oo_automator.core.run_manager import RunManager, generate_combinations


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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_run_manager.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# oo_automator/core/run_manager.py
"""Run manager for orchestrating backtest execution."""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from itertools import product
from typing import Any, Callable, Optional

from .task_queue import TaskQueue
from ..browser.worker import BrowserWorker, TaskResult


class RunStatus(Enum):
    """Run status states."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


def generate_combinations(config: dict) -> list[dict]:
    """Generate parameter combinations from run config."""
    mode = config.get("mode", "sweep")

    if mode == "sweep":
        # Single parameter sweep
        param_name = config["parameter"]
        values = config.get("values", [])
        return [{param_name: v} for v in values]

    elif mode == "grid":
        # Grid search - all combinations
        parameters = config.get("parameters", {})
        if not parameters:
            return []

        param_names = list(parameters.keys())
        param_values = [parameters[name] for name in param_names]

        combinations = []
        for combo in product(*param_values):
            combinations.append(dict(zip(param_names, combo)))

        return combinations

    elif mode == "staged":
        # Staged optimization handled separately
        # This returns first stage combinations
        stages = config.get("stages", [])
        if stages:
            first_stage = stages[0]
            param_name = first_stage["parameter"]
            values = first_stage.get("values", [])
            return [{param_name: v} for v in values]
        return []

    return []


@dataclass
class RunContext:
    """Context for a run."""
    run_id: int
    test_url: str
    config: dict
    credentials: dict
    artifacts_dir: str
    on_task_complete: Optional[Callable] = None
    on_run_complete: Optional[Callable] = None


class RunManager:
    """Manages execution of backtest runs."""

    def __init__(
        self,
        max_browsers: int = 2,
        headless: bool = False,
        base_delay: float = 0.5,
    ):
        self.max_browsers = max_browsers
        self.headless = headless
        self.base_delay = base_delay

        self.status = RunStatus.PENDING
        self.active_browsers = 0

        self._queue = TaskQueue()
        self._workers: list[BrowserWorker] = []
        self._worker_tasks: list[asyncio.Task] = []
        self._current_context: Optional[RunContext] = None

        # Stats
        self._total_tasks = 0
        self._completed = 0
        self._failed = 0
        self._started_at: Optional[datetime] = None

    def get_stats(self) -> dict:
        """Get current run statistics."""
        return {
            "status": self.status.value,
            "total_tasks": self._total_tasks,
            "completed": self._completed,
            "failed": self._failed,
            "pending": self._queue.qsize(),
            "active_browsers": self.active_browsers,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }

    async def start_run(self, context: RunContext) -> None:
        """Start a new run."""
        self._current_context = context
        self.status = RunStatus.RUNNING
        self._started_at = datetime.utcnow()

        # Generate task combinations
        combinations = generate_combinations(context.config)
        self._total_tasks = len(combinations)

        # Add tasks to queue
        for i, params in enumerate(combinations):
            await self._queue.put({
                "task_id": i,
                "parameter_values": params,
                "attempts": 0,
            })

        # Start workers
        await self._start_workers()

    async def _start_workers(self) -> None:
        """Start browser workers."""
        num_workers = min(self.max_browsers, self._total_tasks)

        for i in range(num_workers):
            worker = BrowserWorker(
                worker_id=i,
                headless=self.headless,
                base_delay=self.base_delay,
            )
            self._workers.append(worker)
            task = asyncio.create_task(self._worker_loop(worker))
            self._worker_tasks.append(task)
            self.active_browsers += 1

    async def _worker_loop(self, worker: BrowserWorker) -> None:
        """Worker loop for processing tasks."""
        async with worker:
            while self.status == RunStatus.RUNNING:
                try:
                    task = await self._queue.get(timeout=1.0)
                except asyncio.QueueEmpty:
                    if self._queue.empty():
                        break
                    continue

                # Execute task
                result = await worker.execute_task(
                    task_id=task["task_id"],
                    test_url=self._current_context.test_url,
                    parameter_values=task["parameter_values"],
                    credentials=self._current_context.credentials,
                    artifacts_dir=self._current_context.artifacts_dir,
                )

                # Handle result
                if result.success:
                    self._completed += 1
                    self._queue.mark_completed()
                else:
                    task["attempts"] += 1
                    if task["attempts"] < 3:
                        await self._queue.requeue(task)
                    else:
                        self._failed += 1
                        self._queue.mark_failed()

                # Callback
                if self._current_context.on_task_complete:
                    await self._current_context.on_task_complete(result)

        self.active_browsers -= 1

    async def pause(self) -> None:
        """Pause the run."""
        self.status = RunStatus.PAUSED

    async def resume(self) -> None:
        """Resume a paused run."""
        if self.status == RunStatus.PAUSED:
            self.status = RunStatus.RUNNING
            await self._start_workers()

    async def stop(self) -> None:
        """Stop the run."""
        self.status = RunStatus.COMPLETED
        for task in self._worker_tasks:
            task.cancel()

        if self._current_context and self._current_context.on_run_complete:
            await self._current_context.on_run_complete(self.get_stats())

    async def wait_for_completion(self) -> dict:
        """Wait for all tasks to complete."""
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self.status = RunStatus.COMPLETED
        return self.get_stats()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_run_manager.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add oo_automator/core/run_manager.py tests/core/test_run_manager.py
git commit -m "feat: add run manager for orchestrating backtest execution

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 6: CLI Interface

### Task 6.1: Create Interactive Run Command

**Files:**
- Create: `oo_automator/cli/run.py`
- Modify: `oo_automator/main.py`

**Step 1: Create the run CLI module**

```python
# oo_automator/cli/run.py
"""Interactive run command for OO Automator."""
import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich.panel import Panel

from ..db.connection import get_engine, init_db, get_session
from ..db.queries import (
    get_or_create_test,
    get_recent_tests,
    find_test_by_name_or_url,
    create_run,
    create_tasks_for_run,
)
from ..parameters import list_parameters, get_parameter
from ..core.run_manager import RunManager, RunContext, generate_combinations

console = Console()
app = typer.Typer()


def show_recent_tests(session) -> list:
    """Display recent tests and return them."""
    tests = get_recent_tests(session, limit=5)

    if tests:
        console.print("\n[bold]Recent tests:[/bold]")
        for i, test in enumerate(tests, 1):
            name = test.name or "(unnamed)"
            last_run = test.last_run_at.strftime("%Y-%m-%d") if test.last_run_at else "never"
            console.print(f"  [{i}] {name} - last run: {last_run}")
            console.print(f"      [dim]{test.url}[/dim]")

    return tests


def select_test(session) -> tuple[str, Optional[str]]:
    """Interactive test selection."""
    recent = show_recent_tests(session)

    console.print()
    query = Prompt.ask(
        "Enter test URL, name, or number",
        default="1" if recent else ""
    )

    # Check if it's a number selection
    if query.isdigit() and recent:
        idx = int(query) - 1
        if 0 <= idx < len(recent):
            return recent[idx].url, recent[idx].name

    # Check if it's a URL
    if query.startswith("http"):
        name = Prompt.ask("Name this test (optional)", default="")
        return query, name if name else None

    # Try to find by name
    test = find_test_by_name_or_url(session, query)
    if test:
        return test.url, test.name

    # Treat as new URL
    console.print("[yellow]Test not found. Treating as new URL.[/yellow]")
    return query, None


def select_mode() -> str:
    """Select test mode."""
    console.print("\n[bold]Test mode:[/bold]")
    console.print("  [1] Single parameter sweep")
    console.print("  [2] Grid search (multiple parameters)")
    console.print("  [3] Staged optimization")

    choice = IntPrompt.ask("Select mode", default=1)
    modes = {1: "sweep", 2: "grid", 3: "staged"}
    return modes.get(choice, "sweep")


def select_parameters() -> list[str]:
    """Select parameters to test."""
    params = list_parameters()

    console.print("\n[bold]Available parameters:[/bold]")
    for i, p in enumerate(params, 1):
        console.print(f"  [{i}] {p['display_name']} - {p['description']}")

    selection = Prompt.ask("Select parameter(s) (comma-separated numbers)")

    indices = [int(x.strip()) - 1 for x in selection.split(",")]
    return [params[i]["name"] for i in indices if 0 <= i < len(params)]


def configure_parameter(param_name: str) -> dict:
    """Configure a parameter interactively."""
    param = get_parameter(param_name)
    if not param:
        return {}

    config_schema = param.configure()
    config = {}

    console.print(f"\n[bold]{param.display_name} configuration:[/bold]")

    for field in config_schema.fields:
        if hasattr(field, 'choices'):
            console.print(f"  Options: {', '.join(field.choices)}")
            value = Prompt.ask(f"  {field.label}", default=str(field.default))
        elif hasattr(field, 'min_val'):
            value = IntPrompt.ask(
                f"  {field.label} ({field.min_val}-{field.max_val})",
                default=field.default
            )
        else:
            value = Prompt.ask(f"  {field.label}", default=str(field.default))

        config[field.name] = value

    return config


def build_run_config(mode: str, param_names: list[str]) -> dict:
    """Build run configuration interactively."""
    if mode == "sweep":
        param_name = param_names[0]
        param_config = configure_parameter(param_name)

        param = get_parameter(param_name)
        values = param.generate_values(param_config)

        return {
            "mode": "sweep",
            "parameter": param_name,
            "values": values,
            "param_config": param_config,
        }

    elif mode == "grid":
        parameters = {}
        for param_name in param_names:
            param_config = configure_parameter(param_name)
            param = get_parameter(param_name)
            parameters[param_name] = param.generate_values(param_config)

        return {
            "mode": "grid",
            "parameters": parameters,
        }

    return {"mode": mode}


@app.command()
def interactive(
    browsers: int = typer.Option(2, "--browsers", "-b", help="Number of browsers"),
    headless: bool = typer.Option(False, "--headless", help="Run browsers headless"),
):
    """Start an interactive run session."""
    console.print(Panel.fit(
        "[bold blue]OO Automator v2[/bold blue]\n"
        "Interactive Backtesting Automation",
        border_style="blue"
    ))

    # Initialize database
    engine = init_db()
    session = get_session(engine)

    try:
        # Select test
        test_url, test_name = select_test(session)
        test = get_or_create_test(session, test_url, test_name)
        console.print(f"\n[green]✓[/green] Using test: {test.name or test.url}")

        # Select mode
        mode = select_mode()
        console.print(f"[green]✓[/green] Mode: {mode}")

        # Select parameters
        param_names = select_parameters()
        if not param_names:
            console.print("[red]No parameters selected. Exiting.[/red]")
            return

        # Configure parameters
        run_config = build_run_config(mode, param_names)

        # Show summary
        combinations = generate_combinations(run_config)
        console.print(f"\n[bold]Run Summary:[/bold]")
        console.print(f"  Test: {test.name or test.url}")
        console.print(f"  Mode: {mode}")
        console.print(f"  Parameters: {', '.join(param_names)}")
        console.print(f"  Total tests: {len(combinations)}")
        console.print(f"  Browsers: {browsers}")

        if not Confirm.ask("\nStart run?", default=True):
            console.print("[yellow]Run cancelled.[/yellow]")
            return

        # Get credentials
        console.print("\n[bold]Credentials:[/bold]")
        email = Prompt.ask("  Email")
        password = Prompt.ask("  Password", password=True)

        # Create run in database
        run = create_run(session, test.id, mode, run_config)
        create_tasks_for_run(session, run.id, combinations)

        console.print(f"\n[green]✓[/green] Run created: #{run.id}")
        console.print(f"  Dashboard: http://localhost:8000/runs/{run.id}")

        # TODO: Start actual run execution
        console.print("\n[yellow]Run execution not yet implemented.[/yellow]")
        console.print("Use 'oo-automator serve' to start the dashboard.")

    finally:
        session.close()


@app.command()
def quick(
    url: str = typer.Argument(..., help="Test URL"),
    param: str = typer.Option(..., "--param", "-p", help="Parameter to sweep"),
    start: int = typer.Option(..., "--start", "-s", help="Start value"),
    end: int = typer.Option(..., "--end", "-e", help="End value"),
    step: int = typer.Option(1, "--step", help="Step value"),
    browsers: int = typer.Option(2, "--browsers", "-b", help="Number of browsers"),
):
    """Quick run with command-line parameters."""
    console.print(f"Quick run: {param} from {start} to {end}")
    # TODO: Implement quick run
```

**Step 2: Update main.py to include run commands**

```python
# oo_automator/main.py
import typer

from .cli.run import app as run_app

app = typer.Typer(
    name="oo-automator",
    help="OptionOmega backtesting automation with live dashboard",
    add_completion=False,
)

# Add subcommands
app.add_typer(run_app, name="run")


@app.command()
def version():
    """Show version information."""
    from . import __version__
    typer.echo(f"OO Automator v{__version__}")


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", "-p", help="Port to run on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Start the dashboard server."""
    typer.echo(f"Starting dashboard at http://{host}:{port}")
    # TODO: Implement server


if __name__ == "__main__":
    app()
```

**Step 3: Test CLI commands**

Run: `oo-automator --help`
Expected: Shows help with run and serve commands

Run: `oo-automator run --help`
Expected: Shows run subcommands

**Step 4: Commit**

```bash
git add oo_automator/cli/run.py oo_automator/main.py
git commit -m "feat: add interactive CLI run command

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 7: Web Dashboard (Summary)

The remaining tasks for Phase 7 (Web Dashboard) follow the same pattern:

### Task 7.1: Create FastAPI App Structure
- Create `oo_automator/web/app.py` with FastAPI setup
- Create routes for pages and API

### Task 7.2: Create Dashboard Templates
- Create Jinja2 templates in `oo_automator/web/templates/`
- Home page, run detail, new run form

### Task 7.3: Add WebSocket for Live Updates
- Create `oo_automator/web/routes/websocket.py`
- Real-time progress updates

### Task 7.4: Create Static Assets
- CSS styling matching dark theme
- Chart.js integration for visualizations

---

## Phase 8: Integration & Testing

### Task 8.1: Create Integration Test Suite
- End-to-end tests with mock OptionOmega responses

### Task 8.2: Add Configuration Management
- Environment variables for credentials
- Settings file for defaults

### Task 8.3: Final Documentation
- README with setup instructions
- Usage examples

---

## Execution Checklist

- [ ] Phase 1: Project Setup (Tasks 1.1-1.3)
- [ ] Phase 2: Database Layer (Tasks 2.1-2.2)
- [ ] Phase 3: Parameter Plugin System (Tasks 3.1-3.4)
- [ ] Phase 4: Browser Automation (Tasks 4.1-4.3)
- [ ] Phase 5: Run Manager (Tasks 5.1-5.2)
- [ ] Phase 6: CLI Interface (Task 6.1)
- [ ] Phase 7: Web Dashboard (Tasks 7.1-7.4)
- [ ] Phase 8: Integration & Testing (Tasks 8.1-8.3)

---

**Plan complete and saved to `docs/plans/2026-01-07-oo-automator-v2-implementation.md`.**

Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
