"""Run executor for background task execution."""
import asyncio
import logging
import queue
from datetime import datetime, timezone
from typing import Optional
import heapq
import threading

from sqlmodel import select

from ..db.connection import get_engine, get_session
from ..db.models import Run, Task, Result, Failure
from ..db.queries import update_task_status, save_result, save_failure, update_run_status, get_cached_result
from ..browser.worker import BrowserWorker, TaskResult

logger = logging.getLogger(__name__)


class ExecutorTaskQueue:
    """Simple thread-safe priority queue for executor tasks."""

    def __init__(self):
        self._heap: list[tuple[int, int, int, dict]] = []  # (priority, seq, task_id, params)
        self._lock = threading.Lock()
        self._seq = 0
        self._in_progress: set[int] = set()
        self._completed = 0
        self._failed = 0

    def put(self, task_id: int, params: dict, priority: int = 0):
        """Add a task to the queue."""
        with self._lock:
            self._seq += 1
            heapq.heappush(self._heap, (priority, self._seq, task_id, params))

    def get(self) -> tuple[int, dict]:
        """Get the next task (blocking)."""
        with self._lock:
            if not self._heap:
                raise queue.Empty()
            _, _, task_id, params = heapq.heappop(self._heap)
            self._in_progress.add(task_id)
            return task_id, params

    def mark_completed(self, task_id: int):
        """Mark a task as completed."""
        with self._lock:
            self._in_progress.discard(task_id)
            self._completed += 1

    def mark_failed(self, task_id: int):
        """Mark a task as failed."""
        with self._lock:
            self._in_progress.discard(task_id)
            self._failed += 1

    def requeue(self, task_id: int, params: dict, priority: int = 10):
        """Requeue a task with lower priority."""
        with self._lock:
            self._in_progress.discard(task_id)
            self._seq += 1
            heapq.heappush(self._heap, (priority, self._seq, task_id, params))

    def empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return len(self._heap) == 0

    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            return {
                "pending": len(self._heap),
                "in_progress": len(self._in_progress),
                "completed": self._completed,
                "failed": self._failed,
            }


class RunExecutor:
    """Executes a run with browser workers."""

    def __init__(
        self,
        run_id: int,
        email: str,
        password: str,
        num_browsers: int = 2,
        headless: bool = False,
    ):
        self.run_id = run_id
        self.email = email
        self.password = password
        self.num_browsers = num_browsers
        self.headless = headless
        self.queue = ExecutorTaskQueue()
        self.workers: list[BrowserWorker] = []
        self._running = False
        self._update_callback: Optional[callable] = None

    def set_update_callback(self, callback: callable):
        """Set callback for status updates (e.g., WebSocket broadcast)."""
        self._update_callback = callback

    async def _notify_update(self, update: dict):
        """Notify listeners of status update."""
        if self._update_callback:
            try:
                await self._update_callback(self.run_id, update)
            except Exception as e:
                logger.error(f"Error in update callback: {e}")

    async def load_tasks(self):
        """Load pending tasks from database into queue."""
        engine = get_engine()
        session = get_session(engine)

        try:
            # Get run to find test URL
            run_stmt = select(Run).where(Run.id == self.run_id)
            run = session.exec(run_stmt).first()
            if not run:
                raise ValueError(f"Run {self.run_id} not found")

            # Get test URL
            from ..db.models import Test
            test_stmt = select(Test).where(Test.id == run.test_id)
            test = session.exec(test_stmt).first()
            self.test_url = test.url

            # Load pending tasks
            task_stmt = select(Task).where(
                Task.run_id == self.run_id,
                Task.status.in_(["pending", "running"])
            )
            tasks = list(session.exec(task_stmt).all())

            for task in tasks:
                # Priority based on attempts (fewer attempts = higher priority)
                priority = task.attempts
                self.queue.put(task.id, task.parameter_values, priority=priority)

            logger.info(f"Loaded {len(tasks)} tasks for run {self.run_id}")
            return len(tasks)

        finally:
            session.close()

    async def _worker_loop(self, worker_id: int, worker: BrowserWorker):
        """Worker loop that processes tasks from queue."""
        logger.info(f"Worker {worker_id} starting")

        while self._running:
            try:
                # Get next task (with timeout to allow shutdown check)
                try:
                    task_id, params = await asyncio.wait_for(
                        asyncio.to_thread(self.queue.get),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    # Queue empty or error
                    if self.queue.empty():
                        await asyncio.sleep(0.5)
                    continue

                logger.info(f"Worker {worker_id} processing task {task_id}: {params}")

                # Check for cached result before running
                engine = get_engine()
                session = get_session(engine)
                cached_result = None
                try:
                    # Check cache for each parameter in the combination
                    for param_name, param_value in params.items():
                        cached_result = get_cached_result(
                            session, self.test_url, param_name, str(param_value)
                        )
                        if cached_result:
                            break
                finally:
                    session.close()

                if cached_result:
                    # Use cached result instead of running backtest
                    logger.info(f"Using cached result for task {task_id}: {params}")
                    for param_name, param_value in params.items():
                        logger.info(f"Using cached result for {param_name}={param_value}")

                    # Mark task as completed with cached result
                    session = get_session(engine)
                    try:
                        update_task_status(session, task_id, "completed")
                        # Copy relevant fields from cached result to new result
                        result_data = {
                            "pl": cached_result.pl,
                            "cagr": cached_result.cagr,
                            "max_drawdown": cached_result.max_drawdown,
                            "mar": cached_result.mar,
                            "win_percentage": cached_result.win_percentage,
                            "total_premium": cached_result.total_premium,
                            "capture_rate": cached_result.capture_rate,
                            "starting_capital": cached_result.starting_capital,
                            "ending_capital": cached_result.ending_capital,
                            "total_trades": cached_result.total_trades,
                            "winners": cached_result.winners,
                            "avg_per_trade": cached_result.avg_per_trade,
                            "avg_winner": cached_result.avg_winner,
                            "avg_loser": cached_result.avg_loser,
                            "max_winner": cached_result.max_winner,
                            "max_loser": cached_result.max_loser,
                            "avg_minutes_in_trade": cached_result.avg_minutes_in_trade,
                            "raw_data": cached_result.raw_data,
                            "chart_path": cached_result.chart_path,
                            "results_screenshot": cached_result.results_screenshot,
                            "trade_log_csv": cached_result.trade_log_csv,
                            "trade_count": cached_result.trade_count,
                            "summary": cached_result.summary,
                        }
                        save_result(session, task_id, result_data)
                        self.queue.mark_completed(task_id)
                    finally:
                        session.close()

                    await self._notify_update({
                        "type": "task_completed",
                        "task_id": task_id,
                        "params": params,
                        "result": result_data,
                        "cached": True,
                    })
                    continue

                # Update task status to running
                session = get_session(engine)
                try:
                    update_task_status(session, task_id, "running", increment_attempts=True)
                finally:
                    session.close()

                await self._notify_update({
                    "type": "task_started",
                    "task_id": task_id,
                    "params": params,
                })

                # Execute task
                try:
                    result = await worker.execute_task(task_id, params)

                    if result.success:
                        # Save result to database
                        session = get_session(engine)
                        try:
                            update_task_status(session, task_id, "completed")
                            if result.results:
                                save_result(session, task_id, result.results)
                            self.queue.mark_completed(task_id)
                        finally:
                            session.close()

                        await self._notify_update({
                            "type": "task_completed",
                            "task_id": task_id,
                            "params": params,
                            "result": result.results,
                        })
                    else:
                        # Task failed
                        session = get_session(engine)
                        will_retry = False
                        try:
                            task_stmt = select(Task).where(Task.id == task_id)
                            task = session.exec(task_stmt).first()
                            task_attempts = task.attempts if task else 0

                            if task_attempts >= 3:
                                # Max retries reached
                                update_task_status(session, task_id, "failed")
                                self.queue.mark_failed(task_id)
                                if result.error_message:
                                    save_failure(
                                        session,
                                        task_id,
                                        task_attempts,
                                        result.failure_type or "unknown",
                                        result.error_message,
                                    )
                            else:
                                # Requeue for retry
                                update_task_status(session, task_id, "pending")
                                self.queue.requeue(task_id, params, priority=task_attempts)
                                will_retry = True
                        finally:
                            session.close()

                        await self._notify_update({
                            "type": "task_failed",
                            "task_id": task_id,
                            "params": params,
                            "error": result.error_message,
                            "will_retry": will_retry,
                        })

                except Exception as e:
                    logger.error(f"Worker {worker_id} error on task {task_id}: {e}")
                    session = get_session(engine)
                    try:
                        update_task_status(session, task_id, "pending")
                        self.queue.requeue(task_id, params)
                    finally:
                        session.close()

            except Exception as e:
                logger.error(f"Worker {worker_id} loop error: {e}")
                await asyncio.sleep(1)

        logger.info(f"Worker {worker_id} stopped")

    async def execute(self):
        """Execute the run."""
        logger.info(f"Starting execution of run {self.run_id}")

        # Load tasks
        task_count = await self.load_tasks()
        if task_count == 0:
            logger.info(f"No tasks to execute for run {self.run_id}")
            return

        # Update run status
        engine = get_engine()
        session = get_session(engine)
        try:
            update_run_status(session, self.run_id, "running")
        finally:
            session.close()

        await self._notify_update({
            "type": "run_started",
            "run_id": self.run_id,
            "total_tasks": task_count,
        })

        self._running = True

        try:
            # Create browser workers
            for i in range(self.num_browsers):
                worker = BrowserWorker(
                    worker_id=i,
                    email=self.email,
                    password=self.password,
                    test_url=self.test_url,
                    headless=self.headless,
                )
                self.workers.append(worker)

            # Start workers
            async with asyncio.TaskGroup() as tg:
                # Initialize all workers
                for worker in self.workers:
                    await worker.__aenter__()

                # Start worker loops
                worker_tasks = []
                for i, worker in enumerate(self.workers):
                    task = tg.create_task(self._worker_loop(i, worker))
                    worker_tasks.append(task)

                # Wait for queue to be empty
                while self._running:
                    stats = self.queue.get_stats()
                    if stats["pending"] == 0 and stats["in_progress"] == 0:
                        logger.info("All tasks completed")
                        self._running = False
                        break

                    await self._notify_update({
                        "type": "progress",
                        "run_id": self.run_id,
                        "stats": stats,
                    })

                    await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Run {self.run_id} execution error: {e}")
            session = get_session(engine)
            try:
                update_run_status(session, self.run_id, "failed")
            finally:
                session.close()
            raise

        finally:
            self._running = False

            # Cleanup workers
            for worker in self.workers:
                try:
                    await worker.__aexit__(None, None, None)
                except Exception as e:
                    logger.error(f"Error closing worker: {e}")

        # Update run status to completed
        session = get_session(engine)
        try:
            # Check if any tasks failed
            task_stmt = select(Task).where(
                Task.run_id == self.run_id,
                Task.status == "failed"
            )
            failed_tasks = list(session.exec(task_stmt).all())

            if failed_tasks:
                update_run_status(session, self.run_id, "completed")  # Completed with some failures
            else:
                update_run_status(session, self.run_id, "completed")
        finally:
            session.close()

        await self._notify_update({
            "type": "run_completed",
            "run_id": self.run_id,
            "stats": self.queue.get_stats(),
        })

        logger.info(f"Run {self.run_id} execution completed")

    def stop(self):
        """Stop execution."""
        self._running = False


# Global registry of running executors
_active_executors: dict[int, RunExecutor] = {}


def get_executor(run_id: int) -> Optional[RunExecutor]:
    """Get active executor for a run."""
    return _active_executors.get(run_id)


async def start_run_execution(
    run_id: int,
    email: str,
    password: str,
    num_browsers: int = 2,
    headless: bool = False,
    update_callback: Optional[callable] = None,
):
    """Start executing a run in the background."""
    if run_id in _active_executors:
        raise ValueError(f"Run {run_id} is already executing")

    executor = RunExecutor(
        run_id=run_id,
        email=email,
        password=password,
        num_browsers=num_browsers,
        headless=headless,
    )

    if update_callback:
        executor.set_update_callback(update_callback)

    _active_executors[run_id] = executor

    try:
        await executor.execute()
    finally:
        _active_executors.pop(run_id, None)


def stop_run_execution(run_id: int):
    """Stop a running execution."""
    executor = _active_executors.get(run_id)
    if executor:
        executor.stop()
