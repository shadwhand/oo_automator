# OO Automator v2 - Design Document

**Date:** 2026-01-07
**Status:** Approved
**Author:** Design session with Claude

## Overview

Complete rewrite of the OptionOmega backtesting automation system. The current Selenium-based implementation suffers from timing/race condition issues and architectural complexity that makes maintenance difficult. This redesign addresses those core problems while adding new capabilities.

## Goals

1. **Reliability** - Eliminate timing issues through Playwright's auto-waiting
2. **Smart Recovery** - Classify failures and respond appropriately
3. **Extensibility** - Easy plugin system for new parameters
4. **Visibility** - Live dashboard for monitoring without babysitting
5. **Flexibility** - Support multiple test modes (sweep, grid, staged)

## Non-Goals (YAGNI)

- Multi-user / authentication
- Cloud deployment / Docker
- Real-time alerts (email/SMS)
- Complex scheduling / cron
- More than 2 concurrent browsers

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        OO Automator v2                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   CLI        │    │   Web API    │    │  Dashboard   │      │
│  │   (typer)    │    │  (FastAPI)   │    │  (htmx)      │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             │                                   │
│                    ┌────────▼────────┐                         │
│                    │   Run Manager   │                         │
│                    │  (orchestrator) │                         │
│                    └────────┬────────┘                         │
│                             │                                   │
│         ┌───────────────────┼───────────────────┐              │
│         │                   │                   │               │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐        │
│  │  Browser 1  │    │  Browser 2  │    │   SQLite    │        │
│  │ (Playwright)│    │ (Playwright)│    │  Database   │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Browser Automation | Playwright | Async, auto-waiting solves timing issues |
| Web Framework | FastAPI | Async-native, WebSocket support, simple |
| CLI | Typer | Clean interactive prompts, auto-generated help |
| Database | SQLite | Zero-config, sufficient for local use |
| Frontend | htmx + Jinja2 | Live updates without JS complexity |
| Charts | Chart.js or similar | Simple, no build step |

### Core Components

1. **CLI** - Interactive wizard for configuring and starting runs
2. **Web API** - REST endpoints + WebSocket for live updates
3. **Dashboard** - Browser UI for monitoring and results
4. **Run Manager** - Orchestrates test execution and browser pool
5. **Browser Workers** - Playwright instances executing tests
6. **SQLite Database** - Persistent storage for all data

---

## Parameter Plugin System

### Design Principles

- One file per parameter
- Auto-discovered (no registration required)
- Self-describing (config schema for CLI/dashboard rendering)
- Async-native

### Directory Structure

```
oo_automator/
  parameters/
    __init__.py          # Auto-discovery logic
    base.py              # Base class
    delta.py
    rsi.py
    profit_target.py
    stop_loss.py
    entry_time.py
    exit_time.py
    short_long_ratio.py
    entry_sl_ratio.py
    underlying_movement.py
```

### Base Class Interface

```python
from abc import ABC, abstractmethod
from playwright.async_api import Page
from typing import Any
from dataclasses import dataclass

@dataclass
class ParameterConfig:
    fields: list  # List of field definitions for UI

class Parameter(ABC):
    name: str           # Internal identifier
    display_name: str   # Human-readable name
    description: str    # Help text
    selectors: dict     # UI element selectors

    @abstractmethod
    def configure(self) -> ParameterConfig:
        """Return config schema for CLI/dashboard UI"""
        pass

    @abstractmethod
    def generate_values(self, config: dict) -> list:
        """Generate the list of values to test"""
        pass

    @abstractmethod
    async def set_value(self, page: Page, value: Any) -> bool:
        """Set the parameter value in the UI"""
        pass

    @abstractmethod
    async def verify_value(self, page: Page, value: Any) -> bool:
        """Verify the value was set correctly"""
        pass
```

### Conditional Parameters (Toggle-Revealed Fields)

Some parameters only appear after enabling a toggle. The base class handles this:

```python
class Parameter(ABC):
    # Optional: Toggle that must be enabled before this parameter is visible
    requires_toggle: str | None = None
    toggle_selector: str | None = None

    async def ensure_visible(self, page: Page) -> bool:
        """Enable parent toggle if this parameter requires it"""
        if not self.requires_toggle:
            return True

        toggle = page.locator(self.toggle_selector)
        if await toggle.get_attribute("aria-checked") != "true":
            await toggle.click()
            await page.wait_for_timeout(300)  # Wait for reveal animation
        return True
```

**Example parameters with toggle dependencies:**

| Parameter | Requires Toggle |
|-----------|-----------------|
| Min/Max RSI | "Use Technical Indicators" |
| Exit Time | "Use Early Exit" |
| Movement % | "Use Underlying Price Movement" |
| Entry S/L Ratio | "Use Entry Short/Long Ratio" |

### Example Implementation

```python
# parameters/delta.py
from parameters.base import Parameter, ParameterConfig, IntField, ChoiceField

class DeltaParameter(Parameter):
    name = "delta"
    display_name = "Delta"
    description = "Options delta value for put/call selection"

    selectors = {
        "put": ["#delta-put", "input[name='delta-put']"],
        "call": ["#delta-call", "input[name='delta-call']"],
    }

    def configure(self) -> ParameterConfig:
        return ParameterConfig(
            fields=[
                IntField("start", label="Start", default=5, min=1, max=100),
                IntField("end", label="End", default=50, min=1, max=100),
                IntField("step", label="Step", default=1, min=1),
                ChoiceField("apply_to", label="Apply to",
                           choices=["both", "put_only", "call_only"],
                           default="both"),
            ]
        )

    def generate_values(self, config: dict) -> list:
        return list(range(config["start"], config["end"] + 1, config["step"]))

    async def set_value(self, page: Page, value: int) -> bool:
        apply_to = self.config.get("apply_to", "both")

        if apply_to in ["both", "put_only"]:
            await page.fill(self.selectors["put"][0], str(value))
        if apply_to in ["both", "call_only"]:
            await page.fill(self.selectors["call"][0], str(-value))

        return True

    async def verify_value(self, page: Page, value: int) -> bool:
        apply_to = self.config.get("apply_to", "both")

        if apply_to in ["both", "put_only"]:
            actual = await page.input_value(self.selectors["put"][0])
            if actual != str(value):
                return False
        if apply_to in ["both", "call_only"]:
            actual = await page.input_value(self.selectors["call"][0])
            if actual != str(-value):
                return False

        return True
```

### Auto-Discovery

```python
# parameters/__init__.py
import importlib
import pkgutil
from pathlib import Path

def discover_parameters() -> dict[str, type]:
    """Auto-discover all parameter classes in this package"""
    parameters = {}
    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name in ("__init__", "base"):
            continue

        module = importlib.import_module(f".{module_info.name}", __package__)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                issubclass(attr, Parameter) and
                attr is not Parameter):
                parameters[attr.name] = attr

    return parameters

PARAMETERS = discover_parameters()
```

---

## Test Modes

### 1. Single Parameter Sweep

Test one parameter across a range of values.

```python
{
    "mode": "sweep",
    "parameter": "delta",
    "config": {"start": 5, "end": 50, "step": 1}
}
# Generates: [5, 6, 7, ..., 50] = 46 tests
```

### 2. Grid Search

Test all combinations of multiple parameters.

```python
{
    "mode": "grid",
    "parameters": {
        "delta": {"start": 5, "end": 20, "step": 5},
        "profit_target": {"start": 10, "end": 50, "step": 10}
    }
}
# Generates: 4 delta values × 5 profit_target values = 20 tests
# [(5,10), (5,20), (5,30), ..., (20,50)]
```

### 3. Staged/Dependent Optimization

Optimize parameters sequentially, using best result from previous stage.

```python
{
    "mode": "staged",
    "stages": [
        {
            "parameter": "delta",
            "config": {"start": 5, "end": 50, "step": 1}
        },
        {
            "parameter": "profit_target",
            "use_best_from": "delta",
            "optimize_by": "mar",
            "config": {"start": 10, "end": 100, "step": 5}
        }
    ]
}
# Stage 1: Find best delta (by MAR)
# Stage 2: Using that delta, sweep profit_target
```

---

## Smart Failure Recovery

### Failure Classification

| Type | Detection | Response |
|------|-----------|----------|
| **Timing** | Element not found, click didn't register | Retry with longer waits (up to 3x) |
| **Modal Stuck** | Dialog won't close, overlay blocking | Clear page state, retry |
| **Session Expired** | Login page detected, auth error | Re-authenticate, resume queue |
| **Browser Crash** | Playwright connection lost | Spawn new browser, continue |
| **OptionOmega Error** | Error toast/message in UI | Screenshot, skip test, continue |
| **Permanent** | Same test fails 3+ times | Mark failed, capture artifacts, move on |

### Adaptive Behavior

```python
class AdaptiveThrottling:
    base_delay = 0.5  # seconds between actions

    def adjust(self, recent_failures: int):
        if recent_failures == 0:
            return self.base_delay
        elif recent_failures == 1:
            return 1.0
        elif recent_failures == 2:
            return 2.0  # Also trigger: drop to 1 browser
        else:
            return 3.0  # Log warning
```

### Failure Artifacts

Captured on every failure:
- Screenshot (PNG)
- HTML snapshot
- Browser console logs
- Network requests (optional)

Stored in database with references, viewable in dashboard.

---

## Database Schema

```sql
-- Test configurations (OptionOmega test URLs) - grows over time as user adds tests
CREATE TABLE tests (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    name TEXT,                    -- User-provided friendly name
    last_run_at TIMESTAMP,        -- For sorting by recency
    run_count INTEGER DEFAULT 0,  -- Track usage frequency
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tests_url ON tests(url);
CREATE INDEX idx_tests_name ON tests(name);
CREATE INDEX idx_tests_last_run ON tests(last_run_at DESC);

-- Automation runs
CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    test_id INTEGER REFERENCES tests(id),
    mode TEXT NOT NULL,  -- sweep | grid | staged
    config JSON NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending | running | paused | completed | failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual test tasks
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES runs(id),
    parameter_values JSON NOT NULL,  -- {"delta": 15, "profit_target": 30}
    status TEXT DEFAULT 'pending',  -- pending | running | completed | failed | skipped
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Test results
CREATE TABLE results (
    id INTEGER PRIMARY KEY,
    task_id INTEGER UNIQUE REFERENCES tasks(id),
    cagr REAL,
    max_drawdown REAL,
    win_percentage REAL,
    capture_rate REAL,
    mar REAL,
    raw_data JSON,  -- Full response from OptionOmega
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trade-level data (optional analysis)
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    result_id INTEGER REFERENCES results(id),
    trade_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Failure artifacts
CREATE TABLE failures (
    id INTEGER PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    attempt_number INTEGER,
    failure_type TEXT,  -- timing | modal | session | browser | permanent
    error_message TEXT,
    screenshot_path TEXT,
    html_path TEXT,
    console_log JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_tasks_run_id ON tasks(run_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_results_task_id ON results(task_id);
CREATE INDEX idx_failures_task_id ON failures(task_id);
```

---

## CLI Interface

### Interactive Mode

```
$ oo-automator run

🔧 OO Automator v2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

? Test URL or name:
  Recent tests:
    [1] Put Credit Spread METF (abc123) - last run 2 days ago
    [2] Iron Condor SPY (def456) - last run 1 week ago
    [3] Strangle QQQ (ghi789) - last run 2 weeks ago

  Enter URL, name, or number: https://optionomega.com/test/xyz999

  ✓ New test detected. Name it (optional): My New Strategy

? What would you like to test?
  ❯ Single parameter sweep
    Grid search (multiple parameters)
    Staged optimization

? Select parameter:
  ❯ Delta
    RSI
    Profit Target
    Stop Loss
    Entry Time
    ...

? Delta configuration:
  Start value [5]:
  End value [50]:
  Step [1]:
  Apply to: (use arrows)
    ❯ Both put and call
      Put only
      Call only

? Browsers to use [2]:

? Ready to run 46 tests. Continue? (Y/n)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 Starting run...
   Dashboard: http://localhost:8000/runs/7
```

### Command-Line Flags (Power Users)

```bash
# Full flag specification
oo-automator run \
  --url "https://optionomega.com/test/abc123" \
  --param delta \
  --start 5 \
  --end 50 \
  --step 1 \
  --browsers 2

# From config file
oo-automator run --config my-run.yaml

# Resume interrupted run
oo-automator resume --run-id 7
```

### Other Commands

```bash
# Start dashboard server
oo-automator serve [--port 8000]

# Check status
oo-automator status [--run-id 7]

# List past runs
oo-automator list

# Export results
oo-automator export --run-id 7 --format csv --output results.csv

# Pause/resume
oo-automator pause --run-id 7
oo-automator resume --run-id 7

# Test management
oo-automator tests                     # List all saved tests
oo-automator tests --recent            # Show recent tests (default in run wizard)
oo-automator tests rename abc123 "My Strategy"  # Rename a test
oo-automator tests delete abc123       # Remove a test from history
```

### Test Lookup Behavior

When starting a run, the system accepts:
- **Full URL**: `https://optionomega.com/test/abc123` - adds to history if new
- **Test ID**: `abc123` - looks up in saved tests
- **Name**: `"Put Credit Spread"` - fuzzy matches saved test names
- **Number**: `1`, `2`, `3` - selects from recent tests list

New tests are automatically saved. User can optionally name them for easier recall.

---

## Dashboard UI

### Main Dashboard View

```
┌─────────────────────────────────────────────────────────────────┐
│  OO Automator                    [New Run]  [Settings]         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 Current Run: Delta Sweep (Test abc123)                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  Progress: ████████████░░░░░░░░ 34/46 (74%)   ETA: 12 min      │
│  Browsers: 🟢 Browser 1 (Delta=35)  🟢 Browser 2 (Delta=36)    │
│  Failures: 2 ⚠️                                                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Results                                          [Export CSV] │
│  ┌─────────┬────────┬────────┬────────┬────────┬─────────────┐ │
│  │ Delta   │ CAGR   │ MaxDD  │ Win%   │ MAR    │ Status      │ │
│  ├─────────┼────────┼────────┼────────┼────────┼─────────────┤ │
│  │ 5       │ 0.142  │ -0.08  │ 68.2%  │ 1.78   │ ✅ Complete │ │
│  │ 6       │ 0.156  │ -0.09  │ 71.0%  │ 1.73   │ ✅ Complete │ │
│  │ 7       │ --     │ --     │ --     │ --     │ ❌ Failed   │ │
│  │ 8       │ 0.134  │ -0.07  │ 65.5%  │ 1.91   │ ✅ Complete │ │
│  └─────────┴────────┴────────┴────────┴────────┴─────────────┘ │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  📈 CAGR by Delta                                              │
│  0.20 ┤                    ╭──╮                                │
│  0.15 ┤      ╭─────────────╯  ╰───╮                            │
│  0.10 ┤  ╭───╯                    ╰────                        │
│  0.05 ┤──╯                                                     │
│       └────────────────────────────────────────                │
│         5    10    15    20    25    30    35                  │
└─────────────────────────────────────────────────────────────────┘
```

### Dashboard Pages

1. **Home** - Current run progress, recent runs list
2. **Run Detail** - Full results table, charts, failure log for a specific run
3. **New Run** - Form to configure and start a new run
4. **History** - All past runs with filtering and search
5. **Settings** - Credentials, browser count, timeouts

### Live Updates

- WebSocket connection for real-time updates
- Results table updates as tests complete
- Charts redraw with new data points
- Progress bar updates continuously
- Failure notifications appear immediately

---

## Project Structure

```
oo-automator/
├── pyproject.toml              # Dependencies, project config
├── README.md
│
├── oo_automator/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   │
│   ├── cli/                    # CLI commands
│   │   ├── __init__.py
│   │   ├── run.py              # Interactive run wizard
│   │   ├── status.py           # Check running/past runs
│   │   └── export.py           # Export results
│   │
│   ├── web/                    # Dashboard & API
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI app
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── api.py          # REST endpoints
│   │   │   ├── pages.py        # HTML page routes
│   │   │   └── websocket.py    # Live updates
│   │   ├── templates/          # Jinja2 templates
│   │   │   ├── base.html
│   │   │   ├── index.html
│   │   │   ├── run.html
│   │   │   └── ...
│   │   └── static/
│   │       ├── style.css
│   │       └── charts.js
│   │
│   ├── core/                   # Business logic
│   │   ├── __init__.py
│   │   ├── run_manager.py      # Orchestration
│   │   ├── browser_pool.py     # Browser management
│   │   ├── task_queue.py       # Task distribution
│   │   └── recovery.py         # Failure handling
│   │
│   ├── browser/                # Playwright automation
│   │   ├── __init__.py
│   │   ├── worker.py           # Browser worker
│   │   ├── actions.py          # Common actions
│   │   └── selectors.py        # UI selectors
│   │
│   ├── parameters/             # Plugin system
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── delta.py
│   │   ├── rsi.py
│   │   ├── profit_target.py
│   │   ├── stop_loss.py
│   │   ├── entry_time.py
│   │   ├── exit_time.py
│   │   ├── short_long_ratio.py
│   │   ├── entry_sl_ratio.py
│   │   └── underlying_movement.py
│   │
│   ├── analysis/               # Trade analysis
│   │   ├── __init__.py
│   │   └── metrics.py
│   │
│   └── db/                     # Database
│       ├── __init__.py
│       ├── models.py
│       └── queries.py
│
├── recordings/                 # Chrome DevTools recordings
│   └── backtest_flow.json
│
├── tests/
│   ├── test_parameters.py
│   ├── test_run_manager.py
│   └── ...
│
└── data/                       # Runtime data
    ├── oo_automator.db
    └── artifacts/
        └── failures/
```

---

## Chrome Recording Integration

### Purpose

Chrome DevTools recordings serve as the source of truth for the UI interaction flow. When OptionOmega updates their UI, re-record and update without changing code.

### Usage

1. Record a manual backtest flow in Chrome DevTools
2. Export as JSON to `recordings/backtest_flow.json`
3. System extracts:
   - Selectors for each UI element
   - Expected sequence of actions
   - Timing baselines

### Recording Structure

```json
{
  "title": "Backtest Flow",
  "steps": [
    {
      "type": "click",
      "target": "main",
      "selectors": [["#new-backtest-btn"], ["text=New Backtest"]],
      "offsetX": 50,
      "offsetY": 15
    },
    {
      "type": "waitForElement",
      "selectors": [[".modal-dialog"]]
    },
    {
      "type": "change",
      "target": "main",
      "selectors": [["#delta-input"]],
      "value": "15"
    }
  ]
}
```

---

## Dependencies

```toml
[project]
name = "oo-automator"
version = "2.0.0"
requires-python = ">=3.11"

dependencies = [
    "playwright>=1.40.0",
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "typer>=0.9.0",
    "rich>=13.0.0",
    "sqlmodel>=0.0.14",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.6",
    "websockets>=12.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
]

[project.scripts]
oo-automator = "oo_automator.main:app"
```

---

## Running the Application

```bash
# Install
cd oo-automator
pip install -e .

# Install Playwright browsers
playwright install chromium

# Start dashboard + automation engine
oo-automator serve
# Opens http://localhost:8000

# Or run headless (CLI only)
oo-automator run
```

---

## Future Considerations (Not In Scope)

These are explicitly out of scope but noted for potential future work:

- **Multi-user support** - Authentication, user-specific runs
- **Cloud deployment** - Docker, remote server support
- **Scheduling** - Cron-like scheduled runs
- **Notifications** - Email/SMS alerts on completion or failure
- **More browsers** - Scale beyond 2 concurrent instances
- **Other platforms** - Support for platforms beyond OptionOmega
