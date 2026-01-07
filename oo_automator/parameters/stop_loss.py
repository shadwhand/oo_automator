from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField, ChoiceField


class StopLossParameter(Parameter):
    """Stop loss percentage parameter."""

    name = "stop_loss"
    display_name = "Stop Loss"
    description = "Stop loss percentage for limiting losses"

    selectors = {
        "input": "h3:has-text('Profit & Loss') ~ div label:has-text('Stop Loss') ~ div input",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField("start", label="Start %", default=50, min_val=1, max_val=1000),
                IntField("end", label="End %", default=200, min_val=1, max_val=1000),
                IntField("step", label="Step", default=25, min_val=1, max_val=100),
                ChoiceField("unit", label="Unit", choices=["%", "$"], default="%"),
            ]
        )

    def generate_values(self, config: dict) -> list:
        start = config.get("start", 50)
        end = config.get("end", 200)
        step = config.get("step", 25)
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
