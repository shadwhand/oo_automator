"""Browser automation actions for OptionOmega."""
import re
from typing import Any, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .selectors import Selectors, get_result_selectors


def parse_currency(value: str) -> float:
    """Parse currency string like '$13,376' or '-$155' to float."""
    if not value:
        return 0.0
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

    if '/' in value:
        value = value.split('/')[0].strip()

    if '$' in value:
        return parse_currency(value)

    if '%' in value:
        return parse_percentage(value)

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
        sign_in = page.locator(Selectors.SIGN_IN_BUTTON)
        if await sign_in.is_visible():
            await sign_in.click()
            await page.wait_for_load_state("networkidle")

        await page.fill(Selectors.LOGIN_EMAIL, email)
        await page.fill(Selectors.LOGIN_PASSWORD, password)
        await page.click(Selectors.LOGIN_SUBMIT)
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
        await page.wait_for_timeout(300)
        return True
    except PlaywrightTimeout:
        return False


async def run_backtest(page: Page) -> bool:
    """Click the Run button and wait for results."""
    try:
        await page.click(Selectors.RUN_BUTTON)
        await page.wait_for_selector(Selectors.MODAL_DIALOG, state="hidden", timeout=10000)
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
