"""
Enhanced OptionOmega Backtesting Automation - Main Script
Now using Parameter Plugin System for cleaner code
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
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Import the parameter plugin system
from parameter_plugin_system import ParameterFactory, BaseParameter
# Import the trade analysis plugin
from trade_analysis_plugin import enhance_results_with_trade_metrics

# Try to import undetected-chromedriver for better stealth support
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

# Global thread-safe variables with task status tracking
results_lock = threading.Lock()
progress_lock = threading.Lock()
in_progress_lock = threading.Lock()
shutdown_event = threading.Event()

# Global results storage with enhanced tracking
all_results = []
all_trade_logs = []  # Separate list for trade log data
in_progress_tasks = set()  # Tasks currently being processed
completed_tasks = set()    # Tasks that finished successfully (test + trade log)
failed_tasks = set()       # Tasks that failed and need retry
duplicate_retests = {}     # Track parameters that have been retested for duplicates

# Test run directory - will be set during initialization
TEST_RUN_DIR = None


class TestRunManager:
    """Manages test run directories and file organization"""
    
    def __init__(self, test_url, parameter_type):
        self.test_url = test_url
        self.parameter_type = parameter_type
        self.test_name = self._extract_test_name()
        self.run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.base_dir = self._create_run_directory()
        
    def _extract_test_name(self):
        """Extract test name from URL or create a meaningful name"""
        try:
            # Try to extract test ID from URL
            if '/test/' in self.test_url:
                test_id = self.test_url.split('/test/')[-1]
                # Clean up any query parameters
                test_id = test_id.split('?')[0].split('#')[0]
                return f"Test_{test_id}"
            else:
                return "UnknownTest"
        except:
            return "UnknownTest"
    
    def _create_run_directory(self):
        """Create organized directory structure for this test run"""
        # Main directory: TestName_ParameterType_Timestamp
        dir_name = f"{self.test_name}_{self.parameter_type}_{self.run_timestamp}"
        # Sanitize directory name
        dir_name = re.sub(r'[^\w\-_]', '', dir_name)
        
        base_path = os.path.join("test_runs", dir_name)
        
        # Create subdirectories
        os.makedirs(base_path, exist_ok=True)
        os.makedirs(os.path.join(base_path, "downloads"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "debug"), exist_ok=True)
        os.makedirs(os.path.join(base_path, "backups"), exist_ok=True)
        
        print(f"Created test run directory: {base_path}")
        return base_path
    
    def get_downloads_dir(self):
        return os.path.join(self.base_dir, "downloads")
    
    def get_debug_dir(self):
        return os.path.join(self.base_dir, "debug")
    
    def get_backups_dir(self):
        return os.path.join(self.base_dir, "backups")
    
    def get_results_file(self, filename):
        return os.path.join(self.base_dir, filename)
    
    def cleanup_temp_files(self):
        """Clean up temporary worker files"""
        try:
            # Clean up any worker-specific temp directories
            for item in os.listdir('.'):
                if item.startswith('downloads_worker_') or item.startswith('chrome_worker_'):
                    if os.path.isdir(item):
                        shutil.rmtree(item)
                    else:
                        os.remove(item)
        except Exception as e:
            print(f"Warning: Could not clean up temp files: {e}")


class OptionOmegaWorker:
    """Individual worker for processing backtests in parallel"""
    
    def __init__(self, worker_id, task_queue, config, debug=False):
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.config = config
        self.driver = None
        self.debug = debug
        self.debug_dir = None
        self.backtest_times = []
        self.last_results = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        self.test_run_manager = config.get('test_run_manager')
        
        # Initialize parameter handler using the plugin system
        param_type = config['parameter_type']
        self.parameter_handler = ParameterFactory.create_parameter(param_type, config)
        print(f"Worker {worker_id}: Loaded {self.parameter_handler.get_name()} parameter handler")
        
        if self.debug and self.test_run_manager:
            self.debug_dir = os.path.join(
                self.test_run_manager.get_debug_dir(), 
                f"worker_{worker_id}"
            )
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
    
    def run_single_test(self, parameter_value, delay_seconds=1, default_timeout=300):
        """Execute a single backtest for given parameter value and extract trade log"""
        try:
            print(f"Worker {self.worker_id}: Running test for {self.config['parameter_type']}={parameter_value}")
            
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
            
            # Set the parameter using the plugin system
            if not self.set_parameter_value(self.config['parameter_type'], parameter_value):
                raise Exception(f"Failed to set {self.config['parameter_type']} to {parameter_value}")
            
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
            results['parameter_type'] = self.config['parameter_type']
            results['parameter_value'] = parameter_value
            results['timestamp'] = datetime.now().isoformat()
            results['worker_id'] = self.worker_id
            
            # Convert percentages to decimals for consistency
            results = self._normalize_results(results)
            
            # Check for duplicates
            if self._is_duplicate(results):
                print(f"Worker {self.worker_id}: Duplicate detected, waiting and retrying...")
                time.sleep(5)
                results = self.extract_results()
                results['parameter_type'] = self.config['parameter_type']
                results['parameter_value'] = parameter_value
                results['timestamp'] = datetime.now().isoformat()
                results['worker_id'] = self.worker_id
                results = self._normalize_results(results)
            
            self.last_results = results
            
            # EXTRACT TRADE LOG
            print(f"Worker {self.worker_id}: Extracting trade log for {parameter_value}")
            trade_log_data = self.extract_trade_log(parameter_value)
            
            # Store both results and trade log data thread-safely
            with results_lock:
                all_results.append(results)
                # Add trade log data with backtest reference
                for trade in trade_log_data:
                    trade['backtest_parameter_type'] = self.config['parameter_type']
                    trade['backtest_parameter_value'] = parameter_value
                    trade['backtest_results'] = results
                
                # Store in separate global trade log collection
                all_trade_logs.extend(trade_log_data)
                
                # Update consolidated trade log CSV immediately
                if trade_log_data:
                    self._update_consolidated_trade_log_csv()
            
            # Reset consecutive failures on success
            self.consecutive_failures = 0
            
            print(f"Worker {self.worker_id}: Test complete - {self.config['parameter_type']}={parameter_value}: CAGR={results['cagr']:.6f}, MAR={results['mar']:.2f}, Trades={len(trade_log_data)}")
            return True
            
        except Exception as e:
            self.consecutive_failures += 1
            print(f"Worker {self.worker_id}: Test failed for {parameter_value}: {e}")
            
            # Try to close any open dialogs
            try:
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
            except:
                pass
            
            return False

    def set_parameter_value(self, parameter_type, value):
        """Set parameter value using the plugin system"""
        try:
            return self.parameter_handler.set_value(self.driver, value)
        except Exception as e:
            print(f"Worker {self.worker_id}: Error setting parameter {parameter_type}={value}: {e}")
            return False
    
    # Keep special methods that might still be needed for exit time
    def ensure_early_exit_enabled(self):
        """Ensure the Early Exit toggle is enabled for exit time testing"""
        try:
            # Look for the Early Exit toggle switch with enhanced selectors
            toggle_selectors = [
                "//button[contains(@aria-label, 'Use Early Exit')]",
                "#headlessui-switch-596",
                "//button[@role='switch'][contains(., 'Early Exit')]",
                "[aria-label*='Early Exit']",
                "//button[@role='switch']",
                ".toggle, .switch",
                "//label[contains(text(), 'Early Exit')]/..//button",
            ]
            
            for selector in toggle_selectors:
                try:
                    if selector.startswith("//"):
                        toggle = self.driver.find_element(By.XPATH, selector)
                    else:
                        toggle = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if toggle and toggle.is_displayed():
                        # Check if already enabled
                        is_enabled = (toggle.get_attribute('aria-checked') == 'true' or
                                    'active' in toggle.get_attribute('class').lower() or
                                    'checked' in toggle.get_attribute('class').lower())
                        
                        print(f"Worker {self.worker_id}: Found Early Exit toggle, enabled: {is_enabled}")
                        
                        if not is_enabled:
                            self._safe_click(toggle)
                            time.sleep(1)
                            print(f"Worker {self.worker_id}: Clicked Early Exit toggle")
                        else:
                            print(f"Worker {self.worker_id}: Early Exit already enabled")
                        
                        return True
                except:
                    continue
            
            print(f"Worker {self.worker_id}: Could not find Early Exit toggle")
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error enabling Early Exit: {e}")
            return False
    
    # Keep special method for day of week clearing
    def _clear_all_day_selections(self):
        """Clear all day of week selections first"""
        try:
            # Find all day buttons and unselect them
            day_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                "div.flex-1 > div:nth-of-type(2) > div > div:nth-of-type(4) button")
            
            for button in day_buttons:
                try:
                    # Check if button is selected
                    if 'selected' in button.get_attribute('class').lower() or \
                       button.get_attribute('aria-pressed') == 'true':
                        self._safe_click(button)
                except:
                    continue
                    
        except Exception as e:
            print(f"Worker {self.worker_id}: Error clearing day selections: {e}")

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
    
    def extract_trade_log(self, parameter_value):
        """Navigate to trade log and download complete trade data"""
        try:
            print(f"Worker {self.worker_id}: Downloading trade log for {parameter_value}")
            
            # Navigate to Trade Log tab
            if not self._navigate_to_trade_log():
                return []
            
            time.sleep(3)  # Allow page to load
            
            # Setup download directory using test run manager
            download_dir = self._setup_download_directory()
            
            # Download the trade log file
            downloaded_file = self._download_trade_log_file(download_dir)
            
            if not downloaded_file:
                print(f"Worker {self.worker_id}: Failed to download trade log")
                return []
            
            # Parse the downloaded file
            trades_data = self._parse_downloaded_trade_log(downloaded_file, parameter_value)
            
            # Clean up the downloaded file (move to organized location instead of delete)
            try:
                organized_file = os.path.join(download_dir, f"trade_log_{parameter_value}_{datetime.now().strftime('%H%M%S')}.csv")
                shutil.move(downloaded_file, organized_file)
                print(f"Worker {self.worker_id}: Moved trade log to {organized_file}")
            except Exception as e:
                print(f"Worker {self.worker_id}: Could not move trade log file: {e}")
                # Try to delete if move failed
                try:
                    os.remove(downloaded_file)
                except:
                    pass
            
            print(f"Worker {self.worker_id}: Processed {len(trades_data)} trade records from download")
            return trades_data
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error extracting trade log: {e}")
            return []

    def _navigate_to_trade_log(self):
        """Navigate to the Trade Log tab"""
        try:
            # Look for Trade Log tab using multiple selectors
            trade_log_selectors = [
                "//a[contains(., 'Trade Log')]",
                "//nav//a[contains(@class, 'border-transparent')]",
                "a[href*='trade']",
                "//a[@aria-label='Trade Log']"
            ]
            
            for selector in trade_log_selectors:
                try:
                    if selector.startswith("//"):
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if element and element.is_displayed():
                        self._safe_click(element)
                        print(f"Worker {self.worker_id}: Navigated to Trade Log")
                        return True
                except:
                    continue
            
            print(f"Worker {self.worker_id}: Could not find Trade Log tab")
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error navigating to trade log: {e}")
            return False
    
    def _setup_download_directory(self):
        """Setup download directory using test run manager"""
        if self.test_run_manager:
            worker_download_dir = os.path.join(
                self.test_run_manager.get_downloads_dir(), 
                f"worker_{self.worker_id}"
            )
        else:
            # Fallback if no test run manager
            worker_download_dir = f"downloads_worker_{self.worker_id}"
        
        os.makedirs(worker_download_dir, exist_ok=True)
        
        # Configure Chrome to download to this directory
        try:
            self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': os.path.abspath(worker_download_dir)
            })
        except:
            # Fallback if CDP commands not available
            pass
        
        return worker_download_dir
    
    def _download_trade_log_file(self, download_dir):
        """Find and click the download button, wait for file - DO NOT CHANGE THIS METHOD"""
        try:
            # Multiple selectors for the download button based on your Puppeteer script
            download_selectors = [
                "div.hidden path:nth-of-type(1)",
                "//*[@id='app']/div/div[2]/div[2]/div[2]/div/div[7]/svg/path[1]",
                "svg path[d*='M']",  # Generic SVG path
                "[title*='Download'], [aria-label*='Download']",  # Accessibility attributes
                ".download-btn, .export-btn"  # Common class patterns
            ]
            
            download_button = None
            for selector in download_selectors:
                try:
                    if selector.startswith("//"):
                        element = self.driver.find_element(By.XPATH, selector)
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if element and element.is_displayed():
                        download_button = element
                        break
                except:
                    continue
            
            if not download_button:
                # Try finding parent element that might contain the download icon
                try:
                    parent_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='hidden'] svg, .export svg")
                    for parent in parent_elements:
                        paths = parent.find_elements(By.TAG_NAME, "path")
                        if paths:
                            download_button = paths[0]
                            break
                except:
                    pass
            
            if not download_button:
                print(f"Worker {self.worker_id}: Could not find download button")
                return None
            
            # Get list of files before download
            files_before = set(os.listdir(download_dir))
            
            # Click download with the specific offset if needed
            try:
                # Try clicking at the specified coordinates first
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
                """, download_button)
            except:
                # Fallback to regular click
                self._safe_click(download_button)
            
            print(f"Worker {self.worker_id}: Clicked download button, waiting for file...")
            
            # Wait for new file to appear (up to 30 seconds)
            for i in range(30):
                time.sleep(1)
                files_after = set(os.listdir(download_dir))
                new_files = files_after - files_before
                
                if new_files:
                    # Find the most recent file
                    newest_file = None
                    newest_time = 0
                    
                    for filename in new_files:
                        filepath = os.path.join(download_dir, filename)
                        if os.path.isfile(filepath):
                            file_time = os.path.getmtime(filepath)
                            if file_time > newest_time:
                                newest_time = file_time
                                newest_file = filepath
                    
                    if newest_file and not filename.endswith('.crdownload'):
                        print(f"Worker {self.worker_id}: Downloaded file: {newest_file}")
                        return newest_file
            
            print(f"Worker {self.worker_id}: Download timeout - no file received")
            return None
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error downloading file: {e}")
            return None
    
    def _parse_downloaded_trade_log(self, file_path, parameter_value):
        """Parse the downloaded trade log file (CSV or Excel) with enhanced debugging"""
        try:
            print(f"Worker {self.worker_id}: Parsing downloaded file: {file_path}")
            
            try:
                import pandas as pd
                
                # Try reading with pandas first
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                elif file_path.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path)
                else:
                    # Try CSV first, then Excel
                    try:
                        df = pd.read_csv(file_path)
                    except:
                        df = pd.read_excel(file_path)
                
                print(f"Worker {self.worker_id}: DataFrame shape: {df.shape}")
                print(f"Worker {self.worker_id}: DataFrame columns: {list(df.columns)}")
                
                if len(df) > 0:
                    print(f"Worker {self.worker_id}: First row data: {df.iloc[0].to_dict()}")
                
                trades_data = []
                
                for idx, row in df.iterrows():
                    try:
                        trade_data = self._parse_trade_row_from_df(row, parameter_value)
                        if trade_data:
                            trades_data.append(trade_data)
                    except Exception as e:
                        print(f"Worker {self.worker_id}: Error parsing row {idx}: {e}")
                        continue
                
                return trades_data
                
            except ImportError:
                print(f"Worker {self.worker_id}: pandas not available, using manual parsing")
                return self._parse_downloaded_file_manual(file_path, parameter_value)
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error parsing downloaded file: {e}")
            return []
    
    def _parse_downloaded_file_manual(self, file_path, parameter_value):
        """Manual parsing without pandas for CSV files with enhanced debugging"""
        try:
            trades_data = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                
                # Print headers for debugging
                headers = csv_reader.fieldnames
                print(f"Worker {self.worker_id}: CSV headers found: {headers}")
                
                row_count = 0
                for row in csv_reader:
                    row_count += 1
                    if row_count == 1:
                        print(f"Worker {self.worker_id}: First row data: {dict(row)}")
                    
                    try:
                        trade_data = self._parse_trade_row_from_dict(row, parameter_value)
                        if trade_data:
                            trades_data.append(trade_data)
                    except Exception as e:
                        print(f"Worker {self.worker_id}: Error parsing CSV row {row_count}: {e}")
                        continue
                
                print(f"Worker {self.worker_id}: Processed {row_count} rows, extracted {len(trades_data)} trades")
            
            return trades_data
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error in manual file parsing: {e}")
            return []
    
    def _parse_trade_row_from_df(self, row, parameter_value):
        """Parse trade row from pandas DataFrame"""
        return self._parse_trade_row_from_dict(row.to_dict(), parameter_value)
    
    def _parse_trade_row_from_dict(self, row_dict, parameter_value):
        """Parse trade row from dictionary using actual OptionOmega column names"""
        try:
            # Map OptionOmega's actual column names to our data structure
            trade_data = {
                'backtest_parameter_type': self.config['parameter_type'],
                'backtest_parameter_value': parameter_value,
                'trade_date_time': str(row_dict.get('Date Opened', '')) + ' ' + str(row_dict.get('Time Opened', '')),
                'opening_price': self._get_numeric_from_value(row_dict.get('Opening Price', 0)),
                'legs': str(row_dict.get('Legs', '')),
                'premium': self._get_numeric_from_value(row_dict.get('Premium', 0)),
                'closing_price': self._get_numeric_from_value(row_dict.get('Closing Price', 0)),
                'date_closed': str(row_dict.get('Date Closed', '')),
                'time_closed': str(row_dict.get('Time Closed', '')),
                'avg_closing_cost': self._get_numeric_from_value(row_dict.get('Avg. Closing Cost', 0)),
                'reason_for_close': str(row_dict.get('Reason For Close', '')),
                'trade_pnl': self._get_numeric_from_value(row_dict.get('P/L', 0)),
                'num_contracts': self._get_numeric_from_value(row_dict.get('No. of Contracts', 0)),
                'funds_at_close': self._get_numeric_from_value(row_dict.get('Funds at Close', 0)),
                'margin_req': self._get_numeric_from_value(row_dict.get('Margin Req.', 0)),
                'strategy': str(row_dict.get('Strategy', '')),
                'opening_commissions': self._get_numeric_from_value(row_dict.get('Opening Commissions + Fees', 0)),
                'closing_commissions': self._get_numeric_from_value(row_dict.get('Closing Commissions + Fees', 0)),
                'opening_ratio': self._get_numeric_from_value(row_dict.get('Opening Short/Long Ratio', 0)),
                'closing_ratio': self._get_numeric_from_value(row_dict.get('Closing Short/Long Ratio', 0)),
                'gap': self._get_numeric_from_value(row_dict.get('Gap', 0)),
                'movement': self._get_numeric_from_value(row_dict.get('Movement', 0)),
                'max_profit': self._get_numeric_from_value(row_dict.get('Max Profit', 0)),
                'max_loss': self._get_numeric_from_value(row_dict.get('Max Loss', 0)),
                'extracted_timestamp': datetime.now().isoformat(),
                'worker_id': self.worker_id
            }
            
            return trade_data
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error parsing trade row: {e}")
            return None
    
    def _get_numeric_from_value(self, value):
        """Extract numeric value from any type of value"""
        try:
            if value is None or (isinstance(value, str) and value.lower() in ['nan', '', 'none']):
                return 0
            if isinstance(value, (int, float)):
                return float(value)
            
            # Handle string values
            value_str = str(value).strip()
            # Remove common non-numeric characters
            cleaned = re.sub(r'[,$%]', '', value_str)
            match = re.search(r'-?\d+\.?\d*', cleaned)
            return float(match.group()) if match else 0
        except:
            return 0
    
    def _update_consolidated_trade_log_csv(self):
        """Update the consolidated trade log CSV with all accumulated data"""
        try:
            # Use test run manager for organized file location
            if self.test_run_manager:
                consolidated_filename = self.test_run_manager.get_results_file('consolidated_trade_log.csv')
            else:
                # Fallback for older code
                timestamp = datetime.now().strftime('%Y%m%d')
                consolidated_filename = f'consolidated_trade_log_{timestamp}.csv'
            
            # Write complete trade log data (overwrites file each time)
            with open(consolidated_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Headers matching actual OptionOmega export structure
                headers = [
                    'Backtest Parameter Type', 'Backtest Parameter Value', 'Trade Date Time', 'Opening Price', 'Legs', 'Premium',
                    'Closing Price', 'Date Closed', 'Time Closed', 'Avg Closing Cost', 'Reason For Close',
                    'Trade P&L', 'Num Contracts', 'Funds at Close', 'Margin Req', 'Strategy',
                    'Opening Commissions', 'Closing Commissions', 'Opening Ratio', 'Closing Ratio',
                    'Gap', 'Movement', 'Max Profit', 'Max Loss', 'Extracted Timestamp', 'Worker ID'
                ]
                writer.writerow(headers)
                
                # Sort all trade logs by backtest parameter value, then trade date
                # Convert all parameter values to strings for consistent sorting
                sorted_trades = sorted(all_trade_logs, 
                    key=lambda x: (str(x.get('backtest_parameter_value', '')), 
                                  str(x.get('trade_date_time', ''))))
                
                for trade in sorted_trades:
                    row_data = [
                        trade.get('backtest_parameter_type', ''),
                        trade.get('backtest_parameter_value', ''),
                        trade.get('trade_date_time', ''),
                        trade.get('opening_price', ''),
                        trade.get('legs', ''),
                        trade.get('premium', ''),
                        trade.get('closing_price', ''),
                        trade.get('date_closed', ''),
                        trade.get('time_closed', ''),
                        trade.get('avg_closing_cost', ''),
                        trade.get('reason_for_close', ''),
                        trade.get('trade_pnl', ''),
                        trade.get('num_contracts', ''),
                        trade.get('funds_at_close', ''),
                        trade.get('margin_req', ''),
                        trade.get('strategy', ''),
                        trade.get('opening_commissions', ''),
                        trade.get('closing_commissions', ''),
                        trade.get('opening_ratio', ''),
                        trade.get('closing_ratio', ''),
                        trade.get('gap', ''),
                        trade.get('movement', ''),
                        trade.get('max_profit', ''),
                        trade.get('max_loss', ''),
                        trade.get('extracted_timestamp', ''),
                        trade.get('worker_id', '')
                    ]
                    writer.writerow(row_data)
            
            total_trades = len(all_trade_logs)
            completed_backtests = len(completed_tasks) if 'completed_tasks' in globals() else len(all_results)
            
            print(f"Worker {self.worker_id}: Updated consolidated trade log - {total_trades} total trades from {completed_backtests} completed backtests")
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error updating consolidated trade log: {e}")

    def cleanup(self):
        """Clean up worker resources"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            
        print(f"Worker {self.worker_id}: Cleaned up")


def worker_thread_simplified(worker_id, task_queue, config, credentials, original_values_set):
    """Simplified worker thread - no complex validation logic"""
    worker = OptionOmegaWorker(worker_id, task_queue, config, debug=config.get('debug', False))
    
    try:
        # Staggered initialization
        init_delay = random.randint(5, 30)
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
                parameter_value = task_queue.get(timeout=10)
                parameter_str = str(parameter_value)
                
                # Skip if not in original set (shouldn't happen with new logic)
                if parameter_str not in original_values_set:
                    print(f"Worker {worker_id}: Skipping {parameter_value} - not in original set")
                    task_queue.task_done()
                    continue
                
                # Check if already completed (based on results, not task tracking)
                with results_lock:
                    already_completed = any(
                        str(r.get('parameter_value', '')) == parameter_str 
                        for r in all_results
                    )
                
                if already_completed:
                    print(f"Worker {worker_id}: Parameter {parameter_value} already has results, skipping")
                    task_queue.task_done()
                    continue
                
                print(f"Worker {worker_id}: Processing {config['parameter_type']}={parameter_value}")
                
                # Process the task
                success = worker.run_single_test(
                    parameter_value, 
                    config.get('delay_seconds', 1), 
                    config.get('backtest_timeout', 300)
                )
                
                if success:
                    print(f"Worker {worker_id}: ✅ Completed {parameter_value}")
                else:
                    print(f"Worker {worker_id}: ❌ Failed {parameter_value}")
                    # For failed tests, put back in queue for retry (limited)
                    retry_count = getattr(task_queue, '_retries', {}).get(parameter_str, 0)
                    if retry_count < 2:  # Max 2 retries
                        if not hasattr(task_queue, '_retries'):
                            task_queue._retries = {}
                        task_queue._retries[parameter_str] = retry_count + 1
                        task_queue.put(parameter_value)
                        print(f"Worker {worker_id}: Re-queued {parameter_value} (retry {retry_count + 1})")
                
                # Mark task done
                task_queue.task_done()
                
                # Brief rest
                time.sleep(1)
                
            except queue.Empty:
                # No more tasks
                continue
            except Exception as e:
                print(f"Worker {worker_id}: Unexpected error: {e}")
                try:
                    task_queue.task_done()
                except:
                    pass
                break
        
    except Exception as e:
        print(f"Worker {worker_id}: Fatal error: {e}")
    finally:
        worker.cleanup()
        print(f"Worker {worker_id}: Exited")


def generate_parameter_values(parameter_type, config):
    """Generate list of parameter values using the plugin system"""
    handler = ParameterFactory.create_parameter(parameter_type, config)
    return handler.generate_values()


def interactive_configuration(config):
    """Interactive configuration using parameter plugin system"""
    
    # Always ask for URL first - this is mandatory
    while not config.get('test_url'):
        print("\n" + "="*60)
        print("ENHANCED OPTIONOMEGA AUTOMATION - URL REQUIRED")
        print("="*60)
        url = input("Enter OptionOmega test URL (required): ").strip()
        
        if url and 'optionomega.com' in url and '/test/' in url:
            config['test_url'] = url
            print(f"✅ URL validated: {url}")
        else:
            print("❌ Invalid URL. Must be an OptionOmega test URL (e.g., https://optionomega.com/test/YOUR_ID)")
    
    # Parameter selection using the plugin system
    print("\n" + "="*60)
    print("SELECT PARAMETER TO TEST")
    print("="*60)
    
    available_params = ParameterFactory.get_available_parameters()
    param_handlers = {}
    
    for i, param_type in enumerate(available_params, 1):
        handler = ParameterFactory.create_parameter(param_type, {})
        param_handlers[param_type] = handler
        print(f"{i}. {handler.get_name()} - {handler.get_description()}")
    
    while True:
        try:
            choice = input(f"\nSelect parameter to test (1-{len(available_params)}): ").strip()
            param_index = int(choice) - 1
            if 0 <= param_index < len(available_params):
                config['parameter_type'] = available_params[param_index]
                selected_handler = param_handlers[config['parameter_type']]
                print(f"✅ Selected: {selected_handler.get_name()}")
                break
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a number.")
    
    # Use the parameter handler's interactive configuration
    config = selected_handler.configure_interactive(config)
    
    # General configuration
    while True:
        print("\n" + "="*60)
        print("ENHANCED OPTIONOMEGA AUTOMATION CONFIGURATION")
        print("="*60)
        print(f"1. Test URL:         {config['test_url']}")
        print(f"2. Parameter Type:   {selected_handler.get_name()}")
        
        # Display parameter-specific configuration
        # The handler knows how to display its own config
        param_values = selected_handler.generate_values()
        print(f"3. Test Values:      {len(param_values)} values")
        if len(param_values) <= 10:
            print(f"                     {param_values}")
        else:
            print(f"                     {param_values[:5]}...{param_values[-5:]}")
        
        print(f"4. Delay:            {config.get('delay_seconds', 1)} seconds")
        print(f"5. Backtest Timeout: {config.get('backtest_timeout', 300)} seconds")
        print(f"6. Max Workers:      {config.get('max_workers', 2)} (recommended: 2 for rate limiting)")
        print(f"7. Debug Mode:       {config.get('debug', False)}")
        print("="*60)
        
        # Calculate estimated test count and time
        total_tests = len(param_values)
        estimated_time_per_test = (config.get('backtest_timeout', 300) + config.get('delay_seconds', 1) + 60) / config.get('max_workers', 2)
        estimated_total_minutes = (total_tests * estimated_time_per_test) / 60
        
        print(f"Estimated: {total_tests} tests + trade log extraction")
        print(f"Time: ~{estimated_total_minutes:.1f} minutes with {config.get('max_workers', 2)} workers")
        print("Note: Each test includes comprehensive trade log extraction")
        print("="*60)
        
        response = input("\nChange parameters? (y/n): ").strip().lower()
        
        if response == 'n':
            break
        elif response == 'y':
            choice = input("\nSelect parameter (1-7, 0 to finish): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                url = input("Enter new URL: ").strip()
                if url and 'optionomega.com' in url and '/test/' in url:
                    config['test_url'] = url
            elif choice == '4':
                delay = input("Enter delay in seconds: ").strip()
                if delay.isdigit():
                    config['delay_seconds'] = int(delay)
            elif choice == '5':
                timeout = input("Enter backtest timeout in seconds: ").strip()
                if timeout.isdigit():
                    config['backtest_timeout'] = int(timeout)
            elif choice == '6':
                workers = input("Enter max workers (1-4): ").strip()
                if workers.isdigit() and 1 <= int(workers) <= 4:
                    config['max_workers'] = int(workers)
            elif choice == '7':
                config['debug'] = not config.get('debug', False)
                print(f"Debug mode: {config['debug']}")
    
    # Final confirmation
    print(f"\n📊 FINAL CONFIGURATION SUMMARY:")
    print(f"   • Parameter: {selected_handler.get_name()}")
    print(f"   • Values to test: {len(param_values)}")
    print(f"   • Trade log extraction: Full transaction history per test")
    print(f"   • Parallel workers: {config.get('max_workers', 2)}")
    print(f"   • Estimated duration: {estimated_total_minutes:.1f} minutes")
    print(f"   • Output: Enhanced CSV with backtest results + comprehensive trade logs")
    
    confirm = input("\nStart enhanced automation? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        exit(0)
    
    return config


def load_configuration(args):
    """Load configuration from file and command line"""
    config = {
        'test_url': None,  # Always ask for URL
        'parameter_type': 'entry_time',  # Default
        'delay_seconds': 1,
        'backtest_timeout': 300,
        'max_workers': 2,  # Default to 2 workers for rate limiting
        'chrome_path': None,
        'debug': False,
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
    if args.parameter:
        config['parameter_type'] = args.parameter
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


def find_duplicate_results(tolerance=0.0001):
    """Find parameter values that produced nearly identical results"""
    duplicates = {}
    
    with results_lock:
        if not all_results:
            return duplicates
        
        # Group results by their key metrics (CAGR, drawdown, etc.)
        result_groups = {}
        
        for result in all_results:
            # Create a signature based on the key metrics
            signature = (
                round(result.get('cagr', 0), 6),
                round(result.get('maxDrawdown', 0), 6), 
                round(result.get('winPercentage', 0), 6),
                round(result.get('captureRate', 0), 6)
            )
            
            if signature not in result_groups:
                result_groups[signature] = []
            
            result_groups[signature].append({
                'parameter_value': str(result.get('parameter_value', '')),
                'result': result
            })
        
        # Identify groups with multiple parameter values (potential duplicates)
        for signature, group in result_groups.items():
            if len(group) > 1:
                param_values = [item['parameter_value'] for item in group]
                duplicates[','.join(param_values)] = {
                    'signature': signature,
                    'count': len(group),
                    'parameter_values': param_values,
                    'results': [item['result'] for item in group]
                }
    
    if duplicates:
        print(f"Duplicate detection: Found {len(duplicates)} groups with identical results:")
        for params, data in list(duplicates.items())[:3]:  # Show first 3 groups
            print(f"  Parameters {params}: CAGR={data['signature'][0]}, Count={data['count']}")
    
    return duplicates


def save_progress_periodically(config, all_values):
    """Periodically save progress with backup files"""
    while not shutdown_event.is_set():
        time.sleep(60)  # Save every minute
        
        with progress_lock:
            save_progress_backup(config, all_values)


def save_progress_backup(config, all_values):
    """Save progress with backup using test run manager"""
    try:
        # Calculate completion percentage
        completion_pct = 0
        if all_values:
            with results_lock:
                completion_pct = len(all_results) / len(all_values) * 100
        
        # Create a serializable copy of config (exclude non-serializable objects)
        serializable_config = {k: v for k, v in config.items() if k not in ['test_run_manager', 'parameter_handler']}
        serializable_config['test_run_dir'] = config.get('test_run_manager', {}).base_dir if hasattr(config.get('test_run_manager', {}), 'base_dir') else None
        
        # Save main progress file
        progress_data = {
            'config': serializable_config,
            'completion_percentage': completion_pct,
            'total_tests': len(all_values),
            'completed_tests': len(all_results),
            'timestamp': datetime.now().isoformat(),
            'results': all_results
        }
        
        # Use test run manager for organized file location
        test_run_manager = config.get('test_run_manager')
        if test_run_manager:
            progress_file = test_run_manager.get_results_file('progress.json')
            backup_file = os.path.join(
                test_run_manager.get_backups_dir(), 
                f'backup_{int(completion_pct)}pct_{datetime.now().strftime("%H%M%S")}.json'
            )
        else:
            progress_file = 'optionomega_progress.json'
            backup_file = f'optionomega_backup_{int(completion_pct)}pct.json'
        
        # Save main progress file
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        # Create backup every 5% completion
        if int(completion_pct) % 5 == 0 and completion_pct > 0:
            with open(backup_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        
        # Export CSV backup
        if all_results:
            export_results_to_csv(config, all_results, backup=True)
            
    except Exception as e:
        print(f"Error saving progress: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")


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


def export_results_to_csv(config, results, backup=False):
    """Export results to CSV with enhanced filename"""
    if not results:
        return None
    
    try:
        # Use test run manager for organized file location
        test_run_manager = config.get('test_run_manager')
        parameter_type = config.get('parameter_type', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create filename
        if backup:
            filename = f'results_{parameter_type}_backup_{timestamp}.csv'
        else:
            filename = f'results_{parameter_type}_{timestamp}.csv'
        
        # Get full file path
        if test_run_manager:
            if backup:
                filepath = os.path.join(test_run_manager.get_backups_dir(), filename)
            else:
                filepath = test_run_manager.get_results_file(filename)
        else:
            filepath = filename
        
        # Write CSV with 6 decimal precision
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Parameter Type', 'Parameter Value', 'CAGR', 'Max Drawdown', 
                           'Win Percentage', 'Capture Rate', 'MAR', 'Worker ID', 'Timestamp'])
            
            # Sort results by parameter value
            sorted_results = sorted(results, key=lambda x: str(x.get('parameter_value', '')))
            
            for row in sorted_results:
                writer.writerow([
                    row.get('parameter_type', ''),
                    row.get('parameter_value', ''),
                    f"{row['cagr']:.6f}",
                    f"{row['maxDrawdown']:.6f}",
                    f"{row['winPercentage']:.6f}",
                    f"{row['captureRate']:.6f}",
                    f"{row['mar']:.6f}",
                    row.get('worker_id', 'N/A'),
                    row.get('timestamp', '')
                ])
        
        if not backup:
            print(f"Results exported to: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return None


def main():
    """Main execution function with simplified completion tracking"""
    print("ENHANCED OPTIONOMEGA AUTOMATION v4.0 - WITH PARAMETER PLUGIN SYSTEM")
    print("Cleaner, modular code with easy parameter addition")
    print("="*90)
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Enhanced OptionOmega Backtesting Automation')
    parser.add_argument('--url', type=str, help='Test URL')
    parser.add_argument('--parameter', type=str, choices=ParameterFactory.get_available_parameters(), 
                        help='Parameter type to test')
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
    
    # Create test run manager for organized file handling
    test_run_manager = TestRunManager(config['test_url'], config['parameter_type'])
    config['test_run_manager'] = test_run_manager
    
    # Get credentials
    print("\nLOGIN CREDENTIALS")
    print("="*50)
    credentials = get_credentials()
    print("="*50)
    
    # Generate parameter values to test
    all_values = generate_parameter_values(config['parameter_type'], config)
    original_values_set = set(str(v) for v in all_values)
    task_queue = queue.Queue()
    
    # Populate task queue with original tasks ONLY
    for value in all_values:
        task_queue.put(value)
    
    # Create parameter handler for display
    param_handler = ParameterFactory.create_parameter(config['parameter_type'], config)
    
    print(f"\nStarting automation with {config.get('max_workers', 2)} workers")
    print(f"Parameter: {param_handler.get_name()}")
    print(f"Total tests: {len(all_values)}")
    print(f"Test values: {all_values[:10]}{'...' if len(all_values) > 10 else ''}")
    print("="*90)
    
    # Worker threads
    threads = []
    
    try:
        # Start progress saving thread only
        progress_thread = threading.Thread(target=save_progress_periodically, args=(config, all_values))
        progress_thread.daemon = True
        progress_thread.start()
        
        # Start main worker threads
        for worker_id in range(config.get('max_workers', 2)):
            thread = threading.Thread(
                target=worker_thread_simplified, 
                args=(worker_id, task_queue, config, credentials, original_values_set)
            )
            thread.start()
            threads.append(thread)
        
        # Simplified progress monitoring
        start_time = time.time()
        last_count = 0
        
        while True:
            time.sleep(15)  # Check every 15 seconds
            
            # Calculate progress based on original parameter set
            with results_lock:
                completed_parameters = set()
                for result in all_results:
                    param_value = str(result.get('parameter_value', ''))
                    completed_parameters.add(param_value)
                
                current_count = len(completed_parameters)
                progress_pct = (current_count / len(original_values_set)) * 100 if original_values_set else 0
            
            # Show progress
            if current_count != last_count:
                elapsed_minutes = (time.time() - start_time) / 60
                if current_count > 0:
                    rate_per_minute = current_count / elapsed_minutes
                    eta_minutes = (len(original_values_set) - current_count) / rate_per_minute if rate_per_minute > 0 else 0
                    print(f"Progress: {current_count}/{len(original_values_set)} unique parameters ({progress_pct:.1f}%) - "
                          f"Rate: {rate_per_minute:.1f}/min - ETA: {eta_minutes:.1f}min")
                
                last_count = current_count
                
                # Save progress periodically
                if current_count % max(1, len(original_values_set) // 10) == 0:
                    save_progress_backup(config, all_values)
            
            # Check completion - all original parameters have results
            missing_parameters = original_values_set - completed_parameters
            
            if not missing_parameters:
                print(f"All {len(original_values_set)} original parameters completed!")
                
                # Check for duplicates in final results
                duplicates_found = find_duplicate_results()
                if duplicates_found:
                    print(f"Found {len(duplicates_found)} groups with duplicate results (for analysis):")
                    for param_values_str, result_data in list(duplicates_found.items())[:3]:
                        print(f"  Parameters {param_values_str}: CAGR={result_data['signature'][0]}")
                
                # Signal shutdown
                shutdown_event.set()
                break
            
            # Check if all threads finished but work remains
            active_threads = [t for t in threads if t.is_alive()]
            if not active_threads:
                if missing_parameters:
                    print(f"All workers died but {len(missing_parameters)} parameters still missing: {list(missing_parameters)[:5]}")
                    # Emergency: add missing parameters back to queue and restart one worker
                    for param in list(missing_parameters)[:3]:
                        task_queue.put(param)
                    
                    # Restart one worker
                    thread = threading.Thread(
                        target=worker_thread_simplified, 
                        args=(999, task_queue, config, credentials, original_values_set)
                    )
                    thread.start()
                    threads.append(thread)
                    print("Restarted emergency worker")
                else:
                    # All done
                    break
        
        # Shutdown
        shutdown_event.set()
        
        # Wait for threads to finish
        for thread in threads:
            thread.join(timeout=30)
        
        # Final results summary
        print("\n" + "="*90)
        print("AUTOMATION COMPLETED!")
        print("="*90)
        
        with results_lock:
            total_results = len(all_results)
            unique_parameters = set(str(r.get('parameter_value', '')) for r in all_results)
            
        print(f"Original parameters: {len(original_values_set)}")
        print(f"Unique parameters completed: {len(unique_parameters)}")
        print(f"Total results collected: {total_results}")
        print(f"Total trades extracted: {len(all_trade_logs)}")
        print(f"Total time: {(time.time() - start_time) / 60:.1f} minutes")
        print(f"Files organized in: {test_run_manager.base_dir}")
        
        if all_results:
            # Export final results - remove duplicates first
            unique_results = []
            seen_parameters = set()
            for result in all_results:
                param_val = str(result.get('parameter_value', ''))
                if param_val not in seen_parameters:
                    unique_results.append(result)
                    seen_parameters.add(param_val)
            
            # Export standard results
            csv_filename = export_results_to_csv(config, unique_results)
            print(f"Clean results (no duplicates): {csv_filename}")
            
            # Export enhanced results with trade metrics
            if all_trade_logs:
                enhanced_csv = enhance_results_with_trade_metrics(
                    config, unique_results, all_trade_logs
                )
                if enhanced_csv:
                    print(f"Enhanced results with trade metrics: {enhanced_csv}")
            
            consolidated_trade_log = test_run_manager.get_results_file('consolidated_trade_log.csv')
            if all_trade_logs:
                print(f"Consolidated trade log: {consolidated_trade_log}")
            
            # Summary statistics
            cagr_values = [r['cagr'] for r in unique_results]
            if cagr_values:
                avg_cagr = sum(cagr_values) / len(cagr_values)
                max_cagr = max(cagr_values)
                min_cagr = min(cagr_values)
                
                # Find best parameter value
                best_idx = cagr_values.index(max_cagr)
                best_param = unique_results[best_idx]['parameter_value']
                
                print(f"CAGR Summary - Avg: {avg_cagr:.6f}, Max: {max_cagr:.6f} (at {param_handler.get_name()}={best_param}), Min: {min_cagr:.6f}")
        
        print("="*90)
        
        # Clean up temporary files
        test_run_manager.cleanup_temp_files()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user. Saving progress...")
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            # Remove duplicates before final export
            unique_results = []
            seen_parameters = set()
            for result in all_results:
                param_val = str(result.get('parameter_value', ''))
                if param_val not in seen_parameters:
                    unique_results.append(result)
                    seen_parameters.add(param_val)
            
            export_results_to_csv(config, unique_results)
            
            # Export enhanced results with trade metrics
            if all_trade_logs:
                enhance_results_with_trade_metrics(config, unique_results, all_trade_logs)
            
            save_progress_backup(config, all_values)
        
        # Clean up temporary files
        test_run_manager.cleanup_temp_files()
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            export_results_to_csv(config, all_results)
            
            # Export enhanced results with trade metrics
            if all_trade_logs:
                enhance_results_with_trade_metrics(config, all_results, all_trade_logs)
        
        # Clean up temporary files  
        test_run_manager.cleanup_temp_files()


if __name__ == "__main__":
    main()
