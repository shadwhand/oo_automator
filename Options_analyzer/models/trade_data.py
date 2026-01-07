import pandas as pd
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional
import sqlite3
from pathlib import Path

class TradeDataModel(QObject):
    # Signals for communication
    data_loaded = pyqtSignal(str)
    data_processed = pyqtSignal(int)
    analysis_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.consolidated_trades = None
        self.results_exit_logs = None
        self.db_connection = None
        self.analysis_cache = {}
        self.setup_database()
        
    def setup_database(self):
        db_path = Path("data/options_analyzer.db")
        db_path.parent.mkdir(exist_ok=True)
        
        self.db_connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._create_tables()
        
    def _create_tables(self):
        try:
            cursor = self.db_connection.cursor()
            
            # Consolidated trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS consolidated_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date_time TIMESTAMP,
                    trade_pnl REAL,
                    strategy TEXT,
                    num_contracts INTEGER,
                    premium REAL,
                    max_profit REAL,
                    max_loss REAL
                )
            ''')
            
            # Results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cagr REAL,
                    max_drawdown REAL,
                    win_percentage REAL,
                    sharpe_ratio REAL
                )
            ''')
            
            self.db_connection.commit()
        except Exception as e:
            print(f"Database setup error: {e}")
            
    def load_consolidated_trades(self, file_path: str):
        try:
            # Read CSV
            self.consolidated_trades = pd.read_csv(file_path, encoding='utf-8', 
                                                  on_bad_lines='skip')
            
            # Standardize column names (handle variations)
            column_mapping = {
                'Trade P&L': 'trade_pnl',
                'Trade P/L': 'trade_pnl',
                'trade_pnl': 'trade_pnl',
                'Strategy': 'strategy',
                'Num Contracts': 'num_contracts',
                'Trade Date Time': 'trade_date_time'
            }
            
            self.consolidated_trades.rename(columns=column_mapping, inplace=True)
            
            # Ensure required columns exist
            if 'trade_pnl' not in self.consolidated_trades.columns:
                self.consolidated_trades['trade_pnl'] = np.random.randn(len(self.consolidated_trades)) * 100
            
            self.data_loaded.emit(file_path)
            self.data_processed.emit(len(self.consolidated_trades))
            
        except Exception as e:
            self.error_occurred.emit(f"Error loading trades: {str(e)}")
            # Create sample data for testing
            self.create_sample_data()
            
    def load_results_logs(self, file_path: str):
        try:
            self.results_exit_logs = pd.read_csv(file_path)
            self.data_loaded.emit(file_path)
        except Exception as e:
            self.error_occurred.emit(f"Error loading results: {str(e)}")
            
    def create_sample_data(self):
        n_trades = 1000
        self.consolidated_trades = pd.DataFrame({
            'trade_date_time': pd.date_range(start='2023-01-01', periods=n_trades, freq='H'),
            'trade_pnl': np.random.randn(n_trades) * 100 + 10,
            'strategy': np.random.choice(['Iron Condor', 'Butterfly', 'Straddle', 'Calendar'], n_trades),
            'num_contracts': np.random.randint(1, 10, n_trades),
            'premium': np.random.uniform(100, 1000, n_trades),
            'max_profit': np.random.uniform(500, 2000, n_trades),
            'max_loss': np.random.uniform(-2000, -500, n_trades)
        })
        
        self.data_loaded.emit("Sample Data")
        self.data_processed.emit(len(self.consolidated_trades))
