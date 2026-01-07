# OO Automator v2

Automated backtesting system for OptionOmega with live dashboard and smart parameter optimization.

## Features

- **Browser Automation**: Playwright-based automation with auto-waiting and smart failure recovery
- **Parameter Plugin System**: Auto-discovered parameters with configurable ranges
- **Multiple Test Modes**: Single parameter sweep, grid search, and staged optimization
- **Live Dashboard**: Real-time progress with htmx and WebSocket updates
- **Smart Failure Recovery**: Automatic retry with captured failure artifacts

## Quick Start

### Installation

```bash
# Clone and install
cd OOAutomator
pip install -e .

# Install Playwright browsers
playwright install chromium
```

### Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your OptionOmega credentials:

```bash
OO_EMAIL=your-email@example.com
OO_PASSWORD=your-password
```

### Usage

**Interactive Mode:**
```bash
oo-automator run interactive
```

This launches an interactive wizard to:
1. Select or enter a test URL
2. Choose test mode (sweep/grid/staged)
3. Select parameters to optimize
4. Configure parameter ranges
5. Start the run

**Quick Run:**
```bash
oo-automator run quick https://app.optionomega.com/tests/abc123 \
    --param delta --start 5 --end 20 --step 5
```

**Start Dashboard:**
```bash
oo-automator serve
```

Then open http://localhost:8000 in your browser.

## Test Modes

### Sweep Mode
Test a single parameter across a range of values.

```bash
# Example: Test delta from 5 to 25 in steps of 5
oo-automator run quick <test-url> --param delta --start 5 --end 25 --step 5
```

### Grid Mode
Test multiple parameters in all combinations (use interactive mode).

### Staged Mode
Progressive optimization - uses results from earlier stages to narrow ranges.

## Available Parameters

| Parameter | Description | Default Range |
|-----------|-------------|---------------|
| delta | Option delta for entry | 5-50 |
| profit_target | Profit target percentage | 10-100% |
| stop_loss | Stop loss percentage | 50-200% |
| entry_time | Entry time (HH:MM format) | 09:30-15:00 |

## Dashboard

The web dashboard at http://localhost:8000 shows:

- **Home Page**: Recent tests and active runs
- **Run Detail**: Live progress, tasks table, and results with charts

Features:
- Real-time updates via htmx polling
- WebSocket support for instant notifications
- Chart.js visualizations for P/L and CAGR

## Configuration Options

Set via environment variables or `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| OO_EMAIL | OptionOmega email | - |
| OO_PASSWORD | OptionOmega password | - |
| OO_HEADLESS | Run browsers headless | false |
| OO_MAX_BROWSERS | Max concurrent browsers | 2 |
| OO_DB_PATH | SQLite database path | oo_automator.db |
| OO_PORT | Dashboard port | 8000 |

## Development

### Running Tests

```bash
# All tests
pytest

# Specific test suites
pytest tests/db/ -v
pytest tests/parameters/ -v
pytest tests/core/ -v
pytest tests/web/ -v
pytest tests/integration/ -v
```

### Project Structure

```
oo_automator/
├── db/              # Database models and queries
├── parameters/      # Parameter plugin system
├── browser/         # Playwright automation
├── core/            # Task queue and run manager
├── cli/             # CLI commands
├── analysis/        # Results analysis
└── web/             # FastAPI dashboard
    ├── routes/      # API and page routes
    ├── templates/   # Jinja2 templates
    └── static/      # CSS and JavaScript
```

## License

MIT
