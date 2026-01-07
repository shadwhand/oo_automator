import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QGroupBox
from PyQt6.QtCore import Qt
import numpy as np

class TradingDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QGridLayout()
        
        # Create metric cards
        self.create_metrics_cards(layout)
        
        # Create charts
        self.performance_plot = self.create_performance_chart()
        layout.addWidget(self.performance_plot, 1, 0, 2, 3)
        
        self.pnl_histogram = self.create_pnl_histogram()
        layout.addWidget(self.pnl_histogram, 1, 3, 1, 2)
        
        self.setLayout(layout)
        
    def create_metrics_cards(self, layout):
        metrics = [
            ("Total P&L", "$0.00", 0, 0),
            ("Win Rate", "0%", 0, 1),
            ("Sharpe Ratio", "0.00", 0, 2),
            ("Max Drawdown", "0%", 0, 3),
            ("CAGR", "0%", 0, 4)
        ]
        
        self.metric_labels = {}
        
        for title, value, row, col in metrics:
            card = self.create_metric_card(title, value)
            layout.addWidget(card, row, col)
            
    def create_metric_card(self, title, value):
        card = QGroupBox()
        card.setMaximumHeight(100)
        card.setStyleSheet('''
            QGroupBox {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 10px;
            }
        ''')
        
        layout = QVBoxLayout()
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px; color: #888;")
        
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #fff;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        card.setLayout(layout)
        
        # Store reference to value label
        self.metric_labels[title] = value_label
        
        return card
        
    def create_performance_chart(self):
        plot_widget = pg.PlotWidget(title="Cumulative Performance")
        plot_widget.setLabel('left', 'Cumulative Return (%)')
        plot_widget.setLabel('bottom', 'Trading Days')
        plot_widget.addLegend()
        plot_widget.showGrid(True, True, alpha=0.3)
        
        # Sample data
        x = np.arange(100)
        y1 = np.cumsum(np.random.randn(100) * 0.01) * 100
        y2 = np.cumsum(np.random.randn(100) * 0.008) * 100
        
        plot_widget.plot(x, y1, pen='g', name='Strategy', width=2)
        plot_widget.plot(x, y2, pen='b', name='SPX Benchmark', width=2)
        
        return plot_widget
        
    def create_pnl_histogram(self):
        plot_widget = pg.PlotWidget(title="P&L Distribution")
        plot_widget.setLabel('left', 'Frequency')
        plot_widget.setLabel('bottom', 'P&L ($)')
        
        # Sample data
        data = np.random.normal(100, 500, 1000)
        y, x = np.histogram(data, bins=30)
        
        # Create bar graph
        plot_widget.plot(x, y, stepMode="center", fillLevel=0, 
                        fillOutline=True, brush=(0,0,255,150))
        
        return plot_widget
        
    def update_metrics(self, metrics_dict):
        for key, value in metrics_dict.items():
            if key in self.metric_labels:
                self.metric_labels[key].setText(value)
