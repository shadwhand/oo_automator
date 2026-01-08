"""Recommendation scoring module for identifying optimal parameter configurations."""


def normalize_values(values: list[float]) -> list[float]:
    """Normalize a list of values to 0-1 scale.

    Args:
        values: List of numeric values to normalize.

    Returns:
        List of normalized values between 0 and 1.
        If all values are the same, returns 0.5 for each.
    """
    if not values:
        return []

    min_val = min(values)
    max_val = max(values)

    # If all values are the same, return 0.5 for each
    if max_val == min_val:
        return [0.5] * len(values)

    # Normalize to 0-1 scale
    range_val = max_val - min_val
    return [(v - min_val) / range_val for v in values]


# Weight configurations for different goals
GOAL_WEIGHTS = {
    "balanced": {
        "sharpe": 0.3,
        "cagr": 0.25,
        "win_percentage": 0.2,
        "kelly": 0.15,
        "max_drawdown": 0.1,
    },
    "maximize_returns": {
        "cagr": 0.4,
        "sharpe": 0.2,
        "win_percentage": 0.15,
        "kelly": 0.15,
        "max_drawdown": 0.1,
    },
    "protect_capital": {
        "max_drawdown": 0.3,
        "win_percentage": 0.25,
        "sharpe": 0.2,
        "cagr": 0.15,
        "kelly": 0.1,
    },
}

# Metrics where higher is better
MAXIMIZE_METRICS = {"cagr", "sharpe", "win_percentage", "kelly"}
# Metrics where lower is better
MINIMIZE_METRICS = {"max_drawdown"}


def calculate_score(result: dict, all_results: list[dict], goal: str = "balanced") -> float:
    """Calculate composite score for a result based on goal weighting.

    Args:
        result: The result dict to score, containing metric values.
        all_results: All results to normalize against.
        goal: The optimization goal - 'balanced', 'maximize_returns', or 'protect_capital'.

    Returns:
        Score from 0-100 based on weighted normalized metrics.
    """
    weights = GOAL_WEIGHTS.get(goal, GOAL_WEIGHTS["balanced"])
    metrics = list(weights.keys())

    # Extract metric values for normalization
    metric_values = {metric: [r[metric] for r in all_results] for metric in metrics}

    # Normalize each metric
    normalized_metrics = {
        metric: normalize_values(metric_values[metric]) for metric in metrics
    }

    # Find the index of this result in all_results
    result_idx = all_results.index(result)

    # Calculate weighted score
    score = 0.0
    for metric, weight in weights.items():
        normalized_value = normalized_metrics[metric][result_idx]

        # For minimize metrics (like drawdown), invert so lower = better
        if metric in MINIMIZE_METRICS:
            normalized_value = 1.0 - normalized_value

        score += normalized_value * weight

    # Convert to 0-100 scale
    return score * 100


def find_pareto_optimal(
    results: list[dict],
    maximize: list[str],
    minimize: list[str],
) -> list[dict]:
    """Find Pareto optimal results from a list.

    A result is Pareto optimal if no other result is better in ALL metrics.
    Results on the Pareto front represent optimal tradeoffs.

    Args:
        results: List of result dicts with metric values.
        maximize: List of metric names where higher is better.
        minimize: List of metric names where lower is better.

    Returns:
        List of results on the Pareto front.
    """
    if not results:
        return []

    def dominates(a: dict, b: dict) -> bool:
        """Check if result a dominates result b.

        a dominates b if a is at least as good in all metrics and strictly
        better in at least one metric.
        """
        at_least_as_good = True
        strictly_better = False

        for metric in maximize:
            if a[metric] < b[metric]:
                at_least_as_good = False
                break
            if a[metric] > b[metric]:
                strictly_better = True

        if not at_least_as_good:
            return False

        for metric in minimize:
            if a[metric] > b[metric]:
                at_least_as_good = False
                break
            if a[metric] < b[metric]:
                strictly_better = True

        return at_least_as_good and strictly_better

    pareto_optimal = []
    for candidate in results:
        is_dominated = False
        for other in results:
            if other is candidate:
                continue
            if dominates(other, candidate):
                is_dominated = True
                break
        if not is_dominated:
            pareto_optimal.append(candidate)

    return pareto_optimal


def generate_recommendations(
    results: list[dict],
    goal: str = "balanced",
) -> dict:
    """Generate recommendations from backtesting results.

    Analyzes results to identify:
    - top_pick: The highest scoring result
    - alternatives: Other Pareto optimal results (up to 5)
    - avoid: Dominated results with low scores (up to 3)

    Args:
        results: List of backtesting result dicts with metric values.
        goal: The optimization goal - 'balanced', 'maximize_returns', or 'protect_capital'.

    Returns:
        Dict with keys: top_pick, alternatives, avoid, goal
    """
    if not results:
        return {
            "top_pick": None,
            "alternatives": [],
            "avoid": [],
            "goal": goal,
        }

    # Calculate scores for all results
    scored_results = [
        (result, calculate_score(result, results, goal=goal))
        for result in results
    ]

    # Sort by score descending
    scored_results.sort(key=lambda x: x[1], reverse=True)

    # Top pick is highest scored
    top_pick = scored_results[0][0]

    # Find Pareto optimal results
    pareto_optimal = find_pareto_optimal(
        results,
        maximize=list(MAXIMIZE_METRICS),
        minimize=list(MINIMIZE_METRICS),
    )

    # Pareto optimal set (excluding top pick)
    pareto_ids = {id(r) for r in pareto_optimal}
    top_pick_id = id(top_pick)

    # Alternatives: Pareto optimal results excluding top pick, sorted by score
    alternatives = [
        result for result, score in scored_results
        if id(result) in pareto_ids and id(result) != top_pick_id
    ][:5]

    # Dominated results (not Pareto optimal), sorted by score ascending (worst first)
    dominated = [
        result for result, score in scored_results
        if id(result) not in pareto_ids
    ]
    # Take the worst 3 dominated results
    avoid = dominated[-3:] if len(dominated) >= 3 else dominated
    # Reverse to put worst first
    avoid = list(reversed(avoid))

    return {
        "top_pick": top_pick,
        "alternatives": alternatives,
        "avoid": avoid,
        "goal": goal,
    }
