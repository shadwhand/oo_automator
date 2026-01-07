import pytest
from oo_automator.browser.actions import (
    parse_currency,
    parse_percentage,
    parse_result_value,
    ResultParser,
)


def test_parse_currency_positive():
    assert parse_currency("$13,376") == 13376.0
    assert parse_currency("$250,000") == 250000.0


def test_parse_currency_negative():
    assert parse_currency("-$155") == -155.0


def test_parse_percentage():
    assert parse_percentage("68.2%") == 68.2
    assert parse_percentage("-1%") == -1.0
    assert parse_percentage("0.9%") == 0.9


def test_parse_result_value_with_lot():
    assert parse_result_value("$21 / lot") == 21.0
    assert parse_result_value("-$155 / lot") == -155.0


def test_parse_result_value_plain():
    assert parse_result_value("652") == 652.0
    assert parse_result_value("154.1") == 154.1


def test_result_parser_all_metrics():
    raw_data = {
        "pl": "$13,376",
        "cagr": "0.9%",
        "max_drawdown": "-1%",
        "mar": "1",
        "win_percentage": "61.7%",
        "total_premium": "$86,720",
        "capture_rate": "15.4%",
        "starting_capital": "$250,000",
        "ending_capital": "$263,376",
        "total_trades": "652",
        "winners": "402",
        "avg_per_trade": "$21 / lot",
        "avg_winner": "$130 / lot",
        "avg_loser": "-$155 / lot",
        "max_winner": "$217 / lot",
        "max_loser": "-$377 / lot",
        "avg_minutes_in_trade": "154.1",
    }

    parsed = ResultParser.parse_all(raw_data)

    assert parsed["pl"] == 13376.0
    assert parsed["cagr"] == 0.9
    assert parsed["max_drawdown"] == -1.0
    assert parsed["total_trades"] == 652
    assert parsed["avg_loser"] == -155.0
