"""
Enhanced OptionOmega Backtesting Automation - REFACTORED VERSION
Complete single file - properly structured with checkpoint/resume and failure artifacts
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
import logging
from datetime import datetime
from functools import wraps
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# Import our new utilities
from utils.waiters import wait_click, wait_visible, wait_present, wait_gone, find_any_wait
from utils.selectors import LOGIN_EMAIL, LOGIN_PASSWORD, LOGIN_SUBMIT, NEW_BACKTEST_BTN
from pages.test_page import TestPage

# Import plugin systems
from parameter_plugin_system import ParameterFactory, BaseParameter
from trade_analysis_plugin import enhance_results_with_trade_metrics

# Try to import undetected-chromedriver
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

# Global thread-safe variables
results_lock = threading.Lock()
progress_lock = threading.Lock()
shutdown_event = threading.Event()

# Global results storage
all_results = []
all_trade_logs = []

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging(test_run_dir=None):
    """Setup structured logging with worker ID support"""
    log_format = '%(asctime)s [W%(worker_id)s] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    class WorkerFormatter(logging.Formatter):
        def format(self, record):
            if not hasattr(record, 'worker_id'):
                record.worker_id = 'MAIN'
            return super().format(record)
    
    formatter = WorkerFormatter(log_format, datefmt=date_format)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    handlers = [console_handler]
    if test_run_dir:
        log_file = os.path.join(test_run_dir, 'automation.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        handlers.append(file_handler)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in handlers:
        root_logger.addHandler(handler)
    
    return root_logger


def get_worker_logger(worker_id):
    """Get a logger adapter that includes worker ID"""
    logger = logging.getLogger(__name__)
    return logging.LoggerAdapter(logger, {'worker_id': worker_id})


# ============================================================================
# RESULT PROCESSING - MAR VALIDATION ONLY
# ============================================================================

def calculate_mar(cagr, drawdown):
    """Calculate MAR (MAR = CAGR / MaxDrawdown)"""
    if abs(drawdown) < 0.0001:
        return 0
    return abs(cagr) / abs(drawdown)


def validate_mar(cagr, drawdown, mar_expected):
    """Check if CAGR and Drawdown produce the expected MAR within 1% tolerance"""
    if abs(drawdown) < 0.0001:
        return abs(mar_expected) < 0.0001
    
    mar_calculated = calculate_mar(cagr, drawdown)
    
    if abs(mar_expected) < 0.0001:
        return abs(mar_calculated) < 0.0001
    
    error = abs(mar_calculated - mar_expected) / abs(mar_expected)
    return error < 0.01


def process_result_with_conversion(result):
    """
    Process result - validate and recalculate MAR only.
    No pattern-based conversions - trust OptionOmega's output format.
    """
    corrected = result.copy()
    conversions_made = []
    
    # Only validate/adjust if MAR doesn't match CAGR/Drawdown
    if all(k in corrected for k in ['cagr', 'maxDrawdown', 'mar']):
        cagr = corrected['cagr']
        drawdown = corrected['maxDrawdown']
        mar_expected = corrected['mar']
        
        if not validate_mar(cagr, drawdown, mar_expected):
            # Try dividing by 100 if values seem like percentages
            if abs(cagr) > 1:
                cagr_test = cagr / 100
                if validate_mar(cagr_test, drawdown, mar_expected):
                    corrected['cagr'] = cagr_test
                    conversions_made.append(f"cagr: {cagr} -> {cagr_test} (MAR validation)")
            elif abs(drawdown) > 1:
                dd_test = drawdown / 100
                if validate_mar(cagr, dd_test, mar_expected):
                    corrected['maxDrawdown'] = dd_test
                    conversions_made.append(f"maxDrawdown: {drawdown} -> {dd_test} (MAR validation)")
    
    # Always recalculate MAR from CAGR and Drawdown
    if 'cagr' in corrected and 'maxDrawdown' in corrected:
        corrected['mar'] = calculate_mar(corrected['cagr'], corrected['maxDrawdown'])
    
    if conversions_made and corrected.get('worker_id') is not None:
        worker_id = corrected.get('worker_id', 'N/A')
        param_value = corrected.get('parameter_value', 'unknown')
        logging.info(f"MAR validation adjustments for {param_value}: {', '.join(conversions_made)}", 
                    extra={'worker_id': worker_id})
    
    return corrected


# ============================================================================
# TEST RUN MANAGER
# ============================================================================

class TestRunManager:
    """Manages test run directories and checkpoints"""
    
    def __init__(self, test_url, parameter_type):
        self.test_url = test_url
        self.parameter_type = parameter_type
        self.test_name = self._extract_test_name()
        self.run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.base_dir = self._create_run_directory()
        self.logger = logging.getLogger(__name__)
        
    def _extract_test_name(self):
        try:
            if '/test/' in self.test_url:
                test_id = self.test_url.split('/test/')[-1]
                test_id = test_id.split('?')[0].split('#')[0]
                return f"Test_{test_id}"
            else:
                return "UnknownTest"
        except:
            return "UnknownTest"
    
    def _create_run_directory(self):
        dir_name = f"{self.test_name}_{self.parameter_type}_{self.run_timestamp}"
        dir_name = re.sub(r'[^\w\-_]', '', dir_name)
        
        base_path = os.path.join("test_runs", dir_name)
        
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
        try:
            for item in os.listdir('.'):
                if item.startswith('downloads_worker_') or item.startswith('chrome_worker_'):
                    if os.path.isdir(item):
                        shutil.rmtree(item)
                    else:
                        os.remove(item)
        except Exception as e:
            self.logger.warning(f"Could not clean up temp files: {e}")
    
    # CHECKPOINT METHODS
    
    def _param_key(self, param_value):
        """Canonical key for parameter value (handles dict ordering)"""
        return json.dumps(param_value, sort_keys=True)
    
    def load_completed_params(self):
        """Load set of completed parameter values from checkpoint file"""
        checkpoint_file = self.get_results_file('checkpoint.jsonl')
        completed = set()
        
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            key = self._param_key(data.get('parameter_value'))
                            completed.add(key)
                        except:
                            continue
                self.logger.info(f"Loaded {len(completed)} completed parameters from checkpoint")
            except Exception as e:
                self.logger.warning(f"Could not load checkpoint: {e}")
        
        return completed
    
    def save_checkpoint(self, parameter_value, results):
        """Atomically append completed test to checkpoint file"""
        checkpoint_file = self.get_results_file('checkpoint.jsonl')
        
        try:
            checkpoint_data = {
                'parameter_value': parameter_value,
                'results': results,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(checkpoint_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(checkpoint_data, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
                
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")


# ============================================================================
# RETRY DECORATOR
# ============================================================================

def with_retries(max_attempts=2):
    """Decorator to retry a function on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_error = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    last_error = e
                    self.consecutive_failures += 1
                    self.logger.error(f"Attempt {attempt}/{max_attempts} failed: {e}", 
                                     exc_info=True)
                    
                    if hasattr(self, 'test_page'):
                        self.test_page.clear_all_dialogs()
                    
                    if (self.consecutive_failures >= self.max_consecutive_failures or 
                        attempt == max_attempts):
                        self.logger.warning(f"Recycling driver after {self.consecutive_failures} failures")
                        self._recycle_driver()
                    
                    if attempt < max_attempts:
                        time.sleep(2)
            
            raise last_error
        
        return wrapper
    return decorator


# ============================================================================
# OPTION OMEGA WORKER
# ============================================================================

class OptionOmegaWorker:
    """Individual worker for processing backtests"""
    
    def __init__(self, worker_id, task_queue, config, debug=False):
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.config = config
        self.driver = None
        self.test_page = None
        self.debug = debug
        self.debug_dir = None
        self.backtest_times = []
        self.last_results = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        self.test_run_manager = config.get('test_run_manager')
        self.tests_since_recycle = 0
        self.recycle_interval = 50
        
        self.logger = get_worker_logger(worker_id)
        
        param_type = config['parameter_type']
        self.parameter_handler = ParameterFactory.create_parameter(param_type, config)
        self.logger.info(f"Loaded {self.parameter_handler.get_name()} parameter handler")
        
        if self.debug and self.test_run_manager:
            self.debug_dir = os.path.join(
                self.test_run_manager.get_debug_dir(), 
                f"worker_{worker_id}"
            )
            os.makedirs(self.debug_dir, exist_ok=True)
            self.logger.info(f"Debug mode enabled: {self.debug_dir}")
    
    def setup_driver(self, chrome_path=None, base_port=9222):
        """Initialize Chrome driver"""
        try:
            options = webdriver.ChromeOptions()
            
            user_data_dir = f"chrome_worker_{self.worker_id}_{int(time.time())}"
            debug_port = base_port + self.worker_id
            
            options.add_argument(f'--user-data-dir=/tmp/{user_data_dir}')
            options.add_argument(f'--remote-debugging-port={debug_port}')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-dev-shm-usage')
            
            if self.test_run_manager:
                download_dir = os.path.join(
                    self.test_run_manager.get_downloads_dir(),
                    f"worker_{self.worker_id}"
                )
                os.makedirs(download_dir, exist_ok=True)
                
                options.add_experimental_option("prefs", {
                    "download.default_directory": os.path.abspath(download_dir),
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True,
                })
            
            if self.debug:
                options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
            
            if not chrome_path:
                chrome_path = self._auto_detect_chrome()
            if chrome_path:
                options.binary_location = chrome_path
            
            self._initialize_driver(options)
            self._apply_stealth_scripts()
            
            self.test_page = TestPage(self.driver, self.worker_id, self.logger)
            
            self.logger.info(f"ChromeDriver initialized (port {debug_port})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup driver: {e}")
            return False
    
    def _initialize_driver(self, options):
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except ImportError:
            self.driver = webdriver.Chrome(options=options)
        
        try:
            self.driver.maximize_window()
        except:
            pass
    
    def _apply_stealth_scripts(self):
        try:
            if not hasattr(self.driver, 'execute_cdp_cmd'):
                return
            
            stealth_scripts = [
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
                "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});",
                "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});",
                "window.chrome = {runtime: {}};"
            ]
            
            for script in stealth_scripts:
                self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': script})
                
        except Exception as e:
            self.logger.warning(f"Could not apply stealth scripts: {e}")
    
    def _recycle_driver(self):
        try:
            self.logger.info("Recycling driver...")
            
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
                self.test_page = None
            
            time.sleep(2)
            
            if not self.setup_driver(self.config.get('chrome_path'), base_port=9222):
                raise RuntimeError("Failed to re-initialize driver")
            
            if not self._re_authenticate():
                raise RuntimeError("Failed to re-authenticate after driver recycle")
            
            self.consecutive_failures = 0
            self.tests_since_recycle = 0
            
            self.logger.info("Driver recycled successfully")
            
        except Exception as e:
            self.logger.error(f"Driver recycle failed: {e}")
            raise
    
    def _re_authenticate(self):
        try:
            credentials = self.config.get('credentials')
            if not credentials:
                self.logger.error("No stored credentials for re-authentication")
                return False
            
            login_url = self.config['test_url'].split('/test')[0] + '/login'
            self.driver.get(login_url)
            time.sleep(2)
            
            if not self.perform_login(credentials['username'], credentials['password']):
                return False
            
            return self.test_page.open(self.config['test_url'])
            
        except Exception as e:
            self.logger.error(f"Re-authentication failed: {e}")
            return False
    
    def _auto_detect_chrome(self):
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
    
    def perform_login(self, username, password):
        try:
            self.logger.info("Performing login")
            
            username_field = find_any_wait(self.driver, LOGIN_EMAIL, timeout=10)
            if not username_field:
                self.logger.error("Username field not found")
                return False
            
            username_field.clear()
            username_field.send_keys(username)
            
            password_field = find_any_wait(self.driver, LOGIN_PASSWORD, timeout=10)
            password_field.clear()
            password_field.send_keys(password)
            
            try:
                submit_btn = find_any_wait(self.driver, LOGIN_SUBMIT, timeout=5)
                submit_btn.click()
            except:
                password_field.submit()
            
            time.sleep(3)
            
            current_url = self.driver.current_url.lower()
            if 'login' not in current_url and 'signin' not in current_url:
                self.logger.info("Login successful")
                return True
            
            self.logger.error("Login failed - still on login page")
            return False
            
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False
    
    def capture_failure_artifacts(self, parameter_value):
        """Capture screenshot, HTML, and console logs on failure"""
        try:
            if not self.test_run_manager:
                return
            
            artifacts_dir = os.path.join(
                self.test_run_manager.get_debug_dir(), 
                'failures'
            )
            os.makedirs(artifacts_dir, exist_ok=True)
            
            timestamp = int(time.time())
            base_name = f'failure_{parameter_value}_{timestamp}'
            
            # Screenshot
            try:
                screenshot_path = os.path.join(artifacts_dir, f'{base_name}.png')
                self.driver.save_screenshot(screenshot_path)
                self.logger.debug(f"Saved screenshot: {screenshot_path}")
            except Exception as e:
                self.logger.warning(f"Could not save screenshot: {e}")
            
            # HTML
            try:
                html_path = os.path.join(artifacts_dir, f'{base_name}.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                self.logger.debug(f"Saved HTML: {html_path}")
            except Exception as e:
                self.logger.warning(f"Could not save HTML: {e}")
            
            # Console logs
            try:
                console_path = os.path.join(artifacts_dir, f'{base_name}_console.jsonl')
                logs = self.driver.get_log('browser')
                with open(console_path, 'w', encoding='utf-8') as f:
                    for entry in logs:
                        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
                self.logger.debug(f"Saved console logs: {console_path}")
            except Exception as e:
                self.logger.warning(f"Could not save console logs: {e}")
            
        except Exception as e:
            self.logger.error(f"Artifact capture failed: {e}")
    
    @with_retries(max_attempts=2)
    def run_single_test(self, parameter_value, delay_seconds=1, default_timeout=300):
        """Execute a single backtest"""
        start_time = time.time()
        self.logger.info(f"Starting test for {self.config['parameter_type']}={parameter_value}")
        
        if self.tests_since_recycle >= self.recycle_interval:
            self.logger.info(f"Proactive driver recycle after {self.tests_since_recycle} tests")
            self._recycle_driver()
        
        try:
            previous_results = self.test_page.extract_results()
            
            if not self.test_page.click_new_backtest():
                self.logger.warning("Failed to open dialog, refreshing page")
                self.test_page.refresh_page()
                if not self.test_page.click_new_backtest():
                    raise Exception("Failed to click New Backtest after refresh")
            
            if not self.test_page.wait_for_modal(timeout=10):
                raise Exception("Dialog did not open")
            
            if not self.set_and_verify_parameter(parameter_value):
                raise Exception(f"Failed to set/verify {self.config['parameter_type']}={parameter_value}")
            
            if not self.test_page.click_run():
                raise Exception("Failed to click Run")
            
            if not self.test_page.wait_for_backtest_start(timeout=15):
                self.logger.warning("No progress indicators seen, but continuing...")
            
            timeout = self._get_estimated_timeout(default_timeout)
            if not self.test_page.wait_for_backtest_complete(timeout=timeout):
                raise Exception("Backtest did not complete within timeout")
            
            if not self.test_page.wait_for_results_ready(timeout=20):
                raise Exception("Results not ready")
            
            if not self.test_page.wait_for_results_update(previous_results, timeout=45):
                self.logger.warning("Results may not have updated, but proceeding")
            
            results = self.test_page.extract_results()
            results['parameter_type'] = self.config['parameter_type']
            results['parameter_value'] = parameter_value
            results['timestamp'] = datetime.now().isoformat()
            results['worker_id'] = self.worker_id
            
            results = process_result_with_conversion(results)
            
            self.last_results = results
            
            trade_log_data = self.extract_trade_log(parameter_value)
            
            with results_lock:
                all_results.append(results)
                
                for trade in trade_log_data:
                    trade['backtest_parameter_type'] = self.config['parameter_type']
                    trade['backtest_parameter_value'] = parameter_value
                    trade['backtest_results'] = results
                
                all_trade_logs.extend(trade_log_data)
                
                if trade_log_data:
                    self._update_consolidated_trade_log_csv()
            
            # Save checkpoint after successful test
            if self.test_run_manager:
                self.test_run_manager.save_checkpoint(parameter_value, results)
            
            elapsed = time.time() - start_time
            self.backtest_times.append(int(elapsed))
            self.consecutive_failures = 0
            self.tests_since_recycle += 1
            
            self.logger.info(
                f"Test complete ({elapsed:.1f}s): CAGR={results['cagr']:.6f}, "
                f"MAR={results['mar']:.2f}, Trades={len(trade_log_data)}"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Test failed: {e}", exc_info=True)
            self.capture_failure_artifacts(parameter_value)
            raise
    
    def set_and_verify_parameter(self, value, max_attempts=3):
        """Set parameter value and VERIFY it stuck"""
        for attempt in range(max_attempts):
            try:
                self.logger.debug(f"Setting parameter (attempt {attempt + 1})")
                
                if not self.parameter_handler.set_value(self.driver, value):
                    self.logger.warning(f"Parameter handler returned False on attempt {attempt + 1}")
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)
                        continue
                    return False
                
                time.sleep(0.3)
                
                if self.parameter_handler.verify_value(self.driver, value):
                    self.logger.info(f"Parameter {self.config['parameter_type']}={value} verified")
                    return True
                else:
                    self.logger.warning(f"Parameter verification failed on attempt {attempt + 1}")
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)
                        self.test_page.clear_all_dialogs()
                        time.sleep(0.3)
                        if not self.test_page.click_new_backtest():
                            continue
                        if not self.test_page.wait_for_modal(timeout=10):
                            continue
                
            except Exception as e:
                self.logger.error(f"Error setting parameter on attempt {attempt + 1}: {e}")
                if attempt == max_attempts - 1:
                    return False
                time.sleep(0.5)
        
        return False
    
    def extract_trade_log(self, parameter_value):
        """Extract trade log with atomic download detection"""
        try:
            self.logger.info(f"Extracting trade log for {parameter_value}")
            
            if not self.test_page.navigate_to_trade_log():
                return []
            
            download_dir = self._get_download_directory()
            existing_files = set(os.listdir(download_dir))
            
            if not self.test_page.click_download_trade_log():
                return []
            
            downloaded_file = self._wait_for_download(download_dir, existing_files, timeout=30)
            
            if not downloaded_file:
                self.logger.error("Download timeout - no file received")
                return []
            
            trades_data = self._parse_trade_log_file(downloaded_file, parameter_value)
            
            try:
                timestamp = datetime.now().strftime('%H%M%S')
                organized_file = os.path.join(
                    download_dir, 
                    f"trade_log_{parameter_value}_{timestamp}.csv"
                )
                shutil.move(downloaded_file, organized_file)
                self.logger.info(f"Trade log saved: {organized_file}")
            except Exception as e:
                self.logger.warning(f"Could not move trade log file: {e}")
                try:
                    os.remove(downloaded_file)
                except:
                    pass
            
            self.logger.info(f"Extracted {len(trades_data)} trades")
            return trades_data
            
        except Exception as e:
            self.logger.error(f"Error extracting trade log: {e}")
            return []
    
    def _get_download_directory(self):
        if self.test_run_manager:
            download_dir = os.path.join(
                self.test_run_manager.get_downloads_dir(),
                f"worker_{self.worker_id}"
            )
        else:
            download_dir = f"downloads_worker_{self.worker_id}"
        
        os.makedirs(download_dir, exist_ok=True)
        return download_dir
    
    def _wait_for_download(self, download_dir, existing_files, timeout=30):
        """Wait for new file with atomic detection"""
        start_time = time.time()
        last_new_file = None
        last_size = 0
        stable_checks = 0
        
        while time.time() - start_time < timeout:
            try:
                current_files = set(os.listdir(download_dir))
                new_files = current_files - existing_files
                
                complete_files = [
                    f for f in new_files 
                    if not f.endswith('.crdownload') 
                    and not f.endswith('.tmp')
                    and os.path.isfile(os.path.join(download_dir, f))
                ]
                
                if complete_files:
                    newest_file = max(
                        complete_files,
                        key=lambda f: os.path.getmtime(os.path.join(download_dir, f))
                    )
                    newest_path = os.path.join(download_dir, newest_file)
                    
                    current_size = os.path.getsize(newest_path)
                    
                    if newest_file == last_new_file and current_size == last_size:
                        stable_checks += 1
                        if stable_checks >= 3:
                            self.logger.info(f"Download complete and stable: {newest_file}")
                            return newest_path
                    else:
                        stable_checks = 0
                        last_new_file = newest_file
                        last_size = current_size
                
            except Exception as e:
                self.logger.debug(f"Download check error: {e}")
            
            time.sleep(0.2)
        
        return None
    
    def _parse_trade_log_file(self, file_path, parameter_value):
        try:
            self.logger.debug(f"Parsing trade log: {file_path}")
            
            try:
                import pandas as pd
                
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                elif file_path.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path)
                else:
                    try:
                        df = pd.read_csv(file_path)
                    except:
                        df = pd.read_excel(file_path)
                
                trades_data = []
                for idx, row in df.iterrows():
                    trade_data = self._parse_trade_row(row.to_dict(), parameter_value)
                    if trade_data:
                        trades_data.append(trade_data)
                
                return trades_data
                
            except ImportError:
                return self._parse_trade_log_manual(file_path, parameter_value)
            
        except Exception as e:
            self.logger.error(f"Error parsing trade log: {e}")
            return []
    
    def _parse_trade_log_manual(self, file_path, parameter_value):
        trades_data = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                
                for row in csv_reader:
                    trade_data = self._parse_trade_row(row, parameter_value)
                    if trade_data:
                        trades_data.append(trade_data)
        
        except Exception as e:
            self.logger.error(f"Error in manual CSV parsing: {e}")
        
        return trades_data
    
    def _parse_trade_row(self, row_dict, parameter_value):
        try:
            trade_data = {
                'backtest_parameter_type': self.config['parameter_type'],
                'backtest_parameter_value': parameter_value,
                'trade_date_time': str(row_dict.get('Date Opened', '')) + ' ' + str(row_dict.get('Time Opened', '')),
                'opening_price': self._get_numeric(row_dict.get('Opening Price', 0)),
                'legs': str(row_dict.get('Legs', '')),
                'premium': self._get_numeric(row_dict.get('Premium', 0)),
                'closing_price': self._get_numeric(row_dict.get('Closing Price', 0)),
                'date_closed': str(row_dict.get('Date Closed', '')),
                'time_closed': str(row_dict.get('Time Closed', '')),
                'avg_closing_cost': self._get_numeric(row_dict.get('Avg. Closing Cost', 0)),
                'reason_for_close': str(row_dict.get('Reason For Close', '')),
                'trade_pnl': self._get_numeric(row_dict.get('P/L', 0)),
                'num_contracts': self._get_numeric(row_dict.get('No. of Contracts', 0)),
                'funds_at_close': self._get_numeric(row_dict.get('Funds at Close', 0)),
                'margin_req': self._get_numeric(row_dict.get('Margin Req.', 0)),
                'strategy': str(row_dict.get('Strategy', '')),
                'opening_commissions': self._get_numeric(row_dict.get('Opening Commissions + Fees', 0)),
                'closing_commissions': self._get_numeric(row_dict.get('Closing Commissions + Fees', 0)),
                'opening_ratio': self._get_numeric(row_dict.get('Opening Short/Long Ratio', 0)),
                'closing_ratio': self._get_numeric(row_dict.get('Closing Short/Long Ratio', 0)),
                'gap': self._get_numeric(row_dict.get('Gap', 0)),
                'movement': self._get_numeric(row_dict.get('Movement', 0)),
                'max_profit': self._get_numeric(row_dict.get('Max Profit', 0)),
                'max_loss': self._get_numeric(row_dict.get('Max Loss', 0)),
                'extracted_timestamp': datetime.now().isoformat(),
                'worker_id': self.worker_id
            }
            
            return trade_data
            
        except Exception as e:
            self.logger.warning(f"Error parsing trade row: {e}")
            return None
    
    def _get_numeric(self, value):
        try:
            if value is None or (isinstance(value, str) and value.lower() in ['nan', '', 'none']):
                return 0
            if isinstance(value, (int, float)):
                return float(value)
            
            value_str = str(value).strip()
            cleaned = re.sub(r'[,$%]', '', value_str)
            match = re.search(r'-?\d+\.?\d*', cleaned)
            return float(match.group()) if match else 0
        except:
            return 0
    
    def _update_consolidated_trade_log_csv(self):
        try:
            if self.test_run_manager:
                filepath = self.test_run_manager.get_results_file('consolidated_trade_log.csv')
            else:
                timestamp = datetime.now().strftime('%Y%m%d')
                filepath = f'consolidated_trade_log_{timestamp}.csv'
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                headers = [
                    'Backtest Parameter Type', 'Backtest Parameter Value', 'Trade Date Time',
                    'Opening Price', 'Legs', 'Premium', 'Closing Price', 'Date Closed',
                    'Time Closed', 'Avg Closing Cost', 'Reason For Close', 'Trade P&L',
                    'Num Contracts', 'Funds at Close', 'Margin Req', 'Strategy',
                    'Opening Commissions', 'Closing Commissions', 'Opening Ratio',
                    'Closing Ratio', 'Gap', 'Movement', 'Max Profit', 'Max Loss',
                    'Extracted Timestamp', 'Worker ID'
                ]
                writer.writerow(headers)
                
                sorted_trades = sorted(
                    all_trade_logs,
                    key=lambda x: (str(x.get('backtest_parameter_value', '')),
                                  str(x.get('trade_date_time', '')))
                )
                
                for trade in sorted_trades:
                    row = [
                        trade.get(k, '') for k in [
                            'backtest_parameter_type', 'backtest_parameter_value',
                            'trade_date_time', 'opening_price', 'legs', 'premium',
                            'closing_price', 'date_closed', 'time_closed',
                            'avg_closing_cost', 'reason_for_close', 'trade_pnl',
                            'num_contracts', 'funds_at_close', 'margin_req', 'strategy',
                            'opening_commissions', 'closing_commissions',
                            'opening_ratio', 'closing_ratio', 'gap', 'movement',
                            'max_profit', 'max_loss', 'extracted_timestamp', 'worker_id'
                        ]
                    ]
                    writer.writerow(row)
            
        except Exception as e:
            self.logger.error(f"Error updating consolidated trade log: {e}")
    
    def _get_estimated_timeout(self, default=300):
        if not self.backtest_times:
            return default
        
        recent_times = self.backtest_times[-5:] if len(self.backtest_times) > 5 else self.backtest_times
        avg_time = sum(recent_times) / len(recent_times)
        return max(int(avg_time * 1.5), default)
    
    def cleanup(self):
        try:
            if self.driver:
                self.driver.quit()
            self.logger.info("Worker cleaned up")
        except Exception as e:
            self.logger.warning(f"Cleanup error: {e}")


# ============================================================================
# WORKER THREAD FUNCTION
# ============================================================================

def worker_thread_main(worker_id, task_queue, config, credentials, original_values_set):
    """Main worker thread function"""
    worker = OptionOmegaWorker(worker_id, task_queue, config, debug=config.get('debug', False))
    
    try:
        if worker_id == 0:
            worker.logger.info("Starting immediately (primary worker)")
        else:
            init_delay = random.randint(10, 30)
            worker.logger.info(f"Starting in {init_delay}s (secondary worker)")
            time.sleep(init_delay)
        
        if not worker.setup_driver(config.get('chrome_path'), base_port=9222):
            worker.logger.error("Failed to initialize driver")
            return
        
        login_url = config['test_url'].split('/test')[0] + '/login'
        worker.driver.get(login_url)
        time.sleep(2)
        
        if not worker.perform_login(credentials['username'], credentials['password']):
            worker.logger.error("Login failed")
            return
        
        if not worker.test_page.open(config['test_url']):
            worker.logger.error("Test URL validation failed")
            return
        
        worker.logger.info("Ready to process tasks")
        
        while not shutdown_event.is_set():
            try:
                parameter_value = task_queue.get(timeout=10)
                parameter_str = str(parameter_value)
                
                if parameter_str not in original_values_set:
                    worker.logger.debug(f"Skipping {parameter_value} - not in original set")
                    task_queue.task_done()
                    continue
                
                with results_lock:
                    already_completed = any(
                        str(r.get('parameter_value', '')) == parameter_str
                        for r in all_results
                    )
                
                if already_completed:
                    worker.logger.info(f"Parameter {parameter_value} already completed, skipping")
                    task_queue.task_done()
                    continue
                
                success = worker.run_single_test(
                    parameter_value,
                    config.get('delay_seconds', 1),
                    config.get('backtest_timeout', 300)
                )
                
                if success:
                    worker.logger.info(f"✅ Completed {parameter_value}")
                else:
                    worker.logger.error(f"❌ Failed {parameter_value}")
                
                task_queue.task_done()
                time.sleep(1)
                
            except queue.Empty:
                continue
            except Exception as e:
                worker.logger.error(f"Unexpected error: {e}", exc_info=True)
                try:
                    task_queue.task_done()
                except:
                    pass
        
    except Exception as e:
        worker.logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        worker.cleanup()
        worker.logger.info("Worker exited")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_parameter_values(parameter_type, config):
    handler = ParameterFactory.create_parameter(parameter_type, config)
    return handler.generate_values()


def load_configuration(args):
    config = {
        'test_url': None,
        'parameter_type': 'entry_time',
        'delay_seconds': 1,
        'backtest_timeout': 300,
        'max_workers': 2,
        'chrome_path': None,
        'debug': False,
    }
    
    config_file = args.config if args.config else 'config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
            print(f"Loaded configuration from {config_file}")
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
    
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


def interactive_configuration(config):
    """Interactive configuration - same as before"""
    while not config.get('test_url'):
        print("\n" + "="*60)
        print("ENHANCED OPTIONOMEGA AUTOMATION - URL REQUIRED")
        print("="*60)
        url = input("Enter OptionOmega test URL (required): ").strip()
        
        if url and 'optionomega.com' in url and '/test/' in url:
            config['test_url'] = url
            print(f"✅ URL validated: {url}")
        else:
            print("❌ Invalid URL")
    
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
            choice = input(f"\nSelect parameter (1-{len(available_params)}): ").strip()
            param_index = int(choice) - 1
            if 0 <= param_index < len(available_params):
                config['parameter_type'] = available_params[param_index]
                selected_handler = param_handlers[config['parameter_type']]
                print(f"✅ Selected: {selected_handler.get_name()}")
                break
        except ValueError:
            print("Please enter a number.")
    
    config = selected_handler.configure_interactive(config)
    
    return config


def get_credentials():
    def load_user_config():
        config_file = 'user_config.json'
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_user_config(user_config):
        try:
            with open('user_config.json', 'w') as f:
                json.dump(user_config, f, indent=2)
        except:
            pass
    
    user_config = load_user_config()
    
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
    
    if username:
        user_config['username'] = username
        save_user_config(user_config)
    
    password = getpass.getpass("Enter password (hidden): ")
    
    return {'username': username, 'password': password}


def export_results_to_csv(config, results, backup=False):
    if not results:
        return None
    
    try:
        corrected_results = [process_result_with_conversion(r) for r in results]
        
        test_run_manager = config.get('test_run_manager')
        parameter_type = config.get('parameter_type', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        filename = f'results_{parameter_type}_{"backup_" if backup else ""}{timestamp}.csv'
        
        if test_run_manager:
            filepath = os.path.join(
                test_run_manager.get_backups_dir() if backup else test_run_manager.base_dir,
                filename
            )
        else:
            filepath = filename
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Parameter Type', 'Parameter Value', 'CAGR', 'Max Drawdown',
                'Win Percentage', 'Capture Rate', 'MAR', 'Worker ID', 'Timestamp'
            ])
            
            sorted_results = sorted(corrected_results, key=lambda x: str(x.get('parameter_value', '')))
            
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


def save_progress_backup(config, all_values):
    try:
        completion_pct = 0
        if all_values:
            with results_lock:
                completion_pct = len(all_results) / len(all_values) * 100
        
        serializable_config = {k: v for k, v in config.items() if k not in ['test_run_manager', 'parameter_handler', 'credentials']}
        
        progress_data = {
            'config': serializable_config,
            'completion_percentage': completion_pct,
            'total_tests': len(all_values),
            'completed_tests': len(all_results),
            'timestamp': datetime.now().isoformat(),
            'results': all_results
        }
        
        test_run_manager = config.get('test_run_manager')
        if test_run_manager:
            progress_file = test_run_manager.get_results_file('progress.json')
            backup_file = os.path.join(
                test_run_manager.get_backups_dir(),
                f'backup_{int(completion_pct)}pct_{datetime.now().strftime("%H%M%S")}.json'
            )
        else:
            progress_file = 'progress.json'
            backup_file = f'backup_{int(completion_pct)}pct.json'
        
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        if int(completion_pct) % 5 == 0 and completion_pct > 0:
            with open(backup_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        
        if all_results:
            export_results_to_csv(config, all_results, backup=True)
            
    except Exception as e:
        logging.error(f"Error saving progress: {e}", extra={'worker_id': 'MAIN'})


def save_progress_periodically(config, all_values):
    while not shutdown_event.is_set():
        time.sleep(60)
        with progress_lock:
            save_progress_backup(config, all_values)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    print("ENHANCED OPTIONOMEGA AUTOMATION v5.1 - WITH CHECKPOINT/RESUME")
    print("="*90)
    
    parser = argparse.ArgumentParser(description='Enhanced OptionOmega Automation')
    parser.add_argument('--url', type=str, help='Test URL')
    parser.add_argument('--parameter', type=str, choices=ParameterFactory.get_available_parameters())
    parser.add_argument('--delay', type=int, help='Result delay in seconds')
    parser.add_argument('--timeout', type=int, help='Backtest timeout in seconds')
    parser.add_argument('--max-workers', type=int, help='Maximum worker processes')
    parser.add_argument('--config', type=str, help='Config file path')
    parser.add_argument('--chrome-path', type=str, help='Chrome executable path')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    config = load_configuration(args)
    config = interactive_configuration(config)
    
    test_run_manager = TestRunManager(config['test_url'], config['parameter_type'])
    config['test_run_manager'] = test_run_manager
    
    setup_logging(test_run_manager.base_dir)
    logger = logging.getLogger(__name__)
    logger.info("Automation started", extra={'worker_id': 'MAIN'})
    
    print("\nLOGIN CREDENTIALS")
    print("="*50)
    credentials = get_credentials()
    config['credentials'] = credentials
    print("="*50)
    
    all_values = generate_parameter_values(config['parameter_type'], config)
    original_values_set = set(str(v) for v in all_values)
    
    # Load checkpoint and filter out completed parameters
    if test_run_manager:
        completed = test_run_manager.load_completed_params()
        completed_str = {test_run_manager._param_key(v) for v in all_values 
                        if test_run_manager._param_key(v) in completed}
        
        remaining_values = [v for v in all_values 
                           if test_run_manager._param_key(v) not in completed]
        
        if completed_str:
            logger.info(f"Resuming: {len(completed_str)} already completed, "
                       f"{len(remaining_values)} remaining", 
                       extra={'worker_id': 'MAIN'})
            all_values = remaining_values
        
        if not all_values:
            logger.info("All parameters already completed!", extra={'worker_id': 'MAIN'})
            print("\n" + "="*90)
            print("All tests already complete. Generating final reports...")
            print("="*90)
            
            # Load results from checkpoint for final export
            with results_lock:
                for key in completed:
                    # Load from checkpoint file if needed
                    pass
            
            if all_results:
                export_results_to_csv(config, all_results)
                if all_trade_logs:
                    enhance_results_with_trade_metrics(config, all_results, all_trade_logs)
            
            return
    
    task_queue = queue.Queue()
    
    for value in all_values:
        task_queue.put(value)
    
    param_handler = ParameterFactory.create_parameter(config['parameter_type'], config)
    
    logger.info(f"Starting with {config.get('max_workers', 2)} workers", extra={'worker_id': 'MAIN'})
    logger.info(f"Parameter: {param_handler.get_name()}", extra={'worker_id': 'MAIN'})
    logger.info(f"Total tests: {len(all_values)}", extra={'worker_id': 'MAIN'})
    
    threads = []
    
    try:
        progress_thread = threading.Thread(target=save_progress_periodically, args=(config, all_values))
        progress_thread.daemon = True
        progress_thread.start()
        
        for worker_id in range(config.get('max_workers', 2)):
            thread = threading.Thread(
                target=worker_thread_main,
                args=(worker_id, task_queue, config, credentials, original_values_set)
            )
            thread.start()
            threads.append(thread)
        
        start_time = time.time()
        last_count = 0
        
        while True:
            time.sleep(15)
            
            with results_lock:
                completed_parameters = set(str(r.get('parameter_value', '')) for r in all_results)
                current_count = len(completed_parameters)
                progress_pct = (current_count / len(original_values_set)) * 100 if original_values_set else 0
            
            if current_count != last_count:
                elapsed_minutes = (time.time() - start_time) / 60
                if current_count > 0:
                    rate_per_minute = current_count / elapsed_minutes
                    eta_minutes = (len(original_values_set) - current_count) / rate_per_minute if rate_per_minute > 0 else 0
                    logger.info(
                        f"Progress: {current_count}/{len(original_values_set)} ({progress_pct:.1f}%) - "
                        f"Rate: {rate_per_minute:.1f}/min - ETA: {eta_minutes:.1f}min",
                        extra={'worker_id': 'MAIN'}
                    )
                
                last_count = current_count
                
                if current_count % max(1, len(original_values_set) // 10) == 0:
                    save_progress_backup(config, all_values)
            
            missing_parameters = original_values_set - completed_parameters
            
            if not missing_parameters:
                logger.info(f"All {len(original_values_set)} parameters completed!", extra={'worker_id': 'MAIN'})
                shutdown_event.set()
                break
            
            active_threads = [t for t in threads if t.is_alive()]
            if not active_threads and missing_parameters:
                logger.warning(f"All workers died", extra={'worker_id': 'MAIN'})
                break
        
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=30)
        
        print("\n" + "="*90)
        print("AUTOMATION COMPLETED!")
        print("="*90)
        
        with results_lock:
            total_results = len(all_results)
            unique_parameters = set(str(r.get('parameter_value', '')) for r in all_results)
        
        logger.info(f"Total results: {total_results}", extra={'worker_id': 'MAIN'})
        logger.info(f"Unique parameters: {len(unique_parameters)}", extra={'worker_id': 'MAIN'})
        logger.info(f"Total trades: {len(all_trade_logs)}", extra={'worker_id': 'MAIN'})
        logger.info(f"Total time: {(time.time() - start_time) / 60:.1f} minutes", extra={'worker_id': 'MAIN'})
        
        if all_results:
            unique_results = []
            seen = set()
            for r in all_results:
                param_val = str(r.get('parameter_value', ''))
                if param_val not in seen:
                    unique_results.append(r)
                    seen.add(param_val)
            
            csv_file = export_results_to_csv(config, unique_results)
            
            if all_trade_logs:
                enhanced_csv = enhance_results_with_trade_metrics(config, unique_results, all_trade_logs)
                if enhanced_csv:
                    logger.info(f"Enhanced results: {enhanced_csv}", extra={'worker_id': 'MAIN'})
        
        print("="*90)
        test_run_manager.cleanup_temp_files()
        
    except KeyboardInterrupt:
        print("\nInterrupted. Saving progress...")
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            unique_results = []
            seen = set()
            for r in all_results:
                param_val = str(r.get('parameter_value', ''))
                if param_val not in seen:
                    unique_results.append(r)
                    seen.add(param_val)
            
            export_results_to_csv(config, unique_results)
            if all_trade_logs:
                enhance_results_with_trade_metrics(config, unique_results, all_trade_logs)
            save_progress_backup(config, all_values)
        
        test_run_manager.cleanup_temp_files()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True, extra={'worker_id': 'MAIN'})
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            export_results_to_csv(config, all_results)
            if all_trade_logs:
                enhance_results_with_trade_metrics(config, all_results, all_trade_logs)
        
        test_run_manager.cleanup_temp_files()


if __name__ == "__main__":
    main()
