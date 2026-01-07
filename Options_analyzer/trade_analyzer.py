#!/usr/bin/env python3
"""
Comprehensive Trade Analysis Script
Analyzes trade entries with multiple dimensions including time patterns,
performance metrics, risk analysis, and Monte Carlo simulations.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
from scipy import stats
from typing import Dict, List, Tuple, Any
import json
from pathlib import Path

warnings.filterwarnings('ignore')

# Set style for better visualizations
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

class TradeAnalyzer:
    """Comprehensive trade analysis with multi-dimensional insights."""
    
    def __init__(self, csv_path: str, chunk_size: int = 10000):
        """Initialize analyzer with CSV file path."""
        self.csv_path = csv_path
        self.chunk_size = chunk_size
        self.df = None
        self.results = {}
        
    def load_data(self) -> pd.DataFrame:
        """Load and preprocess trade data efficiently."""
        print("📊 Loading trade data...")
        
        # First, let's check what columns we actually have
        sample_df = pd.read_csv(self.csv_path, nrows=5)
        print(f"📋 Found columns: {list(sample_df.columns)}")
        
        # Define multiple possible column mappings for consistent naming
        column_mapping = {
            # Date columns
            'Date Opened': 'date_opened',
            'Trade Date Time': 'date_opened',  # Alternative name
            'Trade Date': 'date_opened',
            'Date': 'date_opened',
            
            # Time columns
            'Time Opened': 'time_opened',
            'Trade Time': 'time_opened',
            'Time': 'time_opened',
            
            # Price columns
            'Opening Price': 'opening_price',
            'Open Price': 'opening_price',
            
            'Legs': 'legs',
            'Premium': 'premium',
            
            'Closing Price': 'closing_price',
            'Close Price': 'closing_price',
            
            # Date/Time closed
            'Date Closed': 'date_closed',
            'Close Date': 'date_closed',
            'Time Closed': 'time_closed',
            'Close Time': 'time_closed',
            
            # Cost and P&L
            'Avg. Closing Cost': 'avg_closing_cost',
            'Avg Closing Cost': 'avg_closing_cost',
            'Average Closing Cost': 'avg_closing_cost',
            
            'Reason For Close': 'reason_close',
            'Close Reason': 'reason_close',
            
            'P/L': 'pnl',
            'Trade P&L': 'pnl',
            'Trade P/L': 'pnl',
            'PnL': 'pnl',
            'P&L': 'pnl',
            
            # Contracts and funds
            'No. of Contracts': 'contracts',
            'Num Contracts': 'contracts',
            'Number of Contracts': 'contracts',
            'Contracts': 'contracts',
            
            'Funds at Close': 'funds_close',
            'Closing Funds': 'funds_close',
            
            # Margin and strategy
            'Margin Req.': 'margin_req',
            'Margin Req': 'margin_req',
            'Margin Required': 'margin_req',
            'Margin Requirement': 'margin_req',
            
            'Strategy': 'strategy',
            
            # Commissions
            'Opening Commissions + Fees': 'open_comm',
            'Opening Commissions': 'open_comm',
            'Open Commissions': 'open_comm',
            
            'Closing Commissions + Fees': 'close_comm',
            'Closing Commissions': 'close_comm',
            'Close Commissions': 'close_comm',
            
            # Ratios
            'Opening Short/Long Ratio': 'open_ratio',
            'Opening Ratio': 'open_ratio',
            'Open Ratio': 'open_ratio',
            
            'Closing Short/Long Ratio': 'close_ratio',
            'Closing Ratio': 'close_ratio',
            'Close Ratio': 'close_ratio',
            
            # Gap and movement
            'Gap': 'gap',
            'Movement': 'movement',
            'Max Profit': 'max_profit',
            'Max Loss': 'max_loss',
            
            # Additional possible column names
            'Extracted Timestamp': 'extracted_timestamp',
            'Backtest Parameter Value': 'backtest_param'
        }
        
        # Load data in chunks for memory efficiency
        chunks = []
        for chunk in pd.read_csv(self.csv_path, chunksize=self.chunk_size):
            # Rename columns
            chunk.rename(columns=column_mapping, inplace=True)
            chunks.append(chunk)
        
        self.df = pd.concat(chunks, ignore_index=True)
        
        # Check if required columns exist, if not try to identify them
        if 'date_opened' not in self.df.columns:
            print("⚠️ 'date_opened' column not found. Checking for date columns...")
            date_cols = [col for col in self.df.columns if 'date' in col.lower() or 'time' in col.lower()]
            if date_cols:
                print(f"Found potential date columns: {date_cols}")
                # Use the first date-like column as date_opened
                self.df['date_opened'] = pd.to_datetime(self.df[date_cols[0]], errors='coerce')
            else:
                raise ValueError("No date column found in the CSV file!")
        else:
            # Convert date columns
            self.df['date_opened'] = pd.to_datetime(self.df['date_opened'], errors='coerce')
        
        if 'date_closed' in self.df.columns:
            self.df['date_closed'] = pd.to_datetime(self.df['date_closed'], errors='coerce')
        
        # Parse time columns if they exist
        if 'time_opened' in self.df.columns:
            try:
                # Try different time formats
                time_parsed = pd.to_datetime(self.df['time_opened'], format='%H:%M:%S', errors='coerce')
                if time_parsed.isna().all():
                    time_parsed = pd.to_datetime(self.df['time_opened'], format='%H:%M', errors='coerce')
                
                self.df['hour_opened'] = time_parsed.dt.hour
                self.df['minute_opened'] = time_parsed.dt.minute
            except:
                print("⚠️ Could not parse time_opened column, using default hour 10")
                self.df['hour_opened'] = 10
                self.df['minute_opened'] = 0
        else:
            # If no time column, try to extract from datetime if available
            if self.df['date_opened'].dtype == 'datetime64[ns]':
                self.df['hour_opened'] = self.df['date_opened'].dt.hour
                self.df['minute_opened'] = self.df['date_opened'].dt.minute
            else:
                print("⚠️ No time column found, using default hour 10")
                self.df['hour_opened'] = 10
                self.df['minute_opened'] = 0
        
        # Create datetime columns
        if 'time_opened' in self.df.columns:
            self.df['datetime_opened'] = pd.to_datetime(
                self.df['date_opened'].astype(str) + ' ' + self.df['time_opened'].astype(str),
                errors='coerce'
            )
        else:
            self.df['datetime_opened'] = self.df['date_opened']
        
        # Add derived columns
        self.df['day_of_week'] = self.df['date_opened'].dt.day_name()
        self.df['month'] = self.df['date_opened'].dt.month
        self.df['year'] = self.df['date_opened'].dt.year
        self.df['quarter'] = self.df['date_opened'].dt.quarter
        
        # Calculate trade duration if both dates exist
        if 'date_closed' in self.df.columns and 'date_opened' in self.df.columns:
            self.df['trade_duration'] = (self.df['date_closed'] - self.df['date_opened']).dt.total_seconds() / 3600
        else:
            self.df['trade_duration'] = 1  # Default to 1 hour
        
        # Create time buckets for analysis
        self.df['time_bucket'] = self.df['hour_opened'].apply(self._categorize_time)
        
        # Clean numeric columns
        numeric_cols = ['pnl', 'premium', 'contracts', 'margin_req', 'gap', 'movement', 'max_profit', 'max_loss', 
                       'open_ratio', 'close_ratio', 'opening_price', 'closing_price', 'avg_closing_cost']
        for col in numeric_cols:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
        
        # Drop rows where essential columns are NaN
        essential_cols = ['date_opened', 'pnl']
        for col in essential_cols:
            if col in self.df.columns:
                self.df = self.df.dropna(subset=[col])
        
        print(f"✅ Loaded {len(self.df)} trades from {self.df['date_opened'].min()} to {self.df['date_opened'].max()}")
        print(f"📊 Columns available: {', '.join(self.df.columns.tolist())}")
        return self.df
    
    def _categorize_time(self, hour: int) -> str:
        """Categorize hour into time buckets."""
        if 9 <= hour < 10:
            return "09:00-10:00"
        elif 10 <= hour < 11:
            return "10:00-11:00"
        elif 11 <= hour < 12:
            return "11:00-12:00"
        elif 12 <= hour < 13:
            return "12:00-13:00"
        elif 13 <= hour < 14:
            return "13:00-14:00"
        elif 14 <= hour < 15:
            return "14:00-15:00"
        elif 15 <= hour <= 16:
            return "15:00-16:00"
        else:
            return "After Hours"
    
    def analyze_entry_times(self) -> Dict:
        """Analyze performance by entry time with detailed metrics."""
        print("\n⏰ Analyzing entry times...")
        
        results = {}
        
        # Performance by hour
        hourly_perf = self.df.groupby('hour_opened').agg({
            'pnl': ['mean', 'sum', 'std', 'count'],
            'contracts': 'mean'
        }).round(2)
        
        # Performance by time bucket
        time_bucket_perf = {}
        for bucket in self.df['time_bucket'].unique():
            bucket_data = self.df[self.df['time_bucket'] == bucket]
            if len(bucket_data) > 0:
                wins = bucket_data[bucket_data['pnl'] > 0]
                losses = bucket_data[bucket_data['pnl'] < 0]
                
                # Calculate MAR ratio (return/max drawdown)
                cumsum = bucket_data['pnl'].cumsum()
                running_max = cumsum.cummax()
                drawdown = cumsum - running_max
                max_dd = drawdown.min() if len(drawdown) > 0 else -1
                
                mar_ratio = (bucket_data['pnl'].sum() / abs(max_dd)) if max_dd != 0 else 0
                
                # Calculate Sharpe ratio
                if bucket_data['pnl'].std() != 0:
                    sharpe = (bucket_data['pnl'].mean() / bucket_data['pnl'].std()) * np.sqrt(252)
                else:
                    sharpe = 0
                
                time_bucket_perf[bucket] = {
                    'total_trades': len(bucket_data),
                    'win_rate': len(wins) / len(bucket_data) if len(bucket_data) > 0 else 0,
                    'avg_pnl': bucket_data['pnl'].mean(),
                    'total_pnl': bucket_data['pnl'].sum(),
                    'avg_win': wins['pnl'].mean() if len(wins) > 0 else 0,
                    'avg_loss': losses['pnl'].mean() if len(losses) > 0 else 0,
                    'max_drawdown': max_dd,
                    'mar_ratio': mar_ratio,
                    'sharpe_ratio': sharpe,
                    'profit_factor': abs(wins['pnl'].sum() / losses['pnl'].sum()) if losses['pnl'].sum() != 0 else 0
                }
        
        # Day of week analysis
        dow_perf = self.df.groupby('day_of_week').agg({
            'pnl': ['mean', 'sum', 'count']
        }).round(2)
        
        results['hourly_performance'] = hourly_perf.to_dict()
        results['performance_by_time'] = time_bucket_perf
        results['day_of_week_performance'] = dow_perf.to_dict()
        
        self.results['entry_times'] = results
        return results
    
    def calculate_risk_metrics(self) -> Dict:
        """Calculate comprehensive risk metrics including Kelly criterion."""
        print("\n📈 Calculating risk metrics...")
        
        # Sort by date for accurate calculations
        df_sorted = self.df.sort_values('date_opened').copy()
        
        # Calculate cumulative returns
        df_sorted['cumulative_pnl'] = df_sorted['pnl'].cumsum()
        
        # Calculate drawdown
        running_max = df_sorted['cumulative_pnl'].cummax()
        drawdown = df_sorted['cumulative_pnl'] - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / running_max[drawdown.idxmin()]) * 100 if running_max[drawdown.idxmin()] != 0 else 0
        
        # Win/Loss statistics
        wins = df_sorted[df_sorted['pnl'] > 0]
        losses = df_sorted[df_sorted['pnl'] < 0]
        
        win_rate = len(wins) / len(df_sorted) if len(df_sorted) > 0 else 0
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 0
        
        # Kelly Criterion
        if avg_loss > 0:
            kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win if avg_win > 0 else 0
            kelly_fraction_conservative = kelly_fraction * 0.25  # Conservative Kelly (25%)
        else:
            kelly_fraction = 0
            kelly_fraction_conservative = 0
        
        # Sharpe Ratio (annualized)
        daily_returns = df_sorted.groupby('date_opened')['pnl'].sum()
        if daily_returns.std() != 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # Sortino Ratio
        downside_returns = daily_returns[daily_returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() != 0:
            sortino_ratio = (daily_returns.mean() / downside_returns.std()) * np.sqrt(252)
        else:
            sortino_ratio = 0
        
        # Profit Factor
        total_wins = wins['pnl'].sum() if len(wins) > 0 else 0
        total_losses = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # CAGR
        days_traded = (df_sorted['date_opened'].max() - df_sorted['date_opened'].min()).days
        if days_traded > 0:
            years_traded = days_traded / 365.25
            total_return = df_sorted['pnl'].sum()
            initial_capital = df_sorted['funds_close'].iloc[0] if 'funds_close' in df_sorted.columns else 100000
            cagr = ((total_return + initial_capital) / initial_capital) ** (1/years_traded) - 1 if years_traded > 0 else 0
        else:
            cagr = 0
        
        metrics = {
            'total_pnl': df_sorted['pnl'].sum(),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'kelly_fraction': kelly_fraction,
            'kelly_fraction_conservative': kelly_fraction_conservative,
            'cagr': cagr,
            'total_trades': len(df_sorted),
            'winning_trades': len(wins),
            'losing_trades': len(losses)
        }
        
        self.results['performance_metrics'] = metrics
        return metrics
    
    def analyze_patterns(self) -> Dict:
        """Identify specific patterns in trading data."""
        print("\n🔍 Analyzing patterns...")
        
        patterns = {}
        
        # Gap and Movement correlation with P&L
        if 'gap' in self.df.columns and 'movement' in self.df.columns:
            gap_correlation = self.df['gap'].corr(self.df['pnl'])
            movement_correlation = self.df['movement'].corr(self.df['pnl'])
            
            # Profitable gap ranges
            self.df['gap_range'] = pd.cut(self.df['gap'], bins=10)
            gap_performance = self.df.groupby('gap_range')['pnl'].agg(['mean', 'count', 'sum'])
            
            patterns['gap_correlation'] = gap_correlation
            patterns['movement_correlation'] = movement_correlation
            patterns['gap_performance'] = gap_performance.to_dict()
        
        # Streak analysis
        self.df['win'] = self.df['pnl'] > 0
        streaks = []
        current_streak = 0
        streak_type = None
        
        for idx, win in enumerate(self.df['win']):
            if idx == 0:
                current_streak = 1
                streak_type = win
            elif win == streak_type:
                current_streak += 1
            else:
                streaks.append((streak_type, current_streak))
                current_streak = 1
                streak_type = win
        
        win_streaks = [s[1] for s in streaks if s[0]]
        loss_streaks = [s[1] for s in streaks if not s[0]]
        
        patterns['max_win_streak'] = max(win_streaks) if win_streaks else 0
        patterns['max_loss_streak'] = max(loss_streaks) if loss_streaks else 0
        patterns['avg_win_streak'] = np.mean(win_streaks) if win_streaks else 0
        patterns['avg_loss_streak'] = np.mean(loss_streaks) if loss_streaks else 0
        
        # Seasonality patterns
        monthly_perf = self.df.groupby('month')['pnl'].agg(['mean', 'sum', 'count'])
        patterns['monthly_performance'] = monthly_perf.to_dict()
        
        self.results['patterns'] = patterns
        return patterns
    
    def monte_carlo_simulation(self, n_simulations: int = 1000, n_days: int = 252) -> Dict:
        """Run Monte Carlo simulation for forward testing."""
        print(f"\n🎲 Running {n_simulations} Monte Carlo simulations...")
        
        # Get historical trade returns
        returns = self.df['pnl'].values
        
        # Run simulations
        simulation_results = []
        
        for _ in range(n_simulations):
            # Randomly sample with replacement
            simulated_returns = np.random.choice(returns, size=n_days, replace=True)
            cumulative_return = np.cumsum(simulated_returns)
            
            # Calculate metrics for this simulation
            final_pnl = cumulative_return[-1]
            max_dd = np.min(cumulative_return - np.maximum.accumulate(cumulative_return))
            
            simulation_results.append({
                'final_pnl': final_pnl,
                'max_drawdown': max_dd,
                'path': cumulative_return
            })
        
        # Calculate statistics
        final_pnls = [s['final_pnl'] for s in simulation_results]
        max_dds = [s['max_drawdown'] for s in simulation_results]
        
        monte_carlo = {
            'expected_pnl': np.mean(final_pnls),
            'pnl_std': np.std(final_pnls),
            'pnl_5th_percentile': np.percentile(final_pnls, 5),
            'pnl_95th_percentile': np.percentile(final_pnls, 95),
            'expected_max_drawdown': np.mean(max_dds),
            'worst_drawdown': np.min(max_dds),
            'probability_profit': np.mean([1 if p > 0 else 0 for p in final_pnls]),
            'simulation_paths': [s['path'] for s in simulation_results[:100]]  # Store first 100 paths
        }
        
        self.results['monte_carlo'] = monte_carlo
        return monte_carlo
    
    def compare_performance_periods(self) -> Dict:
        """Compare recent performance vs historical performance."""
        print("\n📊 Comparing performance periods...")
        
        # Define periods
        current_date = self.df['date_opened'].max()
        six_months_ago = current_date - timedelta(days=180)
        two_years_ago = current_date - timedelta(days=730)
        
        # Recent 6 months
        recent_df = self.df[self.df['date_opened'] >= six_months_ago]
        
        # Past 2 years (excluding recent 6 months)
        historical_df = self.df[
            (self.df['date_opened'] >= two_years_ago) & 
            (self.df['date_opened'] < six_months_ago)
        ]
        
        def calculate_period_metrics(df, period_name):
            if len(df) == 0:
                return {}
            
            wins = df[df['pnl'] > 0]
            losses = df[df['pnl'] < 0]
            
            # Calculate cumulative metrics
            cumsum = df.sort_values('date_opened')['pnl'].cumsum()
            running_max = cumsum.cummax()
            drawdown = cumsum - running_max
            
            return {
                'period': period_name,
                'total_trades': len(df),
                'total_pnl': df['pnl'].sum(),
                'avg_pnl': df['pnl'].mean(),
                'win_rate': len(wins) / len(df) if len(df) > 0 else 0,
                'avg_win': wins['pnl'].mean() if len(wins) > 0 else 0,
                'avg_loss': losses['pnl'].mean() if len(losses) > 0 else 0,
                'max_drawdown': drawdown.min() if len(drawdown) > 0 else 0,
                'sharpe': (df['pnl'].mean() / df['pnl'].std() * np.sqrt(252)) if df['pnl'].std() != 0 else 0,
                'best_trade': df['pnl'].max(),
                'worst_trade': df['pnl'].min(),
                'avg_trade_duration': df['trade_duration'].mean() if 'trade_duration' in df.columns else 0
            }
        
        recent_metrics = calculate_period_metrics(recent_df, 'Recent 6 Months')
        historical_metrics = calculate_period_metrics(historical_df, 'Past 2 Years')
        
        # Calculate changes
        changes = {}
        for key in recent_metrics:
            if key != 'period' and key in historical_metrics:
                if isinstance(recent_metrics[key], (int, float)) and isinstance(historical_metrics[key], (int, float)):
                    if historical_metrics[key] != 0:
                        changes[f'{key}_change'] = ((recent_metrics[key] - historical_metrics[key]) / abs(historical_metrics[key])) * 100
                    else:
                        changes[f'{key}_change'] = 0
        
        comparison = {
            'recent': recent_metrics,
            'historical': historical_metrics,
            'changes': changes
        }
        
        self.results['period_comparison'] = comparison
        return comparison
    
    def create_visualizations(self):
        """Create comprehensive visualizations."""
        print("\n🎨 Creating visualizations...")
        
        fig = plt.figure(figsize=(20, 16))
        
        # 1. Entry Time Heatmap (Bubble Chart)
        ax1 = plt.subplot(3, 3, 1)
        time_data = self.df.groupby(['hour_opened', 'day_of_week']).agg({
            'pnl': ['sum', 'count']
        }).reset_index()
        time_data.columns = ['hour', 'day', 'total_pnl', 'count']
        
        # Create bubble chart
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        day_mapping = {day: i for i, day in enumerate(days_order)}
        time_data['day_num'] = time_data['day'].map(day_mapping)
        
        scatter = ax1.scatter(time_data['hour'], time_data['day_num'], 
                            s=time_data['count']*50, 
                            c=time_data['total_pnl'], 
                            cmap='RdYlGn', alpha=0.6)
        ax1.set_xlabel('Hour of Day')
        ax1.set_ylabel('Day of Week')
        ax1.set_yticks(range(len(days_order)))
        ax1.set_yticklabels(days_order)
        ax1.set_title('Entry Time Performance (Size=Count, Color=P&L)')
        plt.colorbar(scatter, ax=ax1)
        
        # 2. P&L Distribution
        ax2 = plt.subplot(3, 3, 2)
        ax2.hist(self.df['pnl'], bins=50, edgecolor='black', alpha=0.7)
        ax2.axvline(x=0, color='red', linestyle='--', alpha=0.5)
        ax2.set_xlabel('P&L')
        ax2.set_ylabel('Frequency')
        ax2.set_title('P&L Distribution')
        
        # 3. Cumulative P&L
        ax3 = plt.subplot(3, 3, 3)
        sorted_df = self.df.sort_values('date_opened')
        cumulative_pnl = sorted_df['pnl'].cumsum()
        ax3.plot(sorted_df['date_opened'], cumulative_pnl, linewidth=2)
        ax3.fill_between(sorted_df['date_opened'], cumulative_pnl, alpha=0.3)
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Cumulative P&L')
        ax3.set_title('Cumulative P&L Over Time')
        ax3.grid(True, alpha=0.3)
        
        # 4. Win Rate by Time
        ax4 = plt.subplot(3, 3, 4)
        time_win_rate = self.df.groupby('time_bucket').apply(
            lambda x: (x['pnl'] > 0).mean()
        ).sort_index()
        ax4.bar(range(len(time_win_rate)), time_win_rate.values)
        ax4.set_xticks(range(len(time_win_rate)))
        ax4.set_xticklabels(time_win_rate.index, rotation=45, ha='right')
        ax4.set_ylabel('Win Rate')
        ax4.set_title('Win Rate by Entry Time')
        ax4.axhline(y=0.5, color='red', linestyle='--', alpha=0.5)
        
        # 5. Monte Carlo Paths
        ax5 = plt.subplot(3, 3, 5)
        if 'monte_carlo' in self.results:
            paths = self.results['monte_carlo']['simulation_paths'][:50]
            for path in paths:
                ax5.plot(path, alpha=0.1, color='blue')
            
            # Plot mean path
            mean_path = np.mean(paths, axis=0)
            ax5.plot(mean_path, color='red', linewidth=2, label='Mean Path')
            
            # Plot percentiles
            p5 = np.percentile(paths, 5, axis=0)
            p95 = np.percentile(paths, 95, axis=0)
            ax5.fill_between(range(len(mean_path)), p5, p95, alpha=0.2, color='gray')
            
            ax5.set_xlabel('Trading Days')
            ax5.set_ylabel('Cumulative P&L')
            ax5.set_title('Monte Carlo Simulation (50 paths)')
            ax5.legend()
        
        # 6. Drawdown Chart
        ax6 = plt.subplot(3, 3, 6)
        cumsum = sorted_df['pnl'].cumsum()
        running_max = cumsum.cummax()
        drawdown = cumsum - running_max
        ax6.fill_between(sorted_df['date_opened'], drawdown, 0, color='red', alpha=0.3)
        ax6.plot(sorted_df['date_opened'], drawdown, color='red', linewidth=1)
        ax6.set_xlabel('Date')
        ax6.set_ylabel('Drawdown')
        ax6.set_title('Drawdown Over Time')
        ax6.grid(True, alpha=0.3)
        
        # 7. Performance by Day of Week
        ax7 = plt.subplot(3, 3, 7)
        dow_perf = self.df.groupby('day_of_week')['pnl'].agg(['mean', 'sum'])
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        dow_perf = dow_perf.reindex(days_order)
        
        x = np.arange(len(days_order))
        width = 0.35
        ax7.bar(x - width/2, dow_perf['mean'], width, label='Avg P&L')
        ax7.bar(x + width/2, dow_perf['sum']/100, width, label='Total P&L/100')
        ax7.set_xticks(x)
        ax7.set_xticklabels(days_order, rotation=45, ha='right')
        ax7.set_ylabel('P&L')
        ax7.set_title('Performance by Day of Week')
        ax7.legend()
        
        # 8. Gap vs Movement Analysis
        ax8 = plt.subplot(3, 3, 8)
        if 'gap' in self.df.columns and 'movement' in self.df.columns:
            scatter = ax8.scatter(self.df['gap'], self.df['movement'], 
                                c=self.df['pnl'], cmap='RdYlGn', alpha=0.5)
            ax8.set_xlabel('Gap')
            ax8.set_ylabel('Movement')
            ax8.set_title('Gap vs Movement (Color = P&L)')
            plt.colorbar(scatter, ax=ax8)
        
        # 9. Recent vs Historical Performance
        ax9 = plt.subplot(3, 3, 9)
        if 'period_comparison' in self.results:
            recent = self.results['period_comparison']['recent']
            historical = self.results['period_comparison']['historical']
            
            metrics = ['win_rate', 'sharpe', 'avg_pnl']
            x = np.arange(len(metrics))
            width = 0.35
            
            recent_vals = [recent.get(m, 0) for m in metrics]
            hist_vals = [historical.get(m, 0) for m in metrics]
            
            ax9.bar(x - width/2, recent_vals, width, label='Recent 6M')
            ax9.bar(x + width/2, hist_vals, width, label='Historical')
            ax9.set_xticks(x)
            ax9.set_xticklabels(metrics)
            ax9.set_title('Recent vs Historical Performance')
            ax9.legend()
        
        plt.tight_layout()
        plt.savefig('trade_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        print("✅ Visualizations saved to 'trade_analysis.png'")
    
    def print_summary(self):
        """Print comprehensive analysis summary."""
        print("\n" + "="*80)
        print("📊 TRADE ANALYSIS SUMMARY")
        print("="*80)
        
        # Overall Performance
        if 'performance_metrics' in self.results:
            metrics = self.results['performance_metrics']
            print("\n📈 OVERALL PERFORMANCE:")
            print(f"   • Total P&L: ${metrics['total_pnl']:,.2f}")
            print(f"   • Total Trades: {metrics['total_trades']}")
            print(f"   • Win Rate: {metrics['win_rate']:.1%}")
            print(f"   • Avg Win: ${metrics['avg_win']:,.2f}")
            print(f"   • Avg Loss: ${metrics['avg_loss']:,.2f}")
            print(f"   • Profit Factor: {metrics['profit_factor']:.2f}")
            print(f"   • CAGR: {metrics['cagr']:.1%}")
            print(f"   • Max Drawdown: ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.1%})")
            print(f"   • Sharpe Ratio: {metrics['sharpe_ratio']:.3f}")
            print(f"   • Sortino Ratio: {metrics['sortino_ratio']:.3f}")
        
        # Top Entry Times
        if 'entry_times' in self.results and 'performance_by_time' in self.results['entry_times']:
            print("\n🏆 TOP 3 ENTRY TIMES:")
            perf_df = pd.DataFrame(self.results['entry_times']['performance_by_time']).T
            perf_df = perf_df.sort_values('mar_ratio', ascending=False)
            
            for idx, (time, row) in enumerate(perf_df.head(3).iterrows(), 1):
                print(f"\n   {idx}. Entry Time: {time}")
                print(f"      • MAR Ratio: {row['mar_ratio']:.3f}")
                print(f"      • Win Rate: {row['win_rate']:.1%}")
                print(f"      • Avg P&L: ${row['avg_pnl']:.2f}")
                print(f"      • Sharpe: {row.get('sharpe_ratio', 0):.3f}")
                print(f"      • Trades: {int(row['total_trades'])}")
        
        # Patterns
        if 'patterns' in self.results:
            patterns = self.results['patterns']
            print("\n🔍 KEY PATTERNS:")
            print(f"   • Gap Correlation with P&L: {patterns.get('gap_correlation', 0):.3f}")
            print(f"   • Movement Correlation with P&L: {patterns.get('movement_correlation', 0):.3f}")
            print(f"   • Max Win Streak: {patterns.get('max_win_streak', 0)}")
            print(f"   • Max Loss Streak: {patterns.get('max_loss_streak', 0)}")
        
        # Monte Carlo Results
        if 'monte_carlo' in self.results:
            mc = self.results['monte_carlo']
            print("\n🎲 MONTE CARLO SIMULATION (1-Year Forward):")
            print(f"   • Expected P&L: ${mc['expected_pnl']:,.2f}")
            print(f"   • 5th Percentile: ${mc['pnl_5th_percentile']:,.2f}")
            print(f"   • 95th Percentile: ${mc['pnl_95th_percentile']:,.2f}")
            print(f"   • Probability of Profit: {mc['probability_profit']:.1%}")
            print(f"   • Expected Max Drawdown: ${mc['expected_max_drawdown']:,.2f}")
        
        # Period Comparison
        if 'period_comparison' in self.results:
            comp = self.results['period_comparison']
            changes = comp['changes']
            print("\n📊 RECENT VS HISTORICAL PERFORMANCE:")
            print(f"   • Win Rate Change: {changes.get('win_rate_change', 0):+.1f}%")
            print(f"   • Avg P&L Change: {changes.get('avg_pnl_change', 0):+.1f}%")
            print(f"   • Sharpe Change: {changes.get('sharpe_change', 0):+.1f}%")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        
        # Position sizing
        if 'performance_metrics' in self.results:
            kelly = self.results['performance_metrics'].get('kelly_fraction_conservative', 0.02)
            print(f"   📊 Position Sizing: Risk {kelly:.1%} per trade (Conservative Kelly)")
        
        # Best/Worst times
        if 'entry_times' in self.results and 'performance_by_time' in self.results['entry_times']:
            perf_df = pd.DataFrame(self.results['entry_times']['performance_by_time']).T
            best_times = perf_df.nlargest(3, 'mar_ratio').index.tolist()
            print(f"   ✓ Focus entries on: {', '.join(best_times)}")
            
            worst_times = perf_df[perf_df['total_trades'] >= 10].nsmallest(2, 'mar_ratio').index.tolist()
            if worst_times:
                print(f"   ✗ Avoid entries at: {', '.join(worst_times)}")
        
        # Risk limits
        if 'performance_metrics' in self.results:
            max_dd = abs(self.results['performance_metrics']['max_drawdown'])
            daily_limit = max_dd / 10
            print(f"   🛑 Daily Loss Limit: ${daily_limit:,.0f}")
        
        print("\n" + "="*80)
    
    def run_full_analysis(self):
        """Run complete analysis pipeline."""
        # Load data
        self.load_data()
        
        # Run analyses
        self.analyze_entry_times()
        self.calculate_risk_metrics()
        self.analyze_patterns()
        self.monte_carlo_simulation()
        self.compare_performance_periods()
        
        # Create visualizations
        self.create_visualizations()
        
        # Print summary
        self.print_summary()
        
        # Save results to JSON
        results_path = 'trade_analysis_results.json'
        with open(results_path, 'w') as f:
            # Convert numpy types for JSON serialization
            def convert_types(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {k: convert_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_types(i) for i in obj]
                return obj
            
            json.dump(convert_types(self.results), f, indent=2, default=str)
        
        print(f"\n📁 Detailed results saved to '{results_path}'")
        
        return self.results


def main():
    """Main execution function."""
    # Get CSV file path from user
    csv_path = input("Enter the path to your trade CSV file: ").strip()
    
    # Remove quotes if present
    csv_path = csv_path.strip('"').strip("'")
    
    # Validate file exists
    if not Path(csv_path).exists():
        print(f"❌ Error: File '{csv_path}' not found!")
        return
    
    try:
        # Create analyzer and run analysis
        analyzer = TradeAnalyzer(csv_path)
        results = analyzer.run_full_analysis()
        
        print("\n✅ Analysis complete! Check 'trade_analysis.png' for visualizations.")
        print("📊 Detailed results saved to 'trade_analysis_results.json'")
    
    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
        print("\n🔍 Debugging information:")
        print("Please check that your CSV file has the following columns (or similar):")
        print("- Date Opened (or Trade Date, Date)")
        print("- P/L (or Trade P&L, PnL)")
        print("- Time Opened (optional)")
        print("\nIf your columns have different names, the script will try to detect them.")
        
        # Try to show first few rows of the file for debugging
        try:
            import pandas as pd
            df_debug = pd.read_csv(csv_path, nrows=5)
            print(f"\n📋 First 5 rows of your file:")
            print(df_debug.head())
            print(f"\n📋 Column names found: {list(df_debug.columns)}")
        except:
            pass
        
        raise e


if __name__ == "__main__":
    main()
