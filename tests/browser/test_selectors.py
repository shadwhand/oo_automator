import pytest
from oo_automator.browser.selectors import (
    Selectors,
    get_selector,
    get_result_selectors,
)


def test_selectors_login():
    assert Selectors.LOGIN_EMAIL is not None
    assert Selectors.LOGIN_PASSWORD is not None
    assert Selectors.LOGIN_SUBMIT is not None


def test_selectors_modal():
    assert Selectors.NEW_BACKTEST_BUTTON is not None
    assert Selectors.MODAL_DIALOG is not None
    assert Selectors.RUN_BUTTON is not None


def test_get_selector_by_name():
    selector = get_selector("login_email")
    assert selector is not None


def test_get_result_selectors():
    results = get_result_selectors()
    assert "pl" in results
    assert "cagr" in results
    assert "max_drawdown" in results
    assert "win_percentage" in results
