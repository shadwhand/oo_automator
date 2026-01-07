#!/usr/bin/env python3
"""
OptionOmega Complete Playwright Implementation
Based on working Selenium version with all features
"""

import os
import re
import json
import csv
import time
import queue
import random
import threading
import getpass
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

# ============================================================================
# CONFIGURATION CLASSES
# ============================================================================

class ParameterConfig:
    """Configuration for different test parameters"""
    
    ENTRY_TIME = "entry_time"
    EXIT_TIME = "exit_time"
    DAY_OF_WEEK = "day_of_week"
    PREMIUM_ALLOCATION = "premium_allocation"
    STOP_LOSS = "stop_loss"
    
    PARAMETER_TYPES = {
        ENTRY_TIME: {
            'name': 'Entry Time',
            'type': 'time',
            'description': 'Test different entry times (HH:MM format)',
            'default_range': ['10:00', '15:59', 1]
        },
        EXIT_TIME: {
            'name': 'Exit Time',
            'type': 'time', 
            'description': 'Test different exit times (requires Early Exit toggle)',
            'default_range': ['10:00', '15:59', 1],
            'requires_toggle': 'Use Early Exit'
        },
        DAY_OF_WEEK: {
            'name': 'Day of Week',
            'type': 'multi_select',
            'description': 'Test different days of the week',
            'options': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'default_range': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        },
        PREMIUM_ALLOCATION: {
            'name': 'Premium Allocation',
            'type': 'numeric',
            'description': 'Test different premium allocation values (0-10.0 range)',
            'default_range': [0.0, 10.0, 0.5],
            'field_count_options': [1, 2],
            'default_field_count': 2
        },
        STOP_LOSS: {
            'name': 'Stop Loss',
            'type': 'numeric_with_empty',
            'description': 'Test different stop loss values (empty, 0-100 range)',
            'default_range': [0, 100, 5],
            'field_count_options': [1, 2],
            'default_field_count': 2,
            'allow_empty': True
        }
    }
    
    @classmethod
    def get_parameter_options(cls):
        return list(cls.PARAMETER_TYPES.keys())
    
    @classmethod
    def get_parameter_info(cls, param_type):
        return cls.PARAMETER_TYPES.get(param_type, {})


# ============================================================================
# GLOBAL THREAD-SAFE VARIABLES
# ============================================================================

results_lock = threading.Lock()
progress_lock = threading.Lock()
shutdown_event = threading.Event()

all_results = []
all_trade_logs = []
completed_tasks = set()

# ============================================================================
# TEST RUN MANAGER
# ============================================================================

class TestRunManager:
    """Manages test run directories and file organization"""
    
    def __init__(self, test_url, parameter_type):
        self.test_url = test_url
        self.parameter_type = parameter_type
        self.test_name = self._extract_test_name()
        self.run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.base_dir = self._create_run_directory()
        
    def _extract_test_name(self):
        """Extract test name from URL"""
        try:
            if '/test/' in self.test_url:
                test_id = self.test_url.split('/test/')[-1]
                test_id = test_id.split('?')[0].split('#')[0]
                return f"Test_{test_id}"
            return "UnknownTest"
        except:
            return "UnknownTest"
    
    def _create_run_directory(self):
        """Create organized directory structure"""
        dir_name = f"{self.test_name}_{self.parameter_type}_{self.run_timestamp}"
        dir_name = re.sub(r'[^\w\-_]', '', dir_name)
        
        base_path = Path("test_runs") / dir_name
        base_path.mkdir(parents=True, exist_ok=True)
        (base_path / "downloads").mkdir(exist_ok=True)
        (base_path / "debug").mkdir(exist_ok=True)
        (base_path / "backups").mkdir(exist_ok=True)
        
        print(f"Created test run directory: {base_path}")
        return str(base_path)
    
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
            for item in os.listdir('.'):
                if item.startswith('downloads_worker_') or item.startswith('chrome_worker_'):
                    if os.path.isdir(item):
                        shutil.rmtree(item)
                    else:
                        os.remove(item)
        except Exception as e:
            print(f"Warning: Could not clean up temp files: {e}")


# ============================================================================
# OPTION OMEGA WORKER
# ============================================================================

class OptionOmegaWorker:
    """Worker for browser automation using Playwright"""
    
    def __init__(self, worker_id, task_queue, config, test_run_manager, debug=False):
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.config = config
        self.test_run_manager = test_run_manager
        self.debug = debug
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.last_results = None
        self.backtest_times = []
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        
        if debug:
            self.debug_dir = os.path.join(
                test_run_manager.get_debug_dir(),
                f"worker_{worker_id}"
            )
            os.makedirs(self.debug_dir, exist_ok=True)
    
    def setup_driver(self, base_port=9222):
        """Initialize Playwright browser"""
        try:
            self.playwright = sync_playwright().start()
            
            # Browser launch options
            self.browser = self.playwright.chromium.launch(
                headless=not self.debug,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    f'--remote-debugging-port={base_port + self.worker_id}'
                ]
            )
            
            # Create context
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True,
                accept_downloads=True
            )
            
            # Create page
            self.page = self.context.new_page()
            
            # Apply stealth scripts
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)
            
            print(f"Worker {self.worker_id}: Playwright browser initialized")
            return True
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to setup browser: {e}")
            return False
    
    def perform_login(self, username, password):
        """Login to OptionOmega"""
        try:
            # Find username field using multiple selectors
            username_selectors = [
                "input[type='email']",
                "input[type='text'][name*='email']",
                "input[type='text'][name*='user']",
                "input[type='text']:first-of-type"
            ]
            
            username_field = None
            for selector in username_selectors:
                if self.page.locator(selector).count() > 0:
                    username_field = self.page.locator(selector).first
                    if username_field.is_visible():
                        break
            
            if not username_field:
                return False
            
            username_field.fill(username)
            
            # Find password field
            password_field = self.page.locator("input[type='password']").first
            password_field.fill(password)
            
            # Submit form
            submit_selectors = ["button[type='submit']", "input[type='submit']"]
            for selector in submit_selectors:
                if self.page.locator(selector).count() > 0:
                    self.page.locator(selector).first.click()
                    break
            
            # Wait and verify
            time.sleep(3)
            
            current_url = self.page.url.lower()
            if 'login' not in current_url and 'signin' not in current_url:
                return True
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Login error: {e}")
            return False
    
    def validate_test_url(self, test_url, max_retries=3):
        """Validate test URL"""
        for attempt in range(max_retries):
            try:
                self.page.goto(test_url)
                time.sleep(3)
                
                current_url = self.page.url.lower()
                
                if 'dashboard/tests' in current_url:
                    print(f"Worker {self.worker_id}: Redirected to dashboard, retrying...")
                    continue
                
                # Look for New Backtest button
                if self.page.locator("button:has-text('New Backtest')").count() > 0:
                    print(f"Worker {self.worker_id}: Test page validated")
                    return True
                    
            except Exception as e:
                print(f"Worker {self.worker_id}: URL validation error: {e}")
                time.sleep(5)
        
        return False
    
    def run_single_test(self, parameter_value, delay_seconds=1, default_timeout=300):
        """Execute a single backtest"""
        try:
            print(f"Worker {self.worker_id}: Running test for {self.config['parameter_type']}={parameter_value}")
            
            # Capture baseline results
            previous_results = self.extract_results()
            
            # Click New Backtest
            if not self.click_new_backtest():
                self.page.reload()
                time.sleep(5)
                if not self.click_new_backtest():
                    raise Exception("Failed to click New Backtest")
            
            time.sleep(2)
            
            if not self.wait_for_dialog():
                raise Exception("Dialog did not open")
            
            # Set parameter value
            if not self.set_parameter_value(self.config['parameter_type'], parameter_value):
                raise Exception(f"Failed to set parameter to {parameter_value}")
            
            time.sleep(1)
            
            if not self.click_run():
                raise Exception("Failed to click Run")
            
            # Wait for completion
            timeout = self._get_estimated_timeout(default_timeout)
            if not self.wait_for_backtest_completion(timeout):
                raise Exception("Backtest did not complete")
            
            self.wait_for_dialog_close()
            time.sleep(delay_seconds)
            
            # Extract results
            results = self.extract_results()
            results['parameter_type'] = self.config['parameter_type']
            results['parameter_value'] = parameter_value
            results['timestamp'] = datetime.now().isoformat()
            results['worker_id'] = self.worker_id
            
            # Extract trade log
            print(f"Worker {self.worker_id}: Extracting trade log for {parameter_value}")
            trade_log_data = self.extract_trade_log(parameter_value)
            
            # Store results
            with results_lock:
                all_results.append(results)
                
                for trade in trade_log_data:
                    trade['backtest_parameter_type'] = self.config['parameter_type']
                    trade['backtest_parameter_value'] = parameter_value
                    trade['backtest_results'] = results
                
                all_trade_logs.extend(trade_log_data)
                
                if trade_log_data:
                    self._update_consolidated_trade_log_csv()
            
            self.consecutive_failures = 0
            print(f"Worker {self.worker_id}: Test complete - {parameter_value}: CAGR={results['cagr']:.6f}, Trades={len(trade_log_data)}")
            return True
            
        except Exception as e:
            self.consecutive_failures += 1
            print(f"Worker {self.worker_id}: Test failed for {parameter_value}: {e}")
            
            # Try to close any open dialogs
            try:
                self.page.keyboard.press("Escape")
                time.sleep(1)
            except:
                pass
            
            return False
    
    def set_parameter_value(self, parameter_type, value):
        """Set parameter value based on type"""
        try:
            if parameter_type == ParameterConfig.ENTRY_TIME:
                return self.set_entry_time(value)
            elif parameter_type == ParameterConfig.EXIT_TIME:
                if self.set_exit_time(value):
                    return True
                print(f"Worker {self.worker_id}: Trying to enable Early Exit toggle")
                if self.ensure_early_exit_enabled():
                    time.sleep(2)
                    return self.set_exit_time(value)
                return False
            elif parameter_type == ParameterConfig.DAY_OF_WEEK:
                return self.set_day_of_week(value)
            elif parameter_type == ParameterConfig.PREMIUM_ALLOCATION:
                return self.set_premium_allocation(value)
            elif parameter_type == ParameterConfig.STOP_LOSS:
                return self.set_stop_loss(value)
            else:
                print(f"Worker {self.worker_id}: Unknown parameter type: {parameter_type}")
                return False
        except Exception as e:
            print(f"Worker {self.worker_id}: Error setting parameter: {e}")
            return False
    
    def set_entry_time(self, time_str):
        """Set entry time"""
        try:
            time_input = self.page.locator("input[type='time']").first
            time_input.fill(time_str)
            return True
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to set entry time: {e}")
            return False
    
    def ensure_early_exit_enabled(self):
        """Enable Early Exit toggle"""
        try:
            toggle_selectors = [
                "button:has-text('Use Early Exit')",
                "button[role='switch']:has-text('Early Exit')",
                "button[role='switch']"
            ]
            
            for selector in toggle_selectors:
                if self.page.locator(selector).count() > 0:
                    toggle = self.page.locator(selector).first
                    if toggle.is_visible():
                        aria_checked = toggle.get_attribute('aria-checked')
                        if aria_checked != 'true':
                            toggle.click()
                            time.sleep(1)
                        return True
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error enabling Early Exit: {e}")
            return False
    
    def set_exit_time(self, time_str):
        """Set exit time"""
        try:
            exit_selectors = [
                "div:nth-of-type(6) div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input",
                "input[type='time']:last-of-type"
            ]
            
            for selector in exit_selectors:
                if self.page.locator(selector).count() > 0:
                    exit_input = self.page.locator(selector).first
                    if exit_input.is_visible():
                        exit_input.fill(time_str)
                        return True
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to set exit time: {e}")
            return False
    
    def set_day_of_week(self, day_name):
        """Set day of week"""
        try:
            day_mapping = {
                'Monday': ['M', '1'],
                'Tuesday': ['Tu', '2'],
                'Wednesday': ['W', '3'],
                'Thursday': ['Th', '4'],
                'Friday': ['F', '5']
            }
            
            # Clear all selections first
            day_buttons = self.page.locator("div.flex-1 > div:nth-of-type(2) > div > div:nth-of-type(4) button")
            for i in range(day_buttons.count()):
                button = day_buttons.nth(i)
                if button.get_attribute('aria-pressed') == 'true':
                    button.click()
            
            # Select target day
            identifiers = day_mapping.get(day_name, [])
            for identifier in identifiers:
                selector = f"button:has-text('{identifier}')"
                if self.page.locator(selector).count() > 0:
                    self.page.locator(selector).first.click()
                    print(f"Worker {self.worker_id}: Selected {day_name}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Failed to set day: {e}")
            return False
    
    def set_premium_allocation(self, value):
        """Set premium allocation value(s)"""
        try:
            print(f"Worker {self.worker_id}: Setting premium allocation to {value}")
            
            field_count = self.config.get('premium_allocation_field_count', 2)
            value_str = f"{float(value):.1f}"
            
            field_selectors = [
                "div:nth-of-type(1) > div.inline-flex input",
                "div:nth-of-type(3) > div.inline-flex input"
            ]
            
            successful_sets = 0
            
            for field_index in range(min(field_count, len(field_selectors))):
                selector = field_selectors[field_index]
                if self.page.locator(selector).count() > 0:
                    input_field = self.page.locator(selector).first
                    if input_field.is_visible():
                        input_field.click()
                        time.sleep(0.1)
                        input_field.dblclick()
                        time.sleep(0.1)
                        input_field.fill(value_str)
                        successful_sets += 1
            
            if successful_sets > 0:
                print(f"Worker {self.worker_id}: Set {successful_sets}/{field_count} premium allocation fields")
                return True
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error setting premium allocation: {e}")
            return False
    
    def set_stop_loss(self, value):
        """Set stop loss value(s)"""
        try:
            print(f"Worker {self.worker_id}: Setting stop loss to {value}")
            
            field_count = self.config.get('stop_loss_field_count', 2)
            
            if value == "empty" or value == "" or value is None:
                value_str = ""
                print(f"Worker {self.worker_id}: Setting stop loss to empty")
            else:
                value_str = str(int(float(value)))
            
            field_selectors = [
                "div:nth-of-type(6) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input",
                "div:nth-of-type(7) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input"
            ]
            
            successful_sets = 0
            
            for field_index in range(min(field_count, len(field_selectors))):
                selector = field_selectors[field_index]
                if self.page.locator(selector).count() > 0:
                    input_field = self.page.locator(selector).first
                    if input_field.is_visible():
                        input_field.click()
                        time.sleep(0.1)
                        input_field.clear()
                        
                        if value_str != "":
                            input_field.fill(value_str)
                        
                        successful_sets += 1
            
            if successful_sets > 0:
                print(f"Worker {self.worker_id}: Set {successful_sets}/{field_count} stop loss fields")
                return True
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error setting stop loss: {e}")
            return False
    
    def click_new_backtest(self):
        """Click New Backtest button"""
        time.sleep(2)
        
        try:
            button = self.page.locator("button:has-text('New Backtest')").first
            if button.is_visible():
                button.click()
                return True
        except:
            pass
        
        # Try finding by div.mt-4 > button
        try:
            button = self.page.locator("div.mt-4 > button").first
            if button.is_visible():
                button.click()
                return True
        except:
            pass
        
        return False
    
    def click_run(self):
        """Click Run button"""
        time.sleep(1)
        
        try:
            # Find dialog first
            dialog = self.page.locator("[role='dialog']").first
            if dialog.is_visible():
                # Find last button in dialog (typically Run)
                buttons = dialog.locator("button")
                if buttons.count() > 0:
                    buttons.last.click()
                    return True
        except:
            pass
        
        return False
    
    def wait_for_dialog(self, timeout=5):
        """Wait for dialog to appear"""
        try:
            self.page.wait_for_selector("input[type='time']", timeout=timeout * 1000)
            return True
        except:
            return False
    
    def wait_for_backtest_completion(self, timeout=300):
        """Wait for backtest to complete"""
        try:
            # Wait for progress indicators
            progress_appeared = False
            progress_selectors = [
                "text=Running Backtest",
                "text=ETA",
                "text=Processing",
                ".animate-spin",
                "[role='status']"
            ]
            
            for i in range(15):
                for selector in progress_selectors:
                    if self.page.locator(selector).count() > 0:
                        progress_appeared = True
                        break
                
                if progress_appeared:
                    break
                
                # Check if dialog already closed
                if self.page.locator("[role='dialog']").count() == 0:
                    return True
                
                time.sleep(1)
            
            if not progress_appeared:
                time.sleep(2)
                return True
            
            # Wait for completion
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                progress_found = False
                
                for selector in progress_selectors:
                    if self.page.locator(selector).count() > 0:
                        progress_found = True
                        break
                
                if not progress_found:
                    elapsed = int(time.time() - start_time)
                    self.backtest_times.append(elapsed)
                    time.sleep(2)
                    return True
                
                # Check for dashboard redirect
                if (time.time() - start_time) > 10:
                    if 'dashboard/tests' in self.page.url.lower():
                        print(f"Worker {self.worker_id}: Dashboard redirect detected")
                        return False
                
                time.sleep(0.5)
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error waiting for backtest: {e}")
            return False
    
    def wait_for_dialog_close(self, timeout=15):
        """Wait for dialog to close"""
        try:
            self.page.wait_for_selector("[role='dialog']", state="hidden", timeout=timeout * 1000)
            return True
        except:
            try:
                self.page.keyboard.press("Escape")
                time.sleep(1)
                return True
            except:
                return False
    
    def extract_results(self):
        """Extract backtest results"""
        data = {
            'cagr': self._extract_metric('CAGR'),
            'maxDrawdown': self._extract_metric('Max Drawdown'),
            'winPercentage': self._extract_metric('Win Percentage'),
            'captureRate': self._extract_metric('Capture Rate')
        }
        
        if data['maxDrawdown'] != 0:
            data['mar'] = abs(data['cagr'] / data['maxDrawdown'])
        else:
            data['mar'] = 0
        
        return data
    
    def _extract_metric(self, metric_name):
        """Extract a specific metric"""
        try:
            elements = self.page.locator("dt").all()
            for dt in elements:
                if metric_name in dt.text_content():
                    parent = dt.locator("..").first
                    dd = parent.locator("dd").first
                    match = re.search(r'-?\d+\.?\d*', dd.text_content())
                    if match:
                        value = float(match.group())
                        # Convert percentage to decimal if needed
                        if abs(value) > 1:
                            value = value / 100.0
                        return value
        except:
            pass
        return 0
    
    def extract_trade_log(self, parameter_value):
        """Extract trade log data"""
        try:
            print(f"Worker {self.worker_id}: Downloading trade log for {parameter_value}")
            
            # Navigate to Trade Log tab
            if not self._navigate_to_trade_log():
                return []
            
            time.sleep(3)
            
            # Setup download directory
            download_dir = self._setup_download_directory()
            
            # Download trade log file
            downloaded_file = self._download_trade_log_file(download_dir)
            
            if not downloaded_file:
                print(f"Worker {self.worker_id}: Failed to download trade log")
                return []
            
            # Parse downloaded file
            trades_data = self._parse_downloaded_trade_log(downloaded_file, parameter_value)
            
            # Clean up
            try:
                organized_file = os.path.join(download_dir, f"trade_log_{parameter_value}_{datetime.now().strftime('%H%M%S')}.csv")
                shutil.move(downloaded_file, organized_file)
                print(f"Worker {self.worker_id}: Moved trade log to {organized_file}")
            except:
                pass
            
            print(f"Worker {self.worker_id}: Processed {len(trades_data)} trades")
            return trades_data
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error extracting trade log: {e}")
            return []
    
    def _navigate_to_trade_log(self):
        """Navigate to Trade Log tab"""
        try:
            trade_log_selectors = [
                "a:has-text('Trade Log')",
                "nav a:has-text('Trade')",
                "a[href*='trade']"
            ]
            
            for selector in trade_log_selectors:
                if self.page.locator(selector).count() > 0:
                    self.page.locator(selector).first.click()
                    print(f"Worker {self.worker_id}: Navigated to Trade Log")
                    return True
            
            return False
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error navigating to trade log: {e}")
            return False
    
    def _setup_download_directory(self):
        """Setup download directory"""
        worker_download_dir = os.path.join(
            self.test_run_manager.get_downloads_dir(),
            f"worker_{self.worker_id}"
        )
        os.makedirs(worker_download_dir, exist_ok=True)
        return worker_download_dir
    
    def _download_trade_log_file(self, download_dir):
        """Download trade log file"""
        try:
            # Look for download button
            download_selectors = [
                "svg path",
                "[title*='Download']",
                "[aria-label*='Download']",
                ".download-btn"
            ]
            
            download_button = None
            for selector in download_selectors:
                if self.page.locator(selector).count() > 0:
                    download_button = self.page.locator(selector).first
                    if download_button.is_visible():
                        break
            
            if not download_button:
                print(f"Worker {self.worker_id}: Could not find download button")
                return None
            
            # Start download
            with self.page.expect_download() as download_info:
                download_button.click()
            
            download = download_info.value
            
            # Save to download directory
            download_path = os.path.join(download_dir, download.suggested_filename)
            download.save_as(download_path)
            
            print(f"Worker {self.worker_id}: Downloaded file: {download_path}")
            return download_path
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error downloading file: {e}")
            return None
    
    def _parse_downloaded_trade_log(self, file_path, parameter_value):
        """Parse downloaded trade log CSV"""
        trades = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.DictReader(f)
                
                for row in csv_reader:
                    trade = {
                        'backtest_parameter_type': self.config['parameter_type'],
                        'backtest_parameter_value': parameter_value,
                        'trade_date_time': f"{row.get('Date Opened', '')} {row.get('Time Opened', '')}",
                        'opening_price': self._get_numeric(row.get('Opening Price', 0)),
                        'legs': row.get('Legs', ''),
                        'premium': self._get_numeric(row.get('Premium', 0)),
                        'closing_price': self._get_numeric(row.get('Closing Price', 0)),
                        'date_closed': row.get('Date Closed', ''),
                        'time_closed': row.get('Time Closed', ''),
                        'avg_closing_cost': self._get_numeric(row.get('Avg. Closing Cost', 0)),
                        'reason_for_close': row.get('Reason For Close', ''),
                        'trade_pnl': self._get_numeric(row.get('P/L', 0)),
                        'num_contracts': self._get_numeric(row.get('No. of Contracts', 0)),
                        'funds_at_close': self._get_numeric(row.get('Funds at Close', 0)),
                        'margin_req': self._get_numeric(row.get('Margin Req.', 0)),
                        'strategy': row.get('Strategy', ''),
                        'worker_id': self.worker_id,
                        'extracted_timestamp': datetime.now().isoformat()
                    }
                    trades.append(trade)
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error parsing trade log: {e}")
        
        return trades
    
    def _get_numeric(self, value):
        """Extract numeric value"""
        try:
            if value is None or str(value).lower() in ['nan', '', 'none']:
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
        """Update consolidated trade log CSV"""
        try:
            consolidated_file = self.test_run_manager.get_results_file('consolidated_trade_log.csv')
            
            with open(consolidated_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                headers = [
                    'Backtest Parameter Type', 'Backtest Parameter Value',
                    'Trade Date Time', 'Opening Price', 'Legs', 'Premium',
                    'Closing Price', 'Date Closed', 'Time Closed',
                    'Avg Closing Cost', 'Reason For Close', 'Trade P&L',
                    'Num Contracts', 'Funds at Close', 'Margin Req',
                    'Strategy', 'Worker ID', 'Extracted Timestamp'
                ]
                writer.writerow(headers)
                
                sorted_trades = sorted(all_trade_logs,
                    key=lambda x: (x.get('backtest_parameter_value', ''), x.get('trade_date_time', '')))
                
                for trade in sorted_trades:
                    row = [
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
                        trade.get('worker_id', ''),
                        trade.get('extracted_timestamp', '')
                    ]
                    writer.writerow(row)
            
            print(f"Worker {self.worker_id}: Updated consolidated trade log")
            
        except Exception as e:
            print(f"Worker {self.worker_id}: Error updating consolidated trade log: {e}")
    
    def _get_estimated_timeout(self, default=300):
        """Calculate timeout based on previous times"""
        if not self.backtest_times:
            return default
        
        recent = self.backtest_times[-3:] if len(self.backtest_times) > 3 else self.backtest_times
        avg_time = sum(recent) / len(recent)
        return int(avg_time + 30)
    
    def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass
        
        print(f"Worker {self.worker_id}: Cleaned up")


# ============================================================================
# WORKER THREAD
# ============================================================================

def worker_thread_simplified(worker_id, task_queue, config, credentials, original_values_set, test_run_manager):
    """Simplified worker thread - matches Selenium version"""
    worker = OptionOmegaWorker(worker_id, task_queue, config, test_run_manager, debug=config.get('debug', False))
    
    try:
        # Staggered initialization
        init_delay = random.randint(5, 30)
        print(f"Worker {worker_id}: Initializing in {init_delay} seconds...")
        time.sleep(init_delay)
        
        # Setup browser
        if not worker.setup_driver(base_port=9222):
            print(f"Worker {worker_id}: Failed to initialize browser")
            return
        
        # Login
        login_url = config['test_url'].split('/test')[0] + '/login'
        worker.page.goto(login_url)
        time.sleep(3)
        
        if not worker.perform_login(credentials['username'], credentials['password']):
            print(f"Worker {worker_id}: Login failed")
            return
        
        # Validate test URL
        if not worker.validate_test_url(config['test_url']):
            print(f"Worker {worker_id}: Test URL validation failed")
            return
        
        print(f"Worker {worker_id}: Ready to process tasks")
        
        # Process tasks
        while not shutdown_event.is_set():
            try:
                parameter_value = task_queue.get(timeout=10)
                parameter_str = str(parameter_value)
                
                # Skip if not in original set
                if parameter_str not in original_values_set:
                    print(f"Worker {worker_id}: Skipping {parameter_value} - not in original")
                    task_queue.task_done()
                    continue
                
                # Check if already completed
                with results_lock:
                    already_completed = any(
                        str(r.get('parameter_value', '')) == parameter_str
                        for r in all_results
                    )
                
                if already_completed:
                    print(f"Worker {worker_id}: {parameter_value} already completed")
                    task_queue.task_done()
                    continue
                
                print(f"Worker {worker_id}: Processing {parameter_value}")
                
                # Run test
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
                    if retry_count < 2:
                        if not hasattr(task_queue, '_retries'):
                            task_queue._retries = {}
                        task_queue._retries[parameter_str] = retry_count + 1
                        task_queue.put(parameter_value)
                        print(f"Worker {worker_id}: Re-queued {parameter_value} (retry {retry_count + 1})")
                
                task_queue.task_done()
                time.sleep(1)
                
            except queue.Empty:
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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_parameter_values(parameter_type, config):
    """Generate list of parameter values to test"""
    param_info = ParameterConfig.get_parameter_info(parameter_type)
    
    if parameter_type in [ParameterConfig.ENTRY_TIME, ParameterConfig.EXIT_TIME]:
        return generate_time_list(
            config.get('start_time', param_info['default_range'][0]),
            config.get('end_time', param_info['default_range'][1]),
            config.get('interval_minutes', param_info['default_range'][2])
        )
    
    elif parameter_type == ParameterConfig.DAY_OF_WEEK:
        return config.get('selected_days', param_info['default_range'])
    
    elif parameter_type == ParameterConfig.PREMIUM_ALLOCATION:
        return generate_numeric_list(
            config.get('premium_allocation_start', param_info['default_range'][0]),
            config.get('premium_allocation_end', param_info['default_range'][1]),
            config.get('premium_allocation_step', param_info['default_range'][2])
        )
    
    elif parameter_type == ParameterConfig.STOP_LOSS:
        values = []
        if config.get('stop_loss_include_empty', True):
            values.append("empty")
        if config.get('stop_loss_include_numeric', True):
            numeric_values = generate_numeric_list(
                config.get('stop_loss_start', param_info['default_range'][0]),
                config.get('stop_loss_end', param_info['default_range'][1]),
                config.get('stop_loss_step', param_info['default_range'][2])
            )
            values.extend(numeric_values)
        return values
    
    else:
        raise ValueError(f"Unsupported parameter type: {parameter_type}")


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


def generate_numeric_list(start_value, end_value, step_value):
    """Generate list of numeric values"""
    values = []
    current_value = start_value
    
    while current_value <= end_value:
        values.append(round(current_value, 1))
        current_value += step_value
    
    return values


def get_credentials():
    """Get login credentials"""
    print("\nLOGIN CREDENTIALS")
    print("="*50)
    
    username = input("Enter username/email: ").strip()
    password = getpass.getpass("Enter password: ")
    
    return {'username': username, 'password': password}


def export_results_to_csv(test_run_manager, results):
    """Export results to CSV"""
    if not results:
        return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'results_{timestamp}.csv'
    filepath = test_run_manager.get_results_file(filename)
    
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
                f"{row['mar']:.2f}",
                row.get('worker_id', 'N/A'),
                row.get('timestamp', '')
            ])
    
    print(f"Results exported to: {filepath}")
    return filepath


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution function"""
    print("OPTIONOMEGA PLAYWRIGHT AUTOMATION")
    print("="*80)
    
    # Configuration
    config = {
        'test_url': input("Enter test URL: ").strip(),
        'parameter_type': ParameterConfig.ENTRY_TIME,
        'start_time': '15:30',
        'end_time': '15:59',
        'interval_minutes': 1,
        'delay_seconds': 1,
        'backtest_timeout': 300,
        'max_workers': 2,
        'debug': False
    }
    
    # Create test run manager
    test_run_manager = TestRunManager(config['test_url'], config['parameter_type'])
    
    # Get credentials
    credentials = get_credentials()
    
    # Generate parameter values
    all_values = generate_parameter_values(config['parameter_type'], config)
    original_values_set = set(str(v) for v in all_values)
    task_queue = queue.Queue()
    
    for value in all_values:
        task_queue.put(value)
    
    print(f"\nStarting with {config['max_workers']} workers")
    print(f"Total tests: {len(all_values)}")
    print(f"Values: {all_values[:10]}{'...' if len(all_values) > 10 else ''}")
    print("="*80)
    
    # Start worker threads
    threads = []
    try:
        for worker_id in range(config['max_workers']):
            thread = threading.Thread(
                target=worker_thread_simplified,
                args=(worker_id, task_queue, config, credentials, original_values_set, test_run_manager)
            )
            thread.start()
            threads.append(thread)
        
        # Monitor progress
        start_time = time.time()
        
        while True:
            time.sleep(15)
            
            with results_lock:
                completed_parameters = set()
                for result in all_results:
                    completed_parameters.add(str(result.get('parameter_value', '')))
                
                current_count = len(completed_parameters)
                progress_pct = (current_count / len(original_values_set)) * 100 if original_values_set else 0
            
            print(f"Progress: {current_count}/{len(original_values_set)} ({progress_pct:.1f}%)")
            
            missing = original_values_set - completed_parameters
            if not missing:
                print("All parameters completed!")
                shutdown_event.set()
                break
            
            # Check if workers are alive
            active = [t for t in threads if t.is_alive()]
            if not active and missing:
                print(f"Workers died with {len(missing)} parameters remaining")
                break
        
        # Shutdown
        shutdown_event.set()
        for thread in threads:
            thread.join(timeout=30)
        
        # Export results
        print("\n" + "="*80)
        print("AUTOMATION COMPLETE")
        print(f"Results: {len(all_results)}")
        print(f"Trade logs: {len(all_trade_logs)}")
        print(f"Time: {(time.time() - start_time) / 60:.1f} minutes")
        
        if all_results:
            export_results_to_csv(test_run_manager, all_results)
        
        print(f"Files saved in: {test_run_manager.base_dir}")
        print("="*80)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        shutdown_event.set()
        for thread in threads:
            thread.join(timeout=5)
    
    finally:
        test_run_manager.cleanup_temp_files()


if __name__ == "__main__":
    main()
