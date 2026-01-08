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

    def size(self) -> int:
        """Get queue size."""
        with self._lock:
            return len(self._heap)

    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            return {
                "pending": len(self._heap),
                "in_progress": len(self._in_progress),
                "completed": self._completed,
                "failed": self._failed,
            }

    def get_in_progress_tasks(self) -> set[int]:
        """Get set of in-progress task IDs."""
        with self._lock:
            return self._in_progress.copy()


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
        self._paused = False
        self._skip_cache = False  # Set to True for refresh runs
        self._update_callback: Optional[callable] = None
        self._worker_last_activity: dict[int, datetime] = {}
        self._watchdog_task: Optional[asyncio.Task] = None

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

            # Check if this run should skip cache (for refresh runs)
            self._skip_cache = run.config.get("skip_cache", False)
            if self._skip_cache:
                logger.info(f"Run {self.run_id} will skip cache (refresh mode)")

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

    async def _restart_worker(self, worker_id: int) -> Optional[BrowserWorker]:
        """Restart a crashed worker."""
        logger.info(f"Restarting worker {worker_id}...")

        # Close old worker if it exists
        if worker_id < len(self.workers):
            old_worker = self.workers[worker_id]
            try:
                await old_worker.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing old worker {worker_id}: {e}")

        # Create new worker
        try:
            new_worker = BrowserWorker(
                worker_id=worker_id,
                email=self.email,
                password=self.password,
                test_url=self.test_url,
                headless=self.headless,
            )
            await new_worker.__aenter__()
            self.workers[worker_id] = new_worker
            logger.info(f"Worker {worker_id} restarted successfully")
            return new_worker
        except Exception as e:
            logger.error(f"Failed to restart worker {worker_id}: {e}")
            return None

    async def _watchdog_loop(self):
        """Monitor workers and restart stuck ones."""
        STUCK_THRESHOLD = 300  # 5 minutes without activity = stuck

        while self._running and not self._paused:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                current_time = datetime.now()
                for worker_id, last_activity in list(self._worker_last_activity.items()):
                    elapsed = (current_time - last_activity).total_seconds()

                    if elapsed > STUCK_THRESHOLD:
                        logger.warning(f"Worker {worker_id} appears stuck ({elapsed:.0f}s idle)")

                        # Check if there are pending tasks
                        if not self.queue.empty():
                            logger.info(f"Attempting to restart stuck worker {worker_id}")
                            await self._restart_worker(worker_id)
                            self._worker_last_activity[worker_id] = datetime.now()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

    async def _worker_loop(self, worker_id: int, worker: BrowserWorker):
        """Worker loop that processes tasks from queue."""
        logger.info(f"Worker {worker_id} starting")
        self._worker_last_activity[worker_id] = datetime.now()
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 5

        while self._running:
            # Check if paused
            if self._paused:
                await asyncio.sleep(1)
                continue

            try:
                # Update activity timestamp
                self._worker_last_activity[worker_id] = datetime.now()

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

                # Check for cached result before running (unless skip_cache is set)
                engine = get_engine()
                cached_result = None

                if not self._skip_cache:
                    session = get_session(engine)
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
                    consecutive_failures = 0
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
                        consecutive_failures = 0
                    else:
                        # Task failed
                        consecutive_failures += 1
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

                        # Check if we need to restart the browser
                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            logger.warning(f"Worker {worker_id} has {consecutive_failures} consecutive failures, restarting browser...")
                            new_worker = await self._restart_worker(worker_id)
                            if new_worker:
                                worker = new_worker
                                consecutive_failures = 0

                except Exception as e:
                    logger.error(f"Worker {worker_id} error on task {task_id}: {e}")
                    consecutive_failures += 1

                    session = get_session(engine)
                    try:
                        update_task_status(session, task_id, "pending")
                        self.queue.requeue(task_id, params)
                    finally:
                        session.close()

                    # Check for browser crash and restart
                    if "browser" in str(e).lower() or "target closed" in str(e).lower():
                        logger.warning(f"Browser crash detected for worker {worker_id}, restarting...")
                        new_worker = await self._restart_worker(worker_id)
                        if new_worker:
                            worker = new_worker
                            consecutive_failures = 0
                        else:
                            # Wait before retrying
                            await asyncio.sleep(10)

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
        self._paused = False

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

                # Start watchdog
                self._watchdog_task = tg.create_task(self._watchdog_loop())

                # Start worker loops
                worker_tasks = []
                for i, worker in enumerate(self.workers):
                    task = tg.create_task(self._worker_loop(i, worker))
                    worker_tasks.append(task)

                # Wait for queue to be empty
                while self._running:
                    if self._paused:
                        await asyncio.sleep(1)
                        continue

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

            # Cancel watchdog
            if self._watchdog_task:
                self._watchdog_task.cancel()

            # Cleanup workers
            for worker in self.workers:
                try:
                    await worker.__aexit__(None, None, None)
                except Exception as e:
                    logger.error(f"Error closing worker: {e}")

        # Update run status to completed (only if not paused)
        if not self._paused:
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

    def pause(self):
        """Pause execution (keeps workers alive but stops processing)."""
        self._paused = True
        logger.info(f"Run {self.run_id} paused")

    def is_paused(self) -> bool:
        """Check if executor is paused."""
        return self._paused

    def is_running(self) -> bool:
        """Check if executor is running."""
        return self._running


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


def pause_run_execution(run_id: int) -> bool:
    """Pause a running execution."""
    executor = _active_executors.get(run_id)
    if executor:
        executor.pause()
        return True
    return False


def is_run_paused(run_id: int) -> bool:
    """Check if a run is paused."""
    executor = _active_executors.get(run_id)
    return executor.is_paused() if executor else False
