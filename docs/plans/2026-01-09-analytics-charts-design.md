# Analytics Charts Design

> **For Claude:** Use superpowers:executing-plans to implement this design.

**Goal:** Dedicated analytics page with configurable charts for analyzing trade log data across multiple runs and parameters.

**Phase:** 1 (Core charts from trade log data)

---

## Overview

After completing parameter sweeps, users need to analyze trade-level data across runs. The Analytics page provides a dashboard of preset charts that visualize patterns in P/L, stop losses, VIX impact, and more.

## Data Source

Trade log CSVs downloaded directly from OptionOmega contain:

```
Date Opened, Time Opened, Opening Price, Legs, Premium, Closing Price,
Date Closed, Time Closed, Avg. Closing Cost, Reason For Close, P/L, P/L %,
No. of Contracts, Funds at Close, Margin Req., Strategy,
Opening Commissions + Fees, Closing Commissions + Fees,
Opening Short/Long Ratio, Closing Short/Long Ratio,
Opening VIX, Closing VIX, Gap, Movement, Max Profit, Max Loss
```

## Data Structure

```python
@dataclass
class TradeRecord:
    # Identifiers (added during parsing)
    run_id: int
    parameter_name: str
    parameter_value: str

    # Timing
    date_opened: date
    time_opened: time
    date_closed: date
    time_closed: time

    # P/L
    pl: float                    # Dollar P/L
    pl_percent: float            # P/L %
    premium: float

    # Trade details
    legs: str                    # Strategy legs description
    num_contracts: int
    reason_for_close: str        # "Stop Loss", "Expired", "Profit Target"

    # Market data
    opening_vix: float
    closing_vix: float
    gap: float                   # Market gap
    movement: float              # Intraday movement
    opening_price: float         # Underlying price
    closing_price: float

    # Risk metrics
    max_profit: float            # Theoretical max
    max_loss: float              # Theoretical max
    margin_req: float
```

## Page Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Analytics                                           [Export]   │
├─────────────────────────────────────────────────────────────────┤
│  Test: [Select Test ▼]    Runs: [☑ All] [☐ Run #1] [☐ Run #2]  │
│  Date Range: [Start] to [End]    Parameters: [Select ▼]        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │  Daily P/L by Parameter │  │  Cumulative Returns     │      │
│  │  [Time Series Chart]    │  │  [Time Series Chart]    │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │  Stop Loss Distribution │  │  Win/Loss by Reason     │      │
│  │  [Bar Chart]            │  │  [Bar Chart]            │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
│  ┌─────────────────────────┐  ┌─────────────────────────┐      │
│  │  VIX Impact             │  │  Trade Duration         │      │
│  │  [Scatter Plot]         │  │  [Bar Chart]            │      │
│  └─────────────────────────┘  └─────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

## Preset Charts

### 1. Daily P/L by Parameter
- **Type:** Time series (line chart)
- **X-axis:** Date
- **Y-axis:** Total P/L ($)
- **Series:** One line per parameter value
- **Purpose:** Compare how different parameter values perform over time

### 2. Cumulative Returns
- **Type:** Time series (line chart)
- **X-axis:** Date
- **Y-axis:** Cumulative P/L ($)
- **Series:** One line per parameter value
- **Purpose:** See running total performance, identify drawdown periods

### 3. Stop Loss Distribution
- **Type:** Bar chart
- **X-axis:** Parameter values
- **Y-axis:** Count of stop losses
- **Purpose:** Identify which parameters hit stop losses most frequently

### 4. Win/Loss by Reason
- **Type:** Stacked bar chart
- **X-axis:** Parameter values
- **Y-axis:** Trade count
- **Stacks:** Reason for close (Stop Loss, Profit Target, Expired)
- **Purpose:** See trade outcome distribution per parameter

### 5. VIX Impact
- **Type:** Scatter plot
- **X-axis:** Opening VIX
- **Y-axis:** P/L or P/L %
- **Color:** By parameter value
- **Purpose:** Understand how volatility affects strategy performance

### 6. Trade Duration Analysis
- **Type:** Bar chart
- **X-axis:** Parameter values
- **Y-axis:** Average minutes in trade
- **Purpose:** See how long trades stay open by parameter

## Interactions

- **Filter controls:** Test selector, run checkboxes, date range, parameter dropdown
- **Click to expand:** Any chart can be clicked to view full-screen with more detail
- **Hover tooltips:** Show exact values on hover
- **Live updates:** Charts refresh when filters change
- **Export:** Download aggregated data as CSV

## API Endpoints

### GET /api/analytics/tests
Returns tests that have trade log data available.

```json
{
  "tests": [
    {"id": 1, "name": "Iron Condor SPY", "url": "...", "run_count": 5}
  ]
}
```

### GET /api/analytics/data
Query parameters:
- `test_id` (required)
- `run_ids` (optional, comma-separated)
- `start_date` (optional)
- `end_date` (optional)

Returns aggregated data for all charts:

```json
{
  "trades": [...],           // Raw trade records
  "daily_pl": {...},         // Aggregated by date + parameter
  "cumulative": {...},       // Running totals
  "stop_loss_counts": {...}, // By parameter
  "reason_counts": {...},    // By parameter + reason
  "vix_data": [...],         // For scatter plot
  "duration_avg": {...}      // By parameter
}
```

## File Structure

```
oo_automator/
├── analysis/
│   ├── recommendations.py  (existing)
│   └── charts.py           (new)
└── web/
    ├── routes/
    │   ├── api.py          (add endpoints)
    │   └── pages.py        (add /analytics route)
    └── templates/
        └── analytics.html  (new)
```

## Implementation Tasks

1. Create `charts.py` - trade log parser and data aggregation
2. Add analytics API endpoints to `api.py`
3. Add `/analytics` page route to `pages.py`
4. Create `analytics.html` template with Chart.js charts
5. Add navigation link to analytics page
6. Test with real trade log data

## Future Enhancements

- Custom chart builder (user-defined X/Y axes)
- Save chart configurations
- Compare across different tests
- Additional chart types (histogram, box plot)
- Correlation analysis between metrics

---

*Design approved: 2026-01-09*
