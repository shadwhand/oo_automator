from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship, JSON, Column
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
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    test: Optional[Test] = Relationship(back_populates="runs")
    tasks: list["Task"] = Relationship(back_populates="run")


class Task(SQLModel, table=True):
    """Individual test tasks."""
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id", index=True)
    parameter_values: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending", index=True)
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
    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))

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
    console_log: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    task: Optional[Task] = Relationship(back_populates="failures")
