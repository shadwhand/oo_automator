"""Tests for the charts module - trade log parsing and aggregation."""
import csv
import tempfile
from datetime import date, time
from pathlib import Path

import pytest

from oo_automator.analysis.charts import (
    TradeRecord,
    parse_trade_log_csv,
    aggregate_for_charts,
)


class TestTradeRecord:
    """Tests for the TradeRecord dataclass."""

    def test_creates_trade_record_with_all_fields(self):
        """Test creating a TradeRecord with all required fields."""
        trade = TradeRecord(
            run_id=1,
            parameter_name="entry_time",
            parameter_value="09:30",
            date_opened=date(2025, 9, 25),
            time_opened=time(13, 23, 0),
            date_closed=date(2025, 9, 25),
            time_closed=time(16, 0, 0),
            pl=231.52,
            pl_percent=98.52,
            premium=235.0,
            legs="1 Sep 25 6610 C STO 2.55 | 1 Sep 25 6700 C BTO 0.05",
            num_contracts=1,
            reason_for_close="Expired",
            opening_vix=15.5,
            closing_vix=16.2,
            gap=-29.78,
            movement=-14.88,
            opening_price=6593.31,
            closing_price=6604.72,
            max_profit=100.0,
            max_loss=-119.15,
            margin_req=8440.0,
        )
        assert trade.run_id == 1
        assert trade.parameter_name == "entry_time"
        assert trade.parameter_value == "09:30"
        assert trade.date_opened == date(2025, 9, 25)
        assert trade.time_opened == time(13, 23, 0)
        assert trade.pl == 231.52
        assert trade.reason_for_close == "Expired"

    def test_trade_record_is_dataclass(self):
        """Test that TradeRecord is a dataclass with proper attributes."""
        import dataclasses
        assert dataclasses.is_dataclass(TradeRecord)

    def test_trade_record_has_expected_fields(self):
        """Test that TradeRecord has all expected fields."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(TradeRecord)}
        expected_fields = {
            "run_id", "parameter_name", "parameter_value",
            "date_opened", "time_opened", "date_closed", "time_closed",
            "pl", "pl_percent", "premium",
            "legs", "num_contracts", "reason_for_close",
            "opening_vix", "closing_vix", "gap", "movement",
            "opening_price", "closing_price",
            "max_profit", "max_loss", "margin_req",
        }
        assert field_names == expected_fields


class TestParseTradeLogCsv:
    """Tests for parse_trade_log_csv function."""

    @pytest.fixture
    def sample_csv_path(self, tmp_path):
        """Create a sample trade log CSV file."""
        csv_file = tmp_path / "trade_log.csv"
        csv_content = '''"Date Opened","Time Opened","Opening Price","Legs","Premium","Closing Price","Date Closed","Time Closed","Avg. Closing Cost","Reason For Close","P/L","No. of Contracts","Funds at Close","Margin Req.","Strategy","Opening Commissions + Fees","Closing Commissions + Fees","Opening Short/Long Ratio","Closing Short/Long Ratio","Gap","Movement","Max Profit","Max Loss"
"2025-09-25","13:23:00",6593.31,"1 Sep 25 6610 C STO 2.55 | 1 Sep 25 6700 C BTO 0.05",235,6604.72,"2025-09-25","16:00:00",0,"Expired",231.52,1,252879.84,8440,"",3.48,0,51,1,-29.78,-14.88,100,-119.15
"2025-09-25","13:23:00",6593.31,"1 Sep 25 6575 P STO 3.40 | 1 Sep 25 6485 P BTO 0.15",310,6574.61,"2025-09-25","14:03:00",895,"Stop Loss",-591.04,1,252648.32,8440,"",3.48,2.56,22.67,89.5,-29.78,-14.88,40.32,-233.87
"2025-09-24","13:23:00",6636.61,"1 Sep 24 6645 C STO 2.95 | 1 Sep 24 6735 C BTO 0.05",275,6637.97,"2025-09-24","16:00:00",0,"Expired",271.52,1,253239.36,8475,"",3.48,0,59,1,12.87,-33.18,100,-70.91
'''
        csv_file.write_text(csv_content)
        return str(csv_file)

    def test_parses_csv_returns_list_of_trade_records(self, sample_csv_path):
        """Test that parsing CSV returns a list of TradeRecord objects."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert isinstance(trades, list)
        assert len(trades) == 3
        assert all(isinstance(t, TradeRecord) for t in trades)

    def test_parses_dates_correctly(self, sample_csv_path):
        """Test that dates are parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].date_opened == date(2025, 9, 25)
        assert trades[0].date_closed == date(2025, 9, 25)
        assert trades[2].date_opened == date(2025, 9, 24)

    def test_parses_times_correctly(self, sample_csv_path):
        """Test that times are parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].time_opened == time(13, 23, 0)
        assert trades[0].time_closed == time(16, 0, 0)
        assert trades[1].time_closed == time(14, 3, 0)

    def test_parses_pl_values_correctly(self, sample_csv_path):
        """Test that P/L values are parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].pl == 231.52
        assert trades[1].pl == -591.04
        assert trades[2].pl == 271.52

    def test_parses_reason_for_close(self, sample_csv_path):
        """Test that reason for close is parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].reason_for_close == "Expired"
        assert trades[1].reason_for_close == "Stop Loss"

    def test_parses_market_data_correctly(self, sample_csv_path):
        """Test that market data fields are parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].gap == -29.78
        assert trades[0].movement == -14.88
        assert trades[0].opening_price == 6593.31
        assert trades[0].closing_price == 6604.72

    def test_parses_risk_metrics_correctly(self, sample_csv_path):
        """Test that risk metrics are parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].max_profit == 100.0
        assert trades[0].max_loss == -119.15
        assert trades[0].margin_req == 8440.0

    def test_parses_premium_correctly(self, sample_csv_path):
        """Test that premium is parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].premium == 235.0
        assert trades[1].premium == 310.0

    def test_parses_legs_correctly(self, sample_csv_path):
        """Test that legs string is parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].legs == "1 Sep 25 6610 C STO 2.55 | 1 Sep 25 6700 C BTO 0.05"

    def test_parses_num_contracts_correctly(self, sample_csv_path):
        """Test that number of contracts is parsed correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=1, parameter_name="entry_time", parameter_value="13:23")
        assert trades[0].num_contracts == 1

    def test_sets_run_id_and_parameter_info(self, sample_csv_path):
        """Test that run_id and parameter info are set correctly."""
        trades = parse_trade_log_csv(sample_csv_path, run_id=42, parameter_name="stop_loss", parameter_value="200%")
        assert all(t.run_id == 42 for t in trades)
        assert all(t.parameter_name == "stop_loss" for t in trades)
        assert all(t.parameter_value == "200%" for t in trades)

    def test_handles_empty_csv(self, tmp_path):
        """Test handling of empty CSV file (headers only)."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text('"Date Opened","Time Opened","Opening Price","Legs","Premium","Closing Price","Date Closed","Time Closed","Avg. Closing Cost","Reason For Close","P/L","No. of Contracts","Funds at Close","Margin Req.","Strategy","Opening Commissions + Fees","Closing Commissions + Fees","Opening Short/Long Ratio","Closing Short/Long Ratio","Gap","Movement","Max Profit","Max Loss"\n')
        trades = parse_trade_log_csv(str(csv_file), run_id=1, parameter_name="test", parameter_value="val")
        assert trades == []

    def test_handles_currency_format_in_pl(self, tmp_path):
        """Test handling of currency-formatted P/L values like '$231.52'."""
        csv_file = tmp_path / "currency.csv"
        csv_content = '''"Date Opened","Time Opened","Opening Price","Legs","Premium","Closing Price","Date Closed","Time Closed","Avg. Closing Cost","Reason For Close","P/L","No. of Contracts","Funds at Close","Margin Req.","Strategy","Opening Commissions + Fees","Closing Commissions + Fees","Opening Short/Long Ratio","Closing Short/Long Ratio","Gap","Movement","Max Profit","Max Loss"
"2025-09-25","13:23:00",6593.31,"1 Sep 25 6610 C STO 2.55 | 1 Sep 25 6700 C BTO 0.05","$235.00","$6,604.72","2025-09-25","16:00:00","$0.00","Expired","$231.52",1,252879.84,"$8,440.00","",3.48,0,51,1,-29.78,-14.88,100,-119.15
'''
        csv_file.write_text(csv_content)
        trades = parse_trade_log_csv(str(csv_file), run_id=1, parameter_name="test", parameter_value="val")
        assert trades[0].pl == 231.52
        assert trades[0].premium == 235.0

    def test_handles_percentage_format_in_pl_percent(self, tmp_path):
        """Test handling of percentage-formatted values."""
        csv_file = tmp_path / "percentage.csv"
        csv_content = '''"Date Opened","Time Opened","Opening Price","Legs","Premium","Closing Price","Date Closed","Time Closed","Avg. Closing Cost","Reason For Close","P/L","P/L %","No. of Contracts","Funds at Close","Margin Req.","Strategy","Opening Commissions + Fees","Closing Commissions + Fees","Opening Short/Long Ratio","Closing Short/Long Ratio","Gap","Movement","Max Profit","Max Loss"
"2025-09-25","13:23:00",6593.31,"1 Sep 25 6610 C STO 2.55 | 1 Sep 25 6700 C BTO 0.05",235,6604.72,"2025-09-25","16:00:00",0,"Expired",231.52,"98.52%",1,252879.84,8440,"",3.48,0,51,1,-29.78,-14.88,100,-119.15
'''
        csv_file.write_text(csv_content)
        trades = parse_trade_log_csv(str(csv_file), run_id=1, parameter_name="test", parameter_value="val")
        assert trades[0].pl_percent == 98.52

    def test_handles_alternate_column_names(self, tmp_path):
        """Test handling of alternate column name formats."""
        csv_file = tmp_path / "alternate.csv"
        # OptionOmega sometimes uses different column names
        csv_content = '''"Opened On","Opening Price","Legs","Premium","Closing Price","Closed On","Closing Cost","Reason for Close","P/L","P/L %"
"2025-09-25 13:23:00",6593.31,"1 Sep 25 6610 C STO 2.55 | 1 Sep 25 6700 C BTO 0.05",235,6604.72,"2025-09-25 16:00:00",0,"Expired",231.52,"98.52%"
'''
        csv_file.write_text(csv_content)
        trades = parse_trade_log_csv(str(csv_file), run_id=1, parameter_name="test", parameter_value="val")
        assert len(trades) == 1
        assert trades[0].pl == 231.52

    def test_handles_nonexistent_file(self):
        """Test that nonexistent file raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            parse_trade_log_csv("/nonexistent/path/file.csv", run_id=1, parameter_name="test", parameter_value="val")


class TestAggregateForCharts:
    """Tests for aggregate_for_charts function."""

    @pytest.fixture
    def sample_trades(self):
        """Create sample TradeRecord objects for testing."""
        return [
            # Day 1 - parameter value "09:30"
            TradeRecord(
                run_id=1, parameter_name="entry_time", parameter_value="09:30",
                date_opened=date(2025, 9, 25), time_opened=time(9, 30, 0),
                date_closed=date(2025, 9, 25), time_closed=time(16, 0, 0),
                pl=200.0, pl_percent=85.0, premium=235.0,
                legs="test", num_contracts=1, reason_for_close="Expired",
                opening_vix=15.0, closing_vix=16.0, gap=-10.0, movement=5.0,
                opening_price=6000.0, closing_price=6010.0,
                max_profit=100.0, max_loss=-100.0, margin_req=8000.0,
            ),
            TradeRecord(
                run_id=1, parameter_name="entry_time", parameter_value="09:30",
                date_opened=date(2025, 9, 25), time_opened=time(9, 30, 0),
                date_closed=date(2025, 9, 25), time_closed=time(14, 0, 0),
                pl=-150.0, pl_percent=-63.0, premium=235.0,
                legs="test", num_contracts=1, reason_for_close="Stop Loss",
                opening_vix=15.0, closing_vix=17.0, gap=-10.0, movement=5.0,
                opening_price=6000.0, closing_price=5990.0,
                max_profit=100.0, max_loss=-100.0, margin_req=8000.0,
            ),
            # Day 1 - parameter value "10:00"
            TradeRecord(
                run_id=2, parameter_name="entry_time", parameter_value="10:00",
                date_opened=date(2025, 9, 25), time_opened=time(10, 0, 0),
                date_closed=date(2025, 9, 25), time_closed=time(16, 0, 0),
                pl=180.0, pl_percent=75.0, premium=240.0,
                legs="test", num_contracts=1, reason_for_close="Expired",
                opening_vix=16.0, closing_vix=15.5, gap=-8.0, movement=3.0,
                opening_price=6010.0, closing_price=6020.0,
                max_profit=100.0, max_loss=-100.0, margin_req=8000.0,
            ),
            # Day 2 - parameter value "09:30"
            TradeRecord(
                run_id=1, parameter_name="entry_time", parameter_value="09:30",
                date_opened=date(2025, 9, 26), time_opened=time(9, 30, 0),
                date_closed=date(2025, 9, 26), time_closed=time(16, 0, 0),
                pl=250.0, pl_percent=95.0, premium=260.0,
                legs="test", num_contracts=1, reason_for_close="Profit Target",
                opening_vix=14.0, closing_vix=13.5, gap=5.0, movement=10.0,
                opening_price=6020.0, closing_price=6040.0,
                max_profit=100.0, max_loss=-100.0, margin_req=8000.0,
            ),
            # Day 2 - parameter value "10:00"
            TradeRecord(
                run_id=2, parameter_name="entry_time", parameter_value="10:00",
                date_opened=date(2025, 9, 26), time_opened=time(10, 0, 0),
                date_closed=date(2025, 9, 26), time_closed=time(15, 30, 0),
                pl=-100.0, pl_percent=-40.0, premium=250.0,
                legs="test", num_contracts=1, reason_for_close="Stop Loss",
                opening_vix=14.5, closing_vix=16.0, gap=3.0, movement=-5.0,
                opening_price=6025.0, closing_price=6000.0,
                max_profit=100.0, max_loss=-100.0, margin_req=8000.0,
            ),
        ]

    def test_returns_dict_with_expected_keys(self, sample_trades):
        """Test that aggregate_for_charts returns dict with expected keys."""
        result = aggregate_for_charts(sample_trades)
        assert isinstance(result, dict)
        expected_keys = {"daily_pl", "cumulative", "stop_loss_counts", "reason_counts", "vix_data", "duration_avg"}
        assert set(result.keys()) == expected_keys

    def test_daily_pl_aggregation(self, sample_trades):
        """Test daily P/L aggregation by date and parameter value."""
        result = aggregate_for_charts(sample_trades)
        daily_pl = result["daily_pl"]

        # Day 1: 09:30 had 200 + (-150) = 50, 10:00 had 180
        assert daily_pl["2025-09-25"]["09:30"] == 50.0
        assert daily_pl["2025-09-25"]["10:00"] == 180.0

        # Day 2: 09:30 had 250, 10:00 had -100
        assert daily_pl["2025-09-26"]["09:30"] == 250.0
        assert daily_pl["2025-09-26"]["10:00"] == -100.0

    def test_cumulative_pl_aggregation(self, sample_trades):
        """Test cumulative P/L calculation."""
        result = aggregate_for_charts(sample_trades)
        cumulative = result["cumulative"]

        # Cumulative sums up daily P/L over time
        # Day 1: 09:30 = 50, 10:00 = 180
        # Day 2: 09:30 = 50 + 250 = 300, 10:00 = 180 + (-100) = 80
        assert cumulative["2025-09-25"]["09:30"] == 50.0
        assert cumulative["2025-09-25"]["10:00"] == 180.0
        assert cumulative["2025-09-26"]["09:30"] == 300.0
        assert cumulative["2025-09-26"]["10:00"] == 80.0

    def test_stop_loss_counts(self, sample_trades):
        """Test stop loss count aggregation."""
        result = aggregate_for_charts(sample_trades)
        stop_loss_counts = result["stop_loss_counts"]

        # 09:30 had 1 stop loss, 10:00 had 1 stop loss
        assert stop_loss_counts["09:30"] == 1
        assert stop_loss_counts["10:00"] == 1

    def test_reason_counts(self, sample_trades):
        """Test reason for close count aggregation."""
        result = aggregate_for_charts(sample_trades)
        reason_counts = result["reason_counts"]

        # 09:30: 1 Expired, 1 Stop Loss, 1 Profit Target
        assert reason_counts["09:30"]["Expired"] == 1
        assert reason_counts["09:30"]["Stop Loss"] == 1
        assert reason_counts["09:30"]["Profit Target"] == 1

        # 10:00: 1 Expired, 1 Stop Loss
        assert reason_counts["10:00"]["Expired"] == 1
        assert reason_counts["10:00"]["Stop Loss"] == 1

    def test_vix_data_structure(self, sample_trades):
        """Test VIX data structure for scatter plots."""
        result = aggregate_for_charts(sample_trades)
        vix_data = result["vix_data"]

        assert isinstance(vix_data, list)
        assert len(vix_data) == 5  # 5 trades

        # Each entry should have vix, pl, and param
        for entry in vix_data:
            assert "vix" in entry
            assert "pl" in entry
            assert "param" in entry

    def test_vix_data_values(self, sample_trades):
        """Test VIX data contains correct values."""
        result = aggregate_for_charts(sample_trades)
        vix_data = result["vix_data"]

        # First trade: opening_vix=15.0, pl=200.0, param=09:30
        first_trade_data = next(d for d in vix_data if d["vix"] == 15.0 and d["pl"] == 200.0)
        assert first_trade_data["param"] == "09:30"

    def test_duration_avg_calculation(self, sample_trades):
        """Test average trade duration calculation."""
        result = aggregate_for_charts(sample_trades)
        duration_avg = result["duration_avg"]

        # 09:30 trades:
        # Trade 1: 9:30 to 16:00 = 390 minutes
        # Trade 2: 9:30 to 14:00 = 270 minutes
        # Trade 3: 9:30 to 16:00 = 390 minutes
        # Average: (390 + 270 + 390) / 3 = 350 minutes
        assert duration_avg["09:30"] == pytest.approx(350.0, rel=0.01)

        # 10:00 trades:
        # Trade 1: 10:00 to 16:00 = 360 minutes
        # Trade 2: 10:00 to 15:30 = 330 minutes
        # Average: (360 + 330) / 2 = 345 minutes
        assert duration_avg["10:00"] == pytest.approx(345.0, rel=0.01)

    def test_empty_trades_returns_empty_aggregations(self):
        """Test that empty trades list returns empty aggregations."""
        result = aggregate_for_charts([])
        assert result["daily_pl"] == {}
        assert result["cumulative"] == {}
        assert result["stop_loss_counts"] == {}
        assert result["reason_counts"] == {}
        assert result["vix_data"] == []
        assert result["duration_avg"] == {}

    def test_single_trade_aggregation(self):
        """Test aggregation with a single trade."""
        trade = TradeRecord(
            run_id=1, parameter_name="entry_time", parameter_value="09:30",
            date_opened=date(2025, 9, 25), time_opened=time(9, 30, 0),
            date_closed=date(2025, 9, 25), time_closed=time(16, 0, 0),
            pl=200.0, pl_percent=85.0, premium=235.0,
            legs="test", num_contracts=1, reason_for_close="Expired",
            opening_vix=15.0, closing_vix=16.0, gap=-10.0, movement=5.0,
            opening_price=6000.0, closing_price=6010.0,
            max_profit=100.0, max_loss=-100.0, margin_req=8000.0,
        )
        result = aggregate_for_charts([trade])

        assert result["daily_pl"]["2025-09-25"]["09:30"] == 200.0
        assert result["cumulative"]["2025-09-25"]["09:30"] == 200.0
        assert result["stop_loss_counts"].get("09:30", 0) == 0
        assert result["reason_counts"]["09:30"]["Expired"] == 1
        assert len(result["vix_data"]) == 1
        assert result["duration_avg"]["09:30"] == 390.0  # 6.5 hours


class TestIntegration:
    """Integration tests combining parsing and aggregation."""

    def test_parse_and_aggregate_workflow(self, tmp_path):
        """Test the full workflow of parsing CSV and aggregating data."""
        # Create a realistic CSV
        csv_file = tmp_path / "trade_log.csv"
        csv_content = '''"Date Opened","Time Opened","Opening Price","Legs","Premium","Closing Price","Date Closed","Time Closed","Avg. Closing Cost","Reason For Close","P/L","No. of Contracts","Funds at Close","Margin Req.","Strategy","Opening Commissions + Fees","Closing Commissions + Fees","Opening Short/Long Ratio","Closing Short/Long Ratio","Gap","Movement","Max Profit","Max Loss"
"2025-09-25","13:23:00",6593.31,"1 Sep 25 6610 C STO 2.55 | 1 Sep 25 6700 C BTO 0.05",235,6604.72,"2025-09-25","16:00:00",0,"Expired",231.52,1,252879.84,8440,"",3.48,0,51,1,-29.78,-14.88,100,-119.15
"2025-09-25","13:23:00",6593.31,"1 Sep 25 6575 P STO 3.40 | 1 Sep 25 6485 P BTO 0.15",310,6574.61,"2025-09-25","14:03:00",895,"Stop Loss",-591.04,1,252648.32,8440,"",3.48,2.56,22.67,89.5,-29.78,-14.88,40.32,-233.87
"2025-09-26","13:23:00",6636.61,"1 Sep 24 6645 C STO 2.95 | 1 Sep 24 6735 C BTO 0.05",275,6637.97,"2025-09-26","16:00:00",0,"Expired",271.52,1,253239.36,8475,"",3.48,0,59,1,12.87,-33.18,100,-70.91
'''
        csv_file.write_text(csv_content)

        # Parse
        trades = parse_trade_log_csv(str(csv_file), run_id=1, parameter_name="entry_time", parameter_value="13:23")

        # Aggregate
        result = aggregate_for_charts(trades)

        # Verify workflow produces expected structure
        assert len(trades) == 3
        assert "2025-09-25" in result["daily_pl"]
        assert "2025-09-26" in result["daily_pl"]
        assert result["stop_loss_counts"]["13:23"] == 1
        assert result["reason_counts"]["13:23"]["Expired"] == 2
        assert result["reason_counts"]["13:23"]["Stop Loss"] == 1
