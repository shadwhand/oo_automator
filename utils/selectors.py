"""
Centralized selector definitions with fallback strategies.
Each critical element has 2-3 fallback selectors to handle UI changes.
"""

from selenium.webdriver.common.by import By

# ============================================================================
# MAIN NAVIGATION & STRUCTURE
# ============================================================================

NEW_BACKTEST_BTN = [
    (By.CSS_SELECTOR, "div.mt-4 > button"),
    (By.XPATH, "//button[contains(., 'New Backtest')]"),
    (By.XPATH, "//button[contains(text(), 'New Backtest')]"),
]

LOGIN_EMAIL = [
    (By.CSS_SELECTOR, "input[type='email']"),
    (By.CSS_SELECTOR, "input[type='text'][name*='email']"),
    (By.CSS_SELECTOR, "input[type='text'][name*='user']"),
]

LOGIN_PASSWORD = [
    (By.CSS_SELECTOR, "input[type='password']"),
]

LOGIN_SUBMIT = [
    (By.CSS_SELECTOR, "button[type='submit']"),
    (By.CSS_SELECTOR, "input[type='submit']"),
]

# ============================================================================
# DIALOG/MODAL ELEMENTS
# ============================================================================

MODAL_DIALOG = [
    (By.CSS_SELECTOR, "[role='dialog']"),
    (By.CSS_SELECTOR, "[id^='headlessui-dialog']"),
    (By.XPATH, "//div[@role='dialog']"),
]

MODAL_OVERLAY = [
    (By.CSS_SELECTOR, "div[id*='dialog-overlay']"),
    (By.CSS_SELECTOR, "div[class*='fixed inset-0']"),
]

MODAL_CLOSE_BTN = [
    (By.CSS_SELECTOR, "button[aria-label*='close' i]"),
    (By.CSS_SELECTOR, "button[class*='close']"),
    (By.XPATH, "//button[contains(@aria-label, 'Close')]"),
]

# FIXED: Run button selectors based on Puppeteer inspection
# The actual clickable element is the span inside div.flex-shrink-0
RUN_BTN = [
    # Primary: Target the span inside the button (what Puppeteer clicks)
    (By.CSS_SELECTOR, "[role='dialog'] button[type='submit'] span"),
    (By.CSS_SELECTOR, "div.flex-shrink-0 span"),
    (By.XPATH, "//div[@role='dialog']//button[contains(., 'Run')]//span"),
    # Fallback: Button element itself
    (By.XPATH, "//div[@role='dialog']//button[contains(., 'Run')]"),
    (By.CSS_SELECTOR, "[role='dialog'] button[type='submit']"),
    (By.XPATH, "//button[contains(text(), 'Run')]"),
]

# ============================================================================
# BACKTEST PROGRESS INDICATORS
# ============================================================================

PROGRESS_ANY = [
    (By.XPATH, "//div[contains(text(), 'Running Backtest')]"),
    (By.XPATH, "//div[contains(text(), 'ETA:')]"),
    (By.XPATH, "//div[contains(text(), 'Processing trades')]"),
    (By.CSS_SELECTOR, "svg[class*='animate-spin']"),
    (By.CSS_SELECTOR, "[role='progressbar']"),
    (By.CSS_SELECTOR, "div[role='status'][aria-live='polite']"),
]

PROGRESS_COMPLETE_INDICATORS = [
    (By.XPATH, "//div[contains(text(), 'Complete')]"),
    (By.XPATH, "//div[contains(text(), 'Done')]"),
]

# ============================================================================
# RESULTS ELEMENTS
# ============================================================================

RESULT_CAGR = [
    (By.XPATH, "//dt[contains(text(), 'CAGR')]/..//dd"),
    (By.XPATH, "//*[text()='CAGR']/following::dd[1]"),
]

RESULT_MAX_DRAWDOWN = [
    (By.XPATH, "//dt[contains(text(), 'Max Drawdown')]/..//dd"),
    (By.XPATH, "//*[text()='Max Drawdown']/following::dd[1]"),
]

RESULT_WIN_PERCENTAGE = [
    (By.XPATH, "//dt[contains(text(), 'Win Percentage')]/..//dd"),
    (By.XPATH, "//*[text()='Win Percentage']/following::dd[1]"),
]

RESULT_CAPTURE_RATE = [
    (By.XPATH, "//dt[contains(text(), 'Capture Rate')]/..//dd"),
    (By.XPATH, "//*[text()='Capture Rate']/following::dd[1]"),
]

RESULTS_TABLE = [
    (By.CSS_SELECTOR, "table"),
    (By.XPATH, "//table"),
]

# ============================================================================
# TRADE LOG ELEMENTS
# ============================================================================

TRADE_LOG_TAB = [
    (By.XPATH, "//a[contains(., 'Trade Log')]"),
    (By.XPATH, "//nav//a[contains(text(), 'Trade Log')]"),
    (By.CSS_SELECTOR, "a[href*='trade']"),
]

# FIXED: Download button - MUST be in content area (div[2]), NOT header (div[1])
# The Discord link is in div[1] (header), download button is in div[2] (content)
# Previous selectors were too generic and matched the Discord icon first
TRADE_LOG_DOWNLOAD_BTN = [
    # Most specific - from Puppeteer recording, explicitly in content area (div[2])
    (By.XPATH, "//*[@id='app']/div/div[2]/div[2]/div[2]/div/div[7]/svg"),
    (By.XPATH, "//*[@id='app']/div/div[2]/div[2]/div[2]/div/div[7]/svg/path[1]"),
    
    # CSS with explicit content area prefix (div:nth-of-type(2) = content, not header)
    (By.CSS_SELECTOR, "#app > div > div:nth-of-type(2) div.mx-auto div.hidden svg"),
    (By.CSS_SELECTOR, "#app > div > div:nth-of-type(2) div.hidden svg"),
    
    # Alternative: mx-auto class is only in content area, not header
    (By.CSS_SELECTOR, "div.mx-auto div.hidden svg"),
    
    # Look for download-related attributes but ONLY in content area (div[2])
    (By.XPATH, "//*[@id='app']/div/div[2]//*[contains(@title, 'Download') or contains(@aria-label, 'Download')]"),
    (By.XPATH, "//*[@id='app']/div/div[2]//*[contains(@title, 'download') or contains(@aria-label, 'download')]"),
    
    # Fallback: SVG in the trade log section specifically
    (By.XPATH, "//div[contains(@class, 'mx-auto')]//div[7]//svg"),
]

# ============================================================================
# PARAMETER FIELD TIME INPUTS
# ============================================================================

ENTRY_TIME_INPUT = [
    (By.CSS_SELECTOR, "input[type='time']"),
]

# ============================================================================
# TOGGLE SWITCHES
# ============================================================================

# LEG GROUPS TOGGLE
LEG_GROUPS_TOGGLE = [
    (By.XPATH, "//button[@role='switch' and @aria-label='Use Leg Groups']"),
    (By.XPATH, "//label[text()='Use Leg Groups']/..//button[@role='switch']"),
    (By.XPATH, "//label[text()='Use Leg Groups']/following-sibling::button[@role='switch']"),
]

# EARLY EXIT TOGGLE
EARLY_EXIT_TOGGLE = [
    (By.XPATH, "//button[@role='switch' and @aria-label='Use Early Exit']"),
    (By.XPATH, "//label[text()='Use Early Exit']/..//button[@role='switch']"),
    (By.XPATH, "//label[text()='Use Early Exit']/following-sibling::button[@role='switch']"),
]

# ENTRY S/L RATIO TOGGLE
ENTRY_SL_RATIO_TOGGLE = [
    (By.XPATH, "//button[@role='switch' and @aria-label='Use Entry Short/Long Ratio']"),
    (By.XPATH, "//label[text()='Use Entry Short/Long Ratio']/..//button[@role='switch']"),
    (By.XPATH, "//label[text()='Use Entry Short/Long Ratio']/following-sibling::button[@role='switch']"),
]

# UNDERLYING MOVEMENT TOGGLES
UNDERLYING_MOVEMENT_TOGGLE = [
    (By.XPATH, "//button[@role='switch' and contains(., 'Use Underlying Price Movement')]"),
    (By.XPATH, "//label[contains(text(), 'Use Underlying Price Movement')]/..//button[@role='switch']"),
    (By.XPATH, "//button[@role='switch'][@aria-label='Use Underlying Price Movement']"),
]

UNDERLYING_MOVEMENT_SHORT_PUT_TOGGLE = [
    (By.XPATH, "//button[@role='switch' and contains(., 'Exit When OTM Short Put')]"),
    (By.XPATH, "//label[contains(text(), 'Exit When OTM Short Put')]/..//button[@role='switch']"),
]

UNDERLYING_MOVEMENT_SHORT_CALL_TOGGLE = [
    (By.XPATH, "//button[@role='switch' and contains(., 'Exit When OTM Short Call')]"),
    (By.XPATH, "//label[contains(text(), 'Exit When OTM Short Call')]/..//button[@role='switch']"),
]

# ============================================================================
# PARAMETER FIELDS - RSI
# ============================================================================

RSI_MIN = [
    (By.CSS_SELECTOR, "div:nth-of-type(2) > div > div:nth-of-type(4) div.pr-3 input"),
    (By.XPATH, "//*[@id='headlessui-dialog-138']/div/div[2]/div/form/div[1]/div[2]/div/div[4]/div/div[2]/div[6]/div[1]/div/div/input"),
    (By.CSS_SELECTOR, "div:nth-of-type(4) div.pr-3 input"),
]

RSI_MAX = [
    (By.CSS_SELECTOR, "div:nth-of-type(4) div:nth-of-type(6) > div:nth-of-type(2) input"),
    (By.XPATH, "//*[@id='headlessui-dialog-138']/div/div[2]/div/form/div[1]/div[2]/div/div[4]/div/div[2]/div[6]/div[2]/div/div/input"),
    (By.CSS_SELECTOR, "div:nth-of-type(6) > div:nth-of-type(2) input"),
]

# ============================================================================
# PARAMETER FIELDS - DELTA
# ============================================================================

DELTA_PUT = [
    (By.CSS_SELECTOR, "div:nth-of-type(9) > div:nth-of-type(3) input"),
    (By.XPATH, "//div[9]/div[3]/div/div/input"),
    (By.XPATH, "//*[@id='headlessui-dialog-26']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[9]/div[3]/div/div/input"),
]

DELTA_CALL = [
    (By.CSS_SELECTOR, "div:nth-of-type(10) > div:nth-of-type(2) input"),
    (By.XPATH, "//div[10]/div[2]/div/div/input"),
    (By.XPATH, "//*[@id='headlessui-dialog-26']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[10]/div[2]/div/div/input"),
]

# ============================================================================
# PARAMETER FIELDS - PROFIT TARGET
# ============================================================================

PROFIT_TARGET_CALL = [
    (By.CSS_SELECTOR, "div:nth-of-type(6) > div:nth-of-type(1) div.pr-3 input"),
    (By.XPATH, "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[1]/div/div[2]/div[1]/div[1]/div/div/input"),
    (By.CSS_SELECTOR, "div:nth-of-type(6) div.pr-3 input"),
]

PROFIT_TARGET_PUT = [
    (By.CSS_SELECTOR, "div:nth-of-type(7) > div:nth-of-type(1) div.pr-3 input"),
    (By.XPATH, "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[1]/div/div[2]/div[1]/div[1]/div/div/input"),
    (By.CSS_SELECTOR, "div:nth-of-type(7) div.pr-3 input"),
]

PROFIT_TARGET_MAIN = [
    (By.CSS_SELECTOR, "div.pr-3 input"),
    (By.XPATH, "//div[contains(@class, 'pr-3')]//input"),
]

# ============================================================================
# PARAMETER FIELDS - STOP LOSS
# ============================================================================

STOP_LOSS_CALL = [
    (By.CSS_SELECTOR, "div:nth-of-type(6) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input"),
    (By.XPATH, "//*[@id='headlessui-dialog-21']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[1]/div/div[2]/div[1]/div[2]/div/div/input"),
    (By.CSS_SELECTOR, "div:nth-of-type(6) div.pt-6 input"),
]

STOP_LOSS_PUT = [
    (By.CSS_SELECTOR, "div:nth-of-type(7) div.pt-6 > div:nth-of-type(1) > div:nth-of-type(2) input"),
    (By.XPATH, "//*[@id='headlessui-dialog-21']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[1]/div/div[2]/div[1]/div[2]/div/div/input"),
    (By.CSS_SELECTOR, "div:nth-of-type(7) div.pt-6 input"),
]

STOP_LOSS_MAIN = [
    (By.CSS_SELECTOR, "div.pt-6 input"),
    (By.XPATH, "//div[contains(@class, 'pt-6')]//input"),
]

# ============================================================================
# PARAMETER FIELDS - EXIT TIME
# ============================================================================

EXIT_TIME_CALL = [
    (By.CSS_SELECTOR, "div:nth-of-type(6) div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input"),
    (By.XPATH, "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[2]/div[2]/div/input"),
]

EXIT_TIME_PUT = [
    (By.CSS_SELECTOR, "div:nth-of-type(7) div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input"),
    (By.XPATH, "//*[@id='headlessui-dialog-13']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div[2]/div/div[2]/div[2]/div[2]/div/input"),
]

EXIT_TIME_MAIN = [
    (By.CSS_SELECTOR, "div.pt-6 > div:nth-of-type(2) > div:nth-of-type(2) input"),
    (By.XPATH, "//div[contains(@class, 'pt-6')]//div[2]//div[2]//input"),
    (By.CSS_SELECTOR, "input[type='time']:nth-of-type(2)"),
]

# ============================================================================
# PARAMETER FIELDS - SHORT/LONG RATIO
# ============================================================================

SHORT_LONG_RATIO = [
    (By.CSS_SELECTOR, "div.flex-1 > div:nth-of-type(2) > div > div:nth-of-type(6) div.toggleDescription input"),
    (By.XPATH, "//*[@id='headlessui-dialog-370']/div/div[2]/div/form/div[1]/div[2]/div/div[6]/div[2]/div/div[2]/div[12]/div/input"),
    (By.CSS_SELECTOR, "div.toggleDescription input"),
    (By.XPATH, "//div[contains(@class, 'toggleDescription')]//input"),
]

# ============================================================================
# PARAMETER FIELDS - ENTRY S/L RATIO MINIMUM
# ============================================================================

ENTRY_SL_RATIO_MIN = [
    (By.CSS_SELECTOR, "div:nth-of-type(7) div:nth-of-type(9) > div.pr-3 input"),
    (By.XPATH, "//div[7]//div[9]/div[1]/div/div/input"),
    (By.XPATH, "//*[@id='headlessui-dialog-109']/div/div[2]/div/form/div[1]/div[2]/div/div[7]/div/div[2]/div[9]/div[1]/div/div/input"),
    (By.CSS_SELECTOR, "div:nth-of-type(9) > div.pr-3 input"),
]

# ============================================================================
# PARAMETER FIELDS - UNDERLYING MOVEMENT
# ============================================================================

UNDERLYING_MOVEMENT_SHORT_PUT = [
    (By.XPATH, "//label[contains(text(), 'Exit When OTM Short Put')]/..//input"),
    (By.XPATH, "//button[contains(., 'Exit When OTM Short Put')]/..//input"),
    (By.CSS_SELECTOR, "div:nth-of-type(2) > div > div.pt-6 > div:nth-of-type(6) input"),
]

UNDERLYING_MOVEMENT_SHORT_CALL = [
    (By.XPATH, "//label[contains(text(), 'Exit When OTM Short Call')]/..//input"),
    (By.XPATH, "//button[contains(., 'Exit When OTM Short Call')]/..//input"),
    (By.CSS_SELECTOR, "div:nth-of-type(6) div:nth-of-type(7) input"),
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_metric_selector(metric_name):
    """
    Get selector for a specific metric by name.
    Returns list of fallback selectors.
    """
    metric_map = {
        'CAGR': RESULT_CAGR,
        'Max Drawdown': RESULT_MAX_DRAWDOWN,
        'Win Percentage': RESULT_WIN_PERCENTAGE,
        'Capture Rate': RESULT_CAPTURE_RATE,
    }
    return metric_map.get(metric_name, [])


def exclude_dte_filters():
    """
    Returns XPath predicates to exclude DTE-related elements.
    Use when searching for toggles to avoid false matches.
    """
    return [
        "not(contains(translate(@aria-label, 'DTE', 'dte'), 'dte'))",
        "not(contains(translate(text(), 'DTE', 'dte'), 'dte'))",
        "not(contains(translate(@aria-label, 'EXACT', 'exact'), 'exact'))",
        "not(contains(translate(text(), 'EXACT', 'exact'), 'exact'))",
    ]


def build_toggle_xpath(label_text, exclude_dte=True):
    """
    Build XPath for toggle switch with optional DTE exclusion.
    
    Args:
        label_text: The toggle label text (e.g., "Use Leg Groups")
        exclude_dte: Whether to exclude DTE-related elements
    
    Returns:
        List of XPath selectors
    """
    base_xpaths = [
        f"//button[@role='switch' and @aria-label='{label_text}']",
        f"//label[text()='{label_text}']/..//button[@role='switch']",
        f"//label[text()='{label_text}']/following-sibling::button[@role='switch']",
    ]
    
    if exclude_dte:
        filters = " and ".join(exclude_dte_filters())
        filtered_xpaths = [
            f"//button[@role='switch' and @aria-label='{label_text}' and {filters}]",
            f"//label[text()='{label_text}' and {filters}]/..//button[@role='switch']",
        ]
        return [(By.XPATH, xpath) for xpath in filtered_xpaths + base_xpaths]
    else:
        return [(By.XPATH, xpath) for xpath in base_xpaths]
