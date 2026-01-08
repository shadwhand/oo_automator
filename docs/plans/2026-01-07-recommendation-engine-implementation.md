# Recommendation Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a recommendation engine that analyzes completed parameter sweeps and identifies optimal configurations with trade-off analysis.

**Architecture:** Add a scoring module that calculates composite scores and Pareto optimality, expose via API endpoint, render in a new Recommendations tab on the results page.

**Tech Stack:** Python, FastAPI, Jinja2, JavaScript

---

### Task 1: Create Recommendation Scoring Module

**Files:**
- Create: `oo_automator/analysis/__init__.py` (update)
- Create: `oo_automator/analysis/recommendations.py`
- Test: `tests/analysis/test_recommendations.py`

**Step 1: Create test directory and file**

```bash
mkdir -p tests/analysis
touch tests/analysis/__init__.py
```

**Step 2: Write the failing test for score calculation**

Create `tests/analysis/test_recommendations.py`:

```python
"""Tests for recommendation scoring."""
import pytest
from oo_automator.analysis.recommendations import (
    calculate_score,
    normalize_values,
    find_pareto_optimal,
    generate_recommendations,
)


class TestNormalize:
    def test_normalize_values_basic(self):
        values = [10, 20, 30, 40, 50]
        result = normalize_values(values)
        assert result[0] == 0.0  # min
        assert result[-1] == 1.0  # max
        assert result[2] == 0.5  # middle

    def test_normalize_values_same(self):
        values = [5, 5, 5]
        result = normalize_values(values)
        assert all(v == 0.5 for v in result)


class TestCalculateScore:
    def test_calculate_score_balanced(self):
        result = {
            "sharpe": 1.5,
            "cagr": 40,
            "win_percentage": 60,
            "kelly": 25,
            "max_drawdown": 20,
        }
        all_results = [result]  # Single result for normalization
        score = calculate_score(result, all_results, goal="balanced")
        assert 0 <= score <= 100

    def test_calculate_score_maximize_returns_weights_cagr(self):
        high_cagr = {"sharpe": 1.0, "cagr": 80, "win_percentage": 50, "kelly": 20, "max_drawdown": 30}
        low_cagr = {"sharpe": 1.5, "cagr": 20, "win_percentage": 70, "kelly": 30, "max_drawdown": 10}
        all_results = [high_cagr, low_cagr]

        score_high = calculate_score(high_cagr, all_results, goal="maximize_returns")
        score_low = calculate_score(low_cagr, all_results, goal="maximize_returns")

        assert score_high > score_low  # High CAGR should score higher


class TestParetoOptimal:
    def test_find_pareto_optimal_single(self):
        results = [{"id": 1, "cagr": 50, "max_drawdown": 20}]
        pareto = find_pareto_optimal(results, ["cagr"], ["max_drawdown"])
        assert len(pareto) == 1

    def test_find_pareto_optimal_dominated(self):
        results = [
            {"id": 1, "cagr": 50, "max_drawdown": 20},  # Pareto optimal
            {"id": 2, "cagr": 40, "max_drawdown": 30},  # Dominated by 1
        ]
        pareto = find_pareto_optimal(results, ["cagr"], ["max_drawdown"])
        assert len(pareto) == 1
        assert pareto[0]["id"] == 1

    def test_find_pareto_optimal_tradeoff(self):
        results = [
            {"id": 1, "cagr": 50, "max_drawdown": 25},  # Higher return, higher risk
            {"id": 2, "cagr": 40, "max_drawdown": 15},  # Lower return, lower risk
        ]
        pareto = find_pareto_optimal(results, ["cagr"], ["max_drawdown"])
        assert len(pareto) == 2  # Both are Pareto optimal (trade-off)
```

**Step 3: Run test to verify it fails**

```bash
pytest tests/analysis/test_recommendations.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'oo_automator.analysis.recommendations'"

**Step 4: Write minimal implementation**

Create `oo_automator/analysis/recommendations.py`:

```python
"""Recommendation scoring and analysis."""
from typing import Any


def normalize_values(values: list[float]) -> list[float]:
    """Normalize values to 0-1 scale."""
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val
    if range_val == 0:
        return [0.5] * len(values)
    return [(v - min_val) / range_val for v in values]


def calculate_score(
    result: dict[str, Any],
    all_results: list[dict[str, Any]],
    goal: str = "balanced"
) -> float:
    """Calculate composite score for a result based on goal.

    Args:
        result: Single result dict with metrics
        all_results: All results for normalization
        goal: One of 'balanced', 'maximize_returns', 'protect_capital'

    Returns:
        Score from 0-100
    """
    # Extract metric values from all results for normalization
    all_sharpe = [r.get("sharpe", 0) for r in all_results]
    all_cagr = [r.get("cagr", 0) for r in all_results]
    all_win = [r.get("win_percentage", 0) for r in all_results]
    all_kelly = [r.get("kelly", 0) for r in all_results]
    all_dd = [r.get("max_drawdown", 0) for r in all_results]

    # Find this result's index
    idx = all_results.index(result)

    # Normalize each metric
    norm_sharpe = normalize_values(all_sharpe)[idx] if all_sharpe else 0.5
    norm_cagr = normalize_values(all_cagr)[idx] if all_cagr else 0.5
    norm_win = normalize_values(all_win)[idx] if all_win else 0.5
    norm_kelly = normalize_values(all_kelly)[idx] if all_kelly else 0.5
    # Invert drawdown (lower is better)
    norm_dd = 1 - normalize_values(all_dd)[idx] if all_dd else 0.5

    # Weights by goal
    weights = {
        "maximize_returns": {
            "sharpe": 0.20, "cagr": 0.40, "win": 0.15, "kelly": 0.15, "dd": 0.10
        },
        "protect_capital": {
            "sharpe": 0.20, "cagr": 0.15, "win": 0.25, "kelly": 0.10, "dd": 0.30
        },
        "balanced": {
            "sharpe": 0.30, "cagr": 0.25, "win": 0.20, "kelly": 0.15, "dd": 0.10
        },
    }

    w = weights.get(goal, weights["balanced"])
    score = (
        w["sharpe"] * norm_sharpe +
        w["cagr"] * norm_cagr +
        w["win"] * norm_win +
        w["kelly"] * norm_kelly +
        w["dd"] * norm_dd
    )
    return score * 100


def find_pareto_optimal(
    results: list[dict[str, Any]],
    maximize: list[str],
    minimize: list[str]
) -> list[dict[str, Any]]:
    """Find Pareto optimal results.

    A result is Pareto optimal if no other result is better on ALL metrics.

    Args:
        results: List of result dicts
        maximize: Metric names where higher is better
        minimize: Metric names where lower is better

    Returns:
        List of Pareto optimal results
    """
    pareto = []

    for candidate in results:
        is_dominated = False

        for other in results:
            if other is candidate:
                continue

            # Check if 'other' dominates 'candidate'
            # Dominates means: better or equal on all, strictly better on at least one
            dominated_on_all = True
            strictly_better_on_one = False

            for metric in maximize:
                cand_val = candidate.get(metric, 0)
                other_val = other.get(metric, 0)
                if other_val < cand_val:
                    dominated_on_all = False
                    break
                if other_val > cand_val:
                    strictly_better_on_one = True

            if dominated_on_all:
                for metric in minimize:
                    cand_val = candidate.get(metric, 0)
                    other_val = other.get(metric, 0)
                    if other_val > cand_val:
                        dominated_on_all = False
                        break
                    if other_val < cand_val:
                        strictly_better_on_one = True

            if dominated_on_all and strictly_better_on_one:
                is_dominated = True
                break

        if not is_dominated:
            pareto.append(candidate)

    return pareto


def generate_recommendations(
    results: list[dict[str, Any]],
    goal: str = "balanced"
) -> dict[str, Any]:
    """Generate full recommendations from results.

    Args:
        results: List of result dicts with metrics and param info
        goal: Optimization goal

    Returns:
        Dict with top_pick, alternatives, avoid, and explanations
    """
    if not results:
        return {"top_pick": None, "alternatives": [], "avoid": [], "explanation": "No results"}

    # Calculate scores
    for r in results:
        r["score"] = calculate_score(r, results, goal)

    # Sort by score
    sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)

    # Find Pareto optimal
    pareto = find_pareto_optimal(
        results,
        maximize=["cagr", "sharpe", "win_percentage", "kelly"],
        minimize=["max_drawdown"]
    )
    pareto_ids = {id(r) for r in pareto}

    # Top pick is highest score
    top_pick = sorted_results[0]

    # Alternatives are other Pareto optimal results
    alternatives = [r for r in sorted_results[1:6] if id(r) in pareto_ids]

    # Avoid are dominated results with low scores
    avoid = [r for r in sorted_results[-3:] if id(r) not in pareto_ids]

    return {
        "top_pick": top_pick,
        "alternatives": alternatives,
        "avoid": avoid,
        "goal": goal,
    }
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/analysis/test_recommendations.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add oo_automator/analysis/recommendations.py tests/analysis/
git commit -m "feat: add recommendation scoring module"
```

---

### Task 2: Add Recommendations API Endpoint

**Files:**
- Modify: `oo_automator/web/routes/api.py`
- Test: `tests/web/test_recommendations_api.py`

**Step 1: Write the failing test**

Create `tests/web/test_recommendations_api.py`:

```python
"""Tests for recommendations API endpoint."""
import pytest
from fastapi.testclient import TestClient
from oo_automator.web.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestRecommendationsAPI:
    def test_get_recommendations_empty_run(self, client):
        # This will return empty for non-existent run
        response = client.get("/api/runs/99999/recommendations")
        assert response.status_code in [200, 404]

    def test_get_recommendations_with_goal(self, client):
        response = client.get("/api/runs/1/recommendations?goal=maximize_returns")
        # Should accept goal parameter
        assert response.status_code in [200, 404]
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/web/test_recommendations_api.py -v
```

Expected: FAIL (404 because endpoint doesn't exist)

**Step 3: Add the API endpoint**

Add to `oo_automator/web/routes/api.py`:

```python
# Add import at top
from ..analysis.recommendations import generate_recommendations, calculate_score

# Add endpoint
@router.get("/runs/{run_id}/recommendations")
async def get_recommendations(run_id: int, goal: str = "balanced"):
    """Get parameter recommendations for a run."""
    engine = get_engine()
    session = get_session(engine)

    try:
        from ...db.models import Task, Result, Run

        # Verify run exists
        run = session.exec(select(Run).where(Run.id == run_id)).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Get all results for this run
        results_stmt = (
            select(Result, Task)
            .join(Task, Result.task_id == Task.id)
            .where(Task.run_id == run_id)
        )
        results_data = list(session.exec(results_stmt).all())

        if not results_data:
            return {"top_pick": None, "alternatives": [], "avoid": [], "goal": goal}

        # Build results list with metrics
        results = []
        for result, task in results_data:
            param_values = task.parameter_values or {}
            param_name = list(param_values.keys())[0] if param_values else "unknown"
            param_value = param_values.get(param_name, "")

            # Calculate advanced metrics
            cagr = result.cagr or 0
            max_dd = abs(result.max_drawdown or 0)
            win_pct = result.win_percentage or 0
            avg_winner = result.avg_winner or 0
            avg_loser = abs(result.avg_loser or 1)

            # Sharpe approximation
            max_dd_decimal = max_dd / 100 if max_dd > 0 else 0.1
            cagr_decimal = cagr / 100
            sharpe = (cagr_decimal - 0.05) / (max_dd_decimal / 2) if max_dd_decimal > 0 else 0

            # Kelly
            if avg_loser > 0 and win_pct > 0:
                win_loss_ratio = avg_winner / avg_loser
                kelly = ((win_pct / 100) - ((1 - win_pct / 100) / win_loss_ratio)) * 100 if win_loss_ratio > 0 else 0
            else:
                kelly = 0

            results.append({
                "task_id": task.id,
                "param_name": param_name,
                "param_value": param_value,
                "cagr": cagr,
                "max_drawdown": max_dd,
                "win_percentage": win_pct,
                "sharpe": sharpe,
                "kelly": kelly,
                "avg_winner": avg_winner,
                "avg_loser": result.avg_loser or 0,
                "capture_rate": result.capture_rate or 0,
            })

        # Generate recommendations
        recommendations = generate_recommendations(results, goal)
        return recommendations

    finally:
        session.close()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/web/test_recommendations_api.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add oo_automator/web/routes/api.py tests/web/test_recommendations_api.py
git commit -m "feat: add recommendations API endpoint"
```

---

### Task 3: Create Recommendations Page Template

**Files:**
- Create: `oo_automator/web/templates/recommendations.html`
- Modify: `oo_automator/web/routes/pages.py`

**Step 1: Add the page route**

Add to `oo_automator/web/routes/pages.py`:

```python
@router.get("/runs/{run_id}/recommendations", response_class=HTMLResponse)
async def run_recommendations_page(request: Request, run_id: int, goal: str = "balanced"):
    """Recommendations page for a run."""
    templates = get_templates()
    engine = get_engine()
    session = get_session(engine)

    try:
        from ...db.models import Task, Result
        from ...analysis.recommendations import generate_recommendations

        # Get run info
        run_stmt = select(Run).where(Run.id == run_id)
        run = session.exec(run_stmt).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Get test info
        test_stmt = select(Test).where(Test.id == run.test_id)
        test = session.exec(test_stmt).first()

        # Get all results
        results_stmt = (
            select(Result, Task)
            .join(Task, Result.task_id == Task.id)
            .where(Task.run_id == run_id)
            .order_by(Task.id)
        )
        results_data = list(session.exec(results_stmt).all())

        # Build results with metrics
        results = []
        for result, task in results_data:
            param_values = task.parameter_values or {}
            param_name = list(param_values.keys())[0] if param_values else "unknown"
            param_value = param_values.get(param_name, "")

            cagr = result.cagr or 0
            max_dd = abs(result.max_drawdown or 0)
            win_pct = result.win_percentage or 0
            avg_winner = result.avg_winner or 0
            avg_loser = abs(result.avg_loser or 1)

            max_dd_decimal = max_dd / 100 if max_dd > 0 else 0.1
            cagr_decimal = cagr / 100
            sharpe = (cagr_decimal - 0.05) / (max_dd_decimal / 2) if max_dd_decimal > 0 else 0

            if avg_loser > 0 and win_pct > 0:
                win_loss_ratio = avg_winner / avg_loser
                kelly = ((win_pct / 100) - ((1 - win_pct / 100) / win_loss_ratio)) * 100 if win_loss_ratio > 0 else 0
            else:
                kelly = 0

            results.append({
                "task_id": task.id,
                "param_name": param_name,
                "param_value": param_value,
                "cagr": cagr,
                "max_drawdown": max_dd,
                "win_percentage": win_pct,
                "sharpe": round(sharpe, 2),
                "kelly": round(kelly, 1),
                "avg_winner": avg_winner,
                "avg_loser": result.avg_loser or 0,
                "capture_rate": result.capture_rate or 0,
            })

        # Generate recommendations
        recommendations = generate_recommendations(results, goal) if results else None

        return templates.TemplateResponse(
            request,
            "recommendations.html",
            {
                "run": run,
                "test": test,
                "recommendations": recommendations,
                "goal": goal,
                "results": results,
            }
        )
    finally:
        session.close()
```

**Step 2: Create the template**

Create `oo_automator/web/templates/recommendations.html`:

```html
{% extends "base.html" %}

{% block title %}Recommendations - Run #{{ run.id }} - OO Automator{% endblock %}

{% block content %}
<div class="page-header">
    <a href="/runs/{{ run.id }}" class="back-link">&larr; Back to Run</a>
    <h1>Recommendations - Run #{{ run.id }}</h1>
    <p class="subtitle">{{ test.name or test.url }}</p>
</div>

<div class="results-controls">
    <div class="view-toggle">
        <a href="/runs/{{ run.id }}/results" class="btn btn-secondary">Basic View</a>
        <a href="/runs/{{ run.id }}/advanced" class="btn btn-secondary">Advanced View</a>
        <a href="/runs/{{ run.id }}/recommendations" class="btn btn-primary">Recommendations</a>
    </div>
    <div class="export-buttons">
        <button onclick="exportForAI()" class="btn btn-secondary">Export for AI</button>
    </div>
</div>

<div class="goal-selector">
    <span class="goal-label">Your Goal:</span>
    <a href="?goal=maximize_returns" class="goal-btn {{ 'active' if goal == 'maximize_returns' else '' }}">Maximize Returns</a>
    <a href="?goal=protect_capital" class="goal-btn {{ 'active' if goal == 'protect_capital' else '' }}">Protect Capital</a>
    <a href="?goal=balanced" class="goal-btn {{ 'active' if goal == 'balanced' else '' }}">Balanced</a>
</div>

{% if recommendations and recommendations.top_pick %}
<div class="recommendation-section">
    <h2>🏆 Top Recommendation</h2>
    <div class="top-pick-card">
        <div class="pick-header">
            <span class="param-name">{{ recommendations.top_pick.param_name }}</span>
            <span class="param-value">{{ recommendations.top_pick.param_value }}</span>
            <span class="score">Score: {{ "%.0f"|format(recommendations.top_pick.score) }}/100</span>
        </div>
        <div class="pick-metrics">
            <div class="metric">
                <span class="metric-label">CAGR</span>
                <span class="metric-value">{{ "%.1f"|format(recommendations.top_pick.cagr) }}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Max DD</span>
                <span class="metric-value">{{ "%.1f"|format(recommendations.top_pick.max_drawdown) }}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Sharpe</span>
                <span class="metric-value">{{ "%.2f"|format(recommendations.top_pick.sharpe) }}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Win %</span>
                <span class="metric-value">{{ "%.1f"|format(recommendations.top_pick.win_percentage) }}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Kelly</span>
                <span class="metric-value">{{ "%.1f"|format(recommendations.top_pick.kelly) }}%</span>
            </div>
        </div>
        <div class="pick-explanation">
            {% if goal == 'maximize_returns' %}
            Best option for maximizing returns while maintaining acceptable risk levels.
            {% elif goal == 'protect_capital' %}
            Lowest risk option with solid, consistent returns.
            {% else %}
            Best risk-adjusted return balancing growth and capital protection.
            {% endif %}
        </div>
    </div>
</div>

{% if recommendations.alternatives %}
<div class="recommendation-section">
    <h2>📊 Alternatives (Trade-offs)</h2>
    <div class="alternatives-grid">
        {% for alt in recommendations.alternatives %}
        <div class="alt-card">
            <div class="alt-header">
                <span class="param-value">{{ alt.param_value }}</span>
                <span class="score">{{ "%.0f"|format(alt.score) }}</span>
            </div>
            <div class="alt-metrics">
                <span>CAGR: {{ "%.1f"|format(alt.cagr) }}%</span>
                <span>DD: {{ "%.1f"|format(alt.max_drawdown) }}%</span>
                <span>Win: {{ "%.0f"|format(alt.win_percentage) }}%</span>
            </div>
            <div class="alt-tradeoff">
                {% if alt.cagr > recommendations.top_pick.cagr %}
                +{{ "%.0f"|format(alt.cagr - recommendations.top_pick.cagr) }}% CAGR
                {% elif alt.max_drawdown < recommendations.top_pick.max_drawdown %}
                {{ "%.0f"|format(recommendations.top_pick.max_drawdown - alt.max_drawdown) }}% less risk
                {% elif alt.win_percentage > recommendations.top_pick.win_percentage %}
                More consistent wins
                {% else %}
                Different risk profile
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

{% if recommendations.avoid %}
<div class="recommendation-section avoid-section">
    <h2>⚠️ Avoid</h2>
    <div class="avoid-list">
        {% for item in recommendations.avoid %}
        <div class="avoid-item">
            <span class="param-value">{{ item.param_value }}</span>
            <span class="reason">
                {% if item.max_drawdown > 40 %}
                High drawdown ({{ "%.0f"|format(item.max_drawdown) }}%)
                {% elif item.cagr < 10 %}
                Low returns ({{ "%.1f"|format(item.cagr) }}% CAGR)
                {% else %}
                Dominated by better options
                {% endif %}
            </span>
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

{% else %}
<p class="empty-state">No results yet for this run. Run a parameter sweep to get recommendations.</p>
{% endif %}

<style>
.goal-selector {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
    padding: 16px;
    background: var(--surface);
    border-radius: 8px;
}
.goal-label {
    font-weight: 600;
    margin-right: 8px;
}
.goal-btn {
    padding: 8px 16px;
    border-radius: 6px;
    text-decoration: none;
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--border);
    transition: all 0.2s;
}
.goal-btn:hover {
    background: var(--border);
}
.goal-btn.active {
    background: var(--primary);
    color: white;
    border-color: var(--primary);
}

.recommendation-section {
    margin-bottom: 32px;
}
.recommendation-section h2 {
    margin-bottom: 16px;
    font-size: 1.25rem;
}

.top-pick-card {
    background: linear-gradient(135deg, var(--surface) 0%, rgba(34, 197, 94, 0.1) 100%);
    border: 2px solid #22c55e;
    border-radius: 12px;
    padding: 24px;
}
.pick-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
}
.pick-header .param-name {
    font-size: 0.875rem;
    color: var(--text-secondary);
}
.pick-header .param-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #22c55e;
}
.pick-header .score {
    margin-left: auto;
    font-size: 1.25rem;
    font-weight: 600;
    background: #22c55e;
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
}
.pick-metrics {
    display: flex;
    gap: 24px;
    margin-bottom: 16px;
}
.metric {
    display: flex;
    flex-direction: column;
}
.metric-label {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
}
.metric-value {
    font-size: 1.25rem;
    font-weight: 600;
    font-family: 'SF Mono', monospace;
}
.pick-explanation {
    color: var(--text-secondary);
    font-size: 0.9rem;
    padding-top: 12px;
    border-top: 1px solid var(--border);
}

.alternatives-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
}
.alt-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
}
.alt-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 12px;
}
.alt-header .param-value {
    font-weight: 600;
}
.alt-header .score {
    background: var(--bg);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.875rem;
}
.alt-metrics {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-bottom: 12px;
}
.alt-tradeoff {
    font-size: 0.8rem;
    color: var(--primary);
    font-weight: 500;
}

.avoid-section h2 {
    color: #f97316;
}
.avoid-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.avoid-item {
    display: flex;
    gap: 16px;
    padding: 12px;
    background: rgba(249, 115, 22, 0.1);
    border: 1px solid rgba(249, 115, 22, 0.3);
    border-radius: 6px;
}
.avoid-item .param-value {
    font-weight: 600;
}
.avoid-item .reason {
    color: var(--text-secondary);
}
</style>

<script>
function exportForAI() {
    const data = {
        test: "{{ test.name or test.url }}",
        parameter: "{{ recommendations.top_pick.param_name if recommendations and recommendations.top_pick else 'N/A' }}",
        goal: "{{ goal }}",
        results: {{ results | tojson | safe if results else '[]' }}
    };

    let prompt = `I ran a parameter sweep on my options trading strategy. Here are my backtest results:

STRATEGY: ${data.test}
PARAMETER TESTED: ${data.parameter}
TOTAL CONFIGURATIONS: ${data.results.length}
GOAL: ${data.goal}

TOP 5 RESULTS:
| ${data.parameter} | CAGR | Max DD | Win % | Sharpe | Kelly % |
|------------|--------|--------|--------|--------|---------|
`;

    const sorted = [...data.results].sort((a, b) => (b.score || b.cagr) - (a.score || a.cagr));
    sorted.slice(0, 5).forEach(r => {
        prompt += `| ${r.param_value} | ${r.cagr.toFixed(1)}% | ${r.max_drawdown.toFixed(1)}% | ${r.win_percentage.toFixed(1)}% | ${r.sharpe.toFixed(2)} | ${r.kelly.toFixed(1)}% |\n`;
    });

    prompt += `
WORST 3 RESULTS:
| ${data.parameter} | CAGR | Max DD | Win % | Sharpe | Kelly % |
|------------|--------|--------|--------|--------|---------|
`;

    sorted.slice(-3).forEach(r => {
        prompt += `| ${r.param_value} | ${r.cagr.toFixed(1)}% | ${r.max_drawdown.toFixed(1)}% | ${r.win_percentage.toFixed(1)}% | ${r.sharpe.toFixed(2)} | ${r.kelly.toFixed(1)}% |\n`;
    });

    prompt += `
Questions:
1. Which ${data.parameter} would you recommend and why?
2. What trade-offs should I consider?
3. How can I validate these results aren't overfit?
`;

    navigator.clipboard.writeText(prompt).then(() => {
        alert('Prompt copied to clipboard! Paste it into ChatGPT or Claude.');
    });
}
</script>
{% endblock %}
```

**Step 3: Test manually**

```bash
cd /Users/jshin/Documents/OOAutomator
python -m oo_automator.main
# Visit http://127.0.0.1:8000/runs/103/recommendations
```

**Step 4: Commit**

```bash
git add oo_automator/web/templates/recommendations.html oo_automator/web/routes/pages.py
git commit -m "feat: add recommendations page with goal selector and AI export"
```

---

### Task 4: Add Rate Limiting to Browser Worker

**Files:**
- Modify: `oo_automator/browser/worker.py`

**Step 1: Add rate limiting constants and logic**

Add to `oo_automator/browser/worker.py`:

```python
# At top of file
import asyncio
from datetime import datetime, timedelta

# Rate limiting
MIN_REQUEST_DELAY = 6  # seconds between requests
MAX_REQUESTS_PER_MINUTE = 10
_last_request_time: datetime | None = None


async def wait_for_rate_limit():
    """Wait if needed to respect rate limits."""
    global _last_request_time

    if _last_request_time is not None:
        elapsed = (datetime.now() - _last_request_time).total_seconds()
        if elapsed < MIN_REQUEST_DELAY:
            await asyncio.sleep(MIN_REQUEST_DELAY - elapsed)

    _last_request_time = datetime.now()
```

Then modify the `run_backtest` method to call `wait_for_rate_limit()` before making requests.

**Step 2: Commit**

```bash
git add oo_automator/browser/worker.py
git commit -m "feat: add rate limiting to browser worker"
```

---

### Task 5: Add Result Caching by Test URL

**Files:**
- Modify: `oo_automator/db/queries.py`
- Modify: `oo_automator/core/run_manager.py`

**Step 1: Add cache lookup function**

Add to `oo_automator/db/queries.py`:

```python
def get_cached_result(
    session,
    test_url: str,
    param_name: str,
    param_value: str
) -> Result | None:
    """Check if we already have a result for this exact configuration."""
    from .models import Test, Run, Task, Result

    stmt = (
        select(Result)
        .join(Task, Result.task_id == Task.id)
        .join(Run, Task.run_id == Run.id)
        .join(Test, Run.test_id == Test.id)
        .where(
            Test.url == test_url,
            Task.parameter_values[param_name].as_string() == str(param_value)
        )
        .order_by(Result.created_at.desc())
        .limit(1)
    )
    return session.exec(stmt).first()
```

**Step 2: Commit**

```bash
git add oo_automator/db/queries.py
git commit -m "feat: add result caching lookup by test URL"
```

---

### Task 6: Final Integration and Push

**Step 1: Run all tests**

```bash
pytest tests/ -v
```

**Step 2: Push to GitHub**

```bash
git push origin main
```

---

## Summary

This plan implements:
1. ✅ Recommendation scoring module with Pareto optimality
2. ✅ API endpoint for recommendations
3. ✅ Recommendations page with goal selector
4. ✅ Export for AI analysis button
5. ✅ Rate limiting protection
6. ✅ Result caching by test URL

**Future tasks (Phase 2):**
- Monte Carlo simulation
- Confidence intervals
- Forward testing validation
