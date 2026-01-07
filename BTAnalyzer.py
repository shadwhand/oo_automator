
"""
Trade Analysis Tool v2.0 - Comprehensive Trading Performance Analyzer
Analyzes trade entries with advanced metrics, visualizations, and recommendations
Author: Trade Analysis Systems | Date: 2025
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
from scipy import stats
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Try to import optional libraries for enhanced features
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("💡 Tip: Install 'tqdm' for progress bars: pip install tqdm")

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    COLOR_AVAILABLE = True
except ImportError:
    COLOR_AVAILABLE = False
    print("💡 Tip: Install 'colorama' for colored output: pip install colorama")
    # Create dummy color objects
    class DummyColor:
        def __getattr__(self, name):
            return ""
    Fore = Back = Style = DummyColor()

warnings.filterwarnings('ignore')

# Set style for better visualizations
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

class UserInterface:
    """Handle user interactions and display"""
    
    @staticmethod
    def clear_screen():
        """Clear the console screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def print_header():
        """Print application header"""
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}{'='*80}")
        print(f"{Fore.WHITE}{Style.BRIGHT}                    TRADE ANALYSIS TOOL v2.0")
        print(f"{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}{'='*80}\n")
    
    @staticmethod
    def print_section(title: str):
        """Print section header"""
        print(f"\n{Fore.YELLOW}{'─'*60}")
        print(f"{Fore.YELLOW}{Style.BRIGHT}{title}")
        print(f"{Fore.YELLOW}{'─'*60}")
    
    @staticmethod
    def get_file_path() -> str:
        """Get CSV file path from user"""
        print(f"{Fore.GREEN}📁 Please provide your trade data CSV file:\n")
        
        # Check for common file locations
        common_paths = [
            "trades.csv",
            "trade_data.csv",
            "export.csv",
            os.path.join(os.path.expanduser("~"), "Downloads", "trades.csv"),
            os.path.join(os.path.expanduser("~"), "Documents", "trades.csv")
        ]
        
        # Show found files
        found_files = []
        for i, path in enumerate(common_paths, 1):
            if os.path.exists(path):
                found_files.append(path)
                file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                print(f"   {Fore.CYAN}[{i}]{Fore.WHITE} {path} ({file_size:.1f} MB)")
        
        if found_files:
            print(f"   {Fore.CYAN}[C]{Fore.WHITE} Choose custom path")
            choice = input(f"\n{Fore.GREEN}Select option or enter path: {Fore.WHITE}").strip()
            
            if choice.upper() != 'C':
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(found_files):
                        return found_files[idx]
                except ValueError:
                    if os.path.exists(choice):
                        return choice
        
        # Manual entry
        while True:
            path = input(f"{Fore.GREEN}Enter CSV file path: {Fore.WHITE}").strip()
            path = path.strip('"').strip("'")  # Remove quotes if present
            
            if os.path.exists(path):
                file_size = os.path.getsize(path) / (1024 * 1024)
                print(f"{Fore.GREEN}✅ Found file: {path} ({file_size:.1f} MB)")
                return path
            else:
                print(f"{Fore.RED}❌ File not found. Please try again.")
                retry = input(f"{Fore.YELLOW}Try again? (y/n): {Fore.WHITE}").lower()
                if retry != 'y':
                    sys.exit(0)
    
    @staticmethod
    def get_analysis_options() -> Dict:
        """Get user preferences for analysis"""
        UserInterface.print_section("ANALYSIS OPTIONS")
        
        options = {
            'heatmap': True,
            'bubble': True,
            'dashboard': True,
            'monte_carlo': True,
            'period_comparison': True,
            'save_json': True,
            'show_plots': True
        }
        
        print(f"{Fore.GREEN}Choose analyses to run (default: all):\n")
        print(f"   {Fore.CYAN}[1]{Fore.WHITE} Entry Time Heatmap")
        print(f"   {Fore.CYAN}[2]{Fore.WHITE} Entry Time Bubble Chart")
        print(f"   {Fore.CYAN}[3]{Fore.WHITE} Performance Dashboard")
        print(f"   {Fore.CYAN}[4]{Fore.WHITE} Monte Carlo Simulation")
        print(f"   {Fore.CYAN}[5]{Fore.WHITE} Period Comparison (6mo vs 2yr)")
        print(f"   {Fore.CYAN}[6]{Fore.WHITE} Export to JSON")
        print(f"   {Fore.CYAN}[A]{Fore.WHITE} All analyses (recommended)")
        print(f"   {Fore.CYAN}[Q]{Fore.WHITE} Quick analysis (skip visualizations)")
        
        choice = input(f"\n{Fore.GREEN}Your choice (press Enter for All): {Fore.WHITE}").strip().upper()
        
        if choice == 'Q':
            options = {k: False for k in options}
            options['monte_carlo'] = True
            options['period_comparison'] = True
            options['show_plots'] = False
            print(f"{Fore.YELLOW}Running quick analysis (no visualizations)...")
        elif choice and choice != 'A':
            options = {k: False for k in options}
            for c in choice:
                if c == '1': options['heatmap'] = True
                elif c == '2': options['bubble'] = True
                elif c == '3': options['dashboard'] = True
                elif c == '4': options['monte_carlo'] = True
                elif c == '5': options['period_comparison'] = True
                elif c == '6': options['save_json'] = True
        
        return options
    
    @staticmethod
    def show_progress(message: str, current: int = None, total: int = None):
        """Show progress message"""
        if current and total:
            percentage = (current / total) * 100
            bar_length = 40
            filled = int(bar_length * current / total)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r{Fore.CYAN}{message} [{bar}] {percentage:.1f}%", end='')
            if current == total:
                print()  # New line when complete
        else:
            print(f"{Fore.CYAN}⏳ {message}...")

class TradeAnalyzer:
    """Main analysis engine"""
    
    def __init__(self, filepath: str, ui: UserInterface = None):
        self.filepath = filepath
        self.ui = ui or UserInterface()
        self.df = None
        self.results = {}
        
    def load_data(self) -> pd.DataFrame:
        """Load CSV data with progress indication"""
        self.ui.show_progress(f"Loading data from {os.path.basename(self.filepath)}")
        
        # Get file size
        file_size_mb = os.path.getsize(self.filepath) / (1024 * 1024)
        
        # Determine chunk size based on file size
        if file_size_mb > 100:
            chunk_size = 10000
        elif file_size_mb > 50:
            chunk_size = 5000
        else:
            chunk_size = None  # Read all at once for small files
        
        try:
            # Define dtypes for memory efficiency - updated for actual column names
            dtypes = {
                'Opening Price': 'float32',
                'Premium': 'float32',
                'Closing Price': 'float32',
                'Avg Closing Cost': 'float32',
                'Trade P&L': 'float32',
                'Num Contracts': 'float32',
                'Funds at Close': 'float32',
                'Margin Req': 'float32',
                'Opening Commissions': 'float32',
                'Closing Commissions': 'float32',
                'Opening Ratio': 'float32',
                'Closing Ratio': 'float32',
                'Gap': 'float32',
                'Movement': 'float32',
                'Max Profit': 'float32',
                'Max Loss': 'float32',
                'Worker ID': 'int16'
            }
            
            if chunk_size:
                # Load in chunks with progress
                chunks = []
                total_rows = sum(1 for line in open(self.filepath, 'r')) - 1  # Subtract header
                rows_loaded = 0
                
                for chunk in pd.read_csv(self.filepath, chunksize=chunk_size, dtype=dtypes):
                    chunks.append(chunk)
                    rows_loaded += len(chunk)
                    self.ui.show_progress(f"Loading {file_size_mb:.1f}MB file", rows_loaded, total_rows)
                
                self.df = pd.concat(chunks, ignore_index=True)
            else:
                self.df = pd.read_csv(self.filepath, dtype=dtypes)
            
            # Process dates and times
            self.ui.show_progress("Processing dates and times")
            
            # Parse Trade Date Time (format: 5/16/23 10:00:00 or similar)
            self.df['Datetime Opened'] = pd.to_datetime(self.df['Trade Date Time'], errors='coerce')
            self.df['Date Opened'] = self.df['Datetime Opened'].dt.date
            self.df['Date Opened'] = pd.to_datetime(self.df['Date Opened'])
            
            # Parse Date Closed and Time Closed
            self.df['Date Closed'] = pd.to_datetime(self.df['Date Closed'], errors='coerce')
            
            # Create Datetime Closed from Date Closed and Time Closed
            self.df['Time Closed'] = self.df['Time Closed'].astype(str).str.strip()
            self.df['Datetime Closed'] = pd.to_datetime(
                self.df['Date Closed'].astype(str) + ' ' + self.df['Time Closed'],
                errors='coerce'
            )
            
            # Extract time features from Backtest Entry Time (format: "10:00")
            self.df['Backtest Entry Time'] = self.df['Backtest Entry Time'].astype(str).str.strip()
            time_parts = self.df['Backtest Entry Time'].str.split(':', expand=True)
            self.df['Hour'] = pd.to_numeric(time_parts[0], errors='coerce')
            self.df['Minute'] = pd.to_numeric(time_parts[1] if 1 in time_parts.columns else 0, errors='coerce')
            
            # Additional time features
            self.df['Day of Week'] = self.df['Date Opened'].dt.dayofweek
            self.df['Month'] = self.df['Date Opened'].dt.month
            self.df['Year'] = self.df['Date Opened'].dt.year
            
            # Calculate trade duration
            self.df['Duration (minutes)'] = (
                self.df['Datetime Closed'] - self.df['Datetime Opened']
            ).dt.total_seconds() / 60
            
            # Create P/L column for compatibility (using Trade P&L)
            self.df['P/L'] = self.df['Trade P&L']
            
            # Remove invalid rows
            initial_count = len(self.df)
            self.df = self.df.dropna(subset=['P/L', 'Date Opened'])
            removed_count = initial_count - len(self.df)
            
            print(f"\n{Fore.GREEN}✅ Successfully loaded {len(self.df):,} trades")
            if removed_count > 0:
                print(f"{Fore.YELLOW}⚠️  Removed {removed_count} invalid rows")
            
            # Show date range
            date_min = self.df['Date Opened'].min()
            date_max = self.df['Date Opened'].max()
            if pd.notna(date_min) and pd.notna(date_max):
                print(f"{Fore.WHITE}📅 Date range: {date_min.strftime('%Y-%m-%d')} to {date_max.strftime('%Y-%m-%d')}")
            
            # Show summary of loaded data
            print(f"{Fore.WHITE}💰 Total P&L: ${self.df['P/L'].sum():,.2f}")
            print(f"{Fore.WHITE}📊 Average P&L: ${self.df['P/L'].mean():.2f}")
            
            return self.df
            
        except Exception as e:
            print(f"{Fore.RED}❌ Error loading data: {str(e)}")
            print(f"{Fore.YELLOW}Please check that your CSV file has the expected columns:")
            print(f"{Fore.WHITE}Expected: Backtest Entry Time, Trade Date Time, Trade P&L, etc.")
            sys.exit(1)
    
    def calculate_performance_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate comprehensive performance metrics"""
        metrics = {}
        
        # Basic metrics
        metrics['total_trades'] = len(df)
        metrics['total_pnl'] = df['P/L'].sum()
        metrics['avg_pnl'] = df['P/L'].mean()
        metrics['median_pnl'] = df['P/L'].median()
        metrics['std_pnl'] = df['P/L'].std()
        
        # Win/Loss metrics
        winners = df[df['P/L'] > 0]
        losers = df[df['P/L'] < 0]
        metrics['win_rate'] = len(winners) / len(df) if len(df) > 0 else 0
        metrics['avg_win'] = winners['P/L'].mean() if len(winners) > 0 else 0
        metrics['avg_loss'] = losers['P/L'].mean() if len(losers) > 0 else 0
        metrics['largest_win'] = winners['P/L'].max() if len(winners) > 0 else 0
        metrics['largest_loss'] = losers['P/L'].min() if len(losers) > 0 else 0
        
        # Profit Factor
        total_wins = winners['P/L'].sum() if len(winners) > 0 else 0
        total_losses = abs(losers['P/L'].sum()) if len(losers) > 0 else 1
        metrics['profit_factor'] = total_wins / total_losses if total_losses != 0 else 0
        
        # Calculate cumulative P/L and drawdown
        df_sorted = df.sort_values('Datetime Opened')
        cumulative_pnl = df_sorted['P/L'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        
        metrics['max_drawdown'] = drawdown.min()
        if len(running_max) > 0 and drawdown.idxmin() in running_max.index:
            max_val = running_max[drawdown.idxmin()]
            metrics['max_drawdown_pct'] = (drawdown.min() / max_val * 100) if max_val != 0 else 0
        else:
            metrics['max_drawdown_pct'] = 0
        
        # Sharpe Ratio
        daily_returns = df_sorted.set_index('Date Opened')['P/L'].resample('D').sum()
        if len(daily_returns) > 0 and daily_returns.std() != 0:
            metrics['sharpe_ratio'] = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            metrics['sharpe_ratio'] = 0
        
        # CAGR and MAR Ratio
        if len(df) > 0:
            days = (df['Date Opened'].max() - df['Date Opened'].min()).days
            if days > 30:  # Need at least 30 days for meaningful CAGR
                years = days / 365.25
                ending_value = cumulative_pnl.iloc[-1] if len(cumulative_pnl) > 0 else 0
                starting_value = 100000  # Assume starting capital
                if years > 0 and starting_value > 0:
                    metrics['cagr'] = (((ending_value + starting_value) / starting_value) ** (1/years) - 1)
                    metrics['mar_ratio'] = abs(metrics['cagr'] / metrics['max_drawdown_pct']) if metrics['max_drawdown_pct'] != 0 else 0
                else:
                    metrics['cagr'] = 0
                    metrics['mar_ratio'] = 0
            else:
                metrics['cagr'] = 0
                metrics['mar_ratio'] = 0
        else:
            metrics['cagr'] = 0
            metrics['mar_ratio'] = 0
        
        # Kelly Criterion
        if metrics['win_rate'] > 0 and metrics['avg_loss'] != 0:
            win_loss_ratio = abs(metrics['avg_win'] / metrics['avg_loss'])
            metrics['kelly_fraction'] = (metrics['win_rate'] * win_loss_ratio - (1 - metrics['win_rate'])) / win_loss_ratio
            metrics['kelly_fraction_conservative'] = max(0, min(0.25, metrics['kelly_fraction'] * 0.25))
        else:
            metrics['kelly_fraction'] = 0
            metrics['kelly_fraction_conservative'] = 0
        
        return metrics
    
    def analyze_entry_times(self) -> Dict:
        """Analyze performance by entry time using Backtest Entry Time"""
        self.ui.show_progress("Analyzing entry times")
        results = {}
        
        # Use Backtest Entry Time if available
        if 'Backtest Entry Time' in self.df.columns:
            # Group by exact Backtest Entry Time
            for time_str in self.df['Backtest Entry Time'].dropna().unique():
                time_df = self.df[self.df['Backtest Entry Time'] == time_str]
                if len(time_df) >= 5:  # Minimum trades for significance
                    results[str(time_str)] = self.calculate_performance_metrics(time_df)
        else:
            # Fall back to Hour analysis
            for hour in sorted(self.df['Hour'].dropna().unique()):
                hour_df = self.df[self.df['Hour'] == hour]
                if len(hour_df) >= 5:  # Minimum trades for significance
                    hour_str = f"{int(hour):02d}:00"
                    results[hour_str] = self.calculate_performance_metrics(hour_df)
        
        return results
    
    def analyze_day_of_week(self) -> Dict:
        """Analyze performance by day of week"""
        self.ui.show_progress("Analyzing days of week")
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        results = {}
        
        for day in range(7):
            day_df = self.df[self.df['Day of Week'] == day]
            if len(day_df) > 0:
                results[day_names[day]] = self.calculate_performance_metrics(day_df)
        
        return results
    
    def compare_periods(self) -> Dict:
        """Compare recent vs historical performance"""
        self.ui.show_progress("Comparing time periods")
        results = {}
        
        latest_date = self.df['Date Opened'].max()
        six_months_ago = latest_date - pd.DateOffset(months=6)
        two_years_ago = latest_date - pd.DateOffset(years=2)
        
        # Recent 6 months
        recent_df = self.df[self.df['Date Opened'] >= six_months_ago]
        if len(recent_df) > 0:
            results['recent_6_months'] = self.calculate_performance_metrics(recent_df)
        
        # Past 2 years
        past_2y_df = self.df[self.df['Date Opened'] >= two_years_ago]
        if len(past_2y_df) > 0:
            results['past_2_years'] = self.calculate_performance_metrics(past_2y_df)
        
        # Historical (before 6 months ago)
        historical_df = self.df[self.df['Date Opened'] < six_months_ago]
        if len(historical_df) > 0:
            results['historical'] = self.calculate_performance_metrics(historical_df)
        
        return results
    
    def monte_carlo_simulation(self, n_simulations: int = 1000, show_progress: bool = True) -> Dict:
        """Run Monte Carlo simulation"""
        if show_progress:
            self.ui.show_progress(f"Running {n_simulations} Monte Carlo simulations")
        
        n_trades = len(self.df)
        pnl_values = self.df['P/L'].values
        
        simulation_results = []
        for i in range(n_simulations):
            if show_progress and i % 100 == 0:
                self.ui.show_progress(f"Monte Carlo simulation", i, n_simulations)
            
            simulated_trades = np.random.choice(pnl_values, size=n_trades, replace=True)
            cumulative_pnl = simulated_trades.cumsum()
            simulation_results.append({
                'final_pnl': cumulative_pnl[-1],
                'max_pnl': cumulative_pnl.max(),
                'min_pnl': cumulative_pnl.min(),
                'max_drawdown': np.min(cumulative_pnl - np.maximum.accumulate(cumulative_pnl))
            })
        
        if show_progress:
            self.ui.show_progress(f"Monte Carlo simulation", n_simulations, n_simulations)
        
        sim_df = pd.DataFrame(simulation_results)
        
        return {
            'mean_final_pnl': sim_df['final_pnl'].mean(),
            'std_final_pnl': sim_df['final_pnl'].std(),
            'percentile_5': sim_df['final_pnl'].quantile(0.05),
            'percentile_95': sim_df['final_pnl'].quantile(0.95),
            'prob_profitable': (sim_df['final_pnl'] > 0).mean(),
            'mean_max_drawdown': sim_df['max_drawdown'].mean(),
            'worst_drawdown': sim_df['max_drawdown'].min()
        }
    
    def create_entry_time_heatmap(self):
        """Create heatmap visualization"""
        self.ui.show_progress("Creating entry time heatmap")
        
        # Create pivot tables
        pivot_pnl = self.df.pivot_table(
            values='P/L',
            index=self.df['Hour'],
            columns=self.df['Day of Week'],
            aggfunc='mean'
        )
        
        pivot_count = self.df.pivot_table(
            values='P/L',
            index=self.df['Hour'],
            columns=self.df['Day of Week'],
            aggfunc='count'
        )
        
        # Create figure
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # P/L heatmap
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        sns.heatmap(pivot_pnl, annot=True, fmt='.0f', cmap='RdYlGn', center=0,
                   xticklabels=day_names, yticklabels=[f"{int(h):02d}:00" for h in pivot_pnl.index],
                   ax=ax1, cbar_kws={'label': 'Avg P/L ($)'})
        ax1.set_title('Average P/L by Entry Time', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Day of Week')
        ax1.set_ylabel('Hour of Day')
        
        # Count heatmap
        sns.heatmap(pivot_count, annot=True, fmt='.0f', cmap='Blues',
                   xticklabels=day_names, yticklabels=[f"{int(h):02d}:00" for h in pivot_count.index],
                   ax=ax2, cbar_kws={'label': 'Trade Count'})
        ax2.set_title('Trade Count by Entry Time', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Day of Week')
        ax2.set_ylabel('Hour of Day')
        
        plt.suptitle('Entry Time Analysis', fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        filename = 'entry_time_heatmap.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"{Fore.GREEN}✅ Saved: {filename}")
        
        if self.results.get('show_plots', True):
            plt.show()
        else:
            plt.close()
    
    def create_bubble_chart(self):
        """Create bubble chart visualization"""
        self.ui.show_progress("Creating bubble chart")
        
        # Use Backtest Entry Time if available, otherwise use Hour/Minute
        if 'Backtest Entry Time' in self.df.columns:
            # Group by Backtest Entry Time
            time_analysis = self.df.groupby('Backtest Entry Time').agg({
                'P/L': ['mean', 'sum', 'count']
            }).reset_index()
            
            time_analysis.columns = ['Entry_Time', 'Avg_PnL', 'Total_PnL', 'Trade_Count']
            
            # Calculate win rate for each time
            win_rates = []
            for _, row in time_analysis.iterrows():
                mask = self.df['Backtest Entry Time'] == row['Entry_Time']
                win_rate = (self.df.loc[mask, 'P/L'] > 0).mean()
                win_rates.append(win_rate)
            time_analysis['Win_Rate'] = win_rates
            
            # Parse time to numeric format for plotting
            time_numeric = []
            for time_str in time_analysis['Entry_Time']:
                try:
                    parts = str(time_str).split(':')
                    hour = float(parts[0])
                    minute = float(parts[1]) if len(parts) > 1 else 0
                    time_numeric.append(hour + minute/60)
                except:
                    time_numeric.append(0)
            time_analysis['Time_Numeric'] = time_numeric
            
        else:
            # Fall back to Hour/Minute analysis
            time_analysis = self.df.groupby(['Hour', 'Minute']).agg({
                'P/L': ['mean', 'sum', 'count']
            }).reset_index()
            
            time_analysis.columns = ['Hour', 'Minute', 'Avg_PnL', 'Total_PnL', 'Trade_Count']
            
            # Calculate win rate for each time
            win_rates = []
            for _, row in time_analysis.iterrows():
                mask = (self.df['Hour'] == row['Hour']) & (self.df['Minute'] == row['Minute'])
                win_rate = (self.df.loc[mask, 'P/L'] > 0).mean()
                win_rates.append(win_rate)
            time_analysis['Win_Rate'] = win_rates
            time_analysis['Time_Numeric'] = time_analysis['Hour'] + time_analysis['Minute']/60
        
        # Filter for significance
        time_analysis = time_analysis[time_analysis['Trade_Count'] >= 3]
        
        if len(time_analysis) == 0:
            print(f"{Fore.YELLOW}⚠️  Not enough data for bubble chart")
            return
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Create scatter plot
        scatter = ax.scatter(
            time_analysis['Time_Numeric'],
            time_analysis['Avg_PnL'],
            s=time_analysis['Trade_Count'] * 30,
            c=time_analysis['Win_Rate'],
            cmap='RdYlGn',
            alpha=0.6,
            edgecolors='black',
            linewidth=1,
            vmin=0, vmax=1
        )
        
        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Win Rate', rotation=270, labelpad=15)
        
        # Formatting
        ax.set_xlabel('Hour of Day', fontsize=12, fontweight='bold')
        ax.set_ylabel('Average P/L ($)', fontsize=12, fontweight='bold')
        ax.set_title('Entry Time Performance Analysis\n(Bubble Size = Trade Count, Color = Win Rate)',
                    fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='r', linestyle='--', alpha=0.5, label='Break-even')
        
        # X-axis formatting
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 2))
        ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
        
        # Legend for bubble sizes
        sizes = [10, 50, 100]
        labels = ['10 trades', '50 trades', '100 trades']
        legend_bubbles = []
        for size, label in zip(sizes, labels):
            legend_bubbles.append(plt.scatter([], [], s=size*30, c='gray', alpha=0.6))
        ax.legend(legend_bubbles, labels, scatterpoints=1, loc='upper left',
                 title='Trade Count', frameon=True, fancybox=True)
        
        plt.tight_layout()
        
        filename = 'entry_time_bubbles.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"{Fore.GREEN}✅ Saved: {filename}")
        
        if self.results.get('show_plots', True):
            plt.show()
        else:
            plt.close()
    
    def create_performance_dashboard(self):
        """Create comprehensive dashboard"""
        self.ui.show_progress("Creating performance dashboard")
        
        fig = plt.figure(figsize=(16, 12))
        
        # Prepare data
        df_sorted = self.df.sort_values('Datetime Opened')
        cumulative_pnl = df_sorted['P/L'].cumsum()
        
        # 1. Cumulative P/L
        ax1 = plt.subplot(3, 3, 1)
        ax1.plot(df_sorted['Date Opened'], cumulative_pnl, linewidth=2, color='#2E86AB')
        ax1.fill_between(df_sorted['Date Opened'], 0, cumulative_pnl, alpha=0.3, color='#2E86AB')
        ax1.set_title('Cumulative P/L', fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('P/L ($)')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. P/L Distribution
        ax2 = plt.subplot(3, 3, 2)
        n, bins, patches = ax2.hist(self.df['P/L'], bins=30, edgecolor='black', alpha=0.7)
        # Color bars based on profit/loss
        for i, patch in enumerate(patches):
            if bins[i] < 0:
                patch.set_facecolor('#FF6B6B')
            else:
                patch.set_facecolor('#4ECDC4')
        ax2.axvline(x=0, color='black', linestyle='--', linewidth=2, label='Break-even')
        ax2.axvline(x=self.df['P/L'].mean(), color='gold', linestyle='--', linewidth=2, label=f'Mean: ${self.df["P/L"].mean():.0f}')
        ax2.set_title('P/L Distribution', fontweight='bold')
        ax2.set_xlabel('P/L ($)')
        ax2.set_ylabel('Frequency')
        ax2.legend()
        
        # 3. Win Rate by Month
        ax3 = plt.subplot(3, 3, 3)
        monthly_winrate = self.df.groupby(self.df['Date Opened'].dt.to_period('M')).apply(
            lambda x: (x['P/L'] > 0).mean()
        )
        if len(monthly_winrate) > 0:
            colors = ['#4ECDC4' if wr >= 0.5 else '#FF6B6B' for wr in monthly_winrate.values]
            monthly_winrate.plot(kind='bar', ax=ax3, color=colors, edgecolor='black')
            ax3.axhline(y=0.5, color='black', linestyle='--', alpha=0.5, label='50% Win Rate')
            ax3.set_title('Monthly Win Rate', fontweight='bold')
            ax3.set_xlabel('Month')
            ax3.set_ylabel('Win Rate')
            ax3.legend()
            plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)
        
        # 4. Drawdown
        ax4 = plt.subplot(3, 3, 4)
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        ax4.fill_between(df_sorted['Date Opened'], 0, drawdown, color='#FF6B6B', alpha=0.5)
        ax4.plot(df_sorted['Date Opened'], drawdown, color='#8B0000', linewidth=1)
        ax4.set_title('Drawdown Analysis', fontweight='bold')
        ax4.set_xlabel('Date')
        ax4.set_ylabel('Drawdown ($)')
        ax4.grid(True, alpha=0.3)
        ax4.tick_params(axis='x', rotation=45)
        
        # 5. P/L by Day of Week
        ax5 = plt.subplot(3, 3, 5)
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        daily_pnl = self.df.groupby('Day of Week')['P/L'].mean()
        colors = ['#4ECDC4' if pnl > 0 else '#FF6B6B' for pnl in daily_pnl.values]
        bars = ax5.bar(range(len(daily_pnl)), daily_pnl.values, color=colors, edgecolor='black')
        ax5.set_xticks(range(len(daily_pnl)))
        ax5.set_xticklabels(day_names)
        ax5.set_title('Average P/L by Day', fontweight='bold')
        ax5.set_xlabel('Day of Week')
        ax5.set_ylabel('Avg P/L ($)')
        ax5.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        # Add value labels on bars
        for bar, val in zip(bars, daily_pnl.values):
            height = bar.get_height()
            ax5.text(bar.get_x() + bar.get_width()/2., height,
                    f'${val:.0f}', ha='center', va='bottom' if val > 0 else 'top')
        
        # 6. Trade Duration vs P/L
        ax6 = plt.subplot(3, 3, 6)
        duration_valid = self.df[self.df['Duration (minutes)'].notna() & (self.df['Duration (minutes)'] < 1440)]
        if len(duration_valid) > 0:
            colors = ['#4ECDC4' if pnl > 0 else '#FF6B6B' for pnl in duration_valid['P/L']]
            ax6.scatter(duration_valid['Duration (minutes)'], duration_valid['P/L'],
                       alpha=0.5, s=20, c=colors, edgecolors='black', linewidth=0.5)
            ax6.set_title('P/L vs Trade Duration', fontweight='bold')
            ax6.set_xlabel('Duration (minutes)')
            ax6.set_ylabel('P/L ($)')
            ax6.axhline(y=0, color='black', linestyle='--', alpha=0.5)
            ax6.grid(True, alpha=0.3)
        
        # 7. Rolling Sharpe
        ax7 = plt.subplot(3, 3, 7)
        daily_returns = df_sorted.set_index('Date Opened')['P/L'].resample('D').sum()
        if len(daily_returns) > 30:
            rolling_sharpe = (daily_returns.rolling(30).mean() / daily_returns.rolling(30).std()) * np.sqrt(252)
            ax7.plot(rolling_sharpe.index, rolling_sharpe.values, linewidth=2, color='#7209B7')
            ax7.fill_between(rolling_sharpe.index, 0, rolling_sharpe.values, 
                            where=(rolling_sharpe.values > 0), color='#4ECDC4', alpha=0.3)
            ax7.fill_between(rolling_sharpe.index, 0, rolling_sharpe.values,
                            where=(rolling_sharpe.values <= 0), color='#FF6B6B', alpha=0.3)
            ax7.set_title('30-Day Rolling Sharpe Ratio', fontweight='bold')
            ax7.set_xlabel('Date')
            ax7.set_ylabel('Sharpe Ratio')
            ax7.axhline(y=0, color='black', linestyle='--', alpha=0.5)
            ax7.axhline(y=1, color='green', linestyle='--', alpha=0.3, label='Good (>1)')
            ax7.grid(True, alpha=0.3)
            ax7.legend()
            ax7.tick_params(axis='x', rotation=45)
        
        # 8. Monte Carlo
        ax8 = plt.subplot(3, 3, 8)
        # Run quick MC simulation for visualization
        for _ in range(50):
            sim_trades = np.random.choice(self.df['P/L'].values, size=len(self.df), replace=True)
            ax8.plot(sim_trades.cumsum(), alpha=0.1, color='blue')
        ax8.plot(cumulative_pnl.values, color='red', linewidth=2, label='Actual', zorder=10)
        ax8.set_title('Monte Carlo Simulation (50 runs)', fontweight='bold')
        ax8.set_xlabel('Trade Number')
        ax8.set_ylabel('Cumulative P/L ($)')
        ax8.legend()
        ax8.grid(True, alpha=0.3)
        
        # 9. Top/Bottom Trades or Strategy Performance
        ax9 = plt.subplot(3, 3, 9)
        
        # Check if Strategy column exists and has data
        if 'Strategy' in self.df.columns and self.df['Strategy'].notna().any():
            # Strategy performance
            strategy_perf = self.df.groupby('Strategy')['P/L'].agg(['mean', 'count'])
            strategy_perf = strategy_perf[strategy_perf['count'] >= 5]  # Min 5 trades
            
            if len(strategy_perf) > 0:
                strategy_perf = strategy_perf.sort_values('mean')
                colors_strat = ['#4ECDC4' if x > 0 else '#FF6B6B' for x in strategy_perf['mean']]
                bars = ax9.barh(range(len(strategy_perf)), strategy_perf['mean'], color=colors_strat, edgecolor='black')
                ax9.set_yticks(range(len(strategy_perf)))
                ax9.set_yticklabels([f"{idx}\n({int(row['count'])} trades)" 
                                     for idx, row in strategy_perf.iterrows()])
                ax9.set_title('Average P/L by Strategy', fontweight='bold')
                ax9.set_xlabel('Avg P/L ($)')
                ax9.axvline(x=0, color='black', linestyle='--', alpha=0.5)
                
                # Add value labels
                for bar, val in zip(bars, strategy_perf['mean']):
                    width = bar.get_width()
                    ax9.text(width, bar.get_y() + bar.get_height()/2.,
                            f'${val:.0f}', ha='left' if val > 0 else 'right', va='center')
            else:
                # Fall back to top/bottom trades if no strategy data
                self._plot_top_bottom_trades(ax9)
        else:
            # Default to top/bottom trades
            self._plot_top_bottom_trades(ax9)
        
        plt.suptitle('Trading Performance Dashboard', fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        filename = 'performance_dashboard.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"{Fore.GREEN}✅ Saved: {filename}")
        
        if self.results.get('show_plots', True):
            plt.show()
        else:
            plt.close()
    
    def _plot_top_bottom_trades(self, ax):
        """Helper method to plot top/bottom trades"""
        top_5 = self.df.nlargest(5, 'P/L')['P/L'].values
        bottom_5 = self.df.nsmallest(5, 'P/L')['P/L'].values
        
        positions = list(range(1, 6)) + list(range(7, 12))
        values = list(top_5) + list(bottom_5)
        colors_bars = ['#4ECDC4'] * 5 + ['#FF6B6B'] * 5
        
        bars = ax.barh(positions, values, color=colors_bars, edgecolor='black')
        ax.set_yticks(positions)
        ax.set_yticklabels(['Top 1', 'Top 2', 'Top 3', 'Top 4', 'Top 5',
                            'Bot 1', 'Bot 2', 'Bot 3', 'Bot 4', 'Bot 5'])
        ax.set_title('Best & Worst Trades', fontweight='bold')
        ax.set_xlabel('P/L ($)')
        ax.axvline(x=0, color='black', linestyle='--', alpha=0.5)
        # Add value labels
        for bar, val in zip(bars, values):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2.,
                    f'${val:.0f}', ha='left' if val > 0 else 'right', va='center')
    
    def print_analysis_report(self):
        """Print formatted analysis report"""
        self.ui.print_section("ANALYSIS RESULTS")
        
        # Overall Performance
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 OVERALL PERFORMANCE")
        print(f"{Fore.CYAN}{'─'*40}")
        
        metrics = self.results['performance_metrics']
        
        # Color code based on performance
        pnl_color = Fore.GREEN if metrics['total_pnl'] > 0 else Fore.RED
        wr_color = Fore.GREEN if metrics['win_rate'] > 0.5 else Fore.RED
        sharpe_color = Fore.GREEN if metrics['sharpe_ratio'] > 1 else Fore.YELLOW if metrics['sharpe_ratio'] > 0 else Fore.RED
        
        print(f"{Fore.WHITE}Total Trades: {Style.BRIGHT}{metrics['total_trades']:,}")
        print(f"{Fore.WHITE}Total P&L: {pnl_color}{Style.BRIGHT}${metrics['total_pnl']:,.2f}")
        print(f"{Fore.WHITE}Average P&L: {pnl_color}${metrics['avg_pnl']:.2f}")
        print(f"{Fore.WHITE}Win Rate: {wr_color}{metrics['win_rate']:.1%}")
        print(f"{Fore.WHITE}Profit Factor: {Fore.CYAN}{metrics['profit_factor']:.2f}")
        print(f"{Fore.WHITE}Sharpe Ratio: {sharpe_color}{metrics['sharpe_ratio']:.3f}")
        print(f"{Fore.WHITE}Max Drawdown: {Fore.YELLOW}${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.1%})")
        print(f"{Fore.WHITE}CAGR: {Fore.CYAN}{metrics['cagr']:.1%}")
        
        # Top Entry Times
        if 'performance_by_time' in self.results and self.results['performance_by_time']:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🏆 TOP ENTRY TIMES")
            print(f"{Fore.CYAN}{'─'*40}")
            
            perf_df = pd.DataFrame(self.results['performance_by_time']).T
            perf_df = perf_df.sort_values('mar_ratio', ascending=False)
            
            for idx, (time, row) in enumerate(perf_df.head(3).iterrows(), 1):
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉"
                print(f"\n{medal} {Fore.YELLOW}{Style.BRIGHT}{time}")
                print(f"   {Fore.WHITE}MAR Ratio: {Fore.CYAN}{row['mar_ratio']:.3f}")
                print(f"   {Fore.WHITE}Win Rate: {Fore.GREEN if row['win_rate'] > 0.5 else Fore.RED}{row['win_rate']:.1%}")
                print(f"   {Fore.WHITE}Avg P&L: ${row['avg_pnl']:.2f}")
                print(f"   {Fore.WHITE}Trades: {int(row['total_trades'])}")
        
        # Day of Week Performance
        if 'day_of_week_performance' in self.results and self.results['day_of_week_performance']:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}📅 DAY OF WEEK PERFORMANCE")
            print(f"{Fore.CYAN}{'─'*40}")
            
            dow_df = pd.DataFrame(self.results['day_of_week_performance']).T
            dow_df = dow_df.sort_values('avg_pnl', ascending=False)
            
            for day, row in dow_df.head(3).iterrows():
                pnl_color = Fore.GREEN if row['avg_pnl'] > 0 else Fore.RED
                print(f"{Fore.WHITE}{day}: {pnl_color}${row['avg_pnl']:.2f} {Fore.WHITE}| WR: {row['win_rate']:.0%} | {int(row['total_trades'])} trades")
        
        # Strategy Performance (if available)
        if 'Strategy' in self.df.columns and self.df['Strategy'].notna().any():
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🎯 STRATEGY PERFORMANCE")
            print(f"{Fore.CYAN}{'─'*40}")
            
            strategy_stats = self.df.groupby('Strategy').agg({
                'P/L': ['mean', 'sum', 'count'],
                'Trade P&L': lambda x: (x > 0).mean()  # Win rate
            }).round(2)
            
            strategy_stats.columns = ['Avg P&L', 'Total P&L', 'Trades', 'Win Rate']
            strategy_stats = strategy_stats.sort_values('Avg P&L', ascending=False)
            
            for strategy, row in strategy_stats.iterrows():
                if row['Trades'] >= 5:  # Only show strategies with 5+ trades
                    pnl_color = Fore.GREEN if row['Avg P&L'] > 0 else Fore.RED
                    print(f"{Fore.WHITE}{strategy}: {pnl_color}${row['Avg P&L']:.2f} {Fore.WHITE}| Total: ${row['Total P&L']:.0f} | WR: {row['Win Rate']:.0%} | {int(row['Trades'])} trades")
        
        # Exit Reasons Analysis
        if 'exit_reasons' in self.results and self.results['exit_reasons']:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🚪 EXIT REASON ANALYSIS")
            print(f"{Fore.CYAN}{'─'*40}")
            
            exit_df = pd.DataFrame(self.results['exit_reasons']).T
            exit_df = exit_df.sort_values('avg_pnl', ascending=False)
            
            for reason, row in exit_df.iterrows():
                pnl_color = Fore.GREEN if row['avg_pnl'] > 0 else Fore.RED
                wr_color = Fore.GREEN if row['win_rate'] > 0.5 else Fore.RED
                print(f"{Fore.WHITE}{reason}: {pnl_color}${row['avg_pnl']:.2f} {Fore.WHITE}| WR: {wr_color}{row['win_rate']:.0%} {Fore.WHITE}| {int(row['total_trades'])} trades")
        
        # Period Comparison
        if 'period_comparison' in self.results:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}📈 PERIOD COMPARISON")
            print(f"{Fore.CYAN}{'─'*40}")
            
            if 'recent_6_months' in self.results['period_comparison'] and 'historical' in self.results['period_comparison']:
                recent = self.results['period_comparison']['recent_6_months']
                historical = self.results['period_comparison']['historical']
                
                # Calculate changes
                wr_change = ((recent['win_rate'] - historical['win_rate']) / historical['win_rate'] * 100) if historical['win_rate'] != 0 else 0
                pnl_change = ((recent['avg_pnl'] - historical['avg_pnl']) / abs(historical['avg_pnl']) * 100) if historical['avg_pnl'] != 0 else 0
                
                print(f"\n{Fore.WHITE}Recent 6 Months vs Historical:")
                print(f"  Win Rate: {recent['win_rate']:.1%} vs {historical['win_rate']:.1%} " + 
                     f"({Fore.GREEN if wr_change > 0 else Fore.RED}{wr_change:+.1f}%{Fore.WHITE})")
                print(f"  Avg P&L: ${recent['avg_pnl']:.2f} vs ${historical['avg_pnl']:.2f} " +
                     f"({Fore.GREEN if pnl_change > 0 else Fore.RED}{pnl_change:+.1f}%{Fore.WHITE})")
        
        # Monte Carlo
        if 'monte_carlo' in self.results:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🎲 MONTE CARLO SIMULATION")
            print(f"{Fore.CYAN}{'─'*40}")
            
            mc = self.results['monte_carlo']
            prob_color = Fore.GREEN if mc['prob_profitable'] > 0.7 else Fore.YELLOW if mc['prob_profitable'] > 0.5 else Fore.RED
            
            print(f"{Fore.WHITE}Expected P&L: ${mc['mean_final_pnl']:,.0f} ± ${mc['std_final_pnl']:,.0f}")
            print(f"{Fore.WHITE}95% Confidence: ${mc['percentile_5']:,.0f} to ${mc['percentile_95']:,.0f}")
            print(f"{Fore.WHITE}Probability of Profit: {prob_color}{mc['prob_profitable']:.1%}")
        
        # Recommendations
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}💡 RECOMMENDATIONS")
        print(f"{Fore.YELLOW}{'─'*40}")
        
        # Kelly Criterion
        kelly = metrics.get('kelly_fraction_conservative', 0.02)
        print(f"{Fore.WHITE}📊 Position Sizing: Risk {Fore.GREEN}{kelly:.1%}{Fore.WHITE} per trade (Kelly)")
        
        # Average margin requirement if available
        if 'Margin Req' in self.df.columns:
            avg_margin = self.df['Margin Req'].mean()
            if pd.notna(avg_margin) and avg_margin > 0:
                print(f"{Fore.WHITE}💵 Avg Margin Required: ${avg_margin:,.0f}")
                if kelly > 0:
                    suggested_capital = avg_margin / kelly
                    print(f"{Fore.WHITE}💰 Suggested Capital: ${suggested_capital:,.0f}")
        
        # Entry times
        if 'performance_by_time' in self.results and self.results['performance_by_time']:
            best_times = list(perf_df.head(3).index)
            print(f"{Fore.WHITE}✅ Best entry times: {Fore.GREEN}{', '.join(best_times)}")
            
            worst_times = list(perf_df[perf_df['total_trades'] >= 10].tail(2).index)
            if worst_times:
                print(f"{Fore.WHITE}❌ Avoid: {Fore.RED}{', '.join(worst_times)}")
        
        # Risk limits
        if metrics['max_drawdown'] < 0:
            daily_limit = abs(metrics['max_drawdown']) / 10
            print(f"{Fore.WHITE}🛑 Daily Loss Limit: {Fore.YELLOW}${daily_limit:,.0f}")
        
        print(f"\n{Fore.CYAN}{'='*60}")
        """Print formatted analysis report"""
        self.ui.print_section("ANALYSIS RESULTS")
        
        # Overall Performance
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 OVERALL PERFORMANCE")
        print(f"{Fore.CYAN}{'─'*40}")
        
        metrics = self.results['performance_metrics']
        
        # Color code based on performance
        pnl_color = Fore.GREEN if metrics['total_pnl'] > 0 else Fore.RED
        wr_color = Fore.GREEN if metrics['win_rate'] > 0.5 else Fore.RED
        sharpe_color = Fore.GREEN if metrics['sharpe_ratio'] > 1 else Fore.YELLOW if metrics['sharpe_ratio'] > 0 else Fore.RED
        
        print(f"{Fore.WHITE}Total Trades: {Style.BRIGHT}{metrics['total_trades']:,}")
        print(f"{Fore.WHITE}Total P&L: {pnl_color}{Style.BRIGHT}${metrics['total_pnl']:,.2f}")
        print(f"{Fore.WHITE}Average P&L: {pnl_color}${metrics['avg_pnl']:.2f}")
        print(f"{Fore.WHITE}Win Rate: {wr_color}{metrics['win_rate']:.1%}")
        print(f"{Fore.WHITE}Profit Factor: {Fore.CYAN}{metrics['profit_factor']:.2f}")
        print(f"{Fore.WHITE}Sharpe Ratio: {sharpe_color}{metrics['sharpe_ratio']:.3f}")
        print(f"{Fore.WHITE}Max Drawdown: {Fore.YELLOW}${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.1%})")
        print(f"{Fore.WHITE}CAGR: {Fore.CYAN}{metrics['cagr']:.1%}")
        
        # Top Entry Times
        if 'performance_by_time' in self.results and self.results['performance_by_time']:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🏆 TOP ENTRY TIMES")
            print(f"{Fore.CYAN}{'─'*40}")
            
            perf_df = pd.DataFrame(self.results['performance_by_time']).T
            perf_df = perf_df.sort_values('mar_ratio', ascending=False)
            
            for idx, (time, row) in enumerate(perf_df.head(3).iterrows(), 1):
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉"
                print(f"\n{medal} {Fore.YELLOW}{Style.BRIGHT}{time}")
                print(f"   {Fore.WHITE}MAR Ratio: {Fore.CYAN}{row['mar_ratio']:.3f}")
                print(f"   {Fore.WHITE}Win Rate: {Fore.GREEN if row['win_rate'] > 0.5 else Fore.RED}{row['win_rate']:.1%}")
                print(f"   {Fore.WHITE}Avg P&L: ${row['avg_pnl']:.2f}")
                print(f"   {Fore.WHITE}Trades: {int(row['total_trades'])}")
        
        # Day of Week Performance
        if 'day_of_week_performance' in self.results and self.results['day_of_week_performance']:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}📅 DAY OF WEEK PERFORMANCE")
            print(f"{Fore.CYAN}{'─'*40}")
            
            dow_df = pd.DataFrame(self.results['day_of_week_performance']).T
            dow_df = dow_df.sort_values('avg_pnl', ascending=False)
            
            for day, row in dow_df.head(3).iterrows():
                pnl_color = Fore.GREEN if row['avg_pnl'] > 0 else Fore.RED
                print(f"{Fore.WHITE}{day}: {pnl_color}${row['avg_pnl']:.2f} {Fore.WHITE}| WR: {row['win_rate']:.0%} | {int(row['total_trades'])} trades")
        
        # Strategy Performance (if available)
        if 'Strategy' in self.df.columns and self.df['Strategy'].notna().any():
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🎯 STRATEGY PERFORMANCE")
            print(f"{Fore.CYAN}{'─'*40}")
            
            strategy_stats = self.df.groupby('Strategy').agg({
                'P/L': ['mean', 'sum', 'count'],
                'Trade P&L': lambda x: (x > 0).mean()  # Win rate
            }).round(2)
            
            strategy_stats.columns = ['Avg P&L', 'Total P&L', 'Trades', 'Win Rate']
            strategy_stats = strategy_stats.sort_values('Avg P&L', ascending=False)
            
            for strategy, row in strategy_stats.iterrows():
                if row['Trades'] >= 5:  # Only show strategies with 5+ trades
                    pnl_color = Fore.GREEN if row['Avg P&L'] > 0 else Fore.RED
                    print(f"{Fore.WHITE}{strategy}: {pnl_color}${row['Avg P&L']:.2f} {Fore.WHITE}| Total: ${row['Total P&L']:.0f} | WR: {row['Win Rate']:.0%} | {int(row['Trades'])} trades")
        
        # Exit Reasons Analysis
        if 'exit_reasons' in self.results and self.results['exit_reasons']:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🚪 EXIT REASON ANALYSIS")
            print(f"{Fore.CYAN}{'─'*40}")
            
            exit_df = pd.DataFrame(self.results['exit_reasons']).T
            exit_df = exit_df.sort_values('avg_pnl', ascending=False)
            
            for reason, row in exit_df.iterrows():
                pnl_color = Fore.GREEN if row['avg_pnl'] > 0 else Fore.RED
                wr_color = Fore.GREEN if row['win_rate'] > 0.5 else Fore.RED
                print(f"{Fore.WHITE}{reason}: {pnl_color}${row['avg_pnl']:.2f} {Fore.WHITE}| WR: {wr_color}{row['win_rate']:.0%} {Fore.WHITE}| {int(row['total_trades'])} trades")
        
        # Period Comparison
        if 'period_comparison' in self.results:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}📈 PERIOD COMPARISON")
            print(f"{Fore.CYAN}{'─'*40}")
            
            if 'recent_6_months' in self.results['period_comparison'] and 'historical' in self.results['period_comparison']:
                recent = self.results['period_comparison']['recent_6_months']
                historical = self.results['period_comparison']['historical']
                
                # Calculate changes
                wr_change = ((recent['win_rate'] - historical['win_rate']) / historical['win_rate'] * 100) if historical['win_rate'] != 0 else 0
                pnl_change = ((recent['avg_pnl'] - historical['avg_pnl']) / abs(historical['avg_pnl']) * 100) if historical['avg_pnl'] != 0 else 0
                
                print(f"\n{Fore.WHITE}Recent 6 Months vs Historical:")
                print(f"  Win Rate: {recent['win_rate']:.1%} vs {historical['win_rate']:.1%} " + 
                     f"({Fore.GREEN if wr_change > 0 else Fore.RED}{wr_change:+.1f}%{Fore.WHITE})")
                print(f"  Avg P&L: ${recent['avg_pnl']:.2f} vs ${historical['avg_pnl']:.2f} " +
                     f"({Fore.GREEN if pnl_change > 0 else Fore.RED}{pnl_change:+.1f}%{Fore.WHITE})")
        
        # Monte Carlo
        if 'monte_carlo' in self.results:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}🎲 MONTE CARLO SIMULATION")
            print(f"{Fore.CYAN}{'─'*40}")
            
            mc = self.results['monte_carlo']
            prob_color = Fore.GREEN if mc['prob_profitable'] > 0.7 else Fore.YELLOW if mc['prob_profitable'] > 0.5 else Fore.RED
            
            print(f"{Fore.WHITE}Expected P&L: ${mc['mean_final_pnl']:,.0f} ± ${mc['std_final_pnl']:,.0f}")
            print(f"{Fore.WHITE}95% Confidence: ${mc['percentile_5']:,.0f} to ${mc['percentile_95']:,.0f}")
            print(f"{Fore.WHITE}Probability of Profit: {prob_color}{mc['prob_profitable']:.1%}")
        
        # Recommendations
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}💡 RECOMMENDATIONS")
        print(f"{Fore.YELLOW}{'─'*40}")
        
        # Kelly Criterion
        kelly = metrics.get('kelly_fraction_conservative', 0.02)
        print(f"{Fore.WHITE}📊 Position Sizing: Risk {Fore.GREEN}{kelly:.1%}{Fore.WHITE} per trade (Kelly)")
        
        # Average margin requirement if available
        if 'Margin Req' in self.df.columns:
            avg_margin = self.df['Margin Req'].mean()
            if pd.notna(avg_margin) and avg_margin > 0:
                print(f"{Fore.WHITE}💵 Avg Margin Required: ${avg_margin:,.0f}")
                if kelly > 0:
                    suggested_capital = avg_margin / kelly
                    print(f"{Fore.WHITE}💰 Suggested Capital: ${suggested_capital:,.0f}")
        
        # Entry times
        if 'performance_by_time' in self.results and self.results['performance_by_time']:
            best_times = list(perf_df.head(3).index)
            print(f"{Fore.WHITE}✅ Best entry times: {Fore.GREEN}{', '.join(best_times)}")
            
            worst_times = list(perf_df[perf_df['total_trades'] >= 10].tail(2).index)
            if worst_times:
                print(f"{Fore.WHITE}❌ Avoid: {Fore.RED}{', '.join(worst_times)}")
        
        # Risk limits
        if metrics['max_drawdown'] < 0:
            daily_limit = abs(metrics['max_drawdown']) / 10
            print(f"{Fore.WHITE}🛑 Daily Loss Limit: {Fore.YELLOW}${daily_limit:,.0f}")
        
        print(f"\n{Fore.CYAN}{'='*60}")
    
    def save_results_to_json(self):
        """Export results to JSON file"""
        self.ui.show_progress("Saving results to JSON")
        
        def convert_to_serializable(obj):
            """Convert numpy/pandas types for JSON"""
            if isinstance(obj, (np.ndarray, pd.Series)):
                return obj.tolist()
            elif isinstance(obj, (np.int64, np.int32, np.int16)):
                return int(obj)
            elif isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            return obj
        
        # Prepare export data
        export_data = {
            'analysis_date': datetime.now().isoformat(),
            'file_analyzed': os.path.basename(self.filepath),
            'total_trades': len(self.df),
            'date_range': {
                'start': self.df['Date Opened'].min().isoformat(),
                'end': self.df['Date Opened'].max().isoformat()
            },
            'results': convert_to_serializable(self.results)
        }
        
        filename = f"analysis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"{Fore.GREEN}✅ Results saved to: {filename}")
    
    def analyze_exit_reasons(self) -> Dict:
        """Analyze performance by exit reason"""
        self.ui.show_progress("Analyzing exit reasons")
        results = {}
        
        if 'Reason For Close' in self.df.columns:
            for reason in self.df['Reason For Close'].dropna().unique():
                reason_df = self.df[self.df['Reason For Close'] == reason]
                if len(reason_df) >= 5:  # Minimum trades for significance
                    results[str(reason)] = self.calculate_performance_metrics(reason_df)
        
        return results
    
    def run_analysis(self, options: Dict):
        """Run complete analysis based on user options"""
        self.results = options
        
        # Load data
        self.load_data()
        
        # Always calculate basic metrics
        self.ui.print_section("RUNNING ANALYSIS")
        self.results['performance_metrics'] = self.calculate_performance_metrics(self.df)
        
        # Entry time analysis
        self.results['performance_by_time'] = self.analyze_entry_times()
        
        # Day of week analysis
        self.results['day_of_week_performance'] = self.analyze_day_of_week()
        
        # Exit reasons analysis
        self.results['exit_reasons'] = self.analyze_exit_reasons()
        
        # Optional analyses
        if options.get('period_comparison', True):
            self.results['period_comparison'] = self.compare_periods()
        
        if options.get('monte_carlo', True):
            self.results['monte_carlo'] = self.monte_carlo_simulation()
        
        # Visualizations
        if options.get('heatmap', True):
            self.create_entry_time_heatmap()
        
        if options.get('bubble', True):
            self.create_bubble_chart()
        
        if options.get('dashboard', True):
            self.create_performance_dashboard()
        
        # Print report
        self.print_analysis_report()
        
        # Save JSON
        if options.get('save_json', True):
            self.save_results_to_json()
        
        print(f"\n{Fore.GREEN}{Style.BRIGHT}✅ Analysis Complete!")
        print(f"{Fore.WHITE}Generated files are saved in the current directory.")

def main():
    """Main program entry point"""
    ui = UserInterface()
    
    try:
        # Clear screen and show header
        ui.clear_screen()
        ui.print_header()
        
        # Get file path
        filepath = ui.get_file_path()
        
        # Get analysis options
        options = ui.get_analysis_options()
        
        # Create analyzer and run
        analyzer = TradeAnalyzer(filepath, ui)
        analyzer.run_analysis(options)
        
        # Ask if user wants to run another analysis
        print(f"\n{Fore.YELLOW}Run another analysis? (y/n): ", end="")
        if input().strip().lower() == 'y':
            main()
        else:
            print(f"\n{Fore.CYAN}Thank you for using Trade Analysis Tool!")
            print(f"{Fore.WHITE}Happy Trading! 📈")
        
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Analysis interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}❌ An error occurred: {str(e)}")
        print(f"{Fore.YELLOW}Please check your data and try again.")
        sys.exit(1)

if __name__ == "__main__":
    # Check for required packages
    required_packages = ['pandas', 'numpy', 'matplotlib', 'seaborn', 'scipy']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"{Fore.RED if COLOR_AVAILABLE else ''}❌ Missing required packages: {', '.join(missing_packages)}")
        print(f"{Fore.YELLOW if COLOR_AVAILABLE else ''}Please install them using:")
        print(f"   pip install {' '.join(missing_packages)}")
        sys.exit(1)
    
    main()
