"""
Parameter Plugin System for OptionOmega Automation
This modular approach reduces code from 5000+ lines to manageable chunks
Now with smart Leg Groups detection for automatic field handling
"""

import abc
import re
from typing import List, Dict, Any, Tuple, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


class BaseParameter(abc.ABC):
    """Base class for all parameter types - now with intelligent leg group detection"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.get_name()
        self.selectors = self.get_selectors()
        self.leg_groups_enabled = None  # Will be detected when needed
        
    @abc.abstractmethod
    def get_name(self) -> str:
        """Return the display name of this parameter"""
        pass
    
    @abc.abstractmethod
    def get_selectors(self) -> Dict[str, List[str]]:
        """Return the CSS/XPath selectors for this parameter"""
        pass
    
    @abc.abstractmethod
    def set_value(self, driver, value) -> bool:
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
    
    def check_leg_groups_enabled(self, driver) -> bool:
        """Check if 'Use Leg Groups' toggle is enabled"""
        if self.leg_groups_enabled is not None:
            # Use cached value if already checked
            return self.leg_groups_enabled
        
        try:
            # Selectors for "Use Leg Groups" toggle - very specific to avoid other toggles
            leg_groups_selectors = [
                "//button[@role='switch' and @aria-label='Use Leg Groups']",
                "//label[text()='Use Leg Groups']/..//button[@role='switch']",
                "#headlessui-switch-158"
            ]
            
            # Use the enhanced find method with exclusion
            toggle = self.find_element_by_selectors(driver, leg_groups_selectors, exclude_text=['DTE', 'Exact'])
            
            if toggle:
                # Double-check this isn't a DTE toggle
                aria_label = (toggle.get_attribute('aria-label') or '').lower()
                element_text = (toggle.text or '').lower()
                if 'dte' in aria_label or 'exact' in aria_label or 'dte' in element_text:
                    print("WARNING: Found DTE-related toggle instead of Leg Groups, skipping!")
                    self.leg_groups_enabled = False
                    return False
                
                # Check if enabled
                aria_checked = toggle.get_attribute('aria-checked')
                class_attr = toggle.get_attribute('class') or ''
                
                is_enabled = (
                    aria_checked == 'true' or
                    'bg-blue' in class_attr or
                    'bg-indigo' in class_attr or
                    'active' in class_attr.lower()
                )
                
                self.leg_groups_enabled = is_enabled
                print(f"Detected 'Use Leg Groups' is {'enabled' if is_enabled else 'disabled'}")
                return is_enabled
            else:
                # If we can't find the toggle, assume leg groups are not available/enabled
                print("'Use Leg Groups' toggle not found - assuming single field mode")
                self.leg_groups_enabled = False
                return False
                
        except Exception as e:
            print(f"Error checking 'Use Leg Groups' status: {e}")
            self.leg_groups_enabled = False
            return False
    
    def smart_set_value(self, driver, value, field_type='both') -> bool:
        """
        Intelligently set parameter value based on Leg Groups status
        
        Args:
            driver: Selenium WebDriver instance
            value: Value to set
            field_type: User's preference ('call_only', 'put_only', or 'both')
        
        Returns:
            bool: Success status
        """
        # Check if leg groups are enabled
        leg_groups_enabled = self.check_leg_groups_enabled(driver)
        
        if not leg_groups_enabled:
            # Single field mode - look for any available field
            print(f"Leg Groups disabled - setting single {self.name} field")
            
            # Try main/generic selectors first
            if 'main' in self.selectors:
                element = self.find_element_by_selectors(driver, self.selectors['main'])
                if element:
                    return self._set_field_value(driver, element, value, "main")
            
            # Then try any available selector set (call, put, etc.)
            for selector_key in ['call', 'put']:
                if selector_key in self.selectors:
                    element = self.find_element_by_selectors(driver, self.selectors[selector_key])
                    if element:
                        return self._set_field_value(driver, element, value, selector_key)
            
            print(f"Could not find any {self.name} field")
            return False
            
        else:
            # Leg Groups enabled - handle based on user preference
            if field_type == 'both':
                print(f"Leg Groups enabled - setting both call and put {self.name} fields")
                success_count = 0
                
                # Set call field
                if 'call' in self.selectors:
                    element = self.find_element_by_selectors(driver, self.selectors['call'])
                    if element:
                        if self._set_field_value(driver, element, value, "call"):
                            success_count += 1
                
                # Set put field
                if 'put' in self.selectors:
                    element = self.find_element_by_selectors(driver, self.selectors['put'])
                    if element:
                        if self._set_field_value(driver, element, value, "put"):
                            success_count += 1
                
                return success_count > 0  # Success if at least one field was set
                
            elif field_type == 'call_only':
                print(f"Leg Groups enabled - setting call {self.name} field only")
                self.click_leg_header(driver, 'call')
                time.sleep(0.5)
                
                if 'call' in self.selectors:
                    element = self.find_element_by_selectors(driver, self.selectors['call'])
                    if element:
                        return self._set_field_value(driver, element, value, "call")
                        
            elif field_type == 'put_only':
                print(f"Leg Groups enabled - setting put {self.name} field only")
                self.click_leg_header(driver, 'put')
                time.sleep(0.5)
                
                if 'put' in self.selectors:
                    element = self.find_element_by_selectors(driver, self.selectors['put'])
                    if element:
                        return self._set_field_value(driver, element, value, "put")
            
            return False
    
    def _set_field_value(self, driver, element, value, field_label="field") -> bool:
        """Helper to set a field value with appropriate method"""
        try:
            # Format value appropriately
            if isinstance(value, (int, float)):
                value_str = str(value)
            else:
                value_str = str(value) if value else ""
            
            # Try double-click method first
            success = self.double_click_and_fill(driver, element, value_str)
            
            if not success:
                # Fallback to regular clear and fill
                success = self.clear_and_fill(driver, element, value_str)
            
            if success:
                print(f"Set {field_label} {self.name} to {value_str}")
            else:
                print(f"Failed to set {field_label} {self.name}")
            
            return success
            
        except Exception as e:
            print(f"Error setting {field_label} value: {e}")
            return False
    
    # Common helper methods used by all parameters
    def find_element_by_selectors(self, driver, selectors: List[str], exclude_text: List[str] = None):
        """Try multiple selectors to find an element, with optional text exclusion"""
        exclude_text = exclude_text or []
        
        for selector in selectors:
            try:
                if selector.startswith("//") or selector.startswith("//*"):
                    element = driver.find_element(By.XPATH, selector)
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                
                if element and element.is_displayed():
                    # Check if element contains excluded text
                    if exclude_text:
                        element_text = element.text.lower()
                        aria_label = (element.get_attribute('aria-label') or '').lower()
                        
                        # Check if any excluded text appears in element
                        should_exclude = False
                        for excluded in exclude_text:
                            if excluded.lower() in element_text or excluded.lower() in aria_label:
                                should_exclude = True
                                break
                        
                        if should_exclude:
                            continue  # Skip this element and try next selector
                    
                    return element
            except:
                continue
        return None
    
    def clear_and_fill(self, driver, element, value: str) -> bool:
        """Clear an input field and fill with new value"""
        try:
            driver.execute_script("arguments[0].focus();", element)
            element.click()
            time.sleep(0.1)
            
            # Clear the field
            element.clear()
            
            # Fill with new value
            if value:  # Only send keys if value is not empty
                element.send_keys(str(value))
            
            # Trigger change events
            driver.execute_script("""
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                arguments[0].blur();
            """, element)
            
            # Verify the value was set
            return element.get_attribute('value') == str(value)
            
        except Exception as e:
            print(f"Error setting field value: {e}")
            return False
    
    def double_click_and_fill(self, driver, element, value: str) -> bool:
        """Double-click to select all, then fill"""
        try:
            driver.execute_script("arguments[0].focus();", element)
            element.click()
            time.sleep(0.1)
            
            # Double-click to select all
            ActionChains(driver).double_click(element).perform()
            time.sleep(0.1)
            
            # Clear and fill
            element.clear()
            element.send_keys(str(value))
            
            # Trigger change events
            driver.execute_script("""
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                arguments[0].blur();
            """, element)
            
            return element.get_attribute('value') == str(value)
            
        except Exception as e:
            print(f"Error with double-click fill: {e}")
            return False
    
    def click_leg_header(self, driver, leg_type: str) -> bool:
        """Click on a specific leg header (Call or Put) to focus on that leg's settings"""
        try:
            # Only needed when Leg Groups are enabled
            if not self.check_leg_groups_enabled(driver):
                return True  # Skip if not using leg groups
            
            # Selectors for leg headers
            if leg_type.lower() == 'call':
                header_selectors = [
                    "//h3[contains(text(), 'Profit & Loss – Call')]",
                    "div:nth-of-type(6) > div:nth-of-type(1) h3",
                    "//h3[contains(., 'Call')]",
                    "[aria-label*='Call']",
                    "h3:contains('Call')"
                ]
            else:  # put
                header_selectors = [
                    "//h3[contains(text(), 'Profit & Loss – Put')]",
                    "div:nth-of-type(7) > div:nth-of-type(1) h3", 
                    "//h3[contains(., 'Put')]",
                    "[aria-label*='Put']",
                    "h3:contains('Put')"
                ]
            
            element = self.find_element_by_selectors(driver, header_selectors)
            if element:
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                element.click()
                time.sleep(0.5)
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
                "//*[@id='headlessui-dialog-138']/div/div[2]/div/form/div[1]/div[2]/div/div[4]/div/div[2]/div[6]/div[1]/div/div/input",
                "div:nth-of-type(4) div.pr-3 input",
                "//div[contains(@class, 'pr-3')]//input",
            ],
            'max': [
                "div:nth-of-type(4) div:nth-of-type(6) > div:nth-of-type(2) input",
                "//*[@id='headlessui-dialog-138']/div/div[2]/div/form/div[1]/div[2]/div/div[4]/div/div[2]/div[6]/div[2]/div/div/input",
                "div:nth-of-type(6) > div:nth-of-type(2) input",
                "//div[6]/div[2]//input",
            ]
        }
    
    def set_value(self, driver, value) -> bool:
        """Set RSI value (min or max based on configuration)"""
        field_option = self.config.get('rsi_field_option', 'min')
        value_str = str(int(float(value)))
        
        selectors = self.selectors.get(field_option, self.selectors['min'])
        element = self.find_element_by_selectors(driver, selectors)
        
        if element:
            success = self.clear_and_fill(driver, element, value_str)
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
                "//div[9]/div[3]/div/div/input",
                "//*[@id='headlessui-dialog-26']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[9]/div[3]/div/div/input"
            ],
            'call': [
                "div:nth-of-type(10) > div:nth-of-type(2) input",
                "//div[10]/div[2]/div/div/input",
                "//*[@id='headlessui-dialog-26']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[10]/div[2]/div/div/input"
            ]
        }
    
    def set_value(self, driver, value) -> bool:
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
            element = self.find_element_by_selectors(driver, selectors)
            
            if element:
                if self.double_click_and_fill(driver, element, str(field_value)):
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
    """Profit Target Parameter - now with automatic leg detection"""
    
    def get_name(self) -> str:
        return "Profit Target"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'call': [
                "div:nth-of-type(6) > div:nth-of-type(1) div.pr-3 input",
                "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[1]/div/div[2]/div[1]/div[1]/div/div/input",
                "div:nth-of-type(6) div.pr-3 input",
            ],
            'put': [
                "div:nth-of-type(7) > div:nth-of-type(1) div.pr-3 input",
                "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[1]/div/div[2]/div[1]/div[1]/div/div/input",
                "div:nth-of-type(7) div.pr-3 input",
            ],
            'main': [  # Generic selectors for single field mode
                "div.pr-3 input",
                "//div[contains(@class, 'pr-3')]//input",
                "[placeholder*='profit' i][placeholder*='target' i]",
            ]
        }
    
    def set_value(self, driver, value) -> bool:
        """Set profit target value - automatically handles leg groups"""
        value_str = str(int(float(value)))
        leg_option = self.config.get('profit_target_leg_option', 'both')
        
        # Use the new smart method that detects Leg Groups automatically
        return self.smart_set_value(driver, value_str, leg_option)
    
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
        print("\nLeg preference (system will auto-detect if leg groups are available):")
        print("1. Both Call and Put")
        print("2. Call leg only")
        print("3. Put leg only")
        
        leg_choice = input("Select preference (default: 1): ").strip()
        if leg_choice == '2':
            config['profit_target_leg_option'] = 'call_only'
        elif leg_choice == '3':
            config['profit_target_leg_option'] = 'put_only'
        else:
            config['profit_target_leg_option'] = 'both'
        
        print(f"✅ Preference set: {config['profit_target_leg_option'].replace('_', ' ')}")
        print("   (Will use single field if Leg Groups not enabled)")
        
        # Value range configuration
        start = input("\nStart value (default 1): ").strip()
        config['profit_target_start'] = int(start) if start.isdigit() else 1
        
        end = input("End value (default 100): ").strip()
        config['profit_target_end'] = int(end) if end.isdigit() else 100
        
        step = input("Step size (default 1): ").strip()
        config['profit_target_step'] = int(step) if step.isdigit() else 1
        
        print(f"✅ Range: {config['profit_target_start']} to {config['profit_target_end']} by {config['profit_target_step']}")
        
        return config


class StopLossParameter(BaseParameter):
    """Stop Loss Parameter - now with automatic leg detection"""
    
    def get_name(self) -> str:
        return "Stop Loss"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'call': [
                "div:nth-of-type(6) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input",
                "//*[@id='headlessui-dialog-21']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[1]/div/div[2]/div[1]/div[2]/div/div/input",
                "div:nth-of-type(6) div.pt-6 input"
            ],
            'put': [
                "div:nth-of-type(7) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input",
                "//*[@id='headlessui-dialog-21']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[1]/div/div[2]/div[1]/div[2]/div/div/input",
                "div:nth-of-type(7) div.pt-6 input"
            ],
            'main': [  # Generic selectors for single field mode
                "div.pt-6 input",
                "//div[contains(@class, 'pt-6')]//input",
                "[placeholder*='stop' i][placeholder*='loss' i]",
            ]
        }
    
    def set_value(self, driver, value) -> bool:
        """Set stop loss value - automatically handles leg groups"""
        # Handle empty value case
        if value == "empty" or value == "" or value is None:
            value_str = ""
        else:
            value_str = str(int(float(value)))
        
        leg_option = self.config.get('stop_loss_leg_option', 'both')
        
        # Use the new smart method that detects Leg Groups automatically
        return self.smart_set_value(driver, value_str, leg_option)
    
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
        print("\nLeg preference (system will auto-detect if leg groups are available):")
        print("1. Both Call and Put")
        print("2. Call leg only")
        print("3. Put leg only")
        
        leg_choice = input("Select preference (default: 1): ").strip()
        if leg_choice == '2':
            config['stop_loss_leg_option'] = 'call_only'
        elif leg_choice == '3':
            config['stop_loss_leg_option'] = 'put_only'
        else:
            config['stop_loss_leg_option'] = 'both'
        
        print(f"✅ Preference set: {config['stop_loss_leg_option'].replace('_', ' ')}")
        print("   (Will use single field if Leg Groups not enabled)")
        
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
    """Entry Time Parameter - always single field"""
    
    def get_name(self) -> str:
        return "Entry Time"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'main': ["input[type='time']"]
        }
    
    def set_value(self, driver, value) -> bool:
        """Set entry time value"""
        element = self.find_element_by_selectors(driver, self.selectors['main'])
        
        if element:
            driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, element, value)
            print(f"Set entry time to {value}")
            return True
        
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
    """Exit Time Parameter - now with automatic leg detection"""
    
    def get_name(self) -> str:
        return "Exit Time"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'call': [
                "div:nth-of-type(6) div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input",
                "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[2]/div[2]/div/input",
            ],
            'put': [
                "div:nth-of-type(7) div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input",
                "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[2]/div/div[2]/div[2]/div[2]/div/input",
            ],
            'main': [  # Fallback
                "div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input",
                "//div[contains(@class, 'pt-6')]//div[2]//div[2]//input",
                "[placeholder*='exit' i][type='time']",
                "input[type='time']:nth-of-type(2)",
                "div:nth-of-type(2) input[type='time']"
            ],
            'early_exit_toggle': [
                "//button[@role='switch' and @aria-label='Use Early Exit']",
                "//label[text()='Use Early Exit']/..//button[@role='switch']",
                "//label[contains(text(), 'Early Exit') and not(contains(text(), 'DTE'))]/..//button",
                "#headlessui-switch-596"
            ]
        }
    
    def set_value(self, driver, value) -> bool:
        """Set exit time value - ensures Early Exit is enabled and handles leg groups"""
        # First ensure Early Exit is enabled
        if not self._ensure_early_exit_enabled(driver):
            print("Warning: Could not verify Early Exit is enabled")
        
        leg_option = self.config.get('exit_time_leg_option', 'both')
        
        # Use the smart method to handle leg groups automatically
        return self.smart_set_value(driver, value, leg_option)
    
    def _ensure_early_exit_enabled(self, driver) -> bool:
        """Ensure the Early Exit toggle is enabled for exit time testing"""
        try:
            # Look for the Early Exit toggle with exclusion for DTE
            toggle = self.find_element_by_selectors(driver, self.selectors['early_exit_toggle'], exclude_text=['DTE', 'Exact'])
            
            if toggle:
                # Double-check this isn't a DTE toggle
                aria_label = (toggle.get_attribute('aria-label') or '').lower()
                if 'dte' in aria_label or 'exact' in aria_label:
                    print("WARNING: Found DTE-related toggle, skipping!")
                    return False
                
                # Check if already enabled
                is_enabled = (toggle.get_attribute('aria-checked') == 'true' or
                            'active' in (toggle.get_attribute('class') or '').lower() or
                            'checked' in (toggle.get_attribute('class') or '').lower())
                
                print(f"Found Early Exit toggle, enabled: {is_enabled}")
                
                if not is_enabled:
                    driver.execute_script("arguments[0].click();", toggle)
                    time.sleep(1)
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
        print("Leg preference (system will auto-detect if leg groups are available):")
        print("1. Both Call and Put")
        print("2. Call leg only")
        print("3. Put leg only")
        
        leg_choice = input("Select preference (default: 1): ").strip()
        if leg_choice == '2':
            config['exit_time_leg_option'] = 'call_only'
        elif leg_choice == '3':
            config['exit_time_leg_option'] = 'put_only'
        else:
            config['exit_time_leg_option'] = 'both'
        
        print(f"✅ Preference set: {config['exit_time_leg_option'].replace('_', ' ')}")
        print("   (Will use single field if Leg Groups not enabled)")
        
        # Time range configuration
        start = input(f"\nStart exit time (HH:MM, default 14:00): ").strip()
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
    """Short/Long Ratio Parameter - always single field"""
    
    def get_name(self) -> str:
        return "Short/Long Ratio"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'main': [
                "div.flex-1 > div:nth-of-type(2) > div > div:nth-of-type(6) div.toggleDescription input",
                "//*[@id='headlessui-dialog-370']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[12]/div/input",
                "div.toggleDescription input",
                "//div[contains(@class, 'toggleDescription')]//input",
                "div:nth-of-type(12) input",
                "//div[12]/div/input",
                "[placeholder*='ratio' i]",
                "[placeholder*='short' i][placeholder*='long' i]"
            ]
        }
    
    def set_value(self, driver, value) -> bool:
        """Set short/long ratio value"""
        # Convert value to string with appropriate decimal precision
        if isinstance(value, (int, float)):
            value_str = f"{float(value):.2f}".rstrip('0').rstrip('.')
        else:
            value_str = str(value)
        
        element = self.find_element_by_selectors(driver, self.selectors['main'])
        
        if element:
            # Try double-click method first
            success = self.double_click_and_fill(driver, element, value_str)
            
            if not success:
                # Fallback to regular clear and fill
                success = self.clear_and_fill(driver, element, value_str)
            
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


class EntrySLRatioParameter(BaseParameter):
    """Entry S/L Ratio Minimum Parameter - single global setting with toggle requirement"""
    
    def get_name(self) -> str:
        return "Entry S/L Ratio Minimum"
    
    def get_selectors(self) -> Dict[str, List[str]]:
        return {
            'toggle': [
                "//button[@role='switch' and @aria-label='Use Entry Short/Long Ratio']",
                "//label[text()='Use Entry Short/Long Ratio']/..//button[@role='switch']",
                "//label[@id='headlessui-label-197']/..//button[@role='switch']",
                "#headlessui-switch-196"
            ],
            'main': [
                # The actual input field (appears to be in put section based on Puppeteer)
                "div:nth-of-type(7) div:nth-of-type(9) > div.pr-3 input",
                "//div[7]//div[9]/div[1]/div/div/input",
                "//*[@id='headlessui-dialog-109']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div/div[2]/div[9]/div[1]/div/div/input",
                "div:nth-of-type(9) > div.pr-3 input",
                "//div[9]/div[1]/div/div/input",
                "[placeholder*='ratio' i][placeholder*='minimum' i]",
                "[placeholder*='S/L' i][placeholder*='minimum' i]"
            ]
        }
    
    def _ensure_toggle_enabled(self, driver) -> bool:
        """Check and enable the 'Use Entry Short/Long Ratio' toggle if needed"""
        try:
            # Look for the toggle switch with exclusion for DTE
            toggle = self.find_element_by_selectors(driver, self.selectors['toggle'], exclude_text=['DTE', 'Exact'])
            
            if toggle:
                # Double-check this isn't a DTE toggle
                aria_label = (toggle.get_attribute('aria-label') or '').lower()
                element_text = (toggle.text or '').lower()
                if 'dte' in aria_label or 'exact' in aria_label or 'dte' in element_text:
                    print("WARNING: Found DTE-related toggle instead of Entry S/L Ratio, skipping!")
                    return False
                
                # Check if already enabled
                is_enabled = False
                try:
                    # Check various attributes that indicate enabled state
                    aria_checked = toggle.get_attribute('aria-checked')
                    class_attr = toggle.get_attribute('class') or ''
                    
                    is_enabled = (
                        aria_checked == 'true' or
                        'bg-blue' in class_attr or
                        'bg-indigo' in class_attr or
                        'active' in class_attr.lower() or
                        'checked' in class_attr.lower()
                    )
                except:
                    pass
                
                print(f"Found 'Use Entry Short/Long Ratio' toggle, currently enabled: {is_enabled}")
                
                if is_enabled:
                    # Toggle is already enabled, can proceed directly
                    print("'Use Entry Short/Long Ratio' is enabled - proceeding to set ratio value")
                    return True
                else:
                    # Need to enable the toggle first
                    print("'Use Entry Short/Long Ratio' is disabled - enabling it now")
                    driver.execute_script("arguments[0].scrollIntoView(true);", toggle)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", toggle)
                    time.sleep(1)
                    print("Successfully enabled 'Use Entry Short/Long Ratio' toggle")
                    return True
            else:
                print("Could not find 'Use Entry Short/Long Ratio' toggle")
                # Try to find it by looking for the label and clicking nearby
                try:
                    label = driver.find_element(By.XPATH, "//label[text()='Use Entry Short/Long Ratio']")
                    if label:
                        # Try clicking the label itself
                        driver.execute_script("arguments[0].click();", label)
                        time.sleep(1)
                        print("Clicked on label to enable toggle")
                        return True
                except:
                    pass
                
                return False
                
        except Exception as e:
            print(f"Error checking 'Use Entry Short/Long Ratio' toggle: {e}")
            return False
    
    def set_value(self, driver, value) -> bool:
        """Set S/L ratio minimum value (ensures toggle is enabled first)"""
        # First ensure the global toggle is enabled
        if not self._ensure_toggle_enabled(driver):
            print("Warning: Could not verify 'Use Entry Short/Long Ratio' is enabled")
            # Try to continue anyway
        
        time.sleep(1)  # Wait for UI to update after enabling toggle
        
        # Format value with appropriate decimal precision
        if isinstance(value, (int, float)):
            # Format with up to 2 decimal places, removing trailing zeros
            value_str = f"{float(value):.2f}".rstrip('0').rstrip('.')
        else:
            value_str = str(value)
        
        # Find the input field
        element = self.find_element_by_selectors(driver, self.selectors['main'])
        
        if element:
            # Scroll element into view first
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
            except:
                pass
            
            # Try double-click method first (as shown in puppeteer with count: 2)
            success = self.double_click_and_fill(driver, element, value_str)
            
            if not success:
                # Fallback to regular clear and fill
                success = self.clear_and_fill(driver, element, value_str)
            
            if success:
                print(f"Set Entry S/L ratio minimum to {value_str}")
                return True
            else:
                print(f"Failed to set Entry S/L ratio minimum")
                return False
        else:
            print(f"Could not find Entry S/L ratio minimum field")
            return False
    
    def generate_values(self) -> List:
        """Generate S/L ratio minimum test values"""
        values = []
        
        # Add empty value if enabled
        if self.config.get('sl_ratio_include_empty', False):
            values.append("")  # Empty string for no minimum
        
        # Generate numeric values
        start = self.config.get('sl_ratio_start', 0.0)
        end = self.config.get('sl_ratio_end', 5.0)
        step = self.config.get('sl_ratio_step', 0.25)
        
        current = start
        while current <= end + 0.001:  # Small epsilon for floating point comparison
            values.append(round(current, 2))
            current += step
        
        return values
    
    def configure_interactive(self, config: Dict) -> Dict:
        """Interactive configuration for Entry S/L Ratio Minimum"""
        print(f"\nConfiguring Entry S/L Ratio Minimum testing:")
        print("Note: This feature requires 'Use Entry Short/Long Ratio' to be enabled.")
        print("The automation will enable it automatically if needed.")
        print()
        print("S/L Ratio represents Stop Loss / Loss threshold:")
        print("  - 0.0 = No minimum ratio requirement")
        print("  - 0.25 = Stop loss must be at least 25% of potential loss")
        print("  - 1.0 = Stop loss must equal potential loss")
        print("  - 2.0 = Stop loss must be 2x potential loss")
        print("  - Higher values = More restrictive entry criteria")
        print()
        
        # No leg configuration needed - this is a single global field
        
        # Ask about including empty value
        include_empty = input("Include 'no minimum' (empty) value? (y/n, default: n): ").strip().lower()
        config['sl_ratio_include_empty'] = (include_empty == 'y')
        
        # Start value
        start = input("\nStart ratio (default 0.0): ").strip()
        try:
            config['sl_ratio_start'] = float(start) if start else 0.0
        except ValueError:
            config['sl_ratio_start'] = 0.0
            print("Invalid input, using default 0.0")
        
        # End value
        end = input("End ratio (default 5.0): ").strip()
        try:
            config['sl_ratio_end'] = float(end) if end else 5.0
        except ValueError:
            config['sl_ratio_end'] = 5.0
            print("Invalid input, using default 5.0")
        
        # Step size
        step = input("Step size (default 0.25): ").strip()
        try:
            config['sl_ratio_step'] = float(step) if step else 0.25
        except ValueError:
            config['sl_ratio_step'] = 0.25
            print("Invalid input, using default 0.25")
        
        # Validate configuration
        if config['sl_ratio_start'] < 0:
            config['sl_ratio_start'] = 0.0
            print("Start ratio cannot be negative, using 0.0")
        
        if config['sl_ratio_end'] < config['sl_ratio_start']:
            config['sl_ratio_end'] = config['sl_ratio_start'] + 5.0
            print(f"End ratio must be >= start ratio, using {config['sl_ratio_end']}")
        
        if config['sl_ratio_step'] <= 0:
            config['sl_ratio_step'] = 0.25
            print("Step must be positive, using 0.25")
        
        # Show summary
        test_values = self.generate_values()
        print(f"\n✅ Range: {config['sl_ratio_start']} to {config['sl_ratio_end']} by {config['sl_ratio_step']}")
        if config['sl_ratio_include_empty']:
            print("✅ Including 'no minimum' (empty) value")
        print(f"✅ Will test {len(test_values)} Entry S/L ratio values")
        
        if len(test_values) <= 10:
            print(f"   Values: {test_values}")
        else:
            print(f"   First 5: {test_values[:5]}")
            print(f"   Last 5: {test_values[-5:]}")
        
        return config
    
    def get_description(self) -> str:
        """Return description of this parameter"""
        return "Test different minimum Entry Short/Long ratio requirements (single global setting)"


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
        'entry_sl_ratio': EntrySLRatioParameter,  # New parameter
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


# Example usage in the main worker:
class SimplifiedWorker:
    """Simplified worker using the parameter plugin system"""
    
    def __init__(self, worker_id, config):
        self.worker_id = worker_id
        self.config = config
        self.driver = None
        
        # Load the appropriate parameter handler
        param_type = config['parameter_type']
        self.parameter_handler = ParameterFactory.create_parameter(param_type, config)
        
        print(f"Worker {worker_id}: Loaded {self.parameter_handler.get_name()} parameter handler")
    
    def set_parameter_value(self, value) -> bool:
        """Delegate to the parameter handler"""
        return self.parameter_handler.set_value(self.driver, value)
    
    def get_test_values(self) -> List:
        """Get values to test from the parameter handler"""
        return self.parameter_handler.generate_values()
    
    def run_test(self, value):
        """Run a single test with the given parameter value"""
        print(f"Worker {self.worker_id}: Testing {self.parameter_handler.get_name()}={value}")
        
        # Click New Backtest, wait for dialog, etc.
        # ...
        
        # Set the parameter value using the handler
        if self.set_parameter_value(value):
            print(f"Worker {self.worker_id}: Successfully set value")
            # Continue with test...
        else:
            print(f"Worker {self.worker_id}: Failed to set value")
            # Handle failure...


# Interactive configuration example:
def configure_parameters_interactive():
    """Interactive parameter configuration using the plugin system"""
    
    print("\nSELECT PARAMETER TO TEST")
    print("="*50)
    
    available_params = ParameterFactory.get_available_parameters()
    
    for i, param_type in enumerate(available_params, 1):
        # Create temporary instance to get name and description
        temp_handler = ParameterFactory.create_parameter(param_type, {})
        print(f"{i}. {temp_handler.get_name()} - {temp_handler.get_description()}")
    
    while True:
        choice = input(f"\nSelect parameter (1-{len(available_params)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available_params):
                selected_type = available_params[idx]
                break
        except:
            print("Invalid selection")
    
    # Create handler and run interactive configuration
    config = {'parameter_type': selected_type}
    handler = ParameterFactory.create_parameter(selected_type, config)
    config = handler.configure_interactive(config)
    
    return config, handler
