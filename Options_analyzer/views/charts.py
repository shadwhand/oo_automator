import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
import numpy as np

class ChartsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Top row charts
        top_layout = QHBoxLayout()
        self.volatility_chart = self.create_volatility_chart()
        self.greeks_chart = self.create_greeks_chart()
        top_layout.addWidget(self.volatility_chart)
        top_layout.addWidget(self.greeks_chart)
        
        # Bottom row charts
        bottom_layout = QHBoxLayout()
        self.heatmap = self.create_returns_heatmap()
        self.monte_carlo_chart = self.create_monte_carlo_chart()
        bottom_layout.addWidget(self.heatmap)
        bottom_layout.addWidget(self.monte_carlo_chart)
        
        layout.addLayout(top_layout)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        
    def create_volatility_chart(self):
        plot = pg.PlotWidget(title="Implied Volatility Surface")
        plot.setLabel('left', 'Strike')
        plot.setLabel('bottom', 'Days to Expiry')
        
        # Sample 3D-like visualization
        x = np.linspace(90, 110, 20)
        y = np.linspace(10, 60, 20)
        z = np.random.rand(20, 20) * 0.3 + 0.15
        
        # Create image item for heatmap
        img = pg.ImageItem(z)
        plot.addItem(img)
        
        return plot
        
    def create_greeks_chart(self):
        plot = pg.PlotWidget(title="Greeks Over Time")
        plot.setLabel('left', 'Value')
        plot.setLabel('bottom', 'Days')
        plot.addLegend()
        
        # Sample Greeks data
        days = np.arange(30)
        delta = np.linspace(0.5, 0.9, 30) + np.random.randn(30) * 0.02
        gamma = np.linspace(0.02, 0.01, 30) + np.random.randn(30) * 0.002
        theta = np.linspace(-0.5, -0.1, 30) + np.random.randn(30) * 0.02
        
        plot.plot(days, delta, pen='b', name='Delta', width=2)
        plot.plot(days, gamma * 10, pen='g', name='Gamma x10', width=2)
        plot.plot(days, theta, pen='r', name='Theta', width=2)
        
        return plot
        
    def create_returns_heatmap(self):
        plot = pg.PlotWidget(title="Monthly Returns Heatmap")
        plot.setLabel('left', 'Month')
        plot.setLabel('bottom', 'Year')
        
        # Sample monthly returns
        returns = np.random.randn(12, 3) * 5 + 2
        img = pg.ImageItem(returns)
        plot.addItem(img)
        
        return plot
        
    def create_monte_carlo_chart(self):
        plot = pg.PlotWidget(title="Monte Carlo Simulation Paths")
        plot.setLabel('left', 'Portfolio Value ($)')
        plot.setLabel('bottom', 'Days')
        
        # Sample Monte Carlo paths
        days = 252
        paths = 100
        initial = 100000
        
        for i in range(min(paths, 50)):  # Plot only 50 paths for clarity
            returns = np.random.randn(days) * 0.02 + 0.001
            path = initial * np.exp(np.cumsum(returns))
            plot.plot(np.arange(days), path, pen=(100, 100, 100, 50))
        
        # Plot mean path
        mean_returns = np.random.randn(days) * 0.02 + 0.001
        mean_path = initial * np.exp(np.cumsum(mean_returns))
        plot.plot(np.arange(days), mean_path, pen='y', width=3)
        
        return plot
