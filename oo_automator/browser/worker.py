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
