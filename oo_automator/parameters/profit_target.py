from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField, ChoiceField


class ProfitTargetParameter(Parameter):
    """Profit target percentage parameter."""

    name = "profit_target"
    display_name = "Profit Target"
    description = "Profit target percentage for closing positions"

    selectors = {
        "input": "h3:has-text('Profit & Loss') ~ div label:has-text('Profit Target') ~ div input",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField("start", label="Start %", default=10, min_val=1, max_val=500),
                IntField("end", label="End %", default=100, min_val=1, max_val=500),
                IntField("step", label="Step", default=10, min_val=1, max_val=100),
                ChoiceField("unit", label="Unit", choices=["%", "$"], default="%"),
            ]
        )

    def generate_values(self, config: dict) -> list:
        start = config.get("start", 10)
        end = config.get("end", 100)
        step = config.get("step", 10)
        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step
        return values

    async def set_value(self, page: Page, value: int) -> bool:
        return await self._fill_input(page, self.selectors["input"], value)

    async def verify_value(self, page: Page, value: int) -> bool:
        actual = await self._get_input_value(page, self.selectors["input"])
        return actual == str(value)
