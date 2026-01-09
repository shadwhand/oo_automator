"""Analysis module for OO Automator analytics."""
from .charts import TradeRecord, parse_trade_log_csv, aggregate_for_charts
from .recommendations import (
    normalize_values,
    calculate_score,
    find_pareto_optimal,
    generate_recommendations,
)

__all__ = [
    "TradeRecord",
    "parse_trade_log_csv",
    "aggregate_for_charts",
    "normalize_values",
    "calculate_score",
    "find_pareto_optimal",
    "generate_recommendations",
]
