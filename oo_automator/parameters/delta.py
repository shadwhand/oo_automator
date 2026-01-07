from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField, ChoiceField


class DeltaParameter(Parameter):
    """Delta parameter for options selection."""

    name = "delta"
    display_name = "Delta"
    description = "Options delta value for put/call leg selection"

    selectors = {
        "input": "div.inline-flex:has(button span:text-is('±')) input",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField(
                    "start",
                    label="Start Delta",
                    description="Starting delta value",
                    default=5,
                    min_val=1,
                    max_val=100
                ),
                IntField(
                    "end",
                    label="End Delta",
                    description="Ending delta value",
                    default=50,
                    min_val=1,
                    max_val=100
                ),
                IntField(
                    "step",
                    label="Step",
                    description="Increment between values",
                    default=1,
                    min_val=1,
                    max_val=50
                ),
                ChoiceField(
                    "apply_to",
                    label="Apply To",
                    description="Which legs to apply delta changes",
                    choices=["both", "put_only", "call_only"],
                    default="both"
                ),
            ]
        )

    def generate_values(self, config: dict) -> list:
        """Generate list of delta values to test."""
        start = config.get("start", 5)
        end = config.get("end", 50)
        step = config.get("step", 1)

        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step

        return values

    async def set_value(self, page: Page, value: int) -> bool:
        """Set delta value in the UI."""
        await self.ensure_visible(page)

        apply_to = self.config.get("apply_to", "both")

        # Find delta inputs (legs with ± unit selector)
        delta_inputs = page.locator("div.inline-flex:has(button span:text-is('±')) input")
        count = await delta_inputs.count()

        if count == 0:
            return False

        success = True
        if apply_to in ["both", "put_only"] and count >= 1:
            success = success and await self._fill_input(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=0",
                value
            )

        if apply_to in ["both", "call_only"] and count >= 2:
            success = success and await self._fill_input(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=1",
                value
            )

        return success

    async def verify_value(self, page: Page, value: int) -> bool:
        """Verify delta value was set correctly."""
        apply_to = self.config.get("apply_to", "both")

        delta_inputs = page.locator("div.inline-flex:has(button span:text-is('±')) input")
        count = await delta_inputs.count()

        if apply_to in ["both", "put_only"] and count >= 1:
            actual = await self._get_input_value(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=0"
            )
            if actual != str(value):
                return False

        if apply_to in ["both", "call_only"] and count >= 2:
            actual = await self._get_input_value(
                page,
                "div.inline-flex:has(button span:text-is('±')) input >> nth=1"
            )
            if actual != str(value):
                return False

        return True
