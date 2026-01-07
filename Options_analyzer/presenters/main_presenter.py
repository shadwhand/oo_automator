from PyQt6.QtCore import QObject, QThread, pyqtSignal
import pandas as pd
import numpy as np
from models.analytics_engine import OptionsAnalyticsEngine

class AnalysisWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, trades, engine):
        super().__init__()
        self.trades = trades
        self.engine = engine
        
    def run(self):
        try:
            # Calculate metrics
            metrics = self.engine.calculate_metrics(self.trades)
            self.progress.emit(50)
            
            # Detect patterns
            patterns = self.engine.detect_mispricing_patterns(self.trades)
            self.progress.emit(100)
            
            results = {'metrics': metrics, 'patterns': patterns}
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(str(e))

class MainPresenter(QObject):
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        self.analytics_engine = OptionsAnalyticsEngine()
        self.setup_connections()
        
    def setup_connections(self):
        # View to Presenter
        self.view.load_trades_requested.connect(self.handle_load_trades)
        self.view.load_results_requested.connect(self.handle_load_results)
        self.view.analyze_requested.connect(self.run_analysis)
        
        # Model to View
        self.model.data_loaded.connect(self.on_data_loaded)
        self.model.data_processed.connect(self.on_data_processed)
        self.model.error_occurred.connect(self.show_error)
        self.model.progress_updated.connect(self.view.progress_bar.setValue)
        
    def handle_load_trades(self, file_path: str):
        self.view.log_widget.append(f"Loading trades from: {file_path}")
        self.model.load_consolidated_trades(file_path)
        
    def handle_load_results(self, file_path: str):
        self.view.log_widget.append(f"Loading results from: {file_path}")
        self.model.load_results_logs(file_path)
        
    def on_data_loaded(self, file_path: str):
        self.view.log_widget.append(f"Successfully loaded: {file_path}")
        self.view.memory_label.setText("Data Loaded")
        
    def on_data_processed(self, count: int):
        self.view.trades_label.setText(f"Trades: {count:,}")
        self.view.log_widget.append(f"Processed {count:,} trades")
        
    def run_analysis(self):
        if self.model.consolidated_trades is None:
            self.show_error("No trade data loaded. Please import a CSV file first.")
            return
            
        self.view.log_widget.append("Starting comprehensive analysis...")
        self.view.progress_bar.setValue(0)
        
        # Run analysis in worker thread
        self.analysis_worker = AnalysisWorker(
            self.model.consolidated_trades,
            self.analytics_engine
        )
        self.analysis_worker.progress.connect(self.view.progress_bar.setValue)
        self.analysis_worker.finished.connect(self.on_analysis_complete)
        self.analysis_worker.error.connect(self.show_error)
        self.analysis_worker.start()
        
    def on_analysis_complete(self, results: dict):
        self.view.progress_bar.setValue(100)
        self.view.log_widget.append("Analysis complete!")
        
        # Update dashboard metrics
        metrics = results.get('metrics', {})
        dashboard_metrics = {
            'Total P&L': f"${metrics.get('total_pnl', 0):,.2f}",
            'Win Rate': f"{metrics.get('win_rate', 0):.1%}",
            'Sharpe Ratio': f"{metrics.get('sharpe_ratio', 0):.2f}",
            'Max Drawdown': f"{metrics.get('max_drawdown', 0):.1%}",
            'CAGR': f"{metrics.get('cagr', 0):.1%}"
        }
        self.view.dashboard.update_metrics(dashboard_metrics)
        
        # Log pattern detection results
        patterns = results.get('patterns', {})
        anomalies = patterns.get('volatility_skew_anomalies', [])
        self.view.log_widget.append(f"Found {len(anomalies)} potential mispricing opportunities")
        
    def show_error(self, error_msg: str):
        self.view.log_widget.append(f"ERROR: {error_msg}")
        self.view.memory_label.setText("Error")
        self.view.progress_bar.setValue(0)
