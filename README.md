# OO Automator v2

Automated backtesting tool for [OptionOmega](https://optionomega.com). Run parameter sweeps, analyze results, and get AI-powered recommendations for optimal configurations.

## What This Does

- **Automates backtesting** - No more clicking through hundreds of parameter combinations manually
- **Parameter sweeps** - Test entry times, deltas, profit targets, etc. across ranges
- **Smart recommendations** - Identifies optimal parameters based on your goals (max returns, protect capital, or balanced)
- **Live dashboard** - Watch progress in real-time with charts and results

---

## Getting Started (Beginner Guide)

### Step 1: Prerequisites

You need these installed on your computer:

**Python 3.11 or higher**
- **Mac**: Open Terminal and run: `brew install python` (requires [Homebrew](https://brew.sh))
- **Windows**: Download from [python.org](https://www.python.org/downloads/) and install (check "Add to PATH")
- **Verify**: Run `python3 --version` in your terminal

**Git** (to download the code)
- **Mac**: Usually pre-installed. Run `git --version` to check
- **Windows**: Download from [git-scm.com](https://git-scm.com/downloads)

### Step 2: Download the Code

Open Terminal (Mac) or Command Prompt (Windows) and run:

```bash
# Navigate to where you want to put the project
cd ~/Documents

# Download the code
git clone https://github.com/shadwhand/oo_automator.git

# Enter the project folder
cd oo_automator
```

### Step 3: Install Dependencies

```bash
# Install Python packages
pip3 install -e .

# Install the browser automation tool
playwright install chromium
```

> **Troubleshooting**: If `pip3` doesn't work, try `pip install -e .` instead.

### Step 4: Set Up Your Credentials

```bash
# Create your config file
cp .env.example .env
```

Now edit the `.env` file with your OptionOmega login:

**Mac**: `open -e .env` (opens in TextEdit)
**Windows**: `notepad .env`

Replace the placeholder values:
```
OO_EMAIL=your-actual-email@example.com
OO_PASSWORD=your-actual-password
```

Save and close the file.

### Step 5: Start the Dashboard

```bash
oo-automator serve
```

You should see:
```
╭──────────────────────────────────────────╮
│ OO Automator Dashboard                   │
│ Starting server at http://127.0.0.1:8000 │
╰──────────────────────────────────────────╯
```

**Open your browser** and go to: **http://localhost:8000**

---

## Using the Dashboard

### Creating Your First Run

1. Click **"+ New Run"** on the dashboard
2. Paste your OptionOmega test URL (e.g., `https://optionomega.com/test/abc123`)
3. Select the parameter to sweep (e.g., Entry Time)
4. Set the range (e.g., 09:30 to 11:00, step 5 minutes)
5. Click **"Start Run"**

### Viewing Results

- Click on any test to see all runs for that test
- Click on a run to see progress and results
- Use the **"Basic View"**, **"Advanced View"**, and **"Recommendations"** tabs to analyze results

### Understanding Recommendations

The Recommendations page helps you pick optimal parameters:

- **Maximize Returns** - Prioritizes CAGR and profit
- **Protect Capital** - Prioritizes low drawdown and high win rate
- **Balanced** - Best risk-adjusted returns (Sharpe ratio)

Each recommendation shows:
- **Score (0-100)** - Higher is better for your selected goal
- **Why** - Explanation of what makes this configuration good
- **Alternatives** - Other viable options with different trade-offs
- **Avoid** - Configurations that performed poorly

---

## Command Line Usage

If you prefer the command line over the dashboard:

**Interactive mode** (guided wizard):
```bash
oo-automator run interactive
```

**Quick run** (one-liner):
```bash
oo-automator run quick https://optionomega.com/test/abc123 \
    --param entry_time --start 09:30 --end 11:00 --step 5
```

---

## Configuration Options

Edit your `.env` file to customize:

| Variable | Description | Default |
|----------|-------------|---------|
| `OO_EMAIL` | Your OptionOmega email | (required) |
| `OO_PASSWORD` | Your OptionOmega password | (required) |
| `OO_HEADLESS` | Run browsers invisibly | `false` |
| `OO_MAX_BROWSERS` | Parallel browser count | `2` |
| `OO_PORT` | Dashboard port | `8000` |

---

## Available Parameters

| Parameter | Description | Example Range |
|-----------|-------------|---------------|
| `entry_time` | When to enter trades | 09:30 - 15:00 |
| `delta` | Option delta for entry | 5 - 50 |
| `profit_target` | Take profit % | 10 - 100 |
| `stop_loss` | Stop loss % | 50 - 200 |

---

## Troubleshooting

### "Command not found: oo-automator"
Try running with Python directly:
```bash
python3 -m oo_automator.cli.run serve
```

### "playwright not found"
Install it with:
```bash
pip3 install playwright
playwright install chromium
```

### Browser doesn't open / Login fails
1. Check your credentials in `.env`
2. Try setting `OO_HEADLESS=false` to see what's happening
3. Make sure you can log into OptionOmega manually in your browser

### Port already in use
Change the port:
```bash
oo-automator serve --port 8001
```

---

## Updating

To get the latest version:
```bash
cd ~/Documents/oo_automator
git pull origin main
pip3 install -e .
```

---

## Project Structure

```
oo_automator/
├── analysis/        # Recommendations engine
├── browser/         # Playwright automation
├── cli/             # Command-line interface
├── core/            # Task execution
├── db/              # Database models
├── parameters/      # Parameter definitions
└── web/             # Dashboard (FastAPI)
    ├── routes/      # API endpoints
    ├── templates/   # HTML pages
    └── static/      # CSS/JS
```

---

## License

MIT
