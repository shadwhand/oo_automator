from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QTableView, QPushButton, QFileDialog, QStatusBar,
                           QMenuBar, QDockWidget, QTabWidget, QSplitter,
                           QProgressBar, QLabel, QToolBar, QMessageBox,
                           QTextEdit, QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction
import pyqtgraph as pg
from .dashboard import TradingDashboard
from .charts import ChartsWidget

class MainWindow(QMainWindow):
    # Define signals
    load_trades_requested = pyqtSignal(str)
    load_results_requested = pyqtSignal(str)
    analyze_requested = pyqtSignal()
    export_requested = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Options Trading Analyzer Pro")
        self.setGeometry(100, 100, 1400, 800)
        
        self.setup_ui()
        self.create_menus()
        self.create_toolbar()
        self.create_dock_widgets()
        self.setup_status_bar()
        
    def setup_ui(self):
        # Central widget with tabs
        self.central_widget = QTabWidget()
        self.setCentralWidget(self.central_widget)
        
        # Dashboard tab
        self.dashboard = TradingDashboard()
        self.central_widget.addTab(self.dashboard, "Dashboard")
        
        # Data view tab
        self.data_view = self.create_data_view()
        self.central_widget.addTab(self.data_view, "Trade Data")
        
        # Analytics tab
        self.analytics_view = self.create_analytics_view()
        self.central_widget.addTab(self.analytics_view, "Analytics")
        
        # Charts tab
        self.charts_view = ChartsWidget()
        self.central_widget.addTab(self.charts_view, "Visualizations")
        
    def create_data_view(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Add import button
        import_btn = QPushButton("Import CSV Files")
        import_btn.clicked.connect(self.import_trades)
        layout.addWidget(import_btn)
        
        # Table view for trades
        self.trades_table = QTableView()
        self.trades_table.setSortingEnabled(True)
        self.trades_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.trades_table)
        widget.setLayout(layout)
        return widget
        
    def create_analytics_view(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create analysis sections
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Mispricing panel
        self.mispricing_widget = QGroupBox("Mispricing Analysis")
        mispricing_layout = QVBoxLayout()
        mispricing_layout.addWidget(QLabel("Volatility Skew Anomalies: 0"))
        mispricing_layout.addWidget(QLabel("Put-Call Parity Violations: 0"))
        mispricing_layout.addWidget(QLabel("Calendar Spread Opportunities: 0"))
        self.mispricing_widget.setLayout(mispricing_layout)
        
        # Statistical panel
        self.stats_widget = QGroupBox("Statistical Analysis")
        stats_layout = QVBoxLayout()
        stats_layout.addWidget(QLabel("Sharpe Ratio: 0.00"))
        stats_layout.addWidget(QLabel("Win Rate: 0%"))
        stats_layout.addWidget(QLabel("Max Drawdown: 0%"))
        self.stats_widget.setLayout(stats_layout)
        
        # Risk panel
        self.risk_widget = QGroupBox("Risk Metrics")
        risk_layout = QVBoxLayout()
        risk_layout.addWidget(QLabel("VaR (95%): $0"))
        risk_layout.addWidget(QLabel("CVaR (95%): $0"))
        risk_layout.addWidget(QLabel("Beta: 0.00"))
        self.risk_widget.setLayout(risk_layout)
        
        splitter.addWidget(self.mispricing_widget)
        splitter.addWidget(self.stats_widget)
        splitter.addWidget(self.risk_widget)
        
        layout.addWidget(splitter)
        widget.setLayout(layout)
        return widget
        
    def create_menus(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        import_trades_action = QAction("Import &Trades...", self)
        import_trades_action.setShortcut("Ctrl+T")
        import_trades_action.triggered.connect(self.import_trades)
        file_menu.addAction(import_trades_action)
        
        import_results_action = QAction("Import &Results...", self)
        import_results_action.setShortcut("Ctrl+R")
        import_results_action.triggered.connect(self.import_results)
        file_menu.addAction(import_results_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")
        
        run_analysis_action = QAction("&Run Analysis", self)
        run_analysis_action.setShortcut("Ctrl+A")
        run_analysis_action.triggered.connect(self.run_analysis)
        analysis_menu.addAction(run_analysis_action)
        
        monte_carlo_action = QAction("&Monte Carlo Simulation", self)
        monte_carlo_action.triggered.connect(self.run_monte_carlo)
        analysis_menu.addAction(monte_carlo_action)
        
    def create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        import_action = QAction("Import", self)
        import_action.triggered.connect(self.import_trades)
        toolbar.addAction(import_action)
        
        analyze_action = QAction("Analyze", self)
        analyze_action.triggered.connect(self.run_analysis)
        toolbar.addAction(analyze_action)
        
        toolbar.addSeparator()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        toolbar.addWidget(self.progress_bar)
        
    def create_dock_widgets(self):
        # Log dock
        log_dock = QDockWidget("Analysis Log", self)
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        log_dock.setWidget(self.log_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        
    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.trades_label = QLabel("Trades: 0")
        self.status_bar.addWidget(self.trades_label)
        
        self.memory_label = QLabel("Ready")
        self.status_bar.addWidget(self.memory_label)
        
    def import_trades(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Consolidated Trades", "", "CSV Files (*.csv)")
        
        if file_path:
            self.load_trades_requested.emit(file_path)
            self.log_widget.append(f"Importing trades from: {file_path}")
            
    def import_results(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Results Exit Logs", "", "CSV Files (*.csv)")
        
        if file_path:
            self.load_results_requested.emit(file_path)
            self.log_widget.append(f"Importing results from: {file_path}")
            
    def run_analysis(self):
        self.analyze_requested.emit()
        self.log_widget.append("Running comprehensive analysis...")
        
    def run_monte_carlo(self):
        self.log_widget.append("Running Monte Carlo simulation...")
        QMessageBox.information(self, "Monte Carlo", "Monte Carlo simulation started...")
