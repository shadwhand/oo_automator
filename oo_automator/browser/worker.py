"""Browser worker for executing backtest tasks."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Rate limiting configuration
MIN_REQUEST_DELAY = 6  # Minimum seconds between requests
MAX_REQUESTS_PER_MINUTE = 10

# Module-level variable to track last request time
_last_request_time: datetime | None = None


async def wait_for_rate_limit():
    """Wait if needed to respect rate limits."""
    global _last_request_time

    if _last_request_time is not None:
        elapsed = (datetime.now() - _last_request_time).total_seconds()
        if elapsed < MIN_REQUEST_DELAY:
            wait_time = MIN_REQUEST_DELAY - elapsed
            print(f"Rate limiting: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)

    _last_request_time = datetime.now()

from .actions import (
    login,
    navigate_to_test,
    open_new_backtest_modal,
    run_backtest,
    extract_results,
    extract_full_results,
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
        email: str,
        password: str,
        test_url: str,
        headless: bool = False,
        base_delay: float = 0.5,
        artifacts_dir: str = "./artifacts",
    ):
        self.worker_id = worker_id
        self.email = email
        self.password = password
        self.test_url = test_url
        self.headless = headless
        self.base_delay = base_delay
        self.artifacts_dir = artifacts_dir

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

    async def run_with_retry(self, func: Callable, max_retries: int = 3):
        """Run function with exponential backoff on failure."""
        for attempt in range(max_retries):
            try:
                await wait_for_rate_limit()
                return await func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                print(f"[Worker {self.worker_id}] Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

    async def ensure_logged_in(self, email: str, password: str, base_url: str) -> bool:
        """Ensure worker is logged in."""
        if self._is_logged_in:
            return True

        await self._page.goto(base_url, wait_until="domcontentloaded")
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
        parameter_values: dict,
    ) -> TaskResult:
        """Execute a single backtest task."""
        self.state = WorkerState.RUNNING
        self.current_task = task_id
        print(f"[Worker {self.worker_id}] Starting task {task_id}: {parameter_values}")

        # Apply rate limiting before any OptionOmega interactions
        await wait_for_rate_limit()

        try:
            # Ensure logged in
            print(f"[Worker {self.worker_id}] Ensuring logged in...")
            if not await self.ensure_logged_in(
                self.email,
                self.password,
                "https://optionomega.com/"
            ):
                print(f"[Worker {self.worker_id}] Login failed!")
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Failed to log in",
                    failure_type="session",
                )
            print(f"[Worker {self.worker_id}] Logged in successfully")

            # Navigate to test
            print(f"[Worker {self.worker_id}] Navigating to test: {self.test_url}")
            if not await self.ensure_on_test(self.test_url):
                print(f"[Worker {self.worker_id}] Navigation failed!")
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Failed to navigate to test",
                    failure_type="timing",
                )
            print(f"[Worker {self.worker_id}] On test page")

            # Open new backtest modal
            print(f"[Worker {self.worker_id}] Opening New Backtest modal...")
            if not await open_new_backtest_modal(self._page):
                print(f"[Worker {self.worker_id}] Failed to open modal!")
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Failed to open backtest modal",
                    failure_type="modal",
                )
            print(f"[Worker {self.worker_id}] Modal opened")

            # Set parameter values
            print(f"[Worker {self.worker_id}] Setting parameters...")
            for param_name, value in parameter_values.items():
                param = get_parameter(param_name)
                if param:
                    print(f"[Worker {self.worker_id}] Setting {param_name}={value}")
                    if not await param.set_value(self._page, value):
                        print(f"[Worker {self.worker_id}] Failed to set {param_name}")
                        return TaskResult(
                            success=False,
                            task_id=task_id,
                            parameter_values=parameter_values,
                            error_message=f"Failed to set {param_name}",
                            failure_type="timing",
                        )
                    await asyncio.sleep(self.base_delay)

            # Run backtest
            print(f"[Worker {self.worker_id}] Running backtest...")
            if not await run_backtest(self._page):
                print(f"[Worker {self.worker_id}] Backtest timed out!")
                artifacts = await capture_failure_artifacts(
                    self._page,
                    f"{self.artifacts_dir}/task_{task_id}_screenshot.png",
                    f"{self.artifacts_dir}/task_{task_id}_page.html",
                )
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    parameter_values=parameter_values,
                    error_message="Backtest timed out",
                    failure_type="timing",
                    artifacts=artifacts,
                )

            # Extract results (including chart, trade log, summary)
            print(f"[Worker {self.worker_id}] Extracting full results...")
            results = await extract_full_results(self._page, self.artifacts_dir, task_id)
            print(f"[Worker {self.worker_id}] Task {task_id} completed: {results}")

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
            print(f"[Worker {self.worker_id}] Exception: {e}")

            try:
                artifacts = await capture_failure_artifacts(
                    self._page,
                    f"{self.artifacts_dir}/task_{task_id}_screenshot.png",
                    f"{self.artifacts_dir}/task_{task_id}_page.html",
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
