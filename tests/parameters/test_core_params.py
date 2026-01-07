import pytest
from oo_automator.parameters import get_parameter, PARAMETERS


def test_profit_target_exists():
    # Force rediscovery
    from oo_automator.parameters import discover_parameters
    params = discover_parameters()
    assert "profit_target" in params
    param = get_parameter("profit_target")
    assert param.display_name == "Profit Target"


def test_profit_target_generate_values():
    param = get_parameter("profit_target")
    values = param.generate_values({"start": 10, "end": 50, "step": 10})
    assert values == [10, 20, 30, 40, 50]


def test_stop_loss_exists():
    from oo_automator.parameters import discover_parameters
    params = discover_parameters()
    assert "stop_loss" in params
    param = get_parameter("stop_loss")
    assert param.display_name == "Stop Loss"


def test_stop_loss_generate_values():
    param = get_parameter("stop_loss")
    values = param.generate_values({"start": 50, "end": 200, "step": 50})
    assert values == [50, 100, 150, 200]


def test_entry_time_exists():
    from oo_automator.parameters import discover_parameters
    params = discover_parameters()
    assert "entry_time" in params
    param = get_parameter("entry_time")
    assert param.display_name == "Entry Time"


def test_entry_time_generate_values():
    param = get_parameter("entry_time")
    values = param.generate_values({
        "start_hour": 9,
        "start_minute": 30,
        "end_hour": 10,
        "end_minute": 30,
        "interval_minutes": 30
    })
    assert "09:30" in values
    assert "10:00" in values
    assert "10:30" in values
