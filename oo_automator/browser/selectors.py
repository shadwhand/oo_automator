"""UI selectors for OptionOmega automation.

Selectors are derived from recordings/selectors_expanded.json.
Update this file when OptionOmega UI changes.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Selectors:
    """Static selectors for OptionOmega UI elements."""

    # Login
    LOGIN_EMAIL = "input[type='email'], form div:nth-of-type(1) > input"
    LOGIN_PASSWORD = "input[type='password']"
    LOGIN_SUBMIT = "form button[type='submit'], button:has-text('Sign in')"
    SIGN_IN_BUTTON = "span.btn-primary, text=Sign in"

    # Navigation
    TEST_ROW = "table tbody tr td a"

    # New Backtest Modal
    NEW_BACKTEST_BUTTON = "button:has-text('New Backtest')"
    MODAL_DIALOG = "[id^='headlessui-dialog'], [role='dialog']"
    RUN_BUTTON = "button:has-text('Run')"

    # Date Presets
    DATE_START = "label:has-text('Start Date') ~ input.input"
    DATE_END = "label:has-text('End Date') ~ div input.input"

    # Strategy
    TICKER = "label:has-text('Ticker') ~ div button.selectInput"
    COMMON_STRATEGIES = "label:has-text('Common Strategies') ~ div button.selectInput"

    # Funds
    STARTING_FUNDS = "label:has-text('Starting Funds') ~ div input"
    MARGIN_ALLOCATION = "label:has-text('Margin Allocation % Per Trade') ~ div input"
    MAX_CONTRACTS = "label:has-text('Max Contracts Per Trade') ~ div input"

    # Entry Conditions
    ENTRY_TIME = "label:has-text('Entry Time') ~ div input[type='time']"
    FREQUENCY = "label:has-text('Frequency') ~ div button.selectInput"

    # Profit & Loss
    PROFIT_TARGET = "h3:has-text('Profit & Loss') ~ div label:has-text('Profit Target') ~ div input"
    STOP_LOSS = "h3:has-text('Profit & Loss') ~ div label:has-text('Stop Loss') ~ div input"

    # Misc
    OPENING_COMMISSIONS = "label:has-text('Per Contract Opening Commissions') ~ div input"
    CLOSING_COMMISSIONS = "label:has-text('Per Contract Closing Commissions') ~ div input"
    ENTRY_SLIPPAGE = "label:has-text('Entry Slippage') ~ div input"
    EXIT_SLIPPAGE = "label:has-text('Exit Slippage') ~ div input"


# Result page selectors
RESULT_SELECTORS = {
    "pl": "dt:has-text('P/L') ~ dd",
    "cagr": "dt:has-text('CAGR') ~ dd",
    "max_drawdown": "dt:has-text('Max Drawdown') ~ dd",
    "mar": "dt:has-text('MAR Ratio') ~ dd",
    "win_percentage": "dt:has-text('Win Percentage') ~ dd",
    "total_premium": "dt:has-text('Total Premium') ~ dd",
    "capture_rate": "dt:has-text('Capture Rate') ~ dd",
    "starting_capital": "dt:has-text('Starting Capital') ~ dd",
    "ending_capital": "dt:has-text('Ending Capital') ~ dd",
    "total_trades": "div:has(dt:text-is('Trades')) dd",
    "winners": "dt:has-text('Winners') ~ dd",
    "avg_per_trade": "dt:has-text('Avg Per Trade') ~ dd",
    "avg_winner": "dt:has-text('Avg Winner') ~ dd",
    "avg_loser": "dt:has-text('Avg Loser') ~ dd",
    "max_winner": "dt:has-text('Max Winner') ~ dd",
    "max_loser": "dt:has-text('Max Loser') ~ dd",
    "avg_minutes_in_trade": "dt:has-text('Avg Minutes In Trade') ~ dd",
}

# Toggle selectors for conditional fields
TOGGLE_SELECTORS = {
    "use_vix": "h3:has-text('Entry Conditions') ~ div span:has-text('Use VIX')",
    "use_technical_indicators": "h3:has-text('Entry Conditions') ~ div span:has-text('Use Technical Indicators')",
    "use_gaps": "span:has-text('Use Gaps')",
    "use_intraday_movement": "span:has-text('Use Intraday Movement')",
    "use_early_exit": "span:has-text('Use Early Exit')",
    "use_commissions": "span:has-text('Use Commissions & Fees')",
    "use_slippage": "span:has-text('Use Slippage')",
}


def get_selector(name: str) -> Optional[str]:
    """Get a selector by name."""
    attr = name.upper()
    if hasattr(Selectors, attr):
        return getattr(Selectors, attr)

    if name in RESULT_SELECTORS:
        return RESULT_SELECTORS[name]

    if name in TOGGLE_SELECTORS:
        return TOGGLE_SELECTORS[name]

    return None


def get_result_selectors() -> dict[str, str]:
    """Get all result page selectors."""
    return RESULT_SELECTORS.copy()


def get_toggle_selectors() -> dict[str, str]:
    """Get all toggle selectors."""
    return TOGGLE_SELECTORS.copy()
