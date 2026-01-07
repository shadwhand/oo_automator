import pytest
from oo_automator.parameters import discover_parameters, get_parameter, PARAMETERS


def test_discover_finds_delta():
    params = discover_parameters()
    assert "delta" in params
    assert params["delta"].name == "delta"


def test_parameters_global_populated():
    assert "delta" in PARAMETERS


def test_get_parameter_by_name():
    param = get_parameter("delta")
    assert param is not None
    assert param.name == "delta"


def test_get_parameter_unknown():
    param = get_parameter("nonexistent")
    assert param is None


def test_all_parameters_have_required_attributes():
    for name, param_class in PARAMETERS.items():
        param = param_class()
        assert hasattr(param, "name")
        assert hasattr(param, "display_name")
        assert hasattr(param, "description")
        assert hasattr(param, "selectors")
        assert callable(getattr(param, "configure"))
        assert callable(getattr(param, "generate_values"))
