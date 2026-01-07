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
        param_name = config["parameter"]
        values = config.get("values", [])
        return [{param_name: v} for v in values]

    elif mode == "grid":
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

        combinations = generate_combinations(context.config)
        self._total_tasks = len(combinations)

        for i, params in enumerate(combinations):
            await self._queue.put({
                "task_id": i,
                "parameter_values": params,
                "attempts": 0,
            })

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

                result = await worker.execute_task(
                    task_id=task["task_id"],
                    test_url=self._current_context.test_url,
                    parameter_values=task["parameter_values"],
                    credentials=self._current_context.credentials,
                    artifacts_dir=self._current_context.artifacts_dir,
                )

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
