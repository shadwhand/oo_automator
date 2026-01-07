from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from playwright.async_api import Page
import re


@dataclass
class FieldBase:
    """Base class for configuration fields."""
    name: str
    label: str
    description: str = ""
    required: bool = True

    def validate(self, value: Any) -> bool:
        """Validate field value. Override in subclasses."""
        return True


@dataclass
class IntField(FieldBase):
    """Integer input field."""
    default: int = 0
    min_val: int = 0
    max_val: int = 100
    step: int = 1

    def validate(self, value: Any) -> bool:
        try:
            val = int(value)
            return self.min_val <= val <= self.max_val
        except (TypeError, ValueError):
            return False


@dataclass
class FloatField(FieldBase):
    """Float input field."""
    default: float = 0.0
    min_val: float = 0.0
    max_val: float = 100.0
    step: float = 0.1

    def validate(self, value: Any) -> bool:
        try:
            val = float(value)
            return self.min_val <= val <= self.max_val
        except (TypeError, ValueError):
            return False


@dataclass
class ChoiceField(FieldBase):
    """Choice/dropdown field."""
    choices: list[str] = field(default_factory=list)
    default: str = ""

    def validate(self, value: Any) -> bool:
        return value in self.choices


@dataclass
class TimeField(FieldBase):
    """Time input field (HH:MM format)."""
    default: str = "09:30"

    def validate(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, value))


@dataclass
class BoolField(FieldBase):
    """Boolean toggle field."""
    default: bool = False

    def validate(self, value: Any) -> bool:
        return isinstance(value, bool)


@dataclass
class ParameterConfig:
    """Configuration schema for a parameter."""
    fields: list[FieldBase] = field(default_factory=list)

    def get_defaults(self) -> dict:
        """Get default values for all fields."""
        return {f.name: f.default for f in self.fields}

    def validate(self, values: dict) -> tuple[bool, list[str]]:
        """Validate all field values. Returns (is_valid, error_messages)."""
        errors = []
        for f in self.fields:
            if f.name in values:
                if not f.validate(values[f.name]):
                    errors.append(f"Invalid value for {f.label}")
            elif f.required:
                errors.append(f"{f.label} is required")
        return len(errors) == 0, errors


class Parameter(ABC):
    """Base class for all parameters."""

    name: str  # Internal identifier
    display_name: str  # Human-readable name
    description: str  # Help text
    selectors: dict  # UI element selectors

    # Optional: Toggle that must be enabled before this parameter is visible
    requires_toggle: Optional[str] = None
    toggle_selector: Optional[str] = None

    def __init__(self):
        self._config: Optional[dict] = None

    @property
    def config(self) -> dict:
        """Get current configuration."""
        return self._config or {}

    def set_config(self, config: dict) -> None:
        """Set configuration for this parameter."""
        self._config = config

    @abstractmethod
    def configure(self) -> ParameterConfig:
        """Return config schema for CLI/dashboard UI."""
        pass

    @abstractmethod
    def generate_values(self, config: dict) -> list:
        """Generate the list of values to test."""
        pass

    @abstractmethod
    async def set_value(self, page: Page, value: Any) -> bool:
        """Set the parameter value in the UI."""
        pass

    @abstractmethod
    async def verify_value(self, page: Page, value: Any) -> bool:
        """Verify the value was set correctly."""
        pass

    async def ensure_visible(self, page: Page) -> bool:
        """Enable parent toggle if this parameter requires it."""
        if not self.requires_toggle or not self.toggle_selector:
            return True

        toggle = page.locator(self.toggle_selector)
        try:
            is_checked = await toggle.get_attribute("aria-checked")
            if is_checked != "true":
                await toggle.click()
                await page.wait_for_timeout(300)
        except Exception:
            return False
        return True

    async def _fill_input(self, page: Page, selector: str, value: Any) -> bool:
        """Helper to fill an input field with retry logic."""
        try:
            locator = page.locator(selector)
            await locator.wait_for(state="visible", timeout=5000)
            await locator.clear()
            await locator.fill(str(value))
            return True
        except Exception:
            return False

    async def _get_input_value(self, page: Page, selector: str) -> Optional[str]:
        """Helper to get current input value."""
        try:
            locator = page.locator(selector)
            return await locator.input_value()
        except Exception:
            return None
