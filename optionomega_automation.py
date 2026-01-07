"""
Enhanced OptionOmega Backtesting Automation
Multi-browser parallel processing with comprehensive error handling and progress tracking

Requirements:
- selenium
- webdriver-manager (optional, for auto-downloading ChromeDriver)
- undetected-chromedriver (optional, for enhanced stealth)

Install:
pip install selenium webdriver-manager
pip install undetected-chromedriver  # Optional, for better browser stealth
"""

import time
import csv
import json
import getpass
import argparse
import os
import re
import random
import threading
import queue
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Try to import undetected-chromedriver for better stealth support
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

# Global thread-safe variables
results_lock = threading.Lock()
progress_lock = threading.Lock()
in_progress_lock = threading.Lock()
shutdown_event = threading.Event()

# Global results storage
all_results = []
in_progress_tasks = set()


class OptionOmegaWorker:
    """Individual worker for processing backtests in parallel"""
    
    def __init__(self, worker_id, task_queue, debug=False):
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.driver = None
        self.debug = debug
        self.debug_dir = None
        self.backtest_times = []
        self.last_results = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        
        if self.debug:
            self.debug_dir = f"debug_worker_{worker_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(self.debug_dir, exist_ok=True)
            print(f"Worker {worker_id}: Debug mode enabled. Output directory: {self.debug_dir}")
    
    def setup_driver(self, chrome_path=None, base_port=9222):
        """Initialize Chrome driver with unique profile and anti-detection"""
        try:
            options = webdriver.ChromeOptions()
            
            # Unique user data directory and debugging port for this worker
            user_data_dir = f"chrome_worker_{self.worker_id}_{int(time.time())}"
            debug_port = base_port + self.worker_id
            
            options.add_argument(f'--user-data-dir=/tmp/{user_data_dir}')
            options.add_argument(f'--remote-debugging-port={debug_port}')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            
            # Anti-detection measures
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-dev-shm-usage')
            
            if self.debug:
                options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
            
            # Auto-detect Chrome path
            if not chrome_path:
                chrome_path = self._auto_detect_chrome()
            if chrome_path:
                options.binary_location = chrome_path
            
            # Initialize driver
            self._initialize_driver(options)
            
            # Apply stealth scripts
            self._apply_stealth_scripts()
            
            print(f"Worker {self.worker_id}: ChromeDriver initialized (port {debug_port})")
            return True
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to setup driver: {e}")
            return False
    
    def _auto_detect_chrome(self):
        """Auto-detect Chrome installation path"""
        import platform
        
        system = platform.system()
        paths = {
            "Darwin": [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ],
            "Windows": [
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
            ],
            "Linux": [
                "/usr/bin/google-chrome",
                "/usr/bin/chromium"
            ]
        }
        
        for path in paths.get(system, []):
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                return expanded_path
        return None
    
    def _initialize_driver(self, options):
        """Initialize the webdriver with fallback options"""
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except ImportError:
            self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            raise e
        
        try:
            self.driver.maximize_window()
        except:
            pass
    
    def _apply_stealth_scripts(self):
        """Apply JavaScript to make browser less detectable"""
        try:
            if not hasattr(self.driver, 'execute_cdp_cmd'):
                return
            
            # Override navigator properties
            stealth_scripts = [
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
                "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});",
                "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});",
                "window.chrome = {runtime: {}};"
            ]
            
            for script in stealth_scripts:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': script})
                
        except Exception as e:
            print(f"Worker {self.worker_id}: Could not apply stealth scripts: {e}")
    
    def perform_login(self, username, password):
        """Automated login with provided credentials"""
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # Find username field
            username_field = self._find_username_field(wait)
            if not username_field:
                return False
            
            username_field.clear()
            username_field.send_keys(username)
            
            # Find password field
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit login
            self._submit_login(password_field)
            
            # Verify success
            time.sleep(3)
            return self._verify_login_success()
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Login error: {e}")
            return False
    
    def _find_username_field(self, wait):
        """Find username/email input field"""
        selectors = [
            "input[type='email']",
            "input[type='text'][name*='email']",
            "input[type='text'][name*='user']",
            "input[type='text']:first-of-type"
        ]
        
        for selector in selectors:
            try:
                field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                if field and field.is_displayed():
                    return field
            except:
                continue
        return None
    
    def _submit_login(self, password_field):
        """Submit login form"""
        for selector in ["button[type='submit']", "input[type='submit']"]:
            try:
                button = self.driver.find_element(By.CSS_SELECTOR, selector)
                if button.is_displayed():
                    button.click()
                    return True
            except:
                continue
        
        password_field.submit()
        return True
    
    def _verify_login_success(self):
        """Check if login was successful"""
        current_url = self.driver.current_url.lower()
        if 'login' not in current_url and 'signin' not in current_url:
            return True
        
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if any(error in page_text for error in ["invalid", "incorrect", "failed"]):
                return False
        except:
            pass
        
        return False
    
    def validate_test_url(self, test_url, max_retries=3):
        """Validate test URL and handle dashboard redirects"""
        for attempt in range(max_retries):
            try:
                self.driver.get(test_url)
                time.sleep(3)
                
                current_url = self.driver.current_url.lower()
                
                # Check if redirected to dashboard
                if 'dashboard/tests' in current_url:
                    print(f"Worker {self.worker_id}: Redirected to dashboard, reloading test URL (attempt {attempt + 1})")
                    continue
                
                # Check for system dialog about tests not being completed
                try:
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "tests cannot be completed" in page_text or "system maintenance" in page_text:
                        print(f"Worker {self.worker_id}: System maintenance detected, retrying...")
                        time.sleep(10)
                        continue
                except:
                    pass
                
                # Look for New Backtest button to confirm we're on the right page
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//button[contains(., 'New Backtest')]"))
                    )
                    print(f"Worker {self.worker_id}: Test page validated successfully")
                    return True
                except:
                    print(f"Worker {self.worker_id}: New Backtest button not found, retrying...")
                    continue
                    
            except Exception as e:
                print(f"Worker {self.worker_id}: URL validation error: {e}")
                time.sleep(5)
        
        print(f"Worker {self.worker_id}: Failed to validate test URL after {max_retries} attempts")
        return False
    
    def run_single_test(self, time_str, delay_seconds=1, default_timeout=300):
        """Execute a single backtest for given time"""
        try:
            print(f"Worker {self.worker_id}: Running test for {time_str}")
            
            # Capture baseline results
            previous_results = self.extract_results()
            
            # Execute test sequence
            if not self.click_new_backtest():
                # Try refreshing and retry once
                print(f"Worker {self.worker_id}: Refreshing page and retrying...")
                self.driver.refresh()
                time.sleep(5)
                if not self.click_new_backtest():
                    raise Exception("Failed to click New Backtest after refresh")
            
            time.sleep(2)
            
            if not self.wait_for_dialog():
                raise Exception("Dialog did not open")
            
            if not self.set_entry_time(time_str):
                raise Exception("Failed to set time")
            
            time.sleep(1)
            
            if not self.click_run():
                raise Exception("Failed to click Run")
            
            # Wait for backtest completion with dynamic timeout
            timeout = self._get_estimated_timeout(default_timeout)
            if not self.wait_for_backtest_completion(timeout):
                raise Exception("Backtest did not complete within timeout")
            
            self.wait_for_dialog_close()
            
            # Wait for results to render
            time.sleep(delay_seconds)
            
            # Wait for results to update
            self.wait_for_results_update(previous_results)
            
            # Extract final results
            results = self.extract_results()
            results['entryTime'] = time_str
            results['timestamp'] = datetime.now().isoformat()
            results['worker_id'] = self.worker_id
            
            # Convert percentages to decimals for consistency
            results = self._normalize_results(results)
            
            # Check for duplicates
            if self._is_duplicate(results):
                print(f"Worker {self.worker_id}: Duplicate detected, waiting and retrying...")
                time.sleep(5)
                results = self.extract_results()
                results['entryTime'] = time_str
                results['timestamp'] = datetime.now().isoformat()
                results['worker_id'] = self.worker_id
                results = self._normalize_results(results)
            
            self.last_results = results
            
            # Store results thread-safely
            with results_lock:
                all_results.append(results)
            
            # Reset consecutive failures on success
            self.consecutive_failures = 0
            
            print(f"Worker {self.worker_id}: Test complete - {time_str}: CAGR={results['cagr']:.6f}, MAR={results['mar']:.2f}")
            return True
            
        except Exception as e:
            self.consecutive_failures += 1
            print(f"Worker {self.worker_id}: Test failed for {time_str}: {e}")
            
            # Try to close any open dialogs
            try:
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
            except:
                pass
            
            return False
    
    def _normalize_results(self, results):
        """Convert percentage strings to decimal values"""
        # Ensure all values are properly formatted decimals
        for key in ['cagr', 'maxDrawdown', 'winPercentage', 'captureRate']:
            if key in results:
                value = results[key]
                # If value appears to be a percentage (> 1), convert to decimal
                if abs(value) > 1:
                    results[key] = value / 100.0
        
        return results
    
    def _get_estimated_timeout(self, default=300):
        """Calculate timeout based on previous backtest times"""
        if not self.backtest_times:
            return default
        
        recent_times = self.backtest_times[-3:] if len(self.backtest_times) > 3 else self.backtest_times
        avg_time = sum(recent_times) / len(recent_times)
        return int(avg_time + 30)  # Add 30 second buffer
    
    def _is_duplicate(self, results):
        """Check if results are duplicate of last test with tight tolerance"""
        if not self.last_results:
            return False
        
        tolerance = 0.0001  # Much tighter tolerance for 6 decimal precision
        
        for key in ['cagr', 'maxDrawdown', 'winPercentage', 'captureRate']:
            if abs(self.last_results.get(key, 0) - results.get(key, 0)) > tolerance:
                return False
        
        return True
    
    # [Include all the other methods from the original class: click_new_backtest, set_entry_time, 
    #  click_run, wait_for_dialog, wait_for_backtest_completion, wait_for_dialog_close, 
    #  wait_for_results_update, extract_results, _extract_metric, etc.]
    
    def click_new_backtest(self):
        """Click the New Backtest button with multiple fallback methods"""
        time.sleep(2)
        
        button = self._find_new_backtest_button()
        
        if button:
            self._safe_click(button)
            return True
        
        return False
    
    def _find_new_backtest_button(self):
        """Find New Backtest button using multiple strategies"""
        try:
            return WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.mt-4 > button"))
            )
        except:
            pass
        
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                if "new backtest" in button.text.lower():
                    return button
        except:
            pass
        
        try:
            return self.driver.execute_script("""
                const buttons = document.querySelectorAll('button');
                for (let btn of buttons) {
                    if (btn.textContent.toLowerCase().includes('new backtest')) {
                        return btn;
                    }
                }
                return null;
            """)
        except:
            pass
        
        return None
    
    def set_entry_time(self, time_str):
        """Set the entry time in the dialog"""
        try:
            time_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='time']")
            
            self.driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, time_input, time_str)
            
            return True
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to set time: {e}")
            return False
    
    def click_run(self):
        """Click the Run button in the dialog"""
        time.sleep(1)
        
        button = self._find_run_button()
        
        if button:
            try:
                WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(button))
            except:
                pass
            
            self._safe_click(button)
            
            # Verify click worked
            time.sleep(2)
            try:
                dialog = self.driver.find_element(By.CSS_SELECTOR, "[id^='headlessui-dialog']")
                self._safe_click(button)  # Retry if dialog still present
            except:
                pass  # Dialog gone - good
            
            return True
        
        return False
    
    def _find_run_button(self):
        """Find Run button within dialog"""
        try:
            dialog = self.driver.find_element(By.CSS_SELECTOR, "[role='dialog'], [id^='headlessui-dialog']")
            buttons = dialog.find_elements(By.TAG_NAME, "button")
            if buttons:
                return buttons[-1]  # Run is typically last button
        except:
            pass
        
        try:
            return self.driver.execute_script("""
                const dialog = document.querySelector('[role="dialog"]');
                if (dialog) {
                    const buttons = dialog.querySelectorAll('button');
                    for (let btn of buttons) {
                        if (btn.textContent.trim() === 'Run') {
                            return btn;
                        }
                    }
                }
                return null;
            """)
        except:
            pass
        
        return None
    
    def _safe_click(self, element):
        """Click element with fallback to JavaScript"""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            element.click()
        except:
            self.driver.execute_script("arguments[0].click();", element)
    
    def wait_for_dialog(self, timeout=5):
        """Wait for dialog to appear"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='time']"))
            )
            return True
        except TimeoutException:
            return False
    
    def wait_for_backtest_completion(self, timeout=300):
        """Wait for backtest progress dialog to appear and disappear"""
        try:
            # Wait for progress dialog to appear
            progress_appeared = False
            progress_selectors = [
                "//*[contains(text(), 'Running Backtest')]",
                "//*[contains(text(), 'ETA')]",
                "//*[contains(text(), 'Processing')]",
                "//*[contains(@class, 'animate-spin')]",
                "//div[contains(@role, 'status')]"
            ]
            
            for i in range(15):
                for selector in progress_selectors:
                    try:
                        progress_element = self.driver.find_element(By.XPATH, selector)
                        if progress_element and progress_element.is_displayed():
                            progress_appeared = True
                            break
                    except:
                        continue
                
                if progress_appeared:
                    break
                    
                # Check if dialog closed quickly
                try:
                    self.driver.find_element(By.CSS_SELECTOR, "[id^='headlessui-dialog']")
                except:
                    return True  # Dialog closed - backtest done
                    
                time.sleep(1)
            
            if not progress_appeared:
                time.sleep(2)
                return True
            
            # Wait for progress to complete
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                progress_found = False
                
                for selector in progress_selectors:
                    try:
                        element = self.driver.find_element(By.XPATH, selector)
                        if element and element.is_displayed():
                            progress_found = True
                            break
                    except:
                        continue
                
                if not progress_found:
                    elapsed = int(time.time() - start_time)
                    self.backtest_times.append(elapsed)
                    time.sleep(2)
                    return True
                
                # Check for dashboard redirect during long waits
                if (time.time() - start_time) > 10:
                    current_url = self.driver.current_url.lower()
                    if 'dashboard/tests' in current_url:
                        print(f"Worker {self.worker_id}: Dashboard redirect detected during backtest")
                        return False
                
                time.sleep(0.5)  # Faster polling
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error waiting for backtest: {e}")
            return False
    
    def wait_for_dialog_close(self, timeout=15):
        """Wait for main dialog to close"""
        try:
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[id^='headlessui-dialog']"))
            )
            return True
        except TimeoutException:
            try:
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
                return True
            except:
                return False
    
    def wait_for_results_update(self, previous_results, timeout=45):
        """Wait for results to change from previous values"""
        start_time = time.time()
        time.sleep(1)  # Reduced initial delay
        
        while time.time() - start_time < timeout:
            current_results = self.extract_results()
            
            if self._results_changed(previous_results, current_results):
                time.sleep(1)  # Brief stabilization wait
                return True
            
            time.sleep(0.5)  # Faster polling
        
        return False
    
    def _results_changed(self, old, new, tolerance=0.0001):
        """Check if results have meaningfully changed with tight tolerance"""
        for key in ['cagr', 'maxDrawdown', 'winPercentage', 'captureRate']:
            if abs(new.get(key, 0) - old.get(key, 0)) > tolerance:
                return True
        return False
    
    def extract_results(self):
        """Extract all metrics from current page"""
        data = {
            'cagr': self._extract_metric('CAGR'),
            'maxDrawdown': self._extract_metric('Max Drawdown'),
            'winPercentage': self._extract_metric('Win Percentage'),
            'captureRate': self._extract_metric('Capture Rate')
        }
        
        # Calculate MAR
        if data['maxDrawdown'] != 0:
            data['mar'] = abs(data['cagr'] / data['maxDrawdown'])
        else:
            data['mar'] = 0
        
        return data
    
    def _extract_metric(self, metric_name):
        """Extract a specific metric value"""
        try:
            dt_elements = self.driver.find_elements(By.TAG_NAME, "dt")
            for dt in dt_elements:
                if metric_name in dt.text:
                    parent = dt.find_element(By.XPATH, "..")
                    dd = parent.find_element(By.TAG_NAME, "dd")
                    match = re.search(r'-?\d+\.?\d*', dd.text)
                    if match:
                        return float(match.group())
        except:
            pass
        return 0
    
    def cleanup(self):
        """Clean up worker resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        print(f"Worker {self.worker_id}: Cleaned up")


def worker_thread(worker_id, task_queue, config, credentials):
    """Main worker thread function"""
    worker = OptionOmegaWorker(worker_id, task_queue, debug=config.get('debug', False))
    
    try:
        # Staggered initialization to prevent browser conflicts
        init_delay = random.randint(5, 45)
        print(f"Worker {worker_id}: Initializing in {init_delay} seconds...")
        time.sleep(init_delay)
        
        # Setup browser
        if not worker.setup_driver(config.get('chrome_path'), base_port=9222):
            print(f"Worker {worker_id}: Failed to initialize browser")
            return
        
        # Login
        login_url = config['test_url'].split('/test')[0] + '/login'
        worker.driver.get(login_url)
        time.sleep(3)
        
        if not worker.perform_login(credentials['username'], credentials['password']):
            print(f"Worker {worker_id}: Login failed")
            return
        
        # Validate test URL
        if not worker.validate_test_url(config['test_url']):
            print(f"Worker {worker_id}: Test URL validation failed")
            return
        
        print(f"Worker {worker_id}: Ready to process tasks")
        
        # Process tasks from queue
        while not shutdown_event.is_set():
            try:
                # Get task with timeout
                time_str = task_queue.get(timeout=5)
                
                # Mark task as in progress
                with in_progress_lock:
                    in_progress_tasks.add(time_str)
                
                # Check for consecutive failures
                if worker.consecutive_failures >= worker.max_consecutive_failures:
                    print(f"Worker {worker_id}: Too many consecutive failures, revalidating URL...")
                    if not worker.validate_test_url(config['test_url']):
                        print(f"Worker {worker_id}: URL revalidation failed")
                        break
                    worker.consecutive_failures = 0
                
                # Process the task
                success = worker.run_single_test(
                    time_str, 
                    config.get('delay_seconds', 1), 
                    config.get('backtest_timeout', 300)
                )
                
                if not success:
                    # Return failed task to queue for retry
                    task_queue.put(time_str)
                
                # Mark task as completed
                with in_progress_lock:
                    in_progress_tasks.discard(time_str)
                
                # Mark task done
                task_queue.task_done()
                
                # Brief rest between tasks
                time.sleep(1)
                
            except queue.Empty:
                # No more tasks, but check if others are still working
                if task_queue.empty() and not in_progress_tasks:
                    break
                continue
            except Exception as e:
                print(f"Worker {worker_id}: Unexpected error: {e}")
                break
        
    except Exception as e:
        print(f"Worker {worker_id}: Fatal error: {e}")
    finally:
        worker.cleanup()
        print(f"Worker {worker_id}: Exited")


def validation_worker_thread(task_queue, config, all_times):
    """Thread that monitors for missing times and handles retries"""
    print("Validation worker: Started")
    
    while not shutdown_event.is_set():
        time.sleep(30)  # Check every 30 seconds
        
        # Get currently completed times
        completed_times = set()
        with results_lock:
            completed_times = {result['entryTime'] for result in all_results}
        
        # Find missing times
        missing_times = set(all_times) - completed_times - in_progress_tasks
        
        if missing_times:
            print(f"Validation worker: Found {len(missing_times)} missing times, re-queuing...")
            for time_str in missing_times:
                task_queue.put(time_str)
    
    print("Validation worker: Exited")


def save_progress_periodically(config, all_times):
    """Periodically save progress with backup files"""
    while not shutdown_event.is_set():
        time.sleep(60)  # Save every minute
        
        with progress_lock:
            save_progress_backup(config, all_times)


def save_progress_backup(config, all_times):
    """Save progress with backup"""
    try:
        # Calculate completion percentage
        completion_pct = 0
        if all_times:
            with results_lock:
                completion_pct = len(all_results) / len(all_times) * 100
        
        # Save main progress file
        progress_data = {
            'config': config,
            'completion_percentage': completion_pct,
            'total_tests': len(all_times),
            'completed_tests': len(all_results),
            'timestamp': datetime.now().isoformat(),
            'results': all_results
        }
        
        with open('optionomega_progress.json', 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        # Create backup every 5% completion
        if int(completion_pct) % 5 == 0 and completion_pct > 0:
            backup_filename = f'optionomega_backup_{int(completion_pct)}pct.json'
            with open(backup_filename, 'w') as f:
                json.dump(progress_data, f, indent=2)
        
        # Export CSV backup
        if all_results:
            export_results_to_csv(config, all_results, backup=True)
            
    except Exception as e:
        print(f"Error saving progress: {e}")


def load_user_config():
    """Load or create user configuration"""
    config_file = 'user_config.json'
    user_config = {}
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
        except:
            pass
    
    return user_config


def save_user_config(user_config):
    """Save user configuration"""
    try:
        with open('user_config.json', 'w') as f:
            json.dump(user_config, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save user config: {e}")


def get_credentials():
    """Get login credentials with username persistence"""
    user_config = load_user_config()
    
    # Get username
    saved_username = user_config.get('username', '')
    if saved_username:
        print(f"Saved username: {saved_username}")
        use_saved = input("Use saved username? (y/n): ").strip().lower()
        if use_saved == 'y':
            username = saved_username
        else:
            username = input("Enter username/email: ").strip()
    else:
        username = input("Enter username/email: ").strip()
    
    # Save username for next time
    if username:
        user_config['username'] = username
        save_user_config(user_config)
    
    # Get password (always prompt)
    password = getpass.getpass("Enter password (hidden): ")
    
    return {'username': username, 'password': password}


def extract_test_title(driver):
    """Extract test title from page for filename"""
    try:
        # Try multiple selectors for test title
        title_selectors = [
            "h1",
            "[data-testid='test-title']",
            ".test-title",
            "title"
        ]
        
        for selector in title_selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                title = element.text.strip()
                if title and len(title) > 3:
                    # Sanitize filename
                    title = re.sub(r'[^\w\-_\. ]', '', title)[:50]
                    return title
            except:
                continue
        
        return "UnknownTest"
    except:
        return "UnknownTest"


def export_results_to_csv(config, results, backup=False):
    """Export results to CSV with enhanced filename"""
    if not results:
        return None
    
    try:
        # Extract test info for filename
        test_title = config.get('test_title', 'Test')
        url_part = config['test_url'].split('/')[-1][:10] if config.get('test_url') else 'test'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create filename
        if backup:
            filename = f'{test_title}_{url_part}_backup_{timestamp}.csv'
        else:
            filename = f'{test_title}_{url_part}_{timestamp}.csv'
        
        # Sanitize filename
        filename = re.sub(r'[^\w\-_\.]', '', filename.replace(' ', '_'))
        
        # Write CSV with 6 decimal precision
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Entry Time', 'CAGR', 'Max Drawdown', 
                           'Win Percentage', 'Capture Rate', 'MAR', 'Worker ID', 'Timestamp'])
            
            # Sort results by entry time
            sorted_results = sorted(results, key=lambda x: x['entryTime'])
            
            for row in sorted_results:
                writer.writerow([
                    row['entryTime'],
                    f"{row['cagr']:.6f}",
                    f"{row['maxDrawdown']:.6f}",
                    f"{row['winPercentage']:.6f}",
                    f"{row['captureRate']:.6f}",
                    f"{row['mar']:.6f}",
                    row.get('worker_id', 'N/A'),
                    row.get('timestamp', '')
                ])
        
        if not backup:
            print(f"Results exported to: {filename}")
        return filename
        
    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return None


def generate_time_list(start_time, end_time, interval_minutes):
    """Generate list of test times"""
    times = []
    start_h, start_m = map(int, start_time.split(':'))
    end_h, end_m = map(int, end_time.split(':'))
    
    current_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    
    while current_minutes <= end_minutes:
        hours = current_minutes // 60
        minutes = current_minutes % 60
        times.append(f"{hours:02d}:{minutes:02d}")
        current_minutes += interval_minutes
    
    return times


def load_configuration(args):
    """Load configuration from file and command line"""
    config = {
        'test_url': None,
        'start_time': "10:00",
        'end_time': "15:59",
        'interval_minutes': 1,
        'delay_seconds': 1,
        'backtest_timeout': 300,
        'max_workers': min(4, os.cpu_count() or 4),
        'chrome_path': None,
        'debug': False
    }
    
    # Load from config file
    config_file = args.config if args.config else 'config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
            print(f"Loaded configuration from {config_file}")
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
    
    # Override with command line arguments
    if args.url:
        config['test_url'] = args.url
    if args.start:
        config['start_time'] = args.start
    if args.end:
        config['end_time'] = args.end
    if args.interval:
        config['interval_minutes'] = args.interval
    if args.delay:
        config['delay_seconds'] = args.delay
    if args.timeout:
        config['backtest_timeout'] = args.timeout
    if args.max_workers:
        config['max_workers'] = args.max_workers
    if args.chrome_path:
        config['chrome_path'] = args.chrome_path
    if args.debug:
        config['debug'] = True
    
    return config


def interactive_configuration(config):
    """Interactive configuration with validation"""
    while True:
        print("\n" + "="*60)
        print("ENHANCED OPTIONOMEGA AUTOMATION CONFIGURATION")
        print("="*60)
        print(f"1. Test URL:         {config.get('test_url', 'Not set')}")
        print(f"2. Start Time:       {config['start_time']}")
        print(f"3. End Time:         {config['end_time']}")
        print(f"4. Interval:         {config['interval_minutes']} minutes")
        print(f"5. Delay:            {config['delay_seconds']} seconds")
        print(f"6. Backtest Timeout: {config['backtest_timeout']} seconds")
        print(f"7. Max Workers:      {config['max_workers']}")
        print(f"8. Debug Mode:       {config['debug']}")
        print("="*60)
        
        # Calculate estimated test count and time
        if config.get('test_url'):
            times = generate_time_list(config['start_time'], config['end_time'], config['interval_minutes'])
            total_tests = len(times)
            estimated_time_per_test = (config['backtest_timeout'] + config['delay_seconds'] + 30) / config['max_workers']
            estimated_total_minutes = (total_tests * estimated_time_per_test) / 60
            
            print(f"Estimated: {total_tests} tests, ~{estimated_total_minutes:.1f} minutes with {config['max_workers']} workers")
            print("="*60)
        
        response = input("\nChange parameters? (y/n): ").strip().lower()
        
        if response == 'n':
            break
        elif response == 'y':
            choice = input("\nSelect parameter (1-8, 0 to finish): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                url = input(f"Test URL: ").strip()
                if url and 'optionomega.com' in url:
                    config['test_url'] = url
                else:
                    print("Invalid URL")
            elif choice == '2':
                time_str = input(f"Start time HH:MM: ").strip()
                if time_str and ':' in time_str:
                    try:
                        h, m = map(int, time_str.split(':'))
                        if 0 <= h <= 23 and 0 <= m <= 59:
                            config['start_time'] = f"{h:02d}:{m:02d}"
                        else:
                            print("Invalid time")
                    except:
                        print("Invalid time format")
            elif choice == '3':
                time_str = input(f"End time HH:MM: ").strip()
                if time_str and ':' in time_str:
                    try:
                        h, m = map(int, time_str.split(':'))
                        if 0 <= h <= 23 and 0 <= m <= 59:
                            config['end_time'] = f"{h:02d}:{m:02d}"
                        else:
                            print("Invalid time")
                    except:
                        print("Invalid time format")
            elif choice == '4':
                try:
                    interval = int(input(f"Interval in minutes: "))
                    if 1 <= interval <= 60:
                        config['interval_minutes'] = interval
                    else:
                        print("Interval must be 1-60 minutes")
                except ValueError:
                    print("Invalid number")
            elif choice == '5':
                try:
                    delay = int(input(f"Delay in seconds: "))
                    if 0 <= delay <= 30:
                        config['delay_seconds'] = delay
                    else:
                        print("Delay must be 0-30 seconds")
                except ValueError:
                    print("Invalid number")
            elif choice == '6':
                try:
                    timeout = int(input(f"Backtest timeout in seconds: "))
                    if 60 <= timeout <= 1800:
                        config['backtest_timeout'] = timeout
                    else:
                        print("Timeout must be 60-1800 seconds")
                except ValueError:
                    print("Invalid number")
            elif choice == '7':
                try:
                    workers = int(input(f"Max workers (1-{os.cpu_count() or 4}): "))
                    if 1 <= workers <= (os.cpu_count() or 4):
                        config['max_workers'] = workers
                    else:
                        print(f"Workers must be 1-{os.cpu_count() or 4}")
                except ValueError:
                    print("Invalid number")
            elif choice == '8':
                debug = input(f"Enable debug mode? (y/n): ").lower() == 'y'
                config['debug'] = debug
    
    # Final validation
    if not config.get('test_url'):
        print("\nError: Test URL is required")
        exit(1)
    
    # Confirm start
    times = generate_time_list(config['start_time'], config['end_time'], config['interval_minutes'])
    print(f"\nReady to run {len(times)} tests with {config['max_workers']} parallel workers")
    
    confirm = input("Start automation? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        exit(0)
    
    return config


def main():
    """Main execution function with parallel processing"""
    print("ENHANCED OPTIONOMEGA AUTOMATION v2.0")
    print("Multi-browser parallel processing with comprehensive error handling")
    print("="*80)
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Enhanced OptionOmega Backtesting Automation')
    parser.add_argument('--url', type=str, help='Test URL')
    parser.add_argument('--start', type=str, help='Start time HH:MM')
    parser.add_argument('--end', type=str, help='End time HH:MM')
    parser.add_argument('--interval', type=int, help='Interval in minutes')
    parser.add_argument('--delay', type=int, help='Result rendering delay in seconds')
    parser.add_argument('--timeout', type=int, help='Backtest timeout in seconds')
    parser.add_argument('--max-workers', type=int, help='Maximum worker processes')
    parser.add_argument('--config', type=str, help='Config file path')
    parser.add_argument('--chrome-path', type=str, help='Chrome executable path')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_configuration(args)
    config = interactive_configuration(config)
    
    # Get credentials
    print("\nLOGIN CREDENTIALS")
    print("="*50)
    credentials = get_credentials()
    print("="*50)
    
    # Generate task list
    all_times = generate_time_list(config['start_time'], config['end_time'], config['interval_minutes'])
    task_queue = queue.Queue()
    
    # Populate task queue
    for time_str in all_times:
        task_queue.put(time_str)
    
    print(f"\nStarting automation with {config['max_workers']} workers")
    print(f"Total tests: {len(all_times)}")
    print(f"Time range: {config['start_time']} to {config['end_time']}")
    print(f"Interval: {config['interval_minutes']} minutes")
    print("="*80)
    
    # Start background threads
    threads = []
    
    try:
        # Start progress saving thread
        progress_thread = threading.Thread(target=save_progress_periodically, args=(config, all_times))
        progress_thread.daemon = True
        progress_thread.start()
        
        # Start validation worker
        validation_thread = threading.Thread(target=validation_worker_thread, args=(task_queue, config, all_times))
        validation_thread.daemon = True
        validation_thread.start()
        
        # Start main worker threads
        for worker_id in range(config['max_workers']):
            thread = threading.Thread(
                target=worker_thread, 
                args=(worker_id, task_queue, config, credentials)
            )
            thread.start()
            threads.append(thread)
        
        # Monitor progress
        start_time = time.time()
        last_count = 0
        
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            # Calculate progress
            current_count = len(all_results)
            progress_pct = (current_count / len(all_times)) * 100 if all_times else 0
            
            # Show progress
            if current_count != last_count:
                elapsed_minutes = (time.time() - start_time) / 60
                if current_count > 0:
                    rate_per_minute = current_count / elapsed_minutes
                    eta_minutes = (len(all_times) - current_count) / rate_per_minute if rate_per_minute > 0 else 0
                    print(f"Progress: {current_count}/{len(all_times)} ({progress_pct:.1f}%) - "
                          f"Rate: {rate_per_minute:.1f}/min - ETA: {eta_minutes:.1f}min")
                
                last_count = current_count
                
                # Save progress periodically
                if current_count % max(1, len(all_times) // 20) == 0:
                    save_progress_backup(config, all_times)
            
            # Check if all threads finished
            active_threads = [t for t in threads if t.is_alive()]
            if not active_threads and task_queue.empty():
                break
            
            # Check for stuck threads
            if not active_threads and not task_queue.empty():
                print("Warning: All workers exited but tasks remain. Restarting workers...")
                for worker_id in range(min(2, config['max_workers'])):  # Restart fewer workers
                    thread = threading.Thread(
                        target=worker_thread, 
                        args=(worker_id + 100, task_queue, config, credentials)
                    )
                    thread.start()
                    threads.append(thread)
        
        # Shutdown
        shutdown_event.set()
        
        # Wait for threads to finish
        for thread in threads:
            thread.join(timeout=30)
        
        # Final results
        print("\n" + "="*80)
        print("AUTOMATION COMPLETED!")
        print("="*80)
        print(f"Total tests completed: {len(all_results)}")
        print(f"Total time: {(time.time() - start_time) / 60:.1f} minutes")
        
        if all_results:
            # Final CSV export
            csv_filename = export_results_to_csv(config, all_results)
            print(f"Results saved to: {csv_filename}")
            
            # Summary statistics
            cagr_values = [r['cagr'] for r in all_results]
            if cagr_values:
                avg_cagr = sum(cagr_values) / len(cagr_values)
                max_cagr = max(cagr_values)
                min_cagr = min(cagr_values)
                print(f"CAGR - Avg: {avg_cagr:.6f}, Max: {max_cagr:.6f}, Min: {min_cagr:.6f}")
            
            # Find missing times
            completed_times = {r['entryTime'] for r in all_results}
            missing_times = set(all_times) - completed_times
            if missing_times:
                print(f"Warning: {len(missing_times)} tests may be missing:")
                for time_str in sorted(missing_times)[:10]:  # Show first 10
                    print(f"  - {time_str}")
                if len(missing_times) > 10:
                    print(f"  ... and {len(missing_times) - 10} more")
        
        print("="*80)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user. Saving progress...")
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            export_results_to_csv(config, all_results)
            save_progress_backup(config, all_times)
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            export_results_to_csv(config, all_results)


if __name__ == "__main__":
    main()
