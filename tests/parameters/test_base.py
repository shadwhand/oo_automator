import pytest
from dataclasses import dataclass
from oo_automator.parameters.base import (
    Parameter,
    ParameterConfig,
    IntField,
    FloatField,
    ChoiceField,
    TimeField,
)


class MockParameter(Parameter):
    name = "mock"
    display_name = "Mock Parameter"
    description = "A mock parameter for testing"
    selectors = {"input": "input#mock"}

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField("start", label="Start", default=0, min_val=0, max_val=100),
                IntField("end", label="End", default=10, min_val=0, max_val=100),
            ]
        )

    def generate_values(self, config: dict) -> list:
        return list(range(config["start"], config["end"] + 1))

    async def set_value(self, page, value) -> bool:
        return True

    async def verify_value(self, page, value) -> bool:
        return True


def test_parameter_config_fields():
    param = MockParameter()
    config = param.configure()

    assert len(config.fields) == 2
    assert config.fields[0].name == "start"
    assert config.fields[1].name == "end"


def test_parameter_generate_values():
    param = MockParameter()
    values = param.generate_values({"start": 5, "end": 10})

    assert values == [5, 6, 7, 8, 9, 10]


def test_int_field():
    field = IntField("delta", label="Delta", default=15, min_val=1, max_val=100)
    assert field.name == "delta"
    assert field.default == 15
    assert field.validate(50) is True
    assert field.validate(0) is False
    assert field.validate(101) is False


def test_float_field():
    field = FloatField("ratio", label="Ratio", default=0.5, min_val=0.0, max_val=1.0)
    assert field.validate(0.5) is True
    assert field.validate(-0.1) is False


def test_choice_field():
    field = ChoiceField(
        "apply_to",
        label="Apply To",
        choices=["both", "put_only", "call_only"],
        default="both"
    )
    assert field.validate("both") is True
    assert field.validate("invalid") is False


def test_time_field():
    field = TimeField("entry_time", label="Entry Time", default="09:30")
    assert field.validate("09:30") is True
    assert field.validate("25:00") is False
