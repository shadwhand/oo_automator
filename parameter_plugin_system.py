"""
COMPLETE Parameter Plugin System with Verification
All parameter classes implemented with verify_value() methods
Includes new Underlying Movement parameter
"""

import abc
import re
import time
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from utils.waiters import (
    wait_clickable, wait_visible, wait_present, wait_value_equals,
    safe_click, find_any, find_any_wait, try_until
)
from utils.selectors import *


class BaseParameter(abc.ABC):
    """Base class with verification support"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.get_name()
        self.selectors = self.get_selectors()
        self.leg_groups_enabled = None
        
    @abc.abstractmethod
    def get_name(self) -> str:
        pass
    
    @abc.abstractmethod
    def get_selectors(self) -> Dict[str, List]:
        pass
    
    @abc.abstractmethod
    def set_value(self, driver, value) -> bool:
        pass
    
    @abc.abstractmethod
    def verify_value(self, driver, expected_value) -> bool:
        """CRITICAL: Verify the parameter value was set correctly"""
        pass
    
    @abc.abstractmethod
    def generate_values(self) -> List:
        pass
    
    @abc.abstractmethod
    def configure_interactive(self, config: Dict) -> Dict:
        pass
    
    def get_description(self) -> str:
        return f"Test different {self.name.lower()} values"
    
    # Common helper methods
    def clear_overlays(self, driver):
        try:
            overlays = driver.find_elements(*MODAL_OVERLAY[0])
            for overlay in overlays:
                if overlay.is_displayed():
                    try:
                        driver.execute_script("arguments[0].remove();", overlay)
                    except:
                        pass
            time.sleep(0.2)
        except:
            pass
    
    def check_leg_groups_enabled(self, driver) -> bool:
        if self.leg_groups_enabled is not None:
            return self.leg_groups_enabled
        
        try:
            self.clear_overlays(driver)
            toggle = find_any(driver, LEG_GROUPS_TOGGLE, timeout=5)
            
            if not toggle:
                self.leg_groups_enabled = False
                return False
            
            context = (toggle.get_attribute('aria-label') or '').lower()
            context += ' ' + (toggle.text or '').lower()
            
            if 'dte' in context or 'exact' in context or 'leg' not in context:
                self.leg_groups_enabled = False
                return False
            
            is_enabled = (
                toggle.get_attribute('aria-checked') == 'true' or
                'bg-blue' in (toggle.get_attribute('class') or '')
            )
            
            self.leg_groups_enabled = is_enabled
            return is_enabled
        except:
            self.leg_groups_enabled = False
            return False
    
    def clear_and_fill(self, driver, element, value: str) -> bool:
        try:
            self.clear_overlays(driver)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)
            
            safe_click(driver, element)
            time.sleep(0.1)
            
            element.clear()
            if value:
                element.send_keys(str(value))
            
            driver.execute_script("""
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                arguments[0].blur();
            """, element)
            
            time.sleep(0.2)
            return element.get_attribute('value') == str(value)
        except:
            return False


# ============================================================================
# ALL PARAMETER CLASSES
# ============================================================================

class RSIParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "RSI"
    
    def get_selectors(self) -> Dict[str, List]:
        return {'min': RSI_MIN, 'max': RSI_MAX}
    
    def set_value(self, driver, value) -> bool:
        field_option = self.config.get('rsi_field_option', 'min')
        value_str = str(int(float(value)))
        selectors = self.selectors[field_option]
        element = find_any_wait(driver, selectors, timeout=10)
        return self.clear_and_fill(driver, element, value_str) if element else False
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            field_option = self.config.get('rsi_field_option', 'min')
            value_str = str(int(float(expected_value)))
            element = find_any(driver, self.selectors[field_option], timeout=5)
            return element.get_attribute('value') == value_str if element else False
        except:
            return False
    
    def generate_values(self) -> List[int]:
        return list(range(
            self.config.get('rsi_start', 0),
            self.config.get('rsi_end', 100) + 1,
            self.config.get('rsi_step', 5)
        ))
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring RSI:")
        print("1. Min RSI\n2. Max RSI")
        config['rsi_field_option'] = 'max' if input("Select (default 1): ").strip() == '2' else 'min'
        
        start = input("Start (default 0): ").strip()
        config['rsi_start'] = int(start) if start.isdigit() else 0
        
        end = input("End (default 100): ").strip()
        config['rsi_end'] = int(end) if end.isdigit() else 100
        
        step = input("Step (default 5): ").strip()
        config['rsi_step'] = int(step) if step.isdigit() else 5
        
        return config


class DeltaParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "Delta"
    
    def get_selectors(self) -> Dict[str, List]:
        return {'put': DELTA_PUT, 'call': DELTA_CALL}
    
    def set_value(self, driver, value) -> bool:
        field_option = self.config.get('delta_field_option', 'both')
        delta_value = int(float(value))
        
        fields = []
        if field_option == 'put_only':
            fields = [('put', delta_value)]
        elif field_option == 'call_only':
            fields = [('call', -delta_value)]
        else:
            fields = [('put', delta_value), ('call', -delta_value)]
        
        success_count = 0
        for field_type, field_value in fields:
            element = find_any_wait(driver, self.selectors[field_type], timeout=10)
            if element and self.clear_and_fill(driver, element, str(field_value)):
                success_count += 1
        
        return success_count == len(fields)
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            field_option = self.config.get('delta_field_option', 'both')
            delta_value = int(float(expected_value))
            
            if field_option == 'put_only':
                element = find_any(driver, self.selectors['put'], timeout=5)
                return element.get_attribute('value') == str(delta_value) if element else False
            elif field_option == 'call_only':
                element = find_any(driver, self.selectors['call'], timeout=5)
                return element.get_attribute('value') == str(-delta_value) if element else False
            else:
                put_elem = find_any(driver, self.selectors['put'], timeout=5)
                call_elem = find_any(driver, self.selectors['call'], timeout=5)
                put_ok = put_elem.get_attribute('value') == str(delta_value) if put_elem else False
                call_ok = call_elem.get_attribute('value') == str(-delta_value) if call_elem else False
                return put_ok and call_ok
        except:
            return False
    
    def generate_values(self) -> List[int]:
        return list(range(
            self.config.get('delta_start', 1),
            self.config.get('delta_end', 100) + 1,
            self.config.get('delta_step', 1)
        ))
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Delta:")
        print("1. Put only\n2. Call only\n3. Both (recommended)")
        choice = input("Select (default 3): ").strip()
        
        config['delta_field_option'] = {
            '1': 'put_only',
            '2': 'call_only'
        }.get(choice, 'both')
        
        start = input("Start (default 1): ").strip()
        config['delta_start'] = int(start) if start.isdigit() else 1
        
        end = input("End (default 100): ").strip()
        config['delta_end'] = int(end) if end.isdigit() else 100
        
        step = input("Step (default 1): ").strip()
        config['delta_step'] = int(step) if step.isdigit() else 1
        
        return config


class ProfitTargetParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "Profit Target"
    
    def get_selectors(self) -> Dict[str, List]:
        return {
            'call': PROFIT_TARGET_CALL,
            'put': PROFIT_TARGET_PUT,
            'main': PROFIT_TARGET_MAIN
        }
    
    def set_value(self, driver, value) -> bool:
        value_str = str(int(float(value)))
        leg_option = self.config.get('profit_target_leg_option', 'both')
        
        leg_groups = self.check_leg_groups_enabled(driver)
        
        if not leg_groups:
            element = find_any_wait(driver, self.selectors['main'], timeout=10)
            return self.clear_and_fill(driver, element, value_str) if element else False
        
        if leg_option == 'both':
            call_ok = put_ok = False
            call_elem = find_any_wait(driver, self.selectors['call'], timeout=10)
            if call_elem:
                call_ok = self.clear_and_fill(driver, call_elem, value_str)
            put_elem = find_any_wait(driver, self.selectors['put'], timeout=10)
            if put_elem:
                put_ok = self.clear_and_fill(driver, put_elem, value_str)
            return call_ok or put_ok
        else:
            field = 'call' if leg_option == 'call_only' else 'put'
            element = find_any_wait(driver, self.selectors[field], timeout=10)
            return self.clear_and_fill(driver, element, value_str) if element else False
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            value_str = str(int(float(expected_value)))
            leg_option = self.config.get('profit_target_leg_option', 'both')
            leg_groups = self.check_leg_groups_enabled(driver)
            
            if not leg_groups:
                element = find_any(driver, self.selectors['main'], timeout=5)
                return element.get_attribute('value') == value_str if element else False
            
            if leg_option == 'both':
                call_elem = find_any(driver, self.selectors['call'], timeout=5)
                put_elem = find_any(driver, self.selectors['put'], timeout=5)
                call_ok = call_elem.get_attribute('value') == value_str if call_elem else True
                put_ok = put_elem.get_attribute('value') == value_str if put_elem else True
                return call_ok and put_ok
            else:
                field = 'call' if leg_option == 'call_only' else 'put'
                element = find_any(driver, self.selectors[field], timeout=5)
                return element.get_attribute('value') == value_str if element else False
        except:
            return False
    
    def generate_values(self) -> List[int]:
        return list(range(
            self.config.get('profit_target_start', 1),
            self.config.get('profit_target_end', 100) + 1,
            self.config.get('profit_target_step', 1)
        ))
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Profit Target:")
        print("1. Both Call and Put\n2. Call only\n3. Put only")
        choice = input("Select (default 1): ").strip()
        
        config['profit_target_leg_option'] = {
            '2': 'call_only',
            '3': 'put_only'
        }.get(choice, 'both')
        
        start = input("Start (default 1): ").strip()
        config['profit_target_start'] = int(start) if start.isdigit() else 1
        
        end = input("End (default 100): ").strip()
        config['profit_target_end'] = int(end) if end.isdigit() else 100
        
        step = input("Step (default 1): ").strip()
        config['profit_target_step'] = int(step) if step.isdigit() else 1
        
        return config


class StopLossParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "Stop Loss"
    
    def get_selectors(self) -> Dict[str, List]:
        return {
            'call': STOP_LOSS_CALL,
            'put': STOP_LOSS_PUT,
            'main': STOP_LOSS_MAIN
        }
    
    def set_value(self, driver, value) -> bool:
        value_str = "" if value == "empty" or value == "" else str(int(float(value)))
        leg_option = self.config.get('stop_loss_leg_option', 'both')
        
        leg_groups = self.check_leg_groups_enabled(driver)
        
        if not leg_groups:
            element = find_any_wait(driver, self.selectors['main'], timeout=10)
            return self.clear_and_fill(driver, element, value_str) if element else False
        
        if leg_option == 'both':
            call_ok = put_ok = False
            call_elem = find_any_wait(driver, self.selectors['call'], timeout=10)
            if call_elem:
                call_ok = self.clear_and_fill(driver, call_elem, value_str)
            put_elem = find_any_wait(driver, self.selectors['put'], timeout=10)
            if put_elem:
                put_ok = self.clear_and_fill(driver, put_elem, value_str)
            return call_ok or put_ok
        else:
            field = 'call' if leg_option == 'call_only' else 'put'
            element = find_any_wait(driver, self.selectors[field], timeout=10)
            return self.clear_and_fill(driver, element, value_str) if element else False
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            value_str = "" if expected_value == "empty" or expected_value == "" else str(int(float(expected_value)))
            leg_option = self.config.get('stop_loss_leg_option', 'both')
            leg_groups = self.check_leg_groups_enabled(driver)
            
            if not leg_groups:
                element = find_any(driver, self.selectors['main'], timeout=5)
                return element.get_attribute('value') == value_str if element else False
            
            if leg_option == 'both':
                call_elem = find_any(driver, self.selectors['call'], timeout=5)
                put_elem = find_any(driver, self.selectors['put'], timeout=5)
                call_ok = call_elem.get_attribute('value') == value_str if call_elem else True
                put_ok = put_elem.get_attribute('value') == value_str if put_elem else True
                return call_ok and put_ok
            else:
                field = 'call' if leg_option == 'call_only' else 'put'
                element = find_any(driver, self.selectors[field], timeout=5)
                return element.get_attribute('value') == value_str if element else False
        except:
            return False
    
    def generate_values(self) -> List:
        values = []
        if self.config.get('stop_loss_include_empty', True):
            values.append("empty")
        if self.config.get('stop_loss_include_numeric', True):
            values.extend(list(range(
                self.config.get('stop_loss_start', 0),
                self.config.get('stop_loss_end', 100) + 1,
                self.config.get('stop_loss_step', 5)
            )))
        return values
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Stop Loss:")
        print("1. Both Call and Put\n2. Call only\n3. Put only")
        choice = input("Select (default 1): ").strip()
        
        config['stop_loss_leg_option'] = {
            '2': 'call_only',
            '3': 'put_only'
        }.get(choice, 'both')
        
        print("\n1. Empty only\n2. Numeric only\n3. Both")
        value_type = input("Select (default 3): ").strip()
        
        config['stop_loss_include_empty'] = value_type != '2'
        config['stop_loss_include_numeric'] = value_type != '1'
        
        if config['stop_loss_include_numeric']:
            start = input("Start (default 0): ").strip()
            config['stop_loss_start'] = int(start) if start.isdigit() else 0
            
            end = input("End (default 100): ").strip()
            config['stop_loss_end'] = int(end) if end.isdigit() else 100
            
            step = input("Step (default 5): ").strip()
            config['stop_loss_step'] = int(step) if step.isdigit() else 5
        
        return config


class EntryTimeParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "Entry Time"
    
    def get_selectors(self) -> Dict[str, List]:
        return {'main': ENTRY_TIME_INPUT}
    
    def set_value(self, driver, value) -> bool:
        try:
            element = find_any_wait(driver, self.selectors['main'], timeout=10)
            if element:
                driver.execute_script("""
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, element, value)
                time.sleep(0.2)
                return True
            return False
        except:
            return False
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            element = find_any(driver, self.selectors['main'], timeout=5)
            return element.get_attribute('value') == str(expected_value) if element else False
        except:
            return False
    
    def generate_values(self) -> List[str]:
        start_time = self.config.get('start_time', '10:00')
        end_time = self.config.get('end_time', '15:59')
        interval = self.config.get('interval_minutes', 1)
        
        times = []
        start_h, start_m = map(int, start_time.split(':'))
        end_h, end_m = map(int, end_time.split(':'))
        
        current = start_h * 60 + start_m
        end = end_h * 60 + end_m
        
        while current <= end:
            times.append(f"{current // 60:02d}:{current % 60:02d}")
            current += interval
        
        return times
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Entry Time:")
        
        start = input("Start time (HH:MM, default 10:00): ").strip()
        config['start_time'] = start if start and ':' in start else '10:00'
        
        end = input("End time (HH:MM, default 15:59): ").strip()
        config['end_time'] = end if end and ':' in end else '15:59'
        
        interval = input("Interval (minutes, default 1): ").strip()
        config['interval_minutes'] = int(interval) if interval.isdigit() else 1
        
        return config


class ExitTimeParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "Exit Time"
    
    def get_selectors(self) -> Dict[str, List]:
        return {
            'call': EXIT_TIME_CALL,
            'put': EXIT_TIME_PUT,
            'main': EXIT_TIME_MAIN,
            'toggle': EARLY_EXIT_TOGGLE
        }
    
    def _ensure_early_exit_enabled(self, driver) -> bool:
        try:
            toggle = find_any(driver, self.selectors['toggle'], timeout=5)
            if not toggle:
                return False
            
            context = (toggle.get_attribute('aria-label') or '').lower() + ' ' + (toggle.text or '').lower()
            if 'dte' in context or 'exact' in context or 'early' not in context:
                return False
            
            is_enabled = toggle.get_attribute('aria-checked') == 'true'
            if not is_enabled:
                driver.execute_script("arguments[0].click();", toggle)
                time.sleep(1)
            
            return True
        except:
            return False
    
    def set_value(self, driver, value) -> bool:
        self._ensure_early_exit_enabled(driver)
        leg_option = self.config.get('exit_time_leg_option', 'both')
        leg_groups = self.check_leg_groups_enabled(driver)
        
        if not leg_groups:
            element = find_any_wait(driver, self.selectors['main'], timeout=10)
            if element:
                driver.execute_script("""
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, element, value)
                time.sleep(0.2)
                return True
            return False
        
        if leg_option == 'both':
            call_ok = put_ok = False
            for field in ['call', 'put']:
                elem = find_any_wait(driver, self.selectors[field], timeout=10)
                if elem:
                    driver.execute_script("""
                        arguments[0].value = arguments[1];
                        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    """, elem, value)
                    if field == 'call':
                        call_ok = True
                    else:
                        put_ok = True
            time.sleep(0.2)
            return call_ok or put_ok
        else:
            field = 'call' if leg_option == 'call_only' else 'put'
            element = find_any_wait(driver, self.selectors[field], timeout=10)
            if element:
                driver.execute_script("""
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, element, value)
                time.sleep(0.2)
                return True
            return False
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            leg_option = self.config.get('exit_time_leg_option', 'both')
            leg_groups = self.check_leg_groups_enabled(driver)
            
            if not leg_groups:
                element = find_any(driver, self.selectors['main'], timeout=5)
                return element.get_attribute('value') == str(expected_value) if element else False
            
            if leg_option == 'both':
                call_elem = find_any(driver, self.selectors['call'], timeout=5)
                put_elem = find_any(driver, self.selectors['put'], timeout=5)
                call_ok = call_elem.get_attribute('value') == str(expected_value) if call_elem else True
                put_ok = put_elem.get_attribute('value') == str(expected_value) if put_elem else True
                return call_ok and put_ok
            else:
                field = 'call' if leg_option == 'call_only' else 'put'
                element = find_any(driver, self.selectors[field], timeout=5)
                return element.get_attribute('value') == str(expected_value) if element else False
        except:
            return False
    
    def generate_values(self) -> List[str]:
        start_time = self.config.get('exit_start_time', '14:00')
        end_time = self.config.get('exit_end_time', '15:59')
        interval = self.config.get('exit_interval_minutes', 1)
        
        times = []
        start_h, start_m = map(int, start_time.split(':'))
        end_h, end_m = map(int, end_time.split(':'))
        
        current = start_h * 60 + start_m
        end = end_h * 60 + end_m
        
        while current <= end:
            times.append(f"{current // 60:02d}:{current % 60:02d}")
            current += interval
        
        return times
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Exit Time:")
        print("1. Both Call and Put\n2. Call only\n3. Put only")
        choice = input("Select (default 1): ").strip()
        
        config['exit_time_leg_option'] = {
            '2': 'call_only',
            '3': 'put_only'
        }.get(choice, 'both')
        
        start = input("Start time (HH:MM, default 14:00): ").strip()
        config['exit_start_time'] = start if start and ':' in start else '14:00'
        
        end = input("End time (HH:MM, default 15:59): ").strip()
        config['exit_end_time'] = end if end and ':' in end else '15:59'
        
        interval = input("Interval (minutes, default 1): ").strip()
        config['exit_interval_minutes'] = int(interval) if interval.isdigit() else 1
        
        return config


class ShortLongRatioParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "Short/Long Ratio"
    
    def get_selectors(self) -> Dict[str, List]:
        return {'main': SHORT_LONG_RATIO}
    
    def set_value(self, driver, value) -> bool:
        value_str = f"{float(value):.2f}".rstrip('0').rstrip('.')
        element = find_any_wait(driver, self.selectors['main'], timeout=10)
        return self.clear_and_fill(driver, element, value_str) if element else False
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            value_str = f"{float(expected_value):.2f}".rstrip('0').rstrip('.')
            element = find_any(driver, self.selectors['main'], timeout=5)
            if element:
                actual = element.get_attribute('value')
                return abs(float(actual) - float(value_str)) < 0.01
            return False
        except:
            return False
    
    def generate_values(self) -> List[float]:
        start = self.config.get('ratio_start', 0.1)
        end = self.config.get('ratio_end', 2.0)
        step = self.config.get('ratio_step', 0.1)
        
        values = []
        current = start
        while current <= end + 0.001:
            values.append(round(current, 2))
            current += step
        return values
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Short/Long Ratio:")
        
        start = input("Start ratio (default 0.1): ").strip()
        config['ratio_start'] = float(start) if start else 0.1
        
        end = input("End ratio (default 2.0): ").strip()
        config['ratio_end'] = float(end) if end else 2.0
        
        step = input("Step (default 0.1): ").strip()
        config['ratio_step'] = float(step) if step else 0.1
        
        return config


class EntrySLRatioParameter(BaseParameter):
    
    def get_name(self) -> str:
        return "Entry S/L Ratio Minimum"
    
    def get_selectors(self) -> Dict[str, List]:
        return {
            'toggle': ENTRY_SL_RATIO_TOGGLE,
            'main': ENTRY_SL_RATIO_MIN
        }
    
    def _ensure_toggle_enabled(self, driver) -> bool:
        try:
            toggle = find_any(driver, self.selectors['toggle'], timeout=5)
            if not toggle:
                return False
            
            context = (toggle.get_attribute('aria-label') or '').lower() + ' ' + (toggle.text or '').lower()
            if 'dte' in context or 'exact' in context or 'entry' not in context:
                return False
            
            is_enabled = toggle.get_attribute('aria-checked') == 'true'
            if not is_enabled:
                driver.execute_script("arguments[0].click();", toggle)
                time.sleep(1)
            
            return True
        except:
            return False
    
    def set_value(self, driver, value) -> bool:
        value_str = f"{float(value):.2f}".rstrip('0').rstrip('.') if value else ""
        
        element = find_any(driver, self.selectors['main'], timeout=5)
        if not element:
            if self._ensure_toggle_enabled(driver):
                time.sleep(1)
                element = find_any_wait(driver, self.selectors['main'], timeout=10)
        
        return self.clear_and_fill(driver, element, value_str) if element else False
    
    def verify_value(self, driver, expected_value) -> bool:
        try:
            value_str = f"{float(expected_value):.2f}".rstrip('0').rstrip('.') if expected_value else ""
            element = find_any(driver, self.selectors['main'], timeout=5)
            if element:
                actual = element.get_attribute('value')
                if not value_str:
                    return not actual
                return abs(float(actual) - float(value_str)) < 0.01
            return False
        except:
            return False
    
    def generate_values(self) -> List:
        values = []
        if self.config.get('sl_ratio_include_empty', False):
            values.append("")
        
        start = self.config.get('sl_ratio_start', 0.0)
        end = self.config.get('sl_ratio_end', 5.0)
        step = self.config.get('sl_ratio_step', 0.25)
        
        current = start
        while current <= end + 0.001:
            values.append(round(current, 2))
            current += step
        return values
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Entry S/L Ratio Minimum:")
        
        include_empty = input("Include 'no minimum' value? (y/n, default n): ").strip().lower()
        config['sl_ratio_include_empty'] = (include_empty == 'y')
        
        start = input("Start ratio (default 0.0): ").strip()
        config['sl_ratio_start'] = float(start) if start else 0.0
        
        end = input("End ratio (default 5.0): ").strip()
        config['sl_ratio_end'] = float(end) if end else 5.0
        
        step = input("Step (default 0.25): ").strip()
        config['sl_ratio_step'] = float(step) if step else 0.25
        
        return config


class UnderlyingMovementParameter(BaseParameter):
    """
    Tests Underlying Price Movement for OTM Short Put and Short Call.
    Enables main toggle and individual leg toggles before setting values.
    """
    
    def get_name(self) -> str:
        return "Underlying Movement"
    
    def get_selectors(self) -> Dict[str, List]:
        return {
            'main_toggle': UNDERLYING_MOVEMENT_TOGGLE,
            'short_put_toggle': UNDERLYING_MOVEMENT_SHORT_PUT_TOGGLE,
            'short_call_toggle': UNDERLYING_MOVEMENT_SHORT_CALL_TOGGLE,
            'short_put_input': UNDERLYING_MOVEMENT_SHORT_PUT,
            'short_call_input': UNDERLYING_MOVEMENT_SHORT_CALL
        }
    
    def _ensure_toggle_enabled(self, driver, toggle_selectors) -> bool:
        """Enable a toggle if not already enabled"""
        try:
            toggle = find_any(driver, toggle_selectors, timeout=5)
            if not toggle:
                return False
            
            is_enabled = toggle.get_attribute('aria-checked') == 'true'
            if not is_enabled:
                driver.execute_script("arguments[0].click();", toggle)
                time.sleep(0.5)
            
            return True
        except:
            return False
    
    def set_value(self, driver, value) -> bool:
        """
        Set movement value for Short Put and/or Short Call.
        Enables all necessary toggles before setting values.
        """
        try:
            value_str = str(float(value))
            leg_option = self.config.get('underlying_movement_leg_option', 'both')
            
            # Step 1: Enable main "Use Underlying Price Movement" toggle
            if not self._ensure_toggle_enabled(driver, self.selectors['main_toggle']):
                return False
            
            time.sleep(0.5)
            
            success_count = 0
            
            # Step 2: Enable and set Short Put
            if leg_option in ['both', 'put_only']:
                # Enable the Short Put toggle first
                if self._ensure_toggle_enabled(driver, self.selectors['short_put_toggle']):
                    time.sleep(0.3)
                    # Now set the input value
                    put_elem = find_any_wait(driver, self.selectors['short_put_input'], timeout=10)
                    if put_elem and self.clear_and_fill(driver, put_elem, value_str):
                        success_count += 1
            
            # Step 3: Enable and set Short Call
            if leg_option in ['both', 'call_only']:
                # Enable the Short Call toggle first
                if self._ensure_toggle_enabled(driver, self.selectors['short_call_toggle']):
                    time.sleep(0.3)
                    # Now set the input value
                    call_elem = find_any_wait(driver, self.selectors['short_call_input'], timeout=10)
                    if call_elem and self.clear_and_fill(driver, call_elem, value_str):
                        success_count += 1
            
            expected_count = 2 if leg_option == 'both' else 1
            return success_count == expected_count
            
        except:
            return False
    
    def verify_value(self, driver, expected_value) -> bool:
        """Verify movement values were set correctly"""
        try:
            value_str = str(float(expected_value))
            leg_option = self.config.get('underlying_movement_leg_option', 'both')
            
            # Check main toggle
            main_toggle = find_any(driver, self.selectors['main_toggle'], timeout=5)
            if not main_toggle or main_toggle.get_attribute('aria-checked') != 'true':
                return False
            
            if leg_option in ['both', 'put_only']:
                put_elem = find_any(driver, self.selectors['short_put_input'], timeout=5)
                if not put_elem:
                    return False
                if abs(float(put_elem.get_attribute('value')) - float(value_str)) > 0.01:
                    return False
            
            if leg_option in ['both', 'call_only']:
                call_elem = find_any(driver, self.selectors['short_call_input'], timeout=5)
                if not call_elem:
                    return False
                if abs(float(call_elem.get_attribute('value')) - float(value_str)) > 0.01:
                    return False
            
            return True
            
        except:
            return False
    
    def generate_values(self) -> List[float]:
        """
        Generate movement percentage values.
        Supports negative values and backward iteration (e.g., -10 to -25).
        """
        start = self.config.get('movement_start', -10.0)
        end = self.config.get('movement_end', -25.0)
        step = self.config.get('movement_step', -0.5)
        
        values = []
        
        # Determine direction based on start and end
        if start > end:
            # Backward iteration (decreasing values)
            if step > 0:
                step = -step  # Force step to be negative
            current = start
            while current >= end - 0.001:
                values.append(round(current, 2))
                current += step
        else:
            # Forward iteration (increasing values)
            if step < 0:
                step = -step  # Force step to be positive
            current = start
            while current <= end + 0.001:
                values.append(round(current, 2))
                current += step
        
        return values
    
    def configure_interactive(self, config: Dict) -> Dict:
        print("\nConfiguring Underlying Movement:")
        print("Tests movement % for OTM Short Put and Short Call")
        print("(Use negative values for downward movement)")
        print("\nExample: -10 to -25 with step -0.5")
        print("         (tests -10, -10.5, -11, ..., -24.5, -25)")
        print("\n1. Both Put and Call (recommended)")
        print("2. Put only")
        print("3. Call only")
        choice = input("Select (default 1): ").strip()
        
        config['underlying_movement_leg_option'] = {
            '2': 'put_only',
            '3': 'call_only'
        }.get(choice, 'both')
        
        start = input("Start movement % (default -10.0): ").strip()
        config['movement_start'] = float(start) if start else -10.0
        
        end = input("End movement % (default -25.0): ").strip()
        config['movement_end'] = float(end) if end else -25.0
        
        step = input("Step (default -0.5): ").strip()
        config['movement_step'] = float(step) if step else -0.5
        
        return config


# ============================================================================
# FACTORY
# ============================================================================

class ParameterFactory:
    
    PARAMETER_CLASSES = {
        'rsi': RSIParameter,
        'delta': DeltaParameter,
        'profit_target': ProfitTargetParameter,
        'stop_loss': StopLossParameter,
        'entry_time': EntryTimeParameter,
        'exit_time': ExitTimeParameter,
        'short_long_ratio': ShortLongRatioParameter,
        'entry_sl_ratio': EntrySLRatioParameter,
        'underlying_movement': UnderlyingMovementParameter,
    }
    
    @classmethod
    def create_parameter(cls, parameter_type: str, config: Dict) -> BaseParameter:
        parameter_class = cls.PARAMETER_CLASSES.get(parameter_type)
        if not parameter_class:
            raise ValueError(f"Unknown parameter type: {parameter_type}")
        return parameter_class(config)
    
    @classmethod
    def get_available_parameters(cls) -> List[str]:
        return list(cls.PARAMETER_CLASSES.keys())
    
    @classmethod
    def register_parameter(cls, name: str, parameter_class):
        cls.PARAMETER_CLASSES[name] = parameter_class
