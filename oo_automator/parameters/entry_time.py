from typing import Any
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField


class EntryTimeParameter(Parameter):
    """Entry time parameter for trade entry timing."""

    name = "entry_time"
    display_name = "Entry Time"
    description = "Time of day to enter trades"

    selectors = {
        "input": "label:has-text('Entry Time') ~ div input[type='time']",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField("start_hour", label="Start Hour", default=9, min_val=0, max_val=23),
                IntField("start_minute", label="Start Minute", default=30, min_val=0, max_val=59),
                IntField("end_hour", label="End Hour", default=15, min_val=0, max_val=23),
                IntField("end_minute", label="End Minute", default=0, min_val=0, max_val=59),
                IntField("interval_minutes", label="Interval (minutes)", default=30, min_val=5, max_val=120),
            ]
        )

    def generate_values(self, config: dict) -> list:
        start_hour = config.get("start_hour", 9)
        start_minute = config.get("start_minute", 30)
        end_hour = config.get("end_hour", 15)
        end_minute = config.get("end_minute", 0)
        interval = config.get("interval_minutes", 30)

        values = []
        current_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute

        while current_minutes <= end_minutes:
            hour = current_minutes // 60
            minute = current_minutes % 60
            values.append(f"{hour:02d}:{minute:02d}")
            current_minutes += interval

        return values

    async def set_value(self, page: Page, value: str) -> bool:
        return await self._fill_input(page, self.selectors["input"], value)

    async def verify_value(self, page: Page, value: str) -> bool:
        actual = await self._get_input_value(page, self.selectors["input"])
        return actual == value
