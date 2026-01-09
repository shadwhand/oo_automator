"""Trade log parsing and aggregation for analytics charts."""
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, time, datetime
from typing import Any


@dataclass
class TradeRecord:
    """Represents a single trade from an OptionOmega trade log."""

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
    pl: float
    pl_percent: float
    premium: float

    # Trade details
    legs: str
    num_contracts: int
    reason_for_close: str

    # Market data
    opening_vix: float
    closing_vix: float
    gap: float
    movement: float
    opening_price: float
    closing_price: float

    # Risk metrics
    max_profit: float
    max_loss: float
    margin_req: float


def _parse_currency(value: str) -> float:
    """Parse currency string like '$13,376' or '-$155' to float."""
    if not value:
        return 0.0
    cleaned = re.sub(r'[,$]', '', str(value).strip())
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_percentage(value: str) -> float:
    """Parse percentage string like '68.2%' to float."""
    if not value:
        return 0.0
    cleaned = str(value).replace('%', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_float(value: str) -> float:
    """Parse a float value, handling currency and percentage formats."""
    if not value:
        return 0.0
    value_str = str(value).strip()
    if '$' in value_str:
        return _parse_currency(value_str)
    if '%' in value_str:
        return _parse_percentage(value_str)
    try:
        return float(value_str.replace(',', ''))
    except ValueError:
        return 0.0


def _parse_int(value: str) -> int:
    """Parse an integer value."""
    if not value:
        return 0
    try:
        return int(float(str(value).strip().replace(',', '')))
    except ValueError:
        return 0


def _parse_date(value: str) -> date:
    """Parse a date string in various formats."""
    if not value:
        return date.today()
    value_str = str(value).strip()

    # Try different date formats
    formats = [
        "%Y-%m-%d",       # 2025-09-25
        "%m/%d/%Y",       # 09/25/2025
        "%Y-%m-%d %H:%M:%S",  # 2025-09-25 13:23:00 (combined datetime)
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value_str, fmt)
            return parsed.date()
        except ValueError:
            continue

    # If none worked, return today's date
    return date.today()


def _parse_time(value: str) -> time:
    """Parse a time string in various formats."""
    if not value:
        return time(0, 0, 0)
    value_str = str(value).strip()

    # Try different time formats
    formats = [
        "%H:%M:%S",       # 13:23:00
        "%H:%M",          # 13:23
        "%Y-%m-%d %H:%M:%S",  # 2025-09-25 13:23:00 (extract time from combined)
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(value_str, fmt)
            return parsed.time()
        except ValueError:
            continue

    # If none worked, return midnight
    return time(0, 0, 0)


# Column name mappings to handle variations
COLUMN_MAPPINGS = {
    # Date/Time columns
    "date_opened": ["Date Opened", "Opened On"],
    "time_opened": ["Time Opened"],
    "date_closed": ["Date Closed", "Closed On"],
    "time_closed": ["Time Closed"],

    # P/L columns
    "pl": ["P/L"],
    "pl_percent": ["P/L %"],
    "premium": ["Premium"],

    # Trade details
    "legs": ["Legs"],
    "num_contracts": ["No. of Contracts"],
    "reason_for_close": ["Reason For Close", "Reason for Close"],

    # Market data
    "opening_vix": ["Opening VIX"],
    "closing_vix": ["Closing VIX"],
    "gap": ["Gap"],
    "movement": ["Movement"],
    "opening_price": ["Opening Price"],
    "closing_price": ["Closing Price"],

    # Risk metrics
    "max_profit": ["Max Profit"],
    "max_loss": ["Max Loss"],
    "margin_req": ["Margin Req.", "Margin Req"],
}


def _build_column_index(headers: list[str]) -> dict[str, int]:
    """Build a mapping from field names to column indices."""
    header_lower_map = {h.strip().lower(): i for i, h in enumerate(headers)}
    column_index = {}

    for field, variations in COLUMN_MAPPINGS.items():
        for variation in variations:
            if variation.lower() in header_lower_map:
                column_index[field] = header_lower_map[variation.lower()]
                break

    return column_index


def _get_value(row: list[str], column_index: dict[str, int], field: str, default: str = "") -> str:
    """Get a value from a row by field name."""
    if field in column_index:
        idx = column_index[field]
        if idx < len(row):
            return row[idx]
    return default


def _parse_combined_datetime(value: str) -> tuple[date, time]:
    """Parse a combined datetime string like '2025-09-25 13:23:00'."""
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
        return parsed.date(), parsed.time()
    except ValueError:
        return date.today(), time(0, 0, 0)


def parse_trade_log_csv(
    csv_path: str,
    run_id: int,
    parameter_name: str,
    parameter_value: str,
) -> list[TradeRecord]:
    """Parse a trade log CSV file and return a list of TradeRecord objects.

    Args:
        csv_path: Path to the trade log CSV file.
        run_id: ID of the backtest run.
        parameter_name: Name of the parameter being tested.
        parameter_value: Value of the parameter being tested.

    Returns:
        List of TradeRecord objects parsed from the CSV.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
    """
    trades = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader, [])

        if not headers:
            return []

        column_index = _build_column_index(headers)

        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue

            # Handle combined datetime columns (like "Opened On" = "2025-09-25 13:23:00")
            date_opened_str = _get_value(row, column_index, "date_opened")
            time_opened_str = _get_value(row, column_index, "time_opened")
            date_closed_str = _get_value(row, column_index, "date_closed")
            time_closed_str = _get_value(row, column_index, "time_closed")

            # Check if date column contains combined datetime
            if " " in date_opened_str and not time_opened_str:
                date_opened, time_opened = _parse_combined_datetime(date_opened_str)
            else:
                date_opened = _parse_date(date_opened_str)
                time_opened = _parse_time(time_opened_str)

            if " " in date_closed_str and not time_closed_str:
                date_closed, time_closed = _parse_combined_datetime(date_closed_str)
            else:
                date_closed = _parse_date(date_closed_str)
                time_closed = _parse_time(time_closed_str)

            try:
                trade = TradeRecord(
                    run_id=run_id,
                    parameter_name=parameter_name,
                    parameter_value=parameter_value,
                    date_opened=date_opened,
                    time_opened=time_opened,
                    date_closed=date_closed,
                    time_closed=time_closed,
                    pl=_parse_float(_get_value(row, column_index, "pl")),
                    pl_percent=_parse_float(_get_value(row, column_index, "pl_percent")),
                    premium=_parse_float(_get_value(row, column_index, "premium")),
                    legs=_get_value(row, column_index, "legs"),
                    num_contracts=_parse_int(_get_value(row, column_index, "num_contracts")),
                    reason_for_close=_get_value(row, column_index, "reason_for_close"),
                    opening_vix=_parse_float(_get_value(row, column_index, "opening_vix")),
                    closing_vix=_parse_float(_get_value(row, column_index, "closing_vix")),
                    gap=_parse_float(_get_value(row, column_index, "gap")),
                    movement=_parse_float(_get_value(row, column_index, "movement")),
                    opening_price=_parse_float(_get_value(row, column_index, "opening_price")),
                    closing_price=_parse_float(_get_value(row, column_index, "closing_price")),
                    max_profit=_parse_float(_get_value(row, column_index, "max_profit")),
                    max_loss=_parse_float(_get_value(row, column_index, "max_loss")),
                    margin_req=_parse_float(_get_value(row, column_index, "margin_req")),
                )
                trades.append(trade)
            except Exception:
                # Skip rows that can't be parsed
                continue

    return trades


def _calculate_duration_minutes(
    date_opened: date,
    time_opened: time,
    date_closed: date,
    time_closed: time,
) -> float:
    """Calculate trade duration in minutes."""
    opened_dt = datetime.combine(date_opened, time_opened)
    closed_dt = datetime.combine(date_closed, time_closed)
    duration = closed_dt - opened_dt
    return duration.total_seconds() / 60.0


def aggregate_for_charts(trades: list[TradeRecord]) -> dict[str, Any]:
    """Aggregate trade records for charting.

    Args:
        trades: List of TradeRecord objects to aggregate.

    Returns:
        Dictionary containing aggregated data for various chart types:
        - daily_pl: {date_str: {param_value: total_pl}}
        - cumulative: {date_str: {param_value: cumulative_pl}}
        - stop_loss_counts: {param_value: count}
        - reason_counts: {param_value: {reason: count}}
        - vix_data: [{"vix": x, "pl": y, "param": value}]
        - duration_avg: {param_value: avg_minutes}
    """
    if not trades:
        return {
            "daily_pl": {},
            "cumulative": {},
            "stop_loss_counts": {},
            "reason_counts": {},
            "vix_data": [],
            "duration_avg": {},
        }

    # Initialize aggregation structures
    daily_pl: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    stop_loss_counts: dict[str, int] = defaultdict(int)
    reason_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    vix_data: list[dict[str, Any]] = []
    durations: dict[str, list[float]] = defaultdict(list)

    # Aggregate data
    for trade in trades:
        date_str = trade.date_opened.isoformat()
        param = trade.parameter_value

        # Daily P/L
        daily_pl[date_str][param] += trade.pl

        # Stop loss counts
        if trade.reason_for_close.lower() == "stop loss":
            stop_loss_counts[param] += 1

        # Reason counts
        reason_counts[param][trade.reason_for_close] += 1

        # VIX data for scatter plots
        vix_data.append({
            "vix": trade.opening_vix,
            "pl": trade.pl,
            "param": param,
        })

        # Duration calculation
        duration = _calculate_duration_minutes(
            trade.date_opened,
            trade.time_opened,
            trade.date_closed,
            trade.time_closed,
        )
        durations[param].append(duration)

    # Calculate cumulative P/L
    cumulative: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    # Get all unique parameter values
    all_params = set()
    for date_str in daily_pl:
        all_params.update(daily_pl[date_str].keys())

    # Calculate running totals for each parameter
    running_totals: dict[str, float] = defaultdict(float)

    for date_str in sorted(daily_pl.keys()):
        for param in daily_pl[date_str]:
            running_totals[param] += daily_pl[date_str][param]
            cumulative[date_str][param] = running_totals[param]

    # Calculate average durations
    duration_avg: dict[str, float] = {}
    for param, dur_list in durations.items():
        if dur_list:
            duration_avg[param] = sum(dur_list) / len(dur_list)

    # Convert defaultdicts to regular dicts for JSON serialization
    return {
        "daily_pl": {k: dict(v) for k, v in daily_pl.items()},
        "cumulative": {k: dict(v) for k, v in cumulative.items()},
        "stop_loss_counts": dict(stop_loss_counts),
        "reason_counts": {k: dict(v) for k, v in reason_counts.items()},
        "vix_data": vix_data,
        "duration_avg": duration_avg,
    }
