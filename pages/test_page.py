"""
Page Object for OptionOmega Test Page.
Encapsulates all interactions with the backtest UI in clean, testable methods.
"""

import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.waiters import (
    wait_clickable, wait_click, wait_visible, wait_present, wait_gone,
    wait_not_present, try_until, safe_click, find_any, find_any_wait
)
from utils.selectors import (
    NEW_BACKTEST_BTN, MODAL_DIALOG, MODAL_OVERLAY, MODAL_CLOSE_BTN, RUN_BTN,
    PROGRESS_ANY, RESULT_CAGR, RESULT_MAX_DRAWDOWN, RESULT_WIN_PERCENTAGE,
    RESULT_CAPTURE_RATE, TRADE_LOG_TAB, TRADE_LOG_DOWNLOAD_BTN
)


class TestPage:
    """
    Page Object for OptionOmega Test Page.
    Provides clean interface for all test page interactions.
    """
    
    def __init__(self, driver, worker_id=None, logger=None):
        self.driver = driver
        self.worker_id = worker_id or 0
        self.logger = logger or logging.getLogger(__name__)
    
    # ========================================================================
    # PAGE NAVIGATION
    # ========================================================================
    
    def open(self, url, max_retries=3):
        """
        Navigate to test URL and verify page loaded correctly.
        
        Args:
            url: Test URL to load
            max_retries: Maximum retry attempts
        
        Returns:
            bool: True if page loaded successfully
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Loading test page (attempt {attempt + 1})")
                self.driver.get(url)
                
                # Wait for New Backtest button to confirm page loaded
                try:
                    find_any_wait(self.driver, NEW_BACKTEST_BTN, timeout=20)
                    self.logger.info("Test page loaded successfully")
                    return True
                except TimeoutException:
                    current_url = self.driver.current_url.lower()
                    
                    # Check for dashboard redirect
                    if 'dashboard' in current_url and '/test/' not in current_url:
                        self.logger.warning("Redirected to dashboard, retrying...")
                        continue
                    
                    # Check for login requirement
                    if 'login' in current_url or 'signin' in current_url:
                        self.logger.error("Login required - authentication failed")
                        return False
                    
                    self.logger.warning(f"New Backtest button not found, retrying...")
                    continue
                    
            except Exception as e:
                self.logger.error(f"Error loading page: {e}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(2)
        
        return False
    
    def refresh_page(self):
        """Refresh the current page and wait for it to stabilize"""
        self.logger.info("Refreshing page")
        self.driver.refresh()
        time.sleep(2)
        find_any_wait(self.driver, NEW_BACKTEST_BTN, timeout=20)
    
    # ========================================================================
    # DIALOG/MODAL MANAGEMENT
    # ========================================================================
    
    def clear_all_dialogs(self):
        """
        Clear any stuck dialogs or overlays.
        More thorough than original implementation.
        """
        try:
            # Send ESC key
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            time.sleep(0.3)
            
            # Find and close visible dialogs
            dialogs = self.driver.find_elements(*MODAL_DIALOG[0])
            for dialog in dialogs:
                if dialog.is_displayed():
                    # Try to find close button
                    for close_selector in MODAL_CLOSE_BTN:
                        try:
                            close_btn = dialog.find_element(*close_selector)
                            if close_btn.is_displayed():
                                safe_click(self.driver, close_btn)
                                wait_gone(self.driver, MODAL_DIALOG[0], timeout=3)
                                break
                        except:
                            continue
                    
                    # If still visible, remove via JavaScript
                    if dialog.is_displayed():
                        try:
                            self.driver.execute_script("arguments[0].remove();", dialog)
                        except:
                            pass
            
            # Remove any overlays
            overlays = self.driver.find_elements(*MODAL_OVERLAY[0])
            for overlay in overlays:
                try:
                    if overlay.is_displayed():
                        self.driver.execute_script("arguments[0].remove();", overlay)
                except:
                    pass
            
            time.sleep(0.3)
            self.logger.debug("Dialogs cleared")
            return True
            
        except Exception as e:
            self.logger.warning(f"Error clearing dialogs: {e}")
            return False
    
    # ========================================================================
    # BACKTEST WORKFLOW
    # ========================================================================
    
    def click_new_backtest(self):
        """
        Click the New Backtest button and wait for modal to open.
        
        Returns:
            bool: True if modal opened successfully
        """
        try:
            self.logger.info("Clicking New Backtest button")
            
            # Clear any stuck dialogs first
            self.clear_all_dialogs()
            
            # Find and click button
            button = find_any_wait(self.driver, NEW_BACKTEST_BTN, timeout=10)
            safe_click(self.driver, button)
            
            # Wait for modal to appear
            wait_present(self.driver, MODAL_DIALOG[0], timeout=10)
            self.logger.info("New Backtest modal opened")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to open New Backtest modal: {e}")
            return False
    
    def wait_for_modal(self, timeout=10):
        """Wait for modal dialog to appear"""
        try:
            wait_present(self.driver, MODAL_DIALOG[0], timeout=timeout)
            return True
        except TimeoutException:
            return False
    
    def click_run(self):
        """
        Click the Run button in the modal and wait for it to close.
        Uses Puppeteer-style click with offset for reliability.
        
        Returns:
            bool: True if run started successfully
        """
        try:
            self.logger.info("Clicking Run button")
            
            # Clear any overlays that might block the click
            time.sleep(0.3)
            
            # Find Run button within modal - target the span element
            run_button = find_any_wait(self.driver, RUN_BTN, timeout=10)
            if not run_button:
                self.logger.error("Run button not found")
                return False
            
            # Scroll into view and wait for it to be stable
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", run_button)
            time.sleep(0.4)
            
            # Try multiple click strategies in order of reliability
            click_success = False
            
            # Strategy 1: JavaScript click with offset (mimics Puppeteer)
            try:
                self.driver.execute_script("""
                    var element = arguments[0];
                    var rect = element.getBoundingClientRect();
                    var clickEvent = new MouseEvent('click', {
                        clientX: rect.left + 6.640625,
                        clientY: rect.top + 10,
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    element.dispatchEvent(clickEvent);
                """, run_button)
                self.logger.debug("Clicked Run button with offset event")
                click_success = True
            except Exception as e:
                self.logger.warning(f"Offset click failed: {e}")
            
            # Strategy 2: Regular JavaScript click
            if not click_success:
                try:
                    self.driver.execute_script("arguments[0].click();", run_button)
                    self.logger.debug("Clicked Run button with JS click")
                    click_success = True
                except Exception as e:
                    self.logger.warning(f"JS click failed: {e}")
            
            # Strategy 3: Selenium click
            if not click_success:
                try:
                    run_button.click()
                    self.logger.debug("Clicked Run button with Selenium")
                    click_success = True
                except Exception as e:
                    self.logger.warning(f"Selenium click failed: {e}")
            
            if not click_success:
                self.logger.error("All click strategies failed")
                return False
            
            # Brief pause to let click register
            time.sleep(0.5)
            
            # Verify click worked by checking if modal is closing
            try:
                wait_gone(self.driver, MODAL_DIALOG[0], timeout=5)
                self.logger.info("Run button clicked successfully, modal closing")
                return True
            except TimeoutException:
                # Modal still there - try one more time with direct button click
                self.logger.warning("Modal still visible after first click attempt")
                
                # Look for the button element itself (not span) as last resort
                try:
                    button_element = self.driver.find_element(By.XPATH, "//div[@role='dialog']//button[contains(., 'Run')]")
                    self.driver.execute_script("arguments[0].click();", button_element)
                    time.sleep(0.5)
                    
                    # Check again
                    try:
                        wait_gone(self.driver, MODAL_DIALOG[0], timeout=3)
                        self.logger.info("Run button clicked on retry")
                        return True
                    except:
                        self.logger.error("Modal did not close after Run click retry")
                        return False
                except Exception as e:
                    self.logger.error(f"Final retry failed: {e}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to click Run button: {e}")
            return False
    
    def debug_run_button(self):
        """Debug helper to inspect Run button structure"""
        try:
            self.logger.info("=== DEBUG: Run Button Inspection ===")
            
            # Find the dialog
            dialog = self.driver.find_element(*MODAL_DIALOG[0])
            
            # Look for all buttons in dialog
            buttons = dialog.find_elements(By.TAG_NAME, "button")
            self.logger.info(f"Found {len(buttons)} buttons in dialog")
            
            for i, btn in enumerate(buttons):
                try:
                    text = btn.text
                    classes = btn.get_attribute('class')
                    role = btn.get_attribute('role')
                    aria_label = btn.get_attribute('aria-label')
                    self.logger.info(f"Button {i}: text='{text}', role='{role}', aria='{aria_label}'")
                    self.logger.debug(f"  Classes: {classes}")
                    
                    # Check for spans inside
                    spans = btn.find_elements(By.TAG_NAME, "span")
                    if spans:
                        self.logger.info(f"  Contains {len(spans)} span(s)")
                        for j, span in enumerate(spans):
                            span_text = span.text
                            span_class = span.get_attribute('class')
                            self.logger.debug(f"    Span {j}: text='{span_text}', class='{span_class}'")
                except Exception as e:
                    self.logger.warning(f"  Error inspecting button {i}: {e}")
            
            # Try to find div.flex-shrink-0
            flex_divs = dialog.find_elements(By.CSS_SELECTOR, "div.flex-shrink-0")
            self.logger.info(f"Found {len(flex_divs)} div.flex-shrink-0 elements")
            
            self.logger.info("=== END DEBUG ===")
            
        except Exception as e:
            self.logger.error(f"Debug failed: {e}")
    
    def wait_for_backtest_start(self, timeout=15):
        """
        Wait for backtest to start (progress indicators appear).
        
        Args:
            timeout: Maximum seconds to wait
        
        Returns:
            bool: True if backtest started
        """
        try:
            self.logger.info("Waiting for backtest to start")
            
            def progress_visible():
                for selector in PROGRESS_ANY:
                    try:
                        elements = self.driver.find_elements(*selector)
                        for elem in elements:
                            if elem.is_displayed():
                                # Validate this is actually progress, not just a spinner
                                text = elem.text.lower() if elem.text else ""
                                if any(word in text for word in ['running', 'eta', 'processing', '%']):
                                    return True
                                # Or if it's an animation element
                                if 'animate' in (elem.get_attribute('class') or ''):
                                    return True
                    except:
                        continue
                return False
            
            # Wait for progress to appear
            result = try_until(self.driver, progress_visible, timeout=timeout, poll=0.5)
            
            if result:
                self.logger.info("Backtest started")
            else:
                self.logger.warning("No progress indicators found")
            
            return result
            
        except Exception as e:
            # Check if backtest completed very quickly
            self.logger.warning(f"Error waiting for start (may have completed quickly): {e}")
            return True  # Assume it started and finished quickly
    
    def wait_for_backtest_complete(self, timeout=300):
        """
        Wait for backtest to complete (progress indicators disappear).
        More reliable than original implementation.
        
        Args:
            timeout: Maximum seconds to wait
        
        Returns:
            bool: True if backtest completed
        """
        try:
            self.logger.info(f"Waiting for backtest to complete (timeout: {timeout}s)")
            start_time = time.time()
            
            consecutive_not_found = 0
            last_log_time = time.time()
            
            while True:
                elapsed = time.time() - start_time
                
                # Check for any progress indicators
                progress_found = False
                for selector in PROGRESS_ANY:
                    try:
                        elements = self.driver.find_elements(*selector)
                        for elem in elements:
                            if elem.is_displayed():
                                # Validate it's actually progress-related
                                text = elem.text.lower() if elem.text else ""
                                elem_class = elem.get_attribute('class') or ""
                                
                                # Skip if this is just UI decoration
                                if any(skip in text for skip in ['new backtest', 'settings', 'parameters']):
                                    continue
                                
                                # Count as progress if it has relevant content
                                if (any(prog in text for prog in ['running', 'eta', 'processing', 'calculating', '%']) or
                                    'animate' in elem_class or 'progressbar' in elem_class.lower()):
                                    progress_found = True
                                    break
                        if progress_found:
                            break
                    except:
                        continue
                
                if not progress_found:
                    consecutive_not_found += 1
                    if consecutive_not_found >= 3:  # 1.5 seconds of no progress
                        self.logger.info(f"Backtest completed in {int(elapsed)}s")
                        time.sleep(1)  # Brief stabilization
                        return True
                else:
                    consecutive_not_found = 0
                    # Log progress occasionally
                    if time.time() - last_log_time > 30:
                        self.logger.info(f"Still processing... ({int(elapsed)}s elapsed)")
                        last_log_time = time.time()
                
                # Check for timeout
                if elapsed > timeout:
                    # Final check before giving up
                    if consecutive_not_found > 0:
                        self.logger.warning(f"Timeout reached but no progress indicators - assuming complete")
                        return True
                    else:
                        self.logger.error(f"Backtest timeout after {int(elapsed)}s")
                        return False
                
                # Check for error conditions (dashboard redirect)
                if elapsed > 10:
                    current_url = self.driver.current_url.lower()
                    if 'dashboard' in current_url and '/test/' not in current_url:
                        self.logger.error("Redirected to dashboard during backtest")
                        return False
                
                time.sleep(0.5)
                
        except Exception as e:
            self.logger.error(f"Error waiting for backtest completion: {e}")
            return False
    
    # ========================================================================
    # RESULTS EXTRACTION
    # ========================================================================
    
    def wait_for_results_ready(self, timeout=20):
        """
        Wait for results to be visible and stable.
        
        Returns:
            bool: True if results are ready
        """
        try:
            # Wait for CAGR result to be present
            find_any_wait(self.driver, RESULT_CAGR, timeout=timeout)
            time.sleep(1)  # Brief stabilization
            return True
        except TimeoutException:
            self.logger.error("Results not ready within timeout")
            return False
    
    def extract_results(self):
        """
        Extract all metric values from the current page.
        
        Returns:
            dict: Dictionary with cagr, maxDrawdown, winPercentage, captureRate, mar
        """
        data = {
            'cagr': self._extract_metric('CAGR', RESULT_CAGR),
            'maxDrawdown': self._extract_metric('Max Drawdown', RESULT_MAX_DRAWDOWN),
            'winPercentage': self._extract_metric('Win Percentage', RESULT_WIN_PERCENTAGE),
            'captureRate': self._extract_metric('Capture Rate', RESULT_CAPTURE_RATE)
        }
        
        # Calculate MAR
        if abs(data['maxDrawdown']) > 0.0001:
            data['mar'] = abs(data['cagr'] / data['maxDrawdown'])
        else:
            data['mar'] = 0
        
        return data
    
    def _extract_metric(self, metric_name, selectors):
        """
        Extract a specific metric value from the page.
        
        Args:
            metric_name: Display name of the metric
            selectors: List of selector tuples to try
        
        Returns:
            float: Metric value or 0 if not found
        """
        import re
        
        try:
            element = find_any(self.driver, selectors, timeout=5)
            if element:
                text = element.text.strip()
                match = re.search(r'-?\d+\.?\d*', text)
                if match:
                    value = float(match.group())
                    self.logger.debug(f"Extracted {metric_name}: {value}")
                    return value
        except Exception as e:
            self.logger.warning(f"Could not extract {metric_name}: {e}")
        
        return 0.0
    
    def wait_for_results_update(self, previous_results, timeout=45):
        """
        Wait for results to change from previous values.
        
        Args:
            previous_results: Dictionary of previous result values
            timeout: Maximum seconds to wait
        
        Returns:
            bool: True if results changed
        """
        start_time = time.time()
        time.sleep(1)  # Initial brief wait
        
        while time.time() - start_time < timeout:
            current_results = self.extract_results()
            
            if self._results_changed(previous_results, current_results):
                self.logger.info("Results updated")
                time.sleep(1)  # Stabilization
                return True
            
            time.sleep(0.5)
        
        self.logger.warning("Results did not update within timeout")
        return False
    
    def _results_changed(self, old, new, tolerance=0.0001):
        """Check if results have meaningfully changed"""
        for key in ['cagr', 'maxDrawdown', 'winPercentage', 'captureRate']:
            if abs(new.get(key, 0) - old.get(key, 0)) > tolerance:
                return True
        return False
    
    # ========================================================================
    # TRADE LOG OPERATIONS
    # ========================================================================
    
    def navigate_to_trade_log(self):
        """
        Navigate to the Trade Log tab.
        
        Returns:
            bool: True if navigation successful
        """
        try:
            self.logger.info("Navigating to Trade Log tab")
            tab = find_any_wait(self.driver, TRADE_LOG_TAB, timeout=10)
            safe_click(self.driver, tab)
            time.sleep(2)  # Allow tab to load
            self.logger.info("Trade Log tab opened")
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate to Trade Log: {e}")
            return False
    
    def click_download_trade_log(self):
        """
        Click the download button for trade log.
        
        Returns:
            bool: True if click successful
        """
        try:
            self.logger.info("Clicking trade log download button")
            
            # Try to find the download button
            download_btn = find_any(self.driver, TRADE_LOG_DOWNLOAD_BTN, timeout=10)
            
            if not download_btn:
                self.logger.error("Download button not found")
                return False
            
            # Click with offset if needed (from Puppeteer script)
            try:
                self.driver.execute_script("""
                    var element = arguments[0];
                    var rect = element.getBoundingClientRect();
                    var clickEvent = new MouseEvent('click', {
                        clientX: rect.left + 9.734375,
                        clientY: rect.top + 11.27734375,
                        bubbles: true,
                        cancelable: true
                    });
                    element.dispatchEvent(clickEvent);
                """, download_btn)
            except:
                # Fallback to regular click
                safe_click(self.driver, download_btn)
            
            self.logger.info("Download button clicked")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to click download button: {e}")
            return False
