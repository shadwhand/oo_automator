import pytest
from oo_automator.parameters.delta import DeltaParameter


def test_delta_parameter_metadata():
    param = DeltaParameter()
    assert param.name == "delta"
    assert param.display_name == "Position Delta"
    assert "leg_container" in param.selectors or len(param.selectors) > 0


def test_delta_configure():
    param = DeltaParameter()
    config = param.configure()

    field_names = [f.name for f in config.fields]
    assert "start" in field_names
    assert "end" in field_names
    assert "step" in field_names
    assert "num_legs" in field_names
    assert "leg_to_sweep" in field_names
    assert "delta_type" in field_names


def test_delta_generate_values_range():
    param = DeltaParameter()
    values = param.generate_values({"start": 5, "end": 15, "step": 5})

    assert values == [5, 10, 15]


def test_delta_generate_values_single():
    param = DeltaParameter()
    values = param.generate_values({"start": 10, "end": 10, "step": 1})

    assert values == [10]


def test_delta_generate_values_default_step():
    param = DeltaParameter()
    config = param.configure()
    defaults = config.get_defaults()
    # Default step is 10, so from 5 to 15 we get [5, 15]
    values = param.generate_values({**defaults, "start": 5, "end": 25})

    assert values == [5, 15, 25]
