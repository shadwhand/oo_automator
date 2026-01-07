"""
Enhanced OptionOmega Backtesting Automation - Playwright Version
Migrated from Selenium to Playwright for better reliability and performance
"""

import time  # Still needed for thread management and timing calculations
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
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, expect
import pandas as pd

# Import the parameter plugin system (Playwright version)
from parameter_plugin_system_playwright import ParameterFactory, BaseParameter
# Import the trade analysis plugin (should work with both versions)
try:
    from trade_analysis_plugin import enhance_results_with_trade_metrics
except ImportError:
    enhance_results_with_trade_metrics = None
    print("Warning: trade_analysis_plugin not found, enhanced metrics will be disabled")

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
        os.makedirs(os.path.join(base_path, "traces"), exist_ok=True)  # For Playwright traces
        
        print(f"Created test run directory: {base_path}")
        return base_path
    
    def get_downloads_dir(self):
        return os.path.join(self.base_dir, "downloads")
    
    def get_debug_dir(self):
        return os.path.join(self.base_dir, "debug")
    
    def get_backups_dir(self):
        return os.path.join(self.base_dir, "backups")
    
    def get_traces_dir(self):
        return os.path.join(self.base_dir, "traces")
    
    def get_results_file(self, filename):
        return os.path.join(self.base_dir, filename)
    
    def cleanup_temp_files(self):
        """Clean up temporary worker files"""
        try:
            # Clean up any worker-specific temp directories
            for item in os.listdir('.'):
                if item.startswith('downloads_worker_') or item.startswith('playwright_worker_'):
                    if os.path.isdir(item):
                        shutil.rmtree(item)
                    else:
                        os.remove(item)
        except Exception as e:
            print(f"Warning: Could not clean up temp files: {e}")


class OptionOmegaWorker:
    """Individual worker for processing backtests using Playwright"""
    
    def __init__(self, worker_id, task_queue, config, debug=False):
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.config = config
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
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
    
    def setup_browser(self):
        """Initialize Playwright browser with isolated context"""
        try:
            self.playwright = sync_playwright().start()
            
            # Launch browser with options
            launch_args = [
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
            
            # Launch Chromium browser (Playwright manages its own browser binaries)
            self.browser = self.playwright.chromium.launch(
                headless=False,  # Set to True for production
                args=launch_args
            )
            
            # Create isolated context for this worker
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'ignore_https_errors': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # Setup download handling
            if self.test_run_manager:
                download_dir = os.path.join(
                    self.test_run_manager.get_downloads_dir(),
                    f"worker_{self.worker_id}"
                )
                os.makedirs(download_dir, exist_ok=True)
                context_options['accept_downloads'] = True
                
            self.context = self.browser.new_context(**context_options)
            self.context.set_default_timeout(30000)  # 30 second default timeout
            
            # Enable tracing for debugging if needed
            if self.debug and self.test_run_manager:
                trace_file = os.path.join(
                    self.test_run_manager.get_traces_dir(),
                    f"worker_{self.worker_id}_trace.zip"
                )
                self.context.tracing.start(
                    screenshots=True, 
                    snapshots=True,
                    sources=True
                )
            
            # Create page
            self.page = self.context.new_page()
            
            # Add console logging if debug mode
            if self.debug:
                self.page.on("console", lambda msg: print(f"Worker {self.worker_id} Console: {msg.text}"))
            
            print(f"Worker {self.worker_id}: Playwright browser initialized")
            return True
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to setup browser: {e}")
            return False
    
    def perform_login(self, username, password):
        """Automated login with Playwright's robust waiting"""
        try:
            # Wait for login form to be ready
            self.page.wait_for_load_state('domcontentloaded')
            
            # Find and fill username field - try multiple selectors
            username_selectors = [
                "input[type='email']",
                "input[type='text'][name*='email' i]",
                "input[type='text'][name*='user' i]", 
                "input[placeholder*='email' i]",
                "input[placeholder*='username' i]",
                "#email",
                "#username",
                "input[type='text']:visible"
            ]
            
            username_filled = False
            for selector in username_selectors:
                try:
                    # Try to fill directly - Playwright will wait and throw if element not found
                    self.page.locator(selector).first.fill(username)
                    username_filled = True
                    print(f"Worker {self.worker_id}: Filled username with selector: {selector}")
                    break
                except:
                    continue
            
            if not username_filled:
                print(f"Worker {self.worker_id}: Could not find username field")
                # Try to log visible input fields for debugging
                try:
                    inputs = self.page.locator("input:visible").all()
                    print(f"Worker {self.worker_id}: Found {len(inputs)} visible input fields")
                    for i, inp in enumerate(inputs[:5]):  # Check first 5
                        input_type = inp.get_attribute('type')
                        input_name = inp.get_attribute('name')
                        input_placeholder = inp.get_attribute('placeholder')
                        print(f"  Input {i}: type={input_type}, name={input_name}, placeholder={input_placeholder}")
                except:
                    pass
                return False
            
            # Fill password field
            password_selectors = [
                "input[type='password']",
                "input[name*='pass' i]",
                "#password"
            ]
            
            password_filled = False
            for selector in password_selectors:
                try:
                    self.page.locator(selector).first.fill(password)
                    password_filled = True
                    print(f"Worker {self.worker_id}: Filled password")
                    break
                except:
                    continue
            
            if not password_filled:
                print(f"Worker {self.worker_id}: Could not find password field")
                return False
            
            # Submit login - try multiple methods
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']", 
                "button:has-text('Login')",
                "button:has-text('Sign In')",
                "button:has-text('Sign in')",
                "button:has-text('Log in')",
                "[type='submit']"
            ]
            
            submitted = False
            for selector in submit_selectors:
                try:
                    self.page.locator(selector).first.click()
                    submitted = True
                    print(f"Worker {self.worker_id}: Clicked submit button")
                    break
                except:
                    continue
            
            if not submitted:
                # Try pressing Enter in the password field as fallback
                try:
                    self.page.locator("input[type='password']").press("Enter")
                    submitted = True
                    print(f"Worker {self.worker_id}: Submitted via Enter key")
                except:
                    pass
            
            if not submitted:
                print(f"Worker {self.worker_id}: Could not find submit button")
                return False
            
            # Wait for navigation or URL change
            try:
                # Wait for either dashboard URL or any navigation
                self.page.wait_for_url("**/dashboard/**", timeout=10000)
                print(f"Worker {self.worker_id}: Login successful - navigated to dashboard")
                return True
            except:
                # Check if login was successful by URL
                self.page.wait_for_timeout(3000)  # Wait for page to settle
                current_url = self.page.url.lower()
                if 'login' not in current_url and 'signin' not in current_url:
                    print(f"Worker {self.worker_id}: Login appears successful - URL changed")
                    return True
                
                # Check for error messages
                error_selectors = [
                    "text=/invalid|incorrect|failed/i",
                    ".error-message",
                    ".alert-danger",
                    "[role='alert']"
                ]
                
                for selector in error_selectors:
                    try:
                        if self.page.locator(selector).is_visible():
                            error_text = self.page.locator(selector).first.text_content()
                            print(f"Worker {self.worker_id}: Login error detected: {error_text}")
                            return False
                    except:
                        continue
                
                # If no error and URL changed from login page, might be successful
                if 'login' not in current_url:
                    print(f"Worker {self.worker_id}: Login possibly successful - no longer on login page")
                    return True
                else:
                    print(f"Worker {self.worker_id}: Still on login page after submit")
                    return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Login error: {e}")
            import traceback
            print(f"Worker {self.worker_id}: Traceback: {traceback.format_exc()}")
            return False
    
    def validate_test_url(self, test_url, max_retries=3):
        """Validate test URL and handle dashboard redirects"""
        for attempt in range(max_retries):
            try:
                self.page.goto(test_url, timeout=30000)
                
                # Don't wait for networkidle - just wait for DOM
                try:
                    self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                except:
                    pass  # Page may still be usable even if this times out
                
                # Give the page a moment to render
                self.page.wait_for_timeout(2000)
                
                current_url = self.page.url.lower()
                
                # Check if redirected to dashboard
                if 'dashboard/tests' in current_url:
                    print(f"Worker {self.worker_id}: Redirected to dashboard, reloading test URL (attempt {attempt + 1})")
                    self.page.wait_for_timeout(2000)
                    continue
                
                # Look for New Backtest button to confirm we're on the right page
                try:
                    self.page.locator("button:has-text('New Backtest')").wait_for(timeout=5000)
                    print(f"Worker {self.worker_id}: Test page validated successfully")
                    return True
                except:
                    print(f"Worker {self.worker_id}: New Backtest button not found, retrying...")
                    continue
                    
            except Exception as e:
                print(f"Worker {self.worker_id}: URL validation error: {e}")
                self.page.wait_for_timeout(5000)
        
        print(f"Worker {self.worker_id}: Failed to validate test URL after {max_retries} attempts")
        return False
    
    def click_new_backtest(self):
        """Click the New Backtest button with Playwright's smart waiting"""
        try:
            # Wait a bit for any animations
            self.page.wait_for_timeout(2000)
            
            # Multiple selector strategies
            selectors = [
                "button:has-text('New Backtest')",
                "div.mt-4 > button",
                "button >> text=/new backtest/i",
                "xpath=//button[contains(., 'New Backtest')]"
            ]
            
            for selector in selectors:
                try:
                    # Wait for the button to be visible and click it
                    locator = self.page.locator(selector).first
                    locator.wait_for(state="visible", timeout=2000)
                    locator.click()
                    return True
                except:
                    continue
            
            print(f"Worker {self.worker_id}: Could not find New Backtest button")
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to click New Backtest: {e}")
            return False
    
    def wait_for_dialog(self, timeout=5000):
        """Wait for dialog using Playwright's wait methods"""
        try:
            # Wait for any of these to appear indicating dialog is open
            dialog_selectors = [
                "input[type='time']",
                "[role='dialog']",
                "[id*='headlessui-dialog']",
                "form"
            ]
            
            # Use Playwright's wait_for properly
            for selector in dialog_selectors:
                try:
                    self.page.locator(selector).first.wait_for(state="visible", timeout=timeout)
                    return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error waiting for dialog: {e}")
            return False
    
    def set_parameter_value(self, parameter_type, value):
        """Set parameter value using the plugin system with automatic retry"""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                success = self.parameter_handler.set_value(self.page, value)
                if success:
                    return True
                    
                # If failed, wait and retry
                self.page.wait_for_timeout(1000)
                
            except Exception as e:
                print(f"Worker {self.worker_id}: Attempt {attempt + 1} failed: {e}")
                
        return False
    
    def click_run(self):
        """Click the Run button in the dialog"""
        try:
            self.page.wait_for_timeout(1000)
            
            # Multiple strategies to find Run button
            run_selectors = [
                "button:has-text('Run')",
                "[role='dialog'] button:last-of-type",
                "xpath=//button[text()='Run']",
                "form button:last-child"
            ]
            
            for selector in run_selectors:
                try:
                    locator = self.page.locator(selector).first
                    # Wait for button to be visible and enabled
                    locator.wait_for(state="visible", timeout=2000)
                    locator.click()
                    
                    # Verify dialog starts closing
                    self.page.wait_for_timeout(1000)
                    return True
                except:
                    continue
                    
            print(f"Worker {self.worker_id}: Could not find Run button")
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to click Run: {e}")
            return False
    
    def wait_for_backtest_completion(self, timeout=300000):
        """Wait for backtest with Playwright's robust waiting"""
        try:
            start_time = time.time()
            
            # First, wait for progress indicator to appear
            progress_selectors = [
                "text=/Running Backtest|Processing|ETA/",
                "[class*='animate-spin']",
                "[role='status']",
                "text=/calculating|running/i"
            ]
            
            progress_appeared = False
            # Try to detect progress indicator for up to 10 seconds
            for i in range(10):
                for selector in progress_selectors:
                    try:
                        locator = self.page.locator(selector).first
                        if locator.count() > 0 and locator.is_visible():
                            progress_appeared = True
                            print(f"Worker {self.worker_id}: Backtest progress detected")
                            break
                    except:
                        continue
                
                if progress_appeared:
                    break
                    
                # Check if dialog closed quickly (quick completion)
                try:
                    dialog_locator = self.page.locator("[role='dialog']")
                    if dialog_locator.count() == 0:
                        return True  # Dialog gone, backtest complete
                except:
                    pass
                    
                self.page.wait_for_timeout(1000)
            
            # Wait for progress to disappear (backtest complete)
            if progress_appeared:
                for selector in progress_selectors:
                    try:
                        locator = self.page.locator(selector).first
                        locator.wait_for(state="hidden", timeout=timeout)
                        break
                    except:
                        continue
            
            # Record time taken
            elapsed = int(time.time() - start_time)
            self.backtest_times.append(elapsed)
            print(f"Worker {self.worker_id}: Backtest completed in {elapsed} seconds")
            
            return True
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error waiting for backtest: {e}")
            return False
    
    def wait_for_dialog_close(self, timeout=15000):
        """Wait for main dialog to close"""
        try:
            dialog_selectors = [
                "[role='dialog']",
                "[id*='headlessui-dialog']"
            ]
            
            for selector in dialog_selectors:
                try:
                    self.page.locator(selector).wait_for(state="hidden", timeout=timeout)
                    return True
                except:
                    continue
                    
            # Try pressing escape if dialog is stuck
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(1000)
            return True
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error waiting for dialog close: {e}")
            return False
    
    def wait_for_results_update(self, previous_results, timeout=45000):
        """Wait for results to change from previous values"""
        start_time = time.time()
        self.page.wait_for_timeout(1000)  # Initial delay
        
        while (time.time() - start_time) * 1000 < timeout:
            current_results = self.extract_results()
            
            if self._results_changed(previous_results, current_results):
                self.page.wait_for_timeout(1000)  # Stabilization wait
                return True
            
            self.page.wait_for_timeout(500)  # Poll interval
        
        return False
    
    def _results_changed(self, old, new, tolerance=0.0001):
        """Check if results have meaningfully changed"""
        for key in ['cagr', 'maxDrawdown', 'winPercentage', 'captureRate']:
            if abs(new.get(key, 0) - old.get(key, 0)) > tolerance:
                return True
        return False
    
    def extract_results(self):
        """Extract all metrics from current page using Playwright"""
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
        """Extract a specific metric value using Playwright"""
        try:
            # Find all dt elements
            dt_elements = self.page.locator("dt").all()
            for dt in dt_elements:
                # Get text content of each dt element
                dt_text = dt.text_content()
                if dt_text and metric_name in dt_text:
                    # Find the corresponding dd element
                    parent = dt.locator("..")
                    dd_text = parent.locator("dd").text_content()
                    
                    # Extract numeric value
                    if dd_text:
                        match = re.search(r'-?\d+\.?\d*', dd_text)
                        if match:
                            return float(match.group())
        except Exception as e:
            print(f"Worker {self.worker_id}: Error extracting {metric_name}: {e}")
        
        return 0
    
    def extract_trade_log(self, parameter_value):
        """Navigate to trade log and download complete trade data using Playwright"""
        try:
            print(f"Worker {self.worker_id}: Downloading trade log for {parameter_value}")
            
            # Navigate to Trade Log tab
            trade_log_selectors = [
                "a:has-text('Trade Log')",
                "nav a:has-text('Trade')",
                "a[href*='trade']",
                "xpath=//a[contains(., 'Trade Log')]"
            ]
            
            clicked = False
            for selector in trade_log_selectors:
                try:
                    locator = self.page.locator(selector).first
                    # Wait for the element to be visible before clicking
                    locator.wait_for(state="visible", timeout=2000)
                    locator.click()
                    clicked = True
                    break
                except:
                    continue
            
            if not clicked:
                print(f"Worker {self.worker_id}: Could not find Trade Log tab")
                return []
            
            # Wait for trade log to load - use domcontentloaded instead of networkidle
            try:
                self.page.wait_for_load_state('domcontentloaded', timeout=5000)
            except:
                pass  # Continue even if this times out
            
            # Give the page time to render
            self.page.wait_for_timeout(3000)
            
            # Setup download promise before clicking
            download_path = None
            try:
                with self.page.expect_download() as download_info:
                    # Click download button with multiple strategies
                    download_selectors = [
                        "svg path",
                        "[title*='Download']",
                        "[aria-label*='Download']",
                        ".download-btn",
                        ".export-btn",
                        "button:has(svg)",
                        "div.hidden path:first-of-type"
                    ]
                    
                    for selector in download_selectors:
                        try:
                            locator = self.page.locator(selector).first
                            # Check if element exists before trying to interact
                            if locator.count() > 0:
                                # Try clicking with specific coordinates if needed
                                box = locator.bounding_box()
                                if box:
                                    self.page.mouse.click(box['x'] + 10, box['y'] + 11)
                                    break
                                else:
                                    locator.click()
                                    break
                        except:
                            continue
                
                download = download_info.value
                
                # Save to organized location
                if self.test_run_manager:
                    download_path = os.path.join(
                        self.test_run_manager.get_downloads_dir(),
                        f"trade_log_{parameter_value}_{datetime.now().strftime('%H%M%S')}.csv"
                    )
                else:
                    download_path = f"trade_log_{parameter_value}.csv"
                
                download.save_as(download_path)
                print(f"Worker {self.worker_id}: Saved trade log to {download_path}")
                
            except Exception as e:
                print(f"Worker {self.worker_id}: Download failed: {e}")
                return []
            
            # Parse the downloaded file
            if download_path and os.path.exists(download_path):
                trades_data = self._parse_downloaded_trade_log(download_path, parameter_value)
                print(f"Worker {self.worker_id}: Processed {len(trades_data)} trade records")
                return trades_data
            
            return []
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error extracting trade log: {e}")
            return []
    
    def _parse_downloaded_trade_log(self, file_path, parameter_value):
        """Parse the downloaded trade log file (CSV or Excel)"""
        try:
            print(f"Worker {self.worker_id}: Parsing downloaded file: {file_path}")
            
            # Try pandas first if available
            try:
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
                
                trades_data = []
                for idx, row in df.iterrows():
                    trade_data = self._parse_trade_row_from_dict(row.to_dict(), parameter_value)
                    if trade_data:
                        trades_data.append(trade_data)
                
                return trades_data
                
            except ImportError:
                # Fallback to manual CSV parsing
                return self._parse_downloaded_file_manual(file_path, parameter_value)
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error parsing downloaded file: {e}")
            return []
    
    def _parse_downloaded_file_manual(self, file_path, parameter_value):
        """Manual parsing without pandas for CSV files"""
        try:
            trades_data = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                
                for row in csv_reader:
                    trade_data = self._parse_trade_row_from_dict(row, parameter_value)
                    if trade_data:
                        trades_data.append(trade_data)
            
            return trades_data
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error in manual file parsing: {e}")
            return []
    
    def _parse_trade_row_from_dict(self, row_dict, parameter_value):
        """Parse trade row from dictionary using actual OptionOmega column names"""
        try:
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
                self.page.reload()
                self.page.wait_for_load_state('networkidle')
                if not self.click_new_backtest():
                    raise Exception("Failed to click New Backtest after refresh")
            
            if not self.wait_for_dialog():
                raise Exception("Dialog did not open")
            
            # Set the parameter using the plugin system
            if not self.set_parameter_value(self.config['parameter_type'], parameter_value):
                raise Exception(f"Failed to set {self.config['parameter_type']} to {parameter_value}")
            
            self.page.wait_for_timeout(1000)
            
            if not self.click_run():
                raise Exception("Failed to click Run")
            
            # Wait for backtest completion
            timeout = self._get_estimated_timeout(default_timeout) * 1000  # Convert to ms
            if not self.wait_for_backtest_completion(timeout):
                raise Exception("Backtest did not complete within timeout")
            
            self.wait_for_dialog_close()
            
            # Wait for results to render
            self.page.wait_for_timeout(delay_seconds * 1000)
            
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
                self.page.wait_for_timeout(5000)
                results = self.extract_results()
                results['parameter_type'] = self.config['parameter_type']
                results['parameter_value'] = parameter_value
                results['timestamp'] = datetime.now().isoformat()
                results['worker_id'] = self.worker_id
                results = self._normalize_results(results)
            
            self.last_results = results
            
            # Extract trade log
            print(f"Worker {self.worker_id}: Extracting trade log for {parameter_value}")
            trade_log_data = self.extract_trade_log(parameter_value)
            
            # Store both results and trade log data
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
            
            print(f"Worker {self.worker_id}: Test complete - {self.config['parameter_type']}={parameter_value}: "
                  f"CAGR={results['cagr']:.6f}, MAR={results['mar']:.2f}, Trades={len(trade_log_data)}")
            return True
            
        except Exception as e:
            self.consecutive_failures += 1
            print(f"Worker {self.worker_id}: Test failed for {parameter_value}: {e}")
            
            # Try to close any open dialogs
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(1000)
            except:
                pass
            
            return False
    
    def _normalize_results(self, results):
        """Convert percentage strings to decimal values"""
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
        """Check if results are duplicate of last test"""
        if not self.last_results:
            return False
        
        tolerance = 0.0001  # Tight tolerance for 6 decimal precision
        
        for key in ['cagr', 'maxDrawdown', 'winPercentage', 'captureRate']:
            if abs(self.last_results.get(key, 0) - results.get(key, 0)) > tolerance:
                return False
        
        return True
    
    def _update_consolidated_trade_log_csv(self):
        """Update the consolidated trade log CSV with all accumulated data"""
        try:
            # Use test run manager for organized file location
            if self.test_run_manager:
                consolidated_filename = self.test_run_manager.get_results_file('consolidated_trade_log.csv')
            else:
                timestamp = datetime.now().strftime('%Y%m%d')
                consolidated_filename = f'consolidated_trade_log_{timestamp}.csv'
            
            # Write complete trade log data
            with open(consolidated_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Headers
                headers = [
                    'Backtest Parameter Type', 'Backtest Parameter Value', 'Trade Date Time', 'Opening Price', 'Legs', 'Premium',
                    'Closing Price', 'Date Closed', 'Time Closed', 'Avg Closing Cost', 'Reason For Close',
                    'Trade P&L', 'Num Contracts', 'Funds at Close', 'Margin Req', 'Strategy',
                    'Opening Commissions', 'Closing Commissions', 'Opening Ratio', 'Closing Ratio',
                    'Gap', 'Movement', 'Max Profit', 'Max Loss', 'Extracted Timestamp', 'Worker ID'
                ]
                writer.writerow(headers)
                
                # Sort and write data
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
            
            print(f"Worker {self.worker_id}: Updated consolidated trade log - "
                  f"{len(all_trade_logs)} total trades")
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error updating consolidated trade log: {e}")
    
    def cleanup(self):
        """Clean up worker resources"""
        try:
            # Stop tracing if enabled
            if self.debug and self.context and self.test_run_manager:
                trace_file = os.path.join(
                    self.test_run_manager.get_traces_dir(),
                    f"worker_{self.worker_id}_final.zip"
                )
                self.context.tracing.stop(path=trace_file)
                print(f"Worker {self.worker_id}: Saved trace to {trace_file}")
            
            # Close browser resources
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
                
        except Exception as e:
            print(f"Worker {self.worker_id}: Error during cleanup: {e}")
            
        print(f"Worker {self.worker_id}: Cleaned up")


def worker_thread_playwright(worker_id, task_queue, config, credentials, original_values_set):
    """Worker thread using Playwright"""
    worker = OptionOmegaWorker(worker_id, task_queue, config, debug=config.get('debug', False))
    
    try:
        # Staggered initialization
        init_delay = random.randint(5, 30)
        print(f"Worker {worker_id}: Initializing in {init_delay} seconds...")
        time.sleep(init_delay)
        
        # Setup browser
        if not worker.setup_browser():
            print(f"Worker {worker_id}: Failed to initialize browser")
            return
        
        # Navigate to login page
        login_url = config['test_url'].split('/test')[0] + '/login'
        print(f"Worker {worker_id}: Navigating to login URL: {login_url}")
        
        try:
            # Navigate with longer timeout
            worker.page.goto(login_url, timeout=30000)
            print(f"Worker {worker_id}: Page loaded, current URL: {worker.page.url}")
            
            # Wait for page to be ready - use domcontentloaded instead of networkidle
            # networkidle can timeout on pages with continuous network activity
            try:
                worker.page.wait_for_load_state('domcontentloaded', timeout=5000)
            except:
                # Even if this times out, continue - the page may still be usable
                pass
            
            print(f"Worker {worker_id}: Page is ready, checking for login form...")
            
            # Give the page a moment to render
            worker.page.wait_for_timeout(2000)
            
            # Debug: Take a screenshot for troubleshooting
            if config.get('debug') and worker.test_run_manager:
                screenshot_path = os.path.join(
                    worker.test_run_manager.get_debug_dir(),
                    f"worker_{worker_id}_login_page.png"
                )
                worker.page.screenshot(path=screenshot_path)
                print(f"Worker {worker_id}: Saved login page screenshot to {screenshot_path}")
            
            # Debug: Print page title and check if it's a login page
            page_title = worker.page.title()
            print(f"Worker {worker_id}: Page title: {page_title}")
            
            # Check what's on the page
            try:
                # Look for any forms
                forms = worker.page.locator("form").all()
                print(f"Worker {worker_id}: Found {len(forms)} forms on the page")
                
                # Look for input fields
                inputs = worker.page.locator("input").all()
                print(f"Worker {worker_id}: Found {len(inputs)} input fields")
                
                # Try to identify what inputs are available
                for i, inp in enumerate(inputs[:10]):  # Check first 10 inputs
                    try:
                        input_type = inp.get_attribute('type')
                        input_name = inp.get_attribute('name')
                        input_id = inp.get_attribute('id')
                        input_placeholder = inp.get_attribute('placeholder')
                        is_visible = inp.is_visible()
                        print(f"  Input {i}: type={input_type}, name={input_name}, id={input_id}, "
                              f"placeholder={input_placeholder}, visible={is_visible}")
                    except:
                        pass
                
                # Also check for buttons
                buttons = worker.page.locator("button").all()
                print(f"Worker {worker_id}: Found {len(buttons)} buttons")
                for i, btn in enumerate(buttons[:5]):  # Check first 5 buttons
                    try:
                        btn_text = btn.text_content()
                        btn_type = btn.get_attribute('type')
                        print(f"  Button {i}: text='{btn_text}', type={btn_type}")
                    except:
                        pass
                        
            except Exception as e:
                print(f"Worker {worker_id}: Error checking page elements: {e}")
            
        except Exception as e:
            print(f"Worker {worker_id}: Failed to navigate to login page: {e}")
            import traceback
            print(f"Worker {worker_id}: Traceback: {traceback.format_exc()}")
            return
        
        # Attempt login
        print(f"Worker {worker_id}: Attempting login...")
        if not worker.perform_login(credentials['username'], credentials['password']):
            print(f"Worker {worker_id}: Login failed")
            
            # Try alternative login URL construction
            alt_login_url = config['test_url'].rsplit('/', 1)[0] + '/login'
            if alt_login_url != login_url:
                print(f"Worker {worker_id}: Trying alternative login URL: {alt_login_url}")
                worker.page.goto(alt_login_url, timeout=30000)
                worker.page.wait_for_load_state('networkidle')
                
                if not worker.perform_login(credentials['username'], credentials['password']):
                    print(f"Worker {worker_id}: Login failed with alternative URL too")
                    return
            else:
                return
        
        print(f"Worker {worker_id}: Login successful, navigating to test URL...")
        
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
                
                # Skip if not in original set
                if parameter_str not in original_values_set:
                    print(f"Worker {worker_id}: Skipping {parameter_value} - not in original set")
                    task_queue.task_done()
                    continue
                
                # Check if already completed
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
                    # Retry logic
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
        import traceback
        print(f"Worker {worker_id}: Full traceback: {traceback.format_exc()}")
    finally:
        worker.cleanup()
        print(f"Worker {worker_id}: Exited")


def generate_parameter_values(parameter_type, config):
    """Generate list of parameter values using the plugin system"""
    handler = ParameterFactory.create_parameter(parameter_type, config)
    return handler.generate_values()


def interactive_configuration(config):
    """Interactive configuration using parameter plugin system"""
    
    # Always ask for URL first
    while not config.get('test_url'):
        print("\n" + "="*60)
        print("ENHANCED OPTIONOMEGA AUTOMATION - PLAYWRIGHT VERSION")
        print("="*60)
        url = input("Enter OptionOmega test URL (required): ").strip()
        
        if url and 'optionomega.com' in url and '/test/' in url:
            config['test_url'] = url
            print(f"✅ URL validated: {url}")
        else:
            print("❌ Invalid URL. Must be an OptionOmega test URL")
    
    # Parameter selection
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
        print("PLAYWRIGHT AUTOMATION CONFIGURATION")
        print("="*60)
        print(f"1. Test URL:         {config['test_url']}")
        print(f"2. Parameter Type:   {selected_handler.get_name()}")
        
        param_values = selected_handler.generate_values()
        print(f"3. Test Values:      {len(param_values)} values")
        if len(param_values) <= 10:
            print(f"                     {param_values}")
        else:
            print(f"                     {param_values[:5]}...{param_values[-5:]}")
        
        print(f"4. Delay:            {config.get('delay_seconds', 1)} seconds")
        print(f"5. Backtest Timeout: {config.get('backtest_timeout', 300)} seconds")
        print(f"6. Max Workers:      {config.get('max_workers', 2)} (recommended: 2)")
        print(f"7. Debug Mode:       {config.get('debug', False)}")
        print("="*60)
        
        # Calculate estimates
        total_tests = len(param_values)
        estimated_time_per_test = (config.get('backtest_timeout', 300) + 
                                  config.get('delay_seconds', 1) + 60) / config.get('max_workers', 2)
        estimated_total_minutes = (total_tests * estimated_time_per_test) / 60
        
        print(f"Estimated: {total_tests} tests + trade log extraction")
        print(f"Time: ~{estimated_total_minutes:.1f} minutes with {config.get('max_workers', 2)} workers")
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
    print(f"   • Automation: Playwright (more reliable than Selenium)")
    print(f"   • Parallel workers: {config.get('max_workers', 2)}")
    print(f"   • Estimated duration: {estimated_total_minutes:.1f} minutes")
    
    confirm = input("\nStart automation? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        exit(0)
    
    return config


def load_configuration(args):
    """Load configuration from file and command line"""
    config = {
        'test_url': None,
        'parameter_type': 'entry_time',
        'delay_seconds': 1,
        'backtest_timeout': 300,
        'max_workers': 2,
        'debug': False,
    }
    
    # Load from config file if exists
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
    if args.debug:
        config['debug'] = True
    
    return config


def get_credentials():
    """Get login credentials"""
    username = input("Enter username/email: ").strip()
    password = getpass.getpass("Enter password (hidden): ")
    return {'username': username, 'password': password}


def save_progress_backup(config, all_values):
    """Save progress with backup"""
    try:
        # Calculate completion
        completion_pct = 0
        if all_values:
            with results_lock:
                completion_pct = len(all_results) / len(all_values) * 100
        
        # Create serializable config
        serializable_config = {k: v for k, v in config.items() 
                             if k not in ['test_run_manager', 'parameter_handler']}
        
        # Save progress
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
        else:
            progress_file = 'progress.json'
        
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
            
    except Exception as e:
        print(f"Error saving progress: {e}")


def export_results_to_csv(config, results, backup=False):
    """Export results to CSV"""
    if not results:
        return None
    
    try:
        test_run_manager = config.get('test_run_manager')
        parameter_type = config.get('parameter_type', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if backup:
            filename = f'results_{parameter_type}_backup_{timestamp}.csv'
        else:
            filename = f'results_{parameter_type}_{timestamp}.csv'
        
        if test_run_manager:
            if backup:
                filepath = os.path.join(test_run_manager.get_backups_dir(), filename)
            else:
                filepath = test_run_manager.get_results_file(filename)
        else:
            filepath = filename
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Parameter Type', 'Parameter Value', 'CAGR', 'Max Drawdown', 
                           'Win Percentage', 'Capture Rate', 'MAR', 'Worker ID', 'Timestamp'])
            
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
    """Main execution function"""
    print("OPTIONOMEGA AUTOMATION v5.0 - PLAYWRIGHT EDITION")
    print("Faster, more reliable automation with better error recovery")
    print("="*90)
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='OptionOmega Automation - Playwright Version')
    parser.add_argument('--url', type=str, help='Test URL')
    parser.add_argument('--parameter', type=str, choices=ParameterFactory.get_available_parameters(), 
                        help='Parameter type to test')
    parser.add_argument('--delay', type=int, help='Result rendering delay in seconds')
    parser.add_argument('--timeout', type=int, help='Backtest timeout in seconds')
    parser.add_argument('--max-workers', type=int, help='Maximum worker processes')
    parser.add_argument('--config', type=str, help='Config file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with traces')
    
    args = parser.parse_args()
    
    # Load and configure
    config = load_configuration(args)
    config = interactive_configuration(config)
    
    # Create test run manager
    test_run_manager = TestRunManager(config['test_url'], config['parameter_type'])
    config['test_run_manager'] = test_run_manager
    
    # Get credentials
    print("\nLOGIN CREDENTIALS")
    print("="*50)
    credentials = get_credentials()
    print("="*50)
    
    # Generate parameter values
    all_values = generate_parameter_values(config['parameter_type'], config)
    original_values_set = set(str(v) for v in all_values)
    task_queue = queue.Queue()
    
    # Populate task queue
    for value in all_values:
        task_queue.put(value)
    
    # Create parameter handler for display
    param_handler = ParameterFactory.create_parameter(config['parameter_type'], config)
    
    print(f"\nStarting Playwright automation with {config.get('max_workers', 2)} workers")
    print(f"Parameter: {param_handler.get_name()}")
    print(f"Total tests: {len(all_values)}")
    print(f"Test values: {all_values[:10]}{'...' if len(all_values) > 10 else ''}")
    print("="*90)
    
    # Worker threads
    threads = []
    
    try:
        # Start worker threads
        for worker_id in range(config.get('max_workers', 2)):
            thread = threading.Thread(
                target=worker_thread_playwright, 
                args=(worker_id, task_queue, config, credentials, original_values_set)
            )
            thread.start()
            threads.append(thread)
        
        # Monitor progress
        start_time = time.time()
        last_count = 0
        
        while True:
            time.sleep(15)
            
            # Calculate progress
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
                    print(f"Progress: {current_count}/{len(original_values_set)} ({progress_pct:.1f}%) - "
                          f"Rate: {rate_per_minute:.1f}/min - ETA: {eta_minutes:.1f}min")
                
                last_count = current_count
                
                # Save progress periodically
                if current_count % max(1, len(original_values_set) // 10) == 0:
                    save_progress_backup(config, all_values)
            
            # Check completion
            missing_parameters = original_values_set - completed_parameters
            
            if not missing_parameters:
                print(f"All {len(original_values_set)} parameters completed!")
                shutdown_event.set()
                break
            
            # Check if all threads finished
            active_threads = [t for t in threads if t.is_alive()]
            if not active_threads:
                if missing_parameters:
                    print(f"All workers died but {len(missing_parameters)} parameters still missing")
                break
        
        # Shutdown
        shutdown_event.set()
        
        # Wait for threads
        for thread in threads:
            thread.join(timeout=30)
        
        # Final summary
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
            # Export results
            unique_results = []
            seen_parameters = set()
            for result in all_results:
                param_val = str(result.get('parameter_value', ''))
                if param_val not in seen_parameters:
                    unique_results.append(result)
                    seen_parameters.add(param_val)
            
            csv_filename = export_results_to_csv(config, unique_results)
            print(f"Results exported: {csv_filename}")
            
            # Enhanced results if available
            if enhance_results_with_trade_metrics and all_trade_logs:
                enhanced_csv = enhance_results_with_trade_metrics(
                    config, unique_results, all_trade_logs
                )
                if enhanced_csv:
                    print(f"Enhanced results: {enhanced_csv}")
            
            # Summary statistics
            cagr_values = [r['cagr'] for r in unique_results]
            if cagr_values:
                avg_cagr = sum(cagr_values) / len(cagr_values)
                max_cagr = max(cagr_values)
                min_cagr = min(cagr_values)
                
                best_idx = cagr_values.index(max_cagr)
                best_param = unique_results[best_idx]['parameter_value']
                
                print(f"CAGR Summary - Avg: {avg_cagr:.6f}, "
                      f"Max: {max_cagr:.6f} (at {param_handler.get_name()}={best_param}), "
                      f"Min: {min_cagr:.6f}")
        
        print("="*90)
        
        # Cleanup
        test_run_manager.cleanup_temp_files()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user. Saving progress...")
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            export_results_to_csv(config, all_results)
            save_progress_backup(config, all_values)
        
        test_run_manager.cleanup_temp_files()
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        shutdown_event.set()
        
        for thread in threads:
            thread.join(timeout=5)
        
        if all_results:
            export_results_to_csv(config, all_results)
        
        test_run_manager.cleanup_temp_files()


if __name__ == "__main__":
    main()
