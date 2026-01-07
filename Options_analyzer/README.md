# Options Trading Analyzer Pro

A comprehensive desktop GUI application for analyzing options trading backtest results with advanced statistical analysis, pattern detection, and Monte Carlo simulations.

## Quick Start

1. **Install Python 3.9+**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

## Features

### 🎯 Automatic Mis-pricing Pattern Discovery
- Volatility skew anomaly detection using machine learning
- Put-call parity violation identification  
- Term structure analysis
- Calendar spread opportunities

### 📊 Statistical Analysis
- Year-by-year, month-by-month, day-of-week significance testing
- Confidence intervals and hypothesis testing
- Seasonality detection
- Performance metrics (Sharpe, CAGR, Max Drawdown)

### 🎲 Monte Carlo Simulations
- Portfolio outcome simulations
- Risk metrics (VaR, CVaR)
- Forward testing capabilities
- Stress testing scenarios

### 💻 Professional UI
- Dark theme optimized for trading
- Real-time dashboard
- Interactive charts with PyQtGraph
- Dockable widgets for customizable workspace

## CSV File Format

### Consolidated Trade Log
Your consolidated trade CSV should have these columns:
- Backtest Parameter Value
- Trade Date Time
- Opening Price
- Legs
- Premium
- Closing Price
- Date Closed
- Time Closed
- Avg Closing Cost
- Reason For Close
- Trade P&L
- Num Contracts
- Funds at Close
- Margin Req
- Strategy
- Opening Commissions
- Closing Commissions
- Opening Ratio
- Closing Ratio
- Gap
- Movement
- Max Profit
- Max Loss
- Extracted Timestamp
- Worker ID

### Results Exit Logs
Your results CSV should have these columns:
- Parameter Value
- CAGR
- Max Drawdown
- Win Percentage
- Capture Rate
- MAR
- Worker ID
- Timestamp

## Usage Guide

1. **Import Data**: Use File → Import Trades/Results or click the Import button
2. **Run Analysis**: Click Analyze or use Analysis menu for specific tests
3. **View Results**: Navigate tabs for Dashboard, Data, Analytics, and Charts
4. **Export**: File → Export Analysis to save results

## Support

For issues or questions, please contact support.
