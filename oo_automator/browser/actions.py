"""Browser automation actions for OptionOmega."""
import asyncio
import csv
import re
import time
from typing import Any, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .selectors import Selectors, get_result_selectors


async def _scrape_trade_log_table(page: Page, artifacts_dir: str, task_id: int, results: dict):
    """Fallback: Scrape trade log from table if download fails."""
    trades = []
    table = page.locator("table")
    if await table.count() > 0:
        # Get headers
        headers = []
        header_cells = page.locator("table thead th")
        header_count = await header_cells.count()
        for i in range(header_count):
            header_text = await header_cells.nth(i).text_content()
            headers.append(header_text.strip() if header_text else f"col_{i}")

        # Get rows
        rows = page.locator("table tbody tr")
        row_count = await rows.count()
        for i in range(min(row_count, 500)):  # Limit to 500 rows
            row = rows.nth(i)
            cells = row.locator("td")
            cell_count = await cells.count()
            row_data = {}
            for j in range(cell_count):
                cell_text = await cells.nth(j).text_content()
                header = headers[j] if j < len(headers) else f"col_{j}"
                row_data[header] = cell_text.strip() if cell_text else ""
            trades.append(row_data)

        # Save trade log as CSV
        if trades:
            csv_path = f"{artifacts_dir}/task_{task_id}_trades.csv"
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(trades)
            results["trade_log_csv"] = csv_path
            results["trade_count"] = len(trades)
            print(f"Scraped trade log: {len(trades)} trades")


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
        # Wait for page to be ready (use domcontentloaded, networkidle can timeout)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # Click Sign in button to open login modal
        sign_in_btn = page.locator(Selectors.SIGN_IN_BUTTON)
        if await sign_in_btn.count() > 0:
            await sign_in_btn.first.click()
            await page.wait_for_timeout(1500)  # Wait for modal to open

        # Wait for login form to appear - try multiple selectors
        email_input = page.locator("input[type='email']")
        if await email_input.count() == 0:
            email_input = page.locator(Selectors.LOGIN_EMAIL)
        await email_input.wait_for(state="visible", timeout=10000)

        # Fill in credentials
        await email_input.fill(email)

        # Find password input
        password_input = page.locator("input[type='password']")
        if await password_input.count() == 0:
            password_input = page.locator(Selectors.LOGIN_PASSWORD)
        await password_input.fill(password)

        # Click submit - look for submit button in form
        submit_btn = page.locator("form button[type='submit']")
        if await submit_btn.count() == 0:
            submit_btn = page.locator(Selectors.LOGIN_SUBMIT)
        await submit_btn.click()

        # Wait for navigation after login
        await page.wait_for_timeout(3000)

        # Check if we're logged in by looking for sign out or user menu
        logged_in = await page.locator("text=Sign out").count() > 0 or \
                    await page.locator("text=Dashboard").count() > 0 or \
                    "dashboard" in page.url.lower() or \
                    "app." in page.url.lower()

        return logged_in
    except PlaywrightTimeout:
        return False
    except Exception as e:
        print(f"Login error: {e}")
        return False


async def navigate_to_test(page: Page, url: str) -> bool:
    """Navigate to a specific test URL."""
    try:
        await page.goto(url, wait_until="domcontentloaded")
        # Wait for page to settle - some content loads asynchronously
        await page.wait_for_timeout(3000)
        print(f"Navigated to test: {url}")
        return True
    except PlaywrightTimeout:
        print(f"Navigate timeout: {url}")
        return False
    except Exception as e:
        print(f"Navigate error: {e}")
        return False


async def open_new_backtest_modal(page: Page) -> bool:
    """Open the New Backtest modal."""
    try:
        # Wait for page to be fully interactive
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # Wait for button to be visible and clickable
        btn = page.locator(Selectors.NEW_BACKTEST_BUTTON)
        await btn.wait_for(state="visible", timeout=10000)

        # Click and wait for modal
        await btn.click()
        await page.wait_for_selector(Selectors.MODAL_DIALOG, timeout=10000)
        await page.wait_for_timeout(500)
        return True
    except PlaywrightTimeout as e:
        print(f"New Backtest modal timeout: {e}")
        return False
    except Exception as e:
        print(f"New Backtest modal error: {e}")
        return False


async def run_backtest(page: Page, timeout_ms: int = 120000) -> bool:
    """Click the Run button and wait for results."""
    try:
        # Click Run button
        run_btn = page.locator(Selectors.RUN_BUTTON)
        await run_btn.click()

        # Wait for "Running Backtest" popup to appear
        await page.wait_for_timeout(1000)

        # Wait for backtest to complete - look for "Running Backtest" to disappear
        # or for result elements to appear
        running_popup = page.locator("text=Running Backtest")

        # Wait up to timeout_ms for the running popup to disappear
        start_time = time.time()
        while await running_popup.count() > 0:
            if (time.time() - start_time) * 1000 > timeout_ms:
                return False
            await page.wait_for_timeout(2000)

        # Extra wait for results to load
        await page.wait_for_timeout(2000)

        # Check if results appeared
        cagr = page.locator("dt:has-text('CAGR')")
        return await cagr.count() > 0

    except PlaywrightTimeout:
        return False
    except Exception as e:
        print(f"Run backtest error: {e}")
        return False


async def extract_results(page: Page, artifacts_dir: str = "./artifacts", task_id: int = 0) -> dict[str, Any]:
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

    parsed = ResultParser.parse_all(raw_data)

    # Capture chart screenshot
    try:
        chart_path = f"{artifacts_dir}/task_{task_id}_chart.png"
        chart_element = page.locator("canvas").first
        if await chart_element.count() > 0:
            await chart_element.screenshot(path=chart_path)
            parsed["chart_path"] = chart_path
    except Exception as e:
        print(f"Failed to capture chart: {e}")

    return parsed


async def extract_full_results(page: Page, artifacts_dir: str = "./artifacts", task_id: int = 0) -> dict[str, Any]:
    """Extract full backtest results including trade log and summary."""
    import csv
    import os

    os.makedirs(artifacts_dir, exist_ok=True)

    # Get basic metrics
    results = await extract_results(page, artifacts_dir, task_id)

    # Capture full results page screenshot
    try:
        screenshot_path = f"{artifacts_dir}/task_{task_id}_results.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        results["results_screenshot"] = screenshot_path
    except Exception as e:
        print(f"Failed to capture results screenshot: {e}")

    # Extract trade log by downloading CSV directly from OptionOmega
    try:
        # Click Trade Log tab
        trade_log_tab = page.locator("a:has-text('Trade Log'), span:has-text('Trade Log'), button:has-text('Trade Log')")
        if await trade_log_tab.count() > 0:
            await trade_log_tab.first.click()
            await page.wait_for_timeout(1000)

            # Find and click the download/export button
            download_btn = page.locator(
                "button:has-text('Download'), "
                "button:has-text('Export'), "
                "a:has-text('Download'), "
                "a:has-text('Export'), "
                "[aria-label*='download' i], "
                "[aria-label*='export' i], "
                "button svg[class*='download'], "
                "button:has(svg)"  # Button with icon
            )

            if await download_btn.count() > 0:
                # Set up download handler
                csv_path = f"{artifacts_dir}/task_{task_id}_trades.csv"

                async with page.expect_download() as download_info:
                    await download_btn.first.click()

                download = await download_info.value
                await download.save_as(csv_path)

                # Count rows in the downloaded CSV
                try:
                    with open(csv_path, 'r') as f:
                        # Skip header, count data rows
                        lines = f.readlines()
                        trade_count = max(0, len(lines) - 1)  # Subtract header row
                    results["trade_log_csv"] = csv_path
                    results["trade_count"] = trade_count
                    print(f"Downloaded trade log: {trade_count} trades")
                except Exception as e:
                    print(f"Error reading downloaded CSV: {e}")
                    results["trade_log_csv"] = csv_path
            else:
                print("Download button not found, falling back to table scraping")
                # Fallback: scrape table if download button not found
                await _scrape_trade_log_table(page, artifacts_dir, task_id, results)

            # Click back to Summary tab
            summary_tab = page.locator("a:has-text('Summary'), span:has-text('Summary')")
            if await summary_tab.count() > 0:
                await summary_tab.first.click()
                await page.wait_for_timeout(500)

    except Exception as e:
        print(f"Failed to extract trade log: {e}")
        # Try fallback table scraping
        try:
            await _scrape_trade_log_table(page, artifacts_dir, task_id, results)
        except:
            pass

    # Extract summary/strategy description
    try:
        summary_element = page.locator("div.prose, div:has-text('Strategy') p")
        if await summary_element.count() > 0:
            summary_text = await summary_element.first.text_content()
            results["summary"] = summary_text.strip() if summary_text else ""
    except Exception as e:
        print(f"Failed to extract summary: {e}")

    return results


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
