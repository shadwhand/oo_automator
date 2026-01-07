import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List
from sklearn.ensemble import IsolationForest

class OptionsAnalyticsEngine:
    def __init__(self):
        self.risk_free_rate = 0.05
        
    def detect_mispricing_patterns(self, data: pd.DataFrame) -> Dict:
        results = {
            'volatility_skew_anomalies': [],
            'put_call_parity_violations': [],
            'calendar_spread_opportunities': []
        }
        
        # Simple anomaly detection for demonstration
        if len(data) > 10:
            try:
                # Use Isolation Forest for anomaly detection
                features = data[['trade_pnl']].fillna(0).values
                clf = IsolationForest(contamination=0.1, random_state=42)
                anomalies = clf.fit_predict(features)
                
                anomaly_indices = np.where(anomalies == -1)[0]
                for idx in anomaly_indices[:5]:  # Limit to 5 for display
                    results['volatility_skew_anomalies'].append({
                        'index': idx,
                        'pnl': data.iloc[idx].get('trade_pnl', 0),
                        'type': 'outlier'
                    })
            except Exception as e:
                print(f"Anomaly detection error: {e}")
                
        return results
        
    def calculate_metrics(self, trades: pd.DataFrame) -> Dict:
        if trades is None or len(trades) == 0:
            return self._default_metrics()
            
        metrics = {}
        
        # Ensure trade_pnl column exists
        if 'trade_pnl' in trades.columns:
            pnl = trades['trade_pnl'].fillna(0)
            
            # Basic metrics
            metrics['total_pnl'] = pnl.sum()
            metrics['win_rate'] = (pnl > 0).mean()
            metrics['avg_win'] = pnl[pnl > 0].mean() if len(pnl[pnl > 0]) > 0 else 0
            metrics['avg_loss'] = pnl[pnl < 0].mean() if len(pnl[pnl < 0]) > 0 else 0
            
            # Sharpe ratio
            if pnl.std() != 0:
                metrics['sharpe_ratio'] = (pnl.mean() / pnl.std()) * np.sqrt(252)
            else:
                metrics['sharpe_ratio'] = 0
                
            # Max drawdown
            cumsum = pnl.cumsum()
            running_max = cumsum.cummax()
            drawdown = (cumsum - running_max) / (running_max + 1)
            metrics['max_drawdown'] = drawdown.min()
            
            # CAGR (simplified)
            total_return = pnl.sum() / 100000  # Assume 100k starting capital
            years = len(pnl) / 252  # Assume 252 trading days
            if years > 0:
                metrics['cagr'] = (1 + total_return) ** (1 / years) - 1
            else:
                metrics['cagr'] = 0
                
        else:
            metrics = self._default_metrics()
            
        return metrics
        
    def _default_metrics(self) -> Dict:
        return {
            'total_pnl': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'cagr': 0
        }
