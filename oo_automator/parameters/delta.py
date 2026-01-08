from typing import Any, Optional
from playwright.async_api import Page
from .base import Parameter, ParameterConfig, IntField, ChoiceField, BoolField


class DeltaParameter(Parameter):
    """Delta parameter for options leg selection.

    Delta controls the option selection per leg. Each leg in a strategy can have:
    - Exit below position delta: Trigger when delta goes below threshold
    - Exit above position delta: Trigger when delta goes above threshold

    Range: -100 to 100
    """

    name = "delta"
    display_name = "Position Delta"
    description = "Exit position delta threshold per leg (-100 to 100)"

    selectors = {
        # These are dynamically constructed based on leg number
        "leg_container": "div[class*='leg']",
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField(
                    "num_legs",
                    label="Number of Legs",
                    description="How many legs in your strategy (1-4)",
                    default=2,
                    min_val=1,
                    max_val=4
                ),
                ChoiceField(
                    "leg_to_sweep",
                    label="Leg to Sweep",
                    description="Which leg's delta to sweep (1-based)",
                    choices=["1", "2", "3", "4", "all"],
                    default="1"
                ),
                ChoiceField(
                    "delta_type",
                    label="Delta Type",
                    description="Exit condition type",
                    choices=["below", "above"],
                    default="below"
                ),
                IntField(
                    "start",
                    label="Start Delta",
                    description="Starting delta value",
                    default=-50,
                    min_val=-100,
                    max_val=100
                ),
                IntField(
                    "end",
                    label="End Delta",
                    description="Ending delta value",
                    default=50,
                    min_val=-100,
                    max_val=100
                ),
                IntField(
                    "step",
                    label="Step",
                    description="Increment between values",
                    default=10,
                    min_val=1,
                    max_val=50
                ),
            ]
        )

    def generate_values(self, config: dict) -> list:
        """Generate list of delta values to test."""
        start = config.get("start", -50)
        end = config.get("end", 50)
        step = config.get("step", 10)

        # Handle negative to positive range
        if start > end:
            start, end = end, start

        values = []
        current = start
        while current <= end:
            values.append(current)
            current += step

        return values

    async def _enable_delta_toggle(self, page: Page, leg_index: int, delta_type: str) -> bool:
        """Enable the exit delta toggle for a specific leg.

        Args:
            page: Playwright page
            leg_index: 0-based leg index
            delta_type: 'below' or 'above'
        """
        try:
            # Find all leg containers (they're typically divs with leg content)
            # The structure varies, but toggles for exit conditions are switches

            # Look for toggle switches related to delta exits
            # Pattern: "Exit below position delta" or "Exit above position delta"
            toggle_text = f"Exit {delta_type} position delta"

            # Try to find and enable the toggle
            toggle_selector = f"button[role='switch']:near(:text('{toggle_text}'))"
            toggles = page.locator(toggle_selector)

            count = await toggles.count()
            if count > leg_index:
                toggle = toggles.nth(leg_index)
                is_checked = await toggle.get_attribute("aria-checked")
                if is_checked != "true":
                    await toggle.click()
                    await page.wait_for_timeout(300)
                return True

            # Fallback: try finding by the headlessui pattern
            all_switches = page.locator("button[role='switch'][id^='headlessui-switch']")
            switch_count = await all_switches.count()

            # Find switches that contain delta-related text nearby
            for i in range(switch_count):
                switch = all_switches.nth(i)
                parent = switch.locator("xpath=ancestor::div[contains(@class, 'flex')]")
                text = await parent.text_content() if await parent.count() > 0 else ""

                if delta_type in text.lower() and "delta" in text.lower():
                    is_checked = await switch.get_attribute("aria-checked")
                    if is_checked != "true":
                        await switch.click()
                        await page.wait_for_timeout(300)
                    return True

            return False
        except Exception as e:
            print(f"Error enabling delta toggle: {e}")
            return False

    async def _find_delta_input(self, page: Page, leg_index: int, delta_type: str) -> Optional[str]:
        """Find the delta input selector for a specific leg.

        Returns the selector string if found, None otherwise.
        """
        try:
            # Strategy: Find inputs near "Exit below/above position delta" text
            delta_text = f"Exit {delta_type} position delta"

            # Look for input fields near the delta text
            # The input is typically in a container with the label
            container = page.locator(f"div:has-text('{delta_text}')")

            if await container.count() > leg_index:
                leg_container = container.nth(leg_index)
                input_field = leg_container.locator("input[type='text'], input[type='number'], input:not([type])")

                if await input_field.count() > 0:
                    # Return a unique selector
                    return f"div:has-text('{delta_text}') >> nth={leg_index} >> input"

            # Fallback: Use the pattern from puppeteer recording
            # div:nth-of-type(N) > div:nth-of-type(2) div.pr-3 input
            # where N varies by leg position in the form

            # Find all exit delta inputs by looking for numeric inputs in leg sections
            all_inputs = page.locator("div.flex-wrap input, div.pr-3 input")
            input_count = await all_inputs.count()

            if input_count > leg_index:
                return f"(div.flex-wrap input, div.pr-3 input) >> nth={leg_index}"

            return None
        except Exception as e:
            print(f"Error finding delta input: {e}")
            return None

    async def set_value(self, page: Page, value: int) -> bool:
        """Set delta value in the UI for configured leg(s)."""
        leg_to_sweep = self.config.get("leg_to_sweep", "1")
        delta_type = self.config.get("delta_type", "below")
        num_legs = int(self.config.get("num_legs", 2))

        # Determine which legs to update
        if leg_to_sweep == "all":
            legs_to_update = list(range(num_legs))
        else:
            leg_num = int(leg_to_sweep)
            legs_to_update = [leg_num - 1]  # Convert to 0-based

        success = True
        for leg_index in legs_to_update:
            # Enable the toggle for this leg's delta exit
            toggle_enabled = await self._enable_delta_toggle(page, leg_index, delta_type)
            if not toggle_enabled:
                print(f"Warning: Could not enable delta toggle for leg {leg_index + 1}")

            # Find and fill the input
            input_selector = await self._find_delta_input(page, leg_index, delta_type)
            if input_selector:
                filled = await self._fill_input(page, input_selector, value)
                if not filled:
                    success = False
                    print(f"Failed to fill delta input for leg {leg_index + 1}")
            else:
                # Try direct approach with known selectors
                # These selectors are based on common OptionOmega patterns
                direct_selectors = [
                    f"input[placeholder*='delta' i] >> nth={leg_index}",
                    f"div:has-text('position delta') input >> nth={leg_index}",
                ]

                filled = False
                for sel in direct_selectors:
                    try:
                        if await page.locator(sel).count() > 0:
                            filled = await self._fill_input(page, sel, value)
                            if filled:
                                break
                    except:
                        continue

                if not filled:
                    success = False
                    print(f"Could not find delta input for leg {leg_index + 1}")

        return success

    async def verify_value(self, page: Page, value: int) -> bool:
        """Verify delta value was set correctly."""
        leg_to_sweep = self.config.get("leg_to_sweep", "1")
        delta_type = self.config.get("delta_type", "below")
        num_legs = int(self.config.get("num_legs", 2))

        if leg_to_sweep == "all":
            legs_to_check = list(range(num_legs))
        else:
            leg_num = int(leg_to_sweep)
            legs_to_check = [leg_num - 1]

        for leg_index in legs_to_check:
            input_selector = await self._find_delta_input(page, leg_index, delta_type)
            if input_selector:
                actual = await self._get_input_value(page, input_selector)
                if actual is None or int(actual) != value:
                    return False

        return True
