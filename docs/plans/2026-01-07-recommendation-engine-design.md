# Recommendation Engine Design

> **For Claude:** Use superpowers:executing-plans to implement this design.

**Goal:** Help users identify optimal parameter configurations from completed backtests, with trade-off analysis and robustness scoring.

**Phase:** 1 of 3 (Phase 2: Monte Carlo, Phase 3: Forward Testing)

---

## Overview

After a user completes a parameter sweep (e.g., Entry Time from 9:30-12:00), the recommendation engine analyzes results and identifies:
1. The optimal configuration based on user's goal
2. Alternative trade-offs (Pareto optimal options)
3. Configurations to avoid

## User Goals

Three optimization objectives:
1. **Maximize Returns** - Focus on CAGR, Expected Value
2. **Protect Capital** - Focus on Max Drawdown, Win Rate
3. **Balanced** - Focus on Sharpe, MAR, Kelly %

## Scoring Algorithm

Composite score balances multiple metrics:

```python
def calculate_score(result, goal="balanced"):
    # Normalize each metric to 0-1 scale
    normalized = {
        "sharpe": normalize(result.sharpe, all_sharpe_values),
        "cagr": normalize(result.cagr, all_cagr_values),
        "win_rate": normalize(result.win_percentage, all_win_values),
        "kelly": normalize(result.kelly, all_kelly_values),
        "drawdown": 1 - normalize(result.max_drawdown, all_dd_values),  # Inverted
    }

    # Weights by goal
    weights = {
        "maximize_returns": {"sharpe": 0.2, "cagr": 0.4, "win_rate": 0.15, "kelly": 0.15, "drawdown": 0.1},
        "protect_capital": {"sharpe": 0.2, "cagr": 0.15, "win_rate": 0.25, "kelly": 0.1, "drawdown": 0.3},
        "balanced": {"sharpe": 0.3, "cagr": 0.25, "win_rate": 0.2, "kelly": 0.15, "drawdown": 0.1},
    }

    w = weights[goal]
    score = sum(normalized[k] * w[k] for k in w)
    return score * 100  # 0-100 scale
```

## Trade-off Detection

**Pareto Optimality:**
A result is Pareto optimal if no other result beats it on ALL metrics. These are valid alternatives with different trade-offs.

**Dominance:**
A result is "dominated" if another result is better on every metric. These go in the "Avoid" section.

**Stability:**
Calculate variance of performance for nearby parameter values. High variance = less reliable.

## Data Organization

**Cache results by test URL:**
```python
# Before running a backtest
existing = db.query(Result).filter(
    test_url == url,
    param_name == name,
    param_value == value
).first()

if existing:
    return existing  # Skip, already tested
```

**Group runs by test:**
- Tests page shows all unique test URLs
- Each test shows accumulated results from all runs
- Combine results since backtested data is deterministic

## Rate Limiting

Protect against OptionOmega rate limits:

```python
REQUESTS_PER_MINUTE = 10
MIN_DELAY_SECONDS = 6

async def run_with_throttle(task):
    await asyncio.sleep(MIN_DELAY_SECONDS)
    try:
        return await run_backtest(task)
    except RateLimitError:
        await asyncio.sleep(60)  # Back off
        return await run_backtest(task)
```

## UI Design

**Location:** New "Recommendations" tab on Run Results page

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  [Basic View]  [Advanced View]  [Recommendations]           │
├─────────────────────────────────────────────────────────────┤
│  YOUR GOAL: [Maximize Returns] [Protect Capital] [Balanced] │
├─────────────────────────────────────────────────────────────┤
│  TOP RECOMMENDATION                                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Entry Time: 10:15 AM          Score: 87/100             ││
│  │ CAGR: 45%  |  Max DD: 18%  |  Sharpe: 1.8  |  Win: 62% ││
│  │                                                         ││
│  │ Why: Best risk-adjusted return. Drawdown stays under    ││
│  │ 20% while capturing 85% of possible gains.              ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ALTERNATIVES (Pareto Optimal)                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ 10:30 AM     │ │ 9:45 AM      │ │ 11:00 AM     │        │
│  │ Score: 82    │ │ Score: 79    │ │ Score: 75    │        │
│  │ Higher CAGR  │ │ Lowest risk  │ │ Most stable  │        │
│  │ Higher DD    │ │ Lower CAGR   │ │ Consistent   │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                             │
│  AVOID                                                      │
│  - 9:35 AM: High drawdown (45%) with mediocre returns       │
│  - 12:30 PM: Dominated by 11:00 AM on all metrics           │
└─────────────────────────────────────────────────────────────┘
```

## Matrix/Grid Support

For multi-parameter sweeps (e.g., Entry Time × Delta):

```
Optimal Combination: 10:15 AM + Delta 18

Why this pair works:
- Low correlation of losses between parameters
- Combined Sharpe: 2.1
- Avoids "danger zones" (early entry + high delta)

[Heatmap visualization of all combinations]
```

## Export for AI Analysis

**"Discuss with AI" button** - Generates a formatted prompt with results data that can be pasted into ChatGPT/Claude.

**Example output:**

```
I ran a parameter sweep on my options trading strategy. Here are my backtest results:

STRATEGY: Iron Condor on SPY
PARAMETER TESTED: Entry Time (9:30 AM - 12:00 PM, 5-min intervals)
TOTAL CONFIGURATIONS: 31

TOP 5 RESULTS:
| Entry Time | CAGR   | Max DD | Win %  | Sharpe | Kelly % |
|------------|--------|--------|--------|--------|---------|
| 10:15 AM   | 45.2%  | 18.3%  | 62.1%  | 1.82   | 24.5%   |
| 10:30 AM   | 52.1%  | 26.7%  | 58.4%  | 1.45   | 21.2%   |
| 10:00 AM   | 41.8%  | 15.2%  | 65.3%  | 1.91   | 26.1%   |
| 11:00 AM   | 38.5%  | 14.1%  | 68.2%  | 1.88   | 28.3%   |
| 9:45 AM    | 35.2%  | 12.8%  | 71.0%  | 1.72   | 29.8%   |

WORST 3 RESULTS:
| Entry Time | CAGR   | Max DD | Win %  | Sharpe | Kelly % |
|------------|--------|--------|--------|--------|---------|
| 9:35 AM    | 22.1%  | 45.2%  | 48.3%  | 0.42   | 8.2%    |
| 12:00 PM   | 18.5%  | 38.7%  | 51.2%  | 0.51   | 10.1%   |
| 9:30 AM    | 15.8%  | 52.1%  | 45.8%  | 0.28   | 5.4%    |

MY GOAL: [Balanced risk/reward]

Questions:
1. Which entry time would you recommend and why?
2. What trade-offs should I consider?
3. Why might early entries (9:30-9:45) perform poorly?
4. How can I validate these results aren't overfit?
```

**Implementation:**
- Button on recommendations page: "Export for AI Discussion"
- Copies formatted prompt to clipboard
- Includes: strategy context, top/bottom results, user's goal, suggested questions

## Implementation Tasks

1. Add recommendation scoring module (`oo_automator/analysis/recommendations.py`)
2. Add API endpoint `/api/runs/{id}/recommendations`
3. Create recommendations template (`recommendations.html`)
4. Add result caching by test URL
5. Implement rate limiting in browser worker
6. Add goal selector UI component
7. Add "Export for AI" prompt generator

## Future Phases

**Phase 2: Monte Carlo Analysis**
- Bootstrap sampling of trade results
- Confidence intervals on metrics
- "95% confident CAGR is between X and Y"

**Phase 3: Forward Testing**
- Split data into in-sample / out-of-sample
- Validate that optimal params work on unseen data
- Walk-forward optimization

---

*Design approved: 2026-01-07*
