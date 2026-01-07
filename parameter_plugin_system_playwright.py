"""
Parameter Plugin System for OptionOmega Automation - Playwright Version
Migrated from Selenium to Playwright for better reliability and performance
"""

import abc
import re
from typing import List, Dict, Any, Optional
from playwright.sync_api import Page, Locator, expect


class BaseParameter(abc.ABC):
    """Base class for all parameter types - Playwright version"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.get_name()
        self.selectors = self.get_selectors()
        
    @abc.abstractmethod
    def get_name(self) -> str:
        """Return the display name of this parameter"""
        pass
    
    @abc.abstractmethod
    def get_selectors(self) -> Dict[str, List[str]]:
        """Return the CSS/XPath selectors for this parameter"""
        pass
    
    @abc.abstractmethod
    def set_value(self, page: Page, value) -> bool:
        """Set the parameter value in the UI"""
        pass
    
    @abc.abstractmethod
    def generate_values(self) -> List:
        """Generate list of values to test"""
        pass
    
    @abc.abstractmethod
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for this parameter"""
        pass
    
    def get_description(self) -> str:
        """Return description of this parameter"""
        return f"Test different {self.name.lower()} values"
    
    # Common helper methods using Playwright
    def find_element_by_selectors(self, page: Page, selectors: List[str]) -> Optional[Locator]:
        """Try multiple selectors to find an element using Playwright"""
        for selector in selectors:
            try:
                # Convert XPath to Playwright format if needed
                if selector.startswith("//") or selector.startswith("//*"):
                    locator = page.locator(f"xpath={selector}").first
                else:
                    locator = page.locator(selector).first
                
                # Check if element exists and is visible
                # Note: count() > 0 checks existence, is_visible() checks visibility
                if locator.count() > 0 and locator.is_visible():
                    return locator
            except:
                continue
        return None
    
    def clear_and_fill(self, page: Page, element: Locator, value: str) -> bool:
        """Clear an input field and fill with new value using Playwright"""
        try:
            # Focus the element
            element.focus()
            
            # Clear and fill (Playwright's fill automatically clears)
            if value:  # Only fill if value is not empty
                element.fill(str(value))
            else:
                # For empty values, clear the field
                element.fill("")
            
            # Trigger change events
            element.dispatch_event('input')
            element.dispatch_event('change')
            element.blur()
            
            # Small delay for UI update
            page.wait_for_timeout(100)
            
            # Verify the value was set
            return element.input_value() == str(value)
            
        except Exception as e:
            print(f"Error setting field value: {e}")
            return False
    
    def double_click_and_fill(self, page: Page, element: Locator, value: str) -> bool:
        """Double-click to select all, then fill using Playwright"""
        try:
            # Focus and double-click
            element.focus()
            element.dblclick()
            page.wait_for_timeout(100)
            
            # Fill value
            if value:
                element.fill(str(value))
            else:
                element.fill("")
            
            # Trigger events
            element.dispatch_event('input')
            element.dispatch_event('change')
            element.blur()
            
            page.wait_for_timeout(100)
            
            return element.input_value() == str(value)
            
        except Exception as e:
            print(f"Error with double-click fill: {e}")
            return False
    
    def click_leg_header(self, page: Page, leg_type: str) -> bool:
        """Click on a specific leg header (Call or Put) to focus on that leg's settings"""
        try:
            # Selectors for leg headers
            if leg_type.lower() == 'call':
                header_selectors = [
                    "h3:has-text('Profit & Loss — Call')",
                    "h3:has-text('Call')",
                    "xpath=//h3[contains(text(), 'Profit & Loss — Call')]",
                    "xpath=//h3[contains(., 'Call')]",
                    "[aria-label*='Call']",
                    "div:nth-of-type(6) > div:nth-of-type(1) h3"
                ]
            else:  # put
                header_selectors = [
                    "h3:has-text('Profit & Loss — Put')",
                    "h3:has-text('Put')",
                    "xpath=//h3[contains(text(), 'Profit & Loss — Put')]",
                    "xpath=//h3[contains(., 'Put')]",
                    "[aria-label*='Put']",
                    "div:nth-of-type(7) > div:nth-of-type(1) h3"
                ]
            
            element = self.find_element_by_selectors(page, header_selectors)
            if element:
                element.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                element.click()
                page.wait_for_timeout(500)
                print(f"Clicked on {leg_type} leg header")
                return True
            else:
                print(f"Could not find {leg_type} leg header")
                return False
                
        except Exception as e:
            print(f"Error clicking leg header: {e}")
            return False


class RSIParameter(BaseParameter):
    """RSI Parameter - Min or Max RSI testing"""
    
    def get_name(self) -> str:
        return "RSI"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'min': [
                "div:nth-of-type(2) > div > div:nth-of-type(4) div.pr-3 input",
                "xpath=//*[@id='headlessui-dialog-138']/div/div[2]/div/form/div[1]/div[2]/div/div[4]/div/div[2]/div[6]/div[1]/div/div/input",
                "div:nth-of-type(4) div.pr-3 input",
                "xpath=//div[contains(@class, 'pr-3')]//input",
            ],
            'max': [
                "div:nth-of-type(4) div:nth-of-type(6) > div:nth-of-type(2) input",
                "xpath=//*[@id='headlessui-dialog-138']/div/div[2]/div/form/div[1]/div[2]/div/div[4]/div/div[2]/div[6]/div[2]/div/div/input",
                "div:nth-of-type(6) > div:nth-of-type(2) input",
                "xpath=//div[6]/div[2]//input",
            ]
        }
    
    def set_value(self, page: Page, value) -> bool:
        """Set RSI value (min or max based on configuration)"""
        field_option = self.config.get('rsi_field_option', 'min')
        value_str = str(int(float(value)))
        
        selectors = self.selectors.get(field_option, self.selectors['min'])
        element = self.find_element_by_selectors(page, selectors)
        
        if element:
            success = self.clear_and_fill(page, element, value_str)
            if success:
                print(f"Set {field_option.upper()} RSI to {value_str}")
            return success
        
        print(f"Failed to find {field_option} RSI field")
        return False
    
    def generate_values(self) -> List[int]:
        """Generate RSI test values"""
        start = self.config.get('rsi_start', 0)
        end = self.config.get('rsi_end', 100)
        step = self.config.get('rsi_step', 5)
        
        return list(range(start, end + 1, step))
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for RSI"""
        print(f"\nConfiguring RSI testing:")
        
        # Field option configuration
        print("Which RSI field to test:")
        print("1. Min RSI")
        print("2. Max RSI")
        
        field_choice = input("Select field option (default: 1 for Min RSI): ").strip()
        if field_choice == '2':
            config['rsi_field_option'] = 'max'
        else:
            config['rsi_field_option'] = 'min'
        
        print(f"✅ Will test: {config['rsi_field_option'].upper()} RSI")
        
        # Value range configuration
        start = input("Start value (default 0): ").strip()
        config['rsi_start'] = int(start) if start.isdigit() else 0
        
        end = input("End value (default 100): ").strip()
        config['rsi_end'] = int(end) if end.isdigit() else 100
        
        step = input("Step size (default 5): ").strip()
        config['rsi_step'] = int(step) if step.isdigit() else 5
        
        print(f"✅ Range: {config['rsi_start']} to {config['rsi_end']} by {config['rsi_step']}")
        
        return config


class DeltaParameter(BaseParameter):
    """Delta Parameter - Put and/or Call delta testing"""
    
    def get_name(self) -> str:
        return "Delta"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'put': [
                "div:nth-of-type(9) > div:nth-of-type(3) input",
                "xpath=//div[9]/div[3]/div/div/input",
                "xpath=//*[@id='headlessui-dialog-26']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[9]/div[3]/div/div/input"
            ],
            'call': [
                "div:nth-of-type(10) > div:nth-of-type(2) input",
                "xpath=//div[10]/div[2]/div/div/input",
                "xpath=//*[@id='headlessui-dialog-26']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[10]/div[2]/div/div/input"
            ]
        }
    
    def set_value(self, page: Page, value) -> bool:
        """Set delta value(s) based on configuration"""
        field_option = self.config.get('delta_field_option', 'both')
        delta_value = int(float(value))
        
        fields_to_set = []
        if field_option == 'put_only':
            fields_to_set = [('put', delta_value)]
        elif field_option == 'call_only':
            fields_to_set = [('call', -delta_value)]  # Negative for calls
        else:  # 'both'
            fields_to_set = [('put', delta_value), ('call', -delta_value)]
        
        successful_sets = 0
        for field_type, field_value in fields_to_set:
            selectors = self.selectors[field_type]
            element = self.find_element_by_selectors(page, selectors)
            
            if element:
                if self.double_click_and_fill(page, element, str(field_value)):
                    successful_sets += 1
                    print(f"Set {field_type} delta to {field_value}")
        
        return successful_sets == len(fields_to_set)
    
    def generate_values(self) -> List[int]:
        """Generate delta test values"""
        start = self.config.get('delta_start', 1)
        end = self.config.get('delta_end', 100)
        step = self.config.get('delta_step', 1)
        
        return list(range(start, end + 1, step))
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for Delta"""
        print(f"\nConfiguring Delta testing:")
        
        print("Which delta fields to update:")
        print("1. Put only (positive values)")
        print("2. Call only (negative values)")
        print("3. Both put and call (recommended)")
        
        field_choice = input("Select field option (default: 3): ").strip()
        if field_choice == '1':
            config['delta_field_option'] = 'put_only'
        elif field_choice == '2':
            config['delta_field_option'] = 'call_only'
        else:
            config['delta_field_option'] = 'both'
        
        print(f"✅ Will update: {config['delta_field_option'].replace('_', ' ')}")
        
        # Value range configuration
        start = input("Start value (default 1): ").strip()
        config['delta_start'] = int(start) if start.isdigit() else 1
        
        end = input("End value (default 100): ").strip()
        config['delta_end'] = int(end) if end.isdigit() else 100
        
        step = input("Step size (default 1): ").strip()
        config['delta_step'] = int(step) if step.isdigit() else 1
        
        print(f"✅ Range: {config['delta_start']} to {config['delta_end']} by {config['delta_step']}")
        
        return config


class ProfitTargetParameter(BaseParameter):
    """Profit Target Parameter with leg-specific support"""
    
    def get_name(self) -> str:
        return "Profit Target"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'call': [
                "div:nth-of-type(6) > div:nth-of-type(1) div.pr-3 input",
                "xpath=//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[1]/div/div[2]/div[1]/div[1]/div/div/input",
                "div:nth-of-type(6) div.pr-3 input",
            ],
            'put': [
                "div:nth-of-type(7) > div:nth-of-type(1) div.pr-3 input",
                "xpath=//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[1]/div/div[2]/div[1]/div[1]/div/div/input",
                "div:nth-of-type(7) div.pr-3 input",
            ],
            'main': [  # Fallback for non-leg specific
                "div.pr-3 input",
                "xpath=//div[contains(@class, 'pr-3')]//input",
            ]
        }
    
    def set_value(self, page: Page, value) -> bool:
        """Set profit target value for configured legs"""
        value_str = str(int(float(value)))
        leg_option = self.config.get('profit_target_leg_option', 'both')
        
        legs_to_set = []
        if leg_option == 'call_only':
            legs_to_set = ['call']
        elif leg_option == 'put_only':
            legs_to_set = ['put']
        else:  # 'both'
            legs_to_set = ['call', 'put']
        
        successful_sets = 0
        for leg in legs_to_set:
            # Click the leg header first if setting specific leg
            if leg_option != 'both':
                self.click_leg_header(page, leg)
                page.wait_for_timeout(500)
            
            # Find and set the value
            selectors = self.selectors.get(leg, self.selectors['main'])
            element = self.find_element_by_selectors(page, selectors)
            
            if element:
                success = self.clear_and_fill(page, element, value_str)
                if success:
                    successful_sets += 1
                    print(f"Set {leg} profit target to {value_str}%")
                else:
                    print(f"Failed to set {leg} profit target")
            else:
                print(f"Could not find {leg} profit target field")
        
        return successful_sets == len(legs_to_set)
    
    def generate_values(self) -> List[int]:
        """Generate profit target test values"""
        start = self.config.get('profit_target_start', 1)
        end = self.config.get('profit_target_end', 100)
        step = self.config.get('profit_target_step', 1)
        
        return list(range(start, end + 1, step))
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for Profit Target"""
        print(f"\nConfiguring Profit Target testing:")
        
        # Leg configuration
        print("\nWhich legs to configure:")
        print("1. Both Call and Put")
        print("2. Call leg only")
        print("3. Put leg only")
        
        leg_choice = input("Select leg option (default: 1): ").strip()
        if leg_choice == '2':
            config['profit_target_leg_option'] = 'call_only'
        elif leg_choice == '3':
            config['profit_target_leg_option'] = 'put_only'
        else:
            config['profit_target_leg_option'] = 'both'
        
        print(f"✅ Will configure: {config['profit_target_leg_option'].replace('_', ' ')}")
        
        # Value range configuration
        start = input("Start value (default 1): ").strip()
        config['profit_target_start'] = int(start) if start.isdigit() else 1
        
        end = input("End value (default 100): ").strip()
        config['profit_target_end'] = int(end) if end.isdigit() else 100
        
        step = input("Step size (default 1): ").strip()
        config['profit_target_step'] = int(step) if step.isdigit() else 1
        
        print(f"✅ Range: {config['profit_target_start']} to {config['profit_target_end']} by {config['profit_target_step']}")
        
        return config


class StopLossParameter(BaseParameter):
    """Stop Loss Parameter with leg-specific support and optional empty values"""
    
    def get_name(self) -> str:
        return "Stop Loss"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'call': [
                "div:nth-of-type(6) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input",
                "xpath=//*[@id='headlessui-dialog-21']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[1]/div/div[2]/div[1]/div[2]/div/div/input",
                "div:nth-of-type(6) div.pt-6 input"
            ],
            'put': [
                "div:nth-of-type(7) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input",
                "xpath=//*[@id='headlessui-dialog-21']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[1]/div/div[2]/div[1]/div[2]/div/div/input",
                "div:nth-of-type(7) div.pt-6 input"
            ],
            'main': [  # Fallback
                "div.pt-6 input",
                "xpath=//div[contains(@class, 'pt-6')]//input"
            ]
        }
    
    def set_value(self, page: Page, value) -> bool:
        """Set stop loss value for configured legs"""
        # Handle empty value case
        if value == "empty" or value == "" or value is None:
            value_str = ""
        else:
            value_str = str(int(float(value)))
        
        leg_option = self.config.get('stop_loss_leg_option', 'both')
        
        legs_to_set = []
        if leg_option == 'call_only':
            legs_to_set = ['call']
        elif leg_option == 'put_only':
            legs_to_set = ['put']
        else:  # 'both'
            legs_to_set = ['call', 'put']
        
        successful_sets = 0
        for leg in legs_to_set:
            # Click the leg header first if setting specific leg
            if leg_option != 'both':
                self.click_leg_header(page, leg)
                page.wait_for_timeout(500)
            
            # Find and set the value
            selectors = self.selectors.get(leg, self.selectors['main'])
            element = self.find_element_by_selectors(page, selectors)
            
            if element:
                success = self.clear_and_fill(page, element, value_str)
                if success:
                    successful_sets += 1
                    if value_str == "":
                        print(f"Cleared {leg} stop loss")
                    else:
                        print(f"Set {leg} stop loss to {value_str}%")
                else:
                    print(f"Failed to set {leg} stop loss")
            else:
                print(f"Could not find {leg} stop loss field")
        
        return successful_sets == len(legs_to_set)
    
    def generate_values(self) -> List:
        """Generate stop loss test values"""
        values = []
        
        # Add empty value if enabled
        if self.config.get('stop_loss_include_empty', True):
            values.append("empty")
        
        # Add numeric range if enabled
        if self.config.get('stop_loss_include_numeric', True):
            start = self.config.get('stop_loss_start', 0)
            end = self.config.get('stop_loss_end', 100)
            step = self.config.get('stop_loss_step', 5)
            values.extend(list(range(start, end + 1, step)))
        
        return values
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for Stop Loss"""
        print(f"\nConfiguring Stop Loss testing:")
        
        # Leg configuration
        print("\nWhich legs to configure:")
        print("1. Both Call and Put")
        print("2. Call leg only")
        print("3. Put leg only")
        
        leg_choice = input("Select leg option (default: 1): ").strip()
        if leg_choice == '2':
            config['stop_loss_leg_option'] = 'call_only'
        elif leg_choice == '3':
            config['stop_loss_leg_option'] = 'put_only'
        else:
            config['stop_loss_leg_option'] = 'both'
        
        print(f"✅ Will configure: {config['stop_loss_leg_option'].replace('_', ' ')}")
        
        # Value types
        print("\nStop loss value options:")
        print("1. Empty values only")
        print("2. Numeric range only")
        print("3. Both (recommended)")
        
        value_type = input("Select value type (default: 3): ").strip()
        if value_type == '1':
            config['stop_loss_include_empty'] = True
            config['stop_loss_include_numeric'] = False
        elif value_type == '2':
            config['stop_loss_include_empty'] = False
            config['stop_loss_include_numeric'] = True
        else:
            config['stop_loss_include_empty'] = True
            config['stop_loss_include_numeric'] = True
        
        # Numeric range if needed
        if config.get('stop_loss_include_numeric', True):
            start = input("Start value (default 0): ").strip()
            config['stop_loss_start'] = int(start) if start.isdigit() else 0
            
            end = input("End value (default 100): ").strip()
            config['stop_loss_end'] = int(end) if end.isdigit() else 100
            
            step = input("Step size (default 5): ").strip()
            config['stop_loss_step'] = int(step) if step.isdigit() else 5
        
        return config


class EntryTimeParameter(BaseParameter):
    """Entry Time Parameter"""
    
    def get_name(self) -> str:
        return "Entry Time"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'main': ["input[type='time']", "input[type=time]"]
        }
    
    def set_value(self, page: Page, value) -> bool:
        """Set entry time value using Playwright"""
        try:
            # Find time input
            element = self.find_element_by_selectors(page, self.selectors['main'])
            
            if element:
                # Use Playwright's fill for time inputs
                element.fill(value)
                element.dispatch_event('change')
                print(f"Set entry time to {value}")
                return True
            
            return False
            
        except Exception as e:
            print(f"Error setting entry time: {e}")
            return False
    
    def generate_values(self) -> List[str]:
        """Generate entry time test values"""
        start_time = self.config.get('start_time', '10:00')
        end_time = self.config.get('end_time', '15:59')
        interval_minutes = self.config.get('interval_minutes', 1)
        
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
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for Entry Time"""
        print(f"\nConfiguring Entry Time range:")
        
        start = input(f"Start time (HH:MM, default 10:00): ").strip()
        if start and ':' in start:
            config['start_time'] = start
        else:
            config['start_time'] = '10:00'
        
        end = input(f"End time (HH:MM, default 15:59): ").strip()
        if end and ':' in end:
            config['end_time'] = end
        else:
            config['end_time'] = '15:59'
        
        interval = input(f"Interval in minutes (default 1): ").strip()
        config['interval_minutes'] = int(interval) if interval.isdigit() else 1
        
        print(f"✅ Range: {config['start_time']} to {config['end_time']} every {config['interval_minutes']} min")
        
        return config


class ExitTimeParameter(BaseParameter):
    """Exit Time Parameter with leg-specific support - requires Early Exit to be enabled"""
    
    def get_name(self) -> str:
        return "Exit Time"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'call': [
                "div:nth-of-type(6) div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input",
                "xpath=//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[2]/div[2]/div/input",
            ],
            'put': [
                "div:nth-of-type(7) div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input",
                "xpath=//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[2]/div/div[2]/div[2]/div[2]/div/input",
            ],
            'main': [  # Fallback
                "div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input",
                "xpath=//div[contains(@class, 'pt-6')]//div[2]//div[2]//input",
                "[placeholder*='exit' i][type='time']",
                "input[type='time']:nth-of-type(2)",
                "div:nth-of-type(2) input[type='time']"
            ],
            'early_exit_toggle': [
                "button:has-text('Early Exit')",
                "button[role='switch']:has-text('Early Exit')",
                "xpath=//button[contains(@aria-label, 'Use Early Exit')]",
                "#headlessui-switch-596",
                "xpath=//button[@role='switch'][contains(., 'Early Exit')]",
                "[aria-label*='Early Exit']",
                "xpath=//button[@role='switch']",
                ".toggle, .switch",
                "xpath=//label[contains(text(), 'Early Exit')]/..//button",
            ]
        }
    
    def set_value(self, page: Page, value) -> bool:
        """Set exit time value for configured legs (ensures Early Exit is enabled first)"""
        # First ensure Early Exit is enabled
        if not self._ensure_early_exit_enabled(page):
            print("Warning: Could not verify Early Exit is enabled")
        
        leg_option = self.config.get('exit_time_leg_option', 'both')
        
        legs_to_set = []
        if leg_option == 'call_only':
            legs_to_set = ['call']
        elif leg_option == 'put_only':
            legs_to_set = ['put']
        else:  # 'both'
            legs_to_set = ['call', 'put']
        
        successful_sets = 0
        for leg in legs_to_set:
            # Click the leg header first if setting specific leg
            if leg_option != 'both':
                self.click_leg_header(page, leg)
                page.wait_for_timeout(500)
            
            # Find and set the value
            selectors = self.selectors.get(leg, self.selectors['main'])
            element = self.find_element_by_selectors(page, selectors)
            
            if element:
                # Try double-click method first
                success = self.double_click_and_fill(page, element, value)
                
                if not success:
                    # Fallback to regular fill
                    try:
                        element.fill(value)
                        element.dispatch_event('change')
                        success = True
                    except:
                        success = False
                
                if success:
                    successful_sets += 1
                    print(f"Set {leg} exit time to {value}")
                else:
                    print(f"Failed to set {leg} exit time")
            else:
                print(f"Could not find {leg} exit time field")
        
        return successful_sets == len(legs_to_set)
    
    def _ensure_early_exit_enabled(self, page: Page) -> bool:
        """Ensure the Early Exit toggle is enabled for exit time testing"""
        try:
            # Look for the Early Exit toggle
            toggle = self.find_element_by_selectors(page, self.selectors['early_exit_toggle'])
            
            if toggle:
                # Check if already enabled
                aria_checked = toggle.get_attribute('aria-checked')
                # Also check for other indicators of being enabled
                class_attr = toggle.get_attribute('class') or ''
                is_enabled = (aria_checked == 'true' or 
                            'active' in class_attr.lower() or
                            'checked' in class_attr.lower())
                
                print(f"Found Early Exit toggle, enabled: {is_enabled}")
                
                if not is_enabled:
                    toggle.click()
                    page.wait_for_timeout(1000)
                    print("Enabled Early Exit toggle")
                
                return True
            else:
                print("Could not find Early Exit toggle")
                return False
                
        except Exception as e:
            print(f"Error checking Early Exit toggle: {e}")
            return False
    
    def generate_values(self) -> List[str]:
        """Generate exit time test values"""
        start_time = self.config.get('exit_start_time', '14:00')
        end_time = self.config.get('exit_end_time', '15:59')
        interval_minutes = self.config.get('exit_interval_minutes', 1)
        
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
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for Exit Time"""
        print(f"\nConfiguring Exit Time range:")
        print("Note: Exit Time requires 'Early Exit' to be enabled in the strategy.")
        print("The automation will attempt to enable it automatically.\n")
        
        # Leg configuration
        print("Which legs to configure:")
        print("1. Both Call and Put")
        print("2. Call leg only")
        print("3. Put leg only")
        
        leg_choice = input("Select leg option (default: 1): ").strip()
        if leg_choice == '2':
            config['exit_time_leg_option'] = 'call_only'
        elif leg_choice == '3':
            config['exit_time_leg_option'] = 'put_only'
        else:
            config['exit_time_leg_option'] = 'both'
        
        print(f"✅ Will configure: {config['exit_time_leg_option'].replace('_', ' ')}")
        
        # Time range configuration
        start = input(f"Start exit time (HH:MM, default 14:00): ").strip()
        if start and ':' in start:
            config['exit_start_time'] = start
        else:
            config['exit_start_time'] = '14:00'
        
        end = input(f"End exit time (HH:MM, default 15:59): ").strip()
        if end and ':' in end:
            config['exit_end_time'] = end
        else:
            config['exit_end_time'] = '15:59'
        
        interval = input(f"Interval in minutes (default 1): ").strip()
        config['exit_interval_minutes'] = int(interval) if interval.isdigit() else 1
        
        # Validate times
        start_h, start_m = map(int, config['exit_start_time'].split(':'))
        end_h, end_m = map(int, config['exit_end_time'].split(':'))
        
        if start_h * 60 + start_m >= end_h * 60 + end_m:
            print("Warning: Start time is after end time, swapping...")
            config['exit_start_time'], config['exit_end_time'] = config['exit_end_time'], config['exit_start_time']
        
        test_values = self.generate_values()
        print(f"\n✅ Range: {config['exit_start_time']} to {config['exit_end_time']} every {config['exit_interval_minutes']} min")
        print(f"✅ Will test {len(test_values)} exit times")
        
        if len(test_values) <= 10:
            print(f"   Values: {test_values}")
        else:
            print(f"   First 5: {test_values[:5]}")
            print(f"   Last 5: {test_values[-5:]}")
        
        return config
    
    def get_description(self) -> str:
        """Return description of this parameter"""
        return "Test different exit times (requires Early Exit enabled)"


class ShortLongRatioParameter(BaseParameter):
    """Short/Long Ratio Parameter - for testing different opening short/long ratios"""
    
    def get_name(self) -> str:
        return "Short/Long Ratio"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'main': [
                "div.toggleDescription input",
                "input:has-text('ratio')",
                "xpath=//div[contains(@class, 'toggleDescription')]//input",
                "div.flex-1 > div:nth-of-type(2) > div > div:nth-of-type(6) div.toggleDescription input",
                "xpath=//*[@id='headlessui-dialog-370']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[12]/div/input",
                "div:nth-of-type(12) input",
                "xpath=//div[12]/div/input",
                "[placeholder*='ratio' i]",
                "[placeholder*='short' i][placeholder*='long' i]"
            ]
        }
    
    def set_value(self, page: Page, value) -> bool:
        """Set short/long ratio value using Playwright"""
        # Convert value to string with appropriate decimal precision
        if isinstance(value, (int, float)):
            # Format with up to 2 decimal places, removing trailing zeros
            value_str = f"{float(value):.2f}".rstrip('0').rstrip('.')
        else:
            value_str = str(value)
        
        element = self.find_element_by_selectors(page, self.selectors['main'])
        
        if element:
            # Try double-click method first (as shown in puppeteer)
            success = self.double_click_and_fill(page, element, value_str)
            
            if not success:
                # Fallback to regular clear and fill
                success = self.clear_and_fill(page, element, value_str)
            
            if success:
                print(f"Set Short/Long Ratio to {value_str}")
            else:
                print(f"Failed to set Short/Long Ratio to {value_str}")
            
            return success
        
        print("Failed to find Short/Long Ratio field")
        return False
    
    def generate_values(self) -> List[float]:
        """Generate short/long ratio test values"""
        start = self.config.get('ratio_start', 0.1)
        end = self.config.get('ratio_end', 2.0)
        step = self.config.get('ratio_step', 0.1)
        
        # Generate values with proper decimal precision
        values = []
        current = start
        while current <= end + 0.001:  # Small epsilon for floating point comparison
            values.append(round(current, 2))
            current += step
        
        return values
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for Short/Long Ratio"""
        print(f"\nConfiguring Short/Long Ratio testing:")
        print("Note: Ratio represents short contracts / long contracts")
        print("  - 0.5 = 1 short for every 2 long")
        print("  - 1.0 = equal shorts and longs")
        print("  - 2.0 = 2 shorts for every 1 long")
        print()
        
        # Start value
        start = input("Start ratio (default 0.1): ").strip()
        try:
            config['ratio_start'] = float(start) if start else 0.1
        except ValueError:
            config['ratio_start'] = 0.1
            print("Invalid input, using default 0.1")
        
        # End value
        end = input("End ratio (default 2.0): ").strip()
        try:
            config['ratio_end'] = float(end) if end else 2.0
        except ValueError:
            config['ratio_end'] = 2.0
            print("Invalid input, using default 2.0")
        
        # Step size
        step = input("Step size (default 0.1): ").strip()
        try:
            config['ratio_step'] = float(step) if step else 0.1
        except ValueError:
            config['ratio_step'] = 0.1
            print("Invalid input, using default 0.1")
        
        # Validate configuration
        if config['ratio_start'] < 0:
            config['ratio_start'] = 0.1
            print("Start ratio cannot be negative, using 0.1")
        
        if config['ratio_end'] < config['ratio_start']:
            config['ratio_end'] = config['ratio_start'] + 1.0
            print(f"End ratio must be >= start ratio, using {config['ratio_end']}")
        
        if config['ratio_step'] <= 0:
            config['ratio_step'] = 0.1
            print("Step must be positive, using 0.1")
        
        # Show summary
        test_values = self.generate_values()
        print(f"\n✅ Range: {config['ratio_start']} to {config['ratio_end']} by {config['ratio_step']}")
        print(f"✅ Will test {len(test_values)} ratio values")
        
        if len(test_values) <= 10:
            print(f"   Values: {test_values}")
        else:
            print(f"   First 5: {test_values[:5]}")
            print(f"   Last 5: {test_values[-5:]}")
        
        return config
    
    def get_description(self) -> str:
        """Return description of this parameter"""
        return "Test different Short/Long ratios for opening positions"


class ParameterFactory:
    """Factory class to create parameter handlers"""
    
    # Register all parameter types
    PARAMETER_CLASSES = {
        'rsi': RSIParameter,
        'delta': DeltaParameter,
        'profit_target': ProfitTargetParameter,
        'stop_loss': StopLossParameter,
        'entry_time': EntryTimeParameter,
        'exit_time': ExitTimeParameter,
        'short_long_ratio': ShortLongRatioParameter,
        # Add more as needed
    }
    
    @classmethod
    def create_parameter(cls, parameter_type: str, config: Dict) -> BaseParameter:
        """Create the appropriate parameter handler"""
        parameter_class = cls.PARAMETER_CLASSES.get(parameter_type)
        
        if not parameter_class:
            raise ValueError(f"Unknown parameter type: {parameter_type}")
        
        return parameter_class(config)
    
    @classmethod
    def get_available_parameters(cls) -> List[str]:
        """Get list of all available parameter types"""
        return list(cls.PARAMETER_CLASSES.keys())
    
    @classmethod
    def register_parameter(cls, name: str, parameter_class):
        """Register a new parameter type"""
        cls.PARAMETER_CLASSES[name] = parameter_class


# Example of adding a new parameter type (template)
class NewCustomParameter(BaseParameter):
    """Example of adding a new parameter type"""
    
    def get_name(self) -> str:
        return "Custom Parameter"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'main': ["your-selector-here"]
        }
    
    def set_value(self, page: Page, value) -> bool:
        # Your implementation
        pass
    
    def generate_values(self) -> List:
        # Your implementation
        pass
    
    def configure_interactive(self, config: Dict) -> Dict:
        # Your implementation
        pass


# Register custom parameter if needed:
# ParameterFactory.register_parameter('custom', NewCustomParameter)
