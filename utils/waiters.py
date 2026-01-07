"""
Robust wait utilities to replace time.sleep() throughout the automation.
These wait for actual DOM conditions rather than arbitrary time delays.
"""

import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

DEFAULT_TIMEOUT = 30
POLL_FREQUENCY = 0.2


def wait_clickable(driver, locator, timeout=DEFAULT_TIMEOUT):
    """Wait until element is clickable and return it"""
    return WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(
        EC.element_to_be_clickable(locator)
    )


def wait_click(driver, locator, timeout=DEFAULT_TIMEOUT):
    """Wait for element to be clickable, then click it"""
    element = wait_clickable(driver, locator, timeout)
    element.click()
    return element


def wait_visible(driver, locator, timeout=DEFAULT_TIMEOUT):
    """Wait until element is visible and return it"""
    return WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(
        EC.visibility_of_element_located(locator)
    )


def wait_present(driver, locator, timeout=DEFAULT_TIMEOUT):
    """Wait until element is present in DOM (may not be visible)"""
    return WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(
        EC.presence_of_element_located(locator)
    )


def wait_gone(driver, locator, timeout=DEFAULT_TIMEOUT):
    """Wait until element is no longer visible"""
    try:
        WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(
            EC.invisibility_of_element_located(locator)
        )
        return True
    except TimeoutException:
        return False


def wait_not_present(driver, locator, timeout=DEFAULT_TIMEOUT):
    """Wait until element is completely removed from DOM"""
    def element_not_in_dom(driver):
        from selenium.webdriver.common.by import By
        elements = driver.find_elements(*locator)
        return len(elements) == 0
    
    WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(element_not_in_dom)
    return True


def wait_text_present(driver, locator, text, timeout=DEFAULT_TIMEOUT):
    """Wait until element contains specific text"""
    return WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(
        EC.text_to_be_present_in_element(locator, text)
    )


def wait_value_equals(driver, locator, expected_value, timeout=DEFAULT_TIMEOUT):
    """Wait until input element has specific value"""
    def value_matches(driver):
        try:
            element = driver.find_element(*locator)
            return element.get_attribute('value') == str(expected_value)
        except StaleElementReferenceException:
            return False
    
    WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(value_matches)
    return True


def wait_attribute_equals(driver, locator, attribute, expected_value, timeout=DEFAULT_TIMEOUT):
    """Wait until element attribute has specific value"""
    def attribute_matches(driver):
        try:
            element = driver.find_element(*locator)
            return element.get_attribute(attribute) == expected_value
        except StaleElementReferenceException:
            return False
    
    WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(attribute_matches)
    return True


def try_until(driver, condition_fn, timeout=DEFAULT_TIMEOUT, poll=POLL_FREQUENCY):
    """
    Retry a function until it succeeds or timeout.
    
    Args:
        driver: WebDriver instance
        condition_fn: Function that takes no args and returns truthy on success
        timeout: Maximum seconds to wait
        poll: Seconds between attempts
    
    Returns:
        Result of condition_fn
    
    Raises:
        Last exception if timeout reached
    """
    end_time = time.time() + timeout
    last_error = None
    
    while time.time() < end_time:
        try:
            result = condition_fn()
            if result or result is None:  # Allow None to count as success
                return result
        except Exception as e:
            last_error = e
        time.sleep(poll)
    
    if last_error:
        raise last_error
    raise TimeoutException(f"Condition not met within {timeout}s")


def wait_stable(driver, locator, stable_duration=1.0, check_interval=0.2, timeout=DEFAULT_TIMEOUT):
    """
    Wait until element's value/text remains unchanged for stable_duration.
    Useful for waiting for values to finish updating.
    """
    def is_stable():
        element = driver.find_element(*locator)
        last_value = element.get_attribute('value') or element.text
        stable_start = time.time()
        
        while time.time() - stable_start < stable_duration:
            time.sleep(check_interval)
            current_value = element.get_attribute('value') or element.text
            if current_value != last_value:
                return False
            last_value = current_value
        
        return True
    
    return try_until(driver, is_stable, timeout)


def wait_count(driver, locator, expected_count, timeout=DEFAULT_TIMEOUT):
    """Wait until specific number of elements match locator"""
    def count_matches(driver):
        elements = driver.find_elements(*locator)
        return len(elements) == expected_count
    
    WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(count_matches)
    return True


def wait_count_changes(driver, locator, initial_count, timeout=DEFAULT_TIMEOUT):
    """Wait until number of elements changes from initial_count"""
    def count_changed(driver):
        elements = driver.find_elements(*locator)
        return len(elements) != initial_count
    
    WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(count_changed)
    return True


def safe_click(driver, element, max_attempts=3):
    """
    Click element with retry on stale reference.
    Returns True on success, False on failure.
    """
    for attempt in range(max_attempts):
        try:
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.1)
            
            # Try regular click
            try:
                element.click()
                return True
            except:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", element)
                return True
        except StaleElementReferenceException:
            if attempt == max_attempts - 1:
                return False
            time.sleep(0.2)
        except Exception as e:
            if attempt == max_attempts - 1:
                return False
            time.sleep(0.2)
    
    return False


def wait_ajax_complete(driver, timeout=DEFAULT_TIMEOUT):
    """
    Wait for jQuery AJAX calls to complete (if jQuery is present).
    Falls back to simple time check if jQuery not available.
    """
    def ajax_done():
        try:
            return driver.execute_script("return jQuery.active == 0")
        except:
            return True  # jQuery not present, assume done
    
    try:
        WebDriverWait(driver, timeout, poll_frequency=POLL_FREQUENCY).until(lambda d: ajax_done())
        return True
    except TimeoutException:
        return False


def find_any(driver, locators, timeout=DEFAULT_TIMEOUT):
    """
    Try multiple locators in order, return first matching element.
    
    Args:
        driver: WebDriver instance
        locators: List of (By, selector) tuples
        timeout: Max time to wait for ANY locator to match
    
    Returns:
        Element if found, None if all fail
    """
    end_time = time.time() + timeout
    
    while time.time() < end_time:
        for locator in locators:
            try:
                element = driver.find_element(*locator)
                if element and element.is_displayed():
                    return element
            except:
                continue
        time.sleep(POLL_FREQUENCY)
    
    return None


def find_any_wait(driver, locators, timeout=DEFAULT_TIMEOUT):
    """
    Try multiple locators with proper wait, return first that becomes present.
    More robust than find_any for elements that may load slowly.
    """
    for locator in locators:
        try:
            return wait_present(driver, locator, timeout=timeout/len(locators))
        except TimeoutException:
            continue
    
    raise TimeoutException(f"None of {len(locators)} locators matched within {timeout}s")
