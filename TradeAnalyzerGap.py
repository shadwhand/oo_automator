"""
MEIC Meta Labeling Implementation for 0DTE Iron Condor Optimization
Author: Meta Labeling Framework
Version: 1.0.0
Description: Complete implementation for analyzing and optimizing Multi Entry Iron Condor 
             trades using meta labeling, ensemble ML models, and combinatorial purged CV
"""

# ============================================================================
# IMPORTS
# ============================================================================

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import joblib
import json
from typing import Dict, List, Tuple, Optional, Union

# Machine Learning
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score
from sklearn.model_selection import BaseCrossValidator
from sklearn.calibration import calibration_curve, CalibratedClassifierCV

# XGBoost
import xgboost as xgb

# Visualization
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt

# Utilities
from itertools import combinations
from scipy import stats

warnings.filterwarnings('ignore')

# ============================================================================
# DATA PROCESSING MODULE
# ============================================================================

class MEICDataProcessor:
    """Process MEIC 0DTE backtest data for meta labeling"""
    
    def __init__(self, trades_path: str = None, performance_path: str = None):
        self.trades_df = None
        self.performance_df = None
        self.processed_df = None
        self.trades_path = trades_path
        self.performance_path = performance_path
        
    def load_data(self, trades_path: str = None, performance_path: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load existing backtest data"""
        
        trades_path = trades_path or self.trades_path
        performance_path = performance_path or self.performance_path
        
        # Load trades data
        self.trades_df = pd.read_csv(trades_path)
        self.trades_df['Trade Date Time'] = pd.to_datetime(self.trades_df['Trade Date Time'])
        
        # Load performance summary if provided
        if performance_path:
            self.performance_df = pd.read_csv(performance_path)
        
        # Sort by trade datetime
        self.trades_df = self.trades_df.sort_values('Trade Date Time')
        
        print(f"Loaded {len(self.trades_df)} trades")
        print(f"Date range: {self.trades_df['Trade Date Time'].min()} to {self.trades_df['Trade Date Time'].max()}")
        
        return self.trades_df, self.performance_df
    
    def preprocess_trades(self) -> pd.DataFrame:
        """Preprocess trade data for ML"""
        df = self.trades_df.copy()
        
        # Extract time features
        df['hour'] = df['Trade Date Time'].dt.hour
        df['minute'] = df['Trade Date Time'].dt.minute
        df['day_of_week'] = df['Trade Date Time'].dt.dayofweek
        df['month'] = df['Trade Date Time'].dt.month
        df['day_of_month'] = df['Trade Date Time'].dt.day
        df['entry_time'] = df['hour'] + df['minute']/60
        
        # Calculate trade duration
        df['Date Closed'] = pd.to_datetime(df['Date Closed'])
        df['Time Closed'] = pd.to_datetime(df['Time Closed'], format='%H:%M:%S', errors='coerce').dt.time
        df['trade_duration'] = (df['Date Closed'] - df['Trade Date Time']).dt.total_seconds() / 3600
        
        # Normalize monetary values
        df['premium_normalized'] = df['Premium'] / df['Margin Req']
        df['pnl_pct'] = df['Trade P&L'] / df['Margin Req']
        df['capture_rate'] = np.where(df['Max Profit'] != 0, 
                                      df['Trade P&L'] / df['Max Profit'], 0)
        
        # Market regime indicators
        df['gap_zscore'] = (df['Gap'] - df['Gap'].rolling(20, min_periods=1).mean()) / df['Gap'].rolling(20, min_periods=1).std()
        df['movement_zscore'] = (df['Movement'] - df['Movement'].rolling(20, min_periods=1).mean()) / df['Movement'].rolling(20, min_periods=1).std()
        
        # Entry time encoding for the specific times provided
        entry_times_mapping = {
            9.92: '09:55', 10.03: '10:02', 11.97: '11:58', 12.12: '12:07',
            12.43: '12:26', 12.70: '12:42', 12.92: '12:55', 13.23: '13:14',
            14.45: '14:27', 14.63: '14:38', 15.33: '15:20'
        }
        
        # Map entry times to categories
        df['entry_time_category'] = pd.cut(df['entry_time'], 
                                          bins=[0] + list(entry_times_mapping.keys()) + [16],
                                          labels=range(len(entry_times_mapping)+1))
        
        # Exit reason encoding
        if 'Reason For Close' in df.columns:
            exit_reasons = pd.get_dummies(df['Reason For Close'], prefix='exit')
            df = pd.concat([df, exit_reasons], axis=1)
        
        # Handle missing values
        df = df.fillna(method='ffill').fillna(0)
        
        self.processed_df = df
        print(f"Preprocessed {len(df)} trades with {df.shape[1]} features")
        
        return df

# ============================================================================
# META LABELING MODULE
# ============================================================================

class MetaLabeling:
    """Implement meta labeling for MEIC trades"""
    
    def __init__(self, threshold_profit: float = 0.15, threshold_loss: float = -0.25):
        self.threshold_profit = threshold_profit
        self.threshold_loss = threshold_loss
        self.meta_labels = None
        
    def create_triple_barrier_labels(self, df: pd.DataFrame, volatility_window: int = 20) -> pd.DataFrame:
        """Create labels using triple barrier method adapted for iron condors"""
        
        df = df.copy()
        
        # Calculate dynamic thresholds based on volatility
        df['volatility'] = df['Movement'].rolling(volatility_window, min_periods=1).std()
        df['volatility'].fillna(df['volatility'].mean(), inplace=True)
        
        # Upper barrier (profit target) - dynamic based on volatility
        df['upper_barrier'] = self.threshold_profit * (1 + df['volatility']/100)
        
        # Lower barrier (stop loss) - asymmetric for iron condors
        df['lower_barrier'] = self.threshold_loss * (1 + df['volatility']/200)
        
        # Create meta labels
        conditions = [
            (df['pnl_pct'] >= df['upper_barrier']),  # Hit profit target
            (df['pnl_pct'] <= df['lower_barrier']),  # Hit stop loss
        ]
        choices = [1, -1]
        
        df['meta_label'] = np.select(conditions, choices, default=0)
        
        # Binary labels for classification
        df['trade_success'] = (df['pnl_pct'] > 0).astype(int)
        
        # Multi-class labels based on performance
        df['performance_class'] = pd.cut(df['pnl_pct'], 
                                        bins=[-np.inf, -0.25, 0, 0.15, np.inf],
                                        labels=['large_loss', 'small_loss', 'small_win', 'large_win'])
        
        # Additional label for time-based success (quick wins)
        df['quick_win'] = ((df['pnl_pct'] > 0.05) & (df['trade_duration'] < 2)).astype(int)
        
        self.meta_labels = df
        
        print(f"Meta labels created: {df['trade_success'].sum()} successful trades out of {len(df)}")
        print(f"Win rate: {df['trade_success'].mean():.2%}")
        
        return df
    
    def apply_cusum_filter(self, df: pd.DataFrame, threshold: float = 0.02) -> pd.DataFrame:
        """Apply CUSUM filter to detect significant events"""
        
        df = df.copy()
        df['returns'] = df['Trade P&L'].pct_change()
        
        # Calculate CUSUM
        cusum_pos = 0
        cusum_neg = 0
        events = []
        
        for i, ret in enumerate(df['returns'].fillna(0)):
            cusum_pos = max(0, cusum_pos + ret - threshold)
            cusum_neg = min(0, cusum_neg + ret + threshold)
            
            if cusum_pos > threshold or cusum_neg < -threshold:
                events.append(i)
                cusum_pos = 0
                cusum_neg = 0
        
        # Mark significant events
        df['is_event'] = False
        df.loc[events, 'is_event'] = True
        
        print(f"CUSUM filter identified {len(events)} significant events")
        
        return df

# ============================================================================
# FEATURE ENGINEERING MODULE
# ============================================================================

class IronCondorFeatures:
    """Feature engineering specific to iron condor strategies"""
    
    def __init__(self):
        self.features = None
        self.feature_names = None
        
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create comprehensive features for iron condor analysis"""
        
        # Initialize features dataframe
        features = pd.DataFrame(index=df.index)
        
        # Time-based features
        features['hour'] = df['hour']
        features['minute'] = df['minute'] 
        features['day_of_week'] = df['day_of_week']
        features['entry_time'] = df['entry_time']
        features['month'] = df['month'] if 'month' in df.columns else 1
        features['day_of_month'] = df['day_of_month'] if 'day_of_month' in df.columns else 1
        
        # Market condition features
        features['gap'] = df['Gap']
        features['movement'] = df['Movement']
        features['gap_zscore'] = df['gap_zscore'].fillna(0)
        features['movement_zscore'] = df['movement_zscore'].fillna(0)
        features['gap_abs'] = np.abs(df['Gap'])
        features['movement_abs'] = np.abs(df['Movement'])
        
        # Volatility features
        features['gap_volatility'] = df['Gap'].rolling(5, min_periods=1).std()
        features['movement_volatility'] = df['Movement'].rolling(5, min_periods=1).std()
        features['gap_volatility_20'] = df['Gap'].rolling(20, min_periods=1).std()
        features['movement_volatility_20'] = df['Movement'].rolling(20, min_periods=1).std()
        
        # Time decay features for 0DTE
        features['morning_trade'] = (df['hour'] < 12).astype(int)
        features['afternoon_trade'] = ((df['hour'] >= 12) & (df['hour'] < 15)).astype(int)
        features['last_hour_trade'] = (df['hour'] >= 15).astype(int)
        
        # Optimal time window indicators (10:15 AM - 12:00 PM from research)
        features['optimal_window'] = ((df['entry_time'] >= 10.25) & 
                                      (df['entry_time'] <= 12)).astype(int)
        
        # Market regime detection
        features['trending_market'] = (np.abs(features['movement']) > 
                                       features['movement'].rolling(20, min_periods=1).mean() + 
                                       features['movement'].rolling(20, min_periods=1).std()).astype(int)
        
        features['range_bound'] = (~features['trending_market'].astype(bool)).astype(int)
        
        # Risk metrics
        features['premium_to_margin'] = df['premium_normalized'] if 'premium_normalized' in df.columns else 0
        features['max_profit_ratio'] = df['Max Profit'] / df['Margin Req'] if 'Margin Req' in df.columns else 1
        features['max_loss_ratio'] = df['Max Loss'] / df['Margin Req'] if 'Margin Req' in df.columns else -1
        
        # Commission impact
        if 'Opening Commissions' in df.columns and 'Closing Commissions' in df.columns:
            features['commission_impact'] = (df['Opening Commissions'] + 
                                            df['Closing Commissions']) / (df['Premium'] + 1e-10)
        else:
            features['commission_impact'] = 0
        
        # Rolling statistics
        for window in [5, 10, 20]:
            features[f'gap_ma_{window}'] = df['Gap'].rolling(window, min_periods=1).mean()
            features[f'movement_ma_{window}'] = df['Movement'].rolling(window, min_periods=1).mean()
            
            if 'trade_success' in df.columns:
                features[f'win_rate_{window}'] = df['trade_success'].rolling(window, min_periods=1).mean()
        
        # Contrarian indicators (from research)
        features['gap_above_ma'] = (df['Gap'] > features['gap_ma_5']).astype(int)
        features['gap_below_ma'] = (df['Gap'] < features['gap_ma_5']).astype(int)
        features['contrarian_signal'] = ((df['Gap'] > 0.5) | (df['Gap'] < -0.5)).astype(int)
        
        # Theta decay acceleration (exponential after 3:30 PM)
        features['theta_acceleration'] = np.where(df['hour'] >= 15.5, 2.0,
                                                 np.where(df['hour'] >= 14, 1.5,
                                                        np.where(df['hour'] >= 12, 1.2, 1.0)))
        
        # Forward-fill any NaN values
        features = features.fillna(method='ffill').fillna(0)
        
        # Replace any infinite values
        features = features.replace([np.inf, -np.inf], 0)
        
        self.features = features
        self.feature_names = features.columns.tolist()
        
        print(f"Created {len(self.feature_names)} features")
        
        return features

# ============================================================================
# COMBINATORIAL PURGED CROSS-VALIDATION
# ============================================================================

class CombinatorialPurgedKFold(BaseCrossValidator):
    """CPCV for overlapping 0DTE trades"""
    
    def __init__(self, n_splits: int = 6, n_test_splits: int = 2, embargo_td: timedelta = None):
        self.n_splits = n_splits
        self.n_test_splits = n_test_splits
        self.embargo_td = embargo_td or timedelta(hours=1)
        
    def split(self, X, y=None, groups=None):
        """Generate CPCV splits with purging for 0DTE overlaps"""
        
        if groups is None:
            # Use index as groups if not provided
            if hasattr(X, 'index'):
                groups = pd.to_datetime(X.index).date
            else:
                groups = np.arange(len(X))
        
        # Get unique dates
        unique_dates = np.unique(groups)
        n_dates = len(unique_dates)
        
        # Split dates into groups
        group_size = n_dates // self.n_splits
        date_groups = []
        
        for i in range(self.n_splits):
            start_idx = i * group_size
            end_idx = (i + 1) * group_size if i < self.n_splits - 1 else n_dates
            date_groups.append(unique_dates[start_idx:end_idx])
        
        # Generate all combinations of test groups
        test_combinations = list(combinations(range(self.n_splits), self.n_test_splits))
        
        for test_groups in test_combinations:
            test_dates = []
            train_dates = []
            
            for i, dates in enumerate(date_groups):
                if i in test_groups:
                    test_dates.extend(dates)
                else:
                    train_dates.extend(dates)
            
            # Get indices
            train_idx = np.where(np.isin(groups, train_dates))[0]
            test_idx = np.where(np.isin(groups, test_dates))[0]
            
            # Apply embargo (remove train samples too close to test)
            if len(test_idx) > 0:
                train_idx = self._apply_embargo(train_idx, test_idx, groups)
            
            if len(train_idx) > 0 and len(test_idx) > 0:
                yield train_idx, test_idx
    
    def _apply_embargo(self, train_idx, test_idx, groups):
        """Remove training samples that overlap with test period"""
        # For 0DTE, remove same-day trades from training
        train_dates = groups[train_idx]
        test_dates = groups[test_idx]
        
        # Remove overlapping dates
        mask = ~np.isin(train_dates, test_dates)
        return train_idx[mask]
    
    def get_n_splits(self, X=None, y=None, groups=None):
        """Return number of splitting iterations"""
        from math import comb
        return comb(self.n_splits, self.n_test_splits)

# ============================================================================
# ENSEMBLE ML MODELS
# ============================================================================

class MEICEnsembleModels:
    """Train ensemble models for trade selection"""
    
    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.feature_importance = None
        self.calibrated_models = {}
        
    def train_models(self, X_train, y_train, X_val=None, y_val=None):
        """Train multiple models with different approaches"""
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        if X_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            eval_set = [(X_val_scaled, y_val)]
        else:
            eval_set = None
        
        print("Training XGBoost...")
        # XGBoost with specific parameters for financial data
        self.models['xgboost'] = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            gamma=0.1,  # Regularization
            reg_alpha=0.1,  # L1 regularization
            reg_lambda=1.0,  # L2 regularization
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        
        if eval_set:
            self.models['xgboost'].fit(X_train_scaled, y_train,
                                      eval_set=eval_set,
                                      early_stopping_rounds=10,
                                      verbose=False)
        else:
            self.models['xgboost'].fit(X_train_scaled, y_train, verbose=False)
        
        print("Training Random Forest...")
        # Random Forest
        self.models['random_forest'] = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1
        )
        self.models['random_forest'].fit(X_train_scaled, y_train)
        
        print("Training Logistic Regression...")
        # Logistic Regression with regularization
        self.models['logistic'] = LogisticRegression(
            penalty='l2',  # Using L2 instead of elasticnet for stability
            solver='liblinear',
            C=1.0,
            max_iter=1000,
            random_state=42
        )
        self.models['logistic'].fit(X_train_scaled, y_train)
        
        print("Creating ensemble model...")
        # Ensemble voting classifier
        self.models['ensemble'] = VotingClassifier(
            estimators=[
                ('xgb', self.models['xgboost']),
                ('rf', self.models['random_forest']),
                ('lr', self.models['logistic'])
            ],
            voting='soft',
            weights=[2, 1, 1]  # Weight XGBoost higher
        )
        self.models['ensemble'].fit(X_train_scaled, y_train)
        
        # Calibrate models for better probability estimates
        print("Calibrating models...")
        self._calibrate_models(X_train_scaled, y_train)
        
        # Calculate feature importance
        self._calculate_feature_importance(X_train)
        
        return self.models
    
    def _calibrate_models(self, X_train, y_train):
        """Calibrate model probabilities"""
        for name, model in self.models.items():
            if hasattr(model, 'predict_proba'):
                self.calibrated_models[name] = CalibratedClassifierCV(
                    model, method='isotonic', cv=3
                )
                self.calibrated_models[name].fit(X_train, y_train)
    
    def _calculate_feature_importance(self, X_train):
        """Calculate and store feature importance"""
        
        # Get feature names
        feature_names = X_train.columns if hasattr(X_train, 'columns') else [f'f{i}' for i in range(X_train.shape[1])]
        
        # XGBoost importance
        xgb_importance = self.models['xgboost'].feature_importances_
        
        # Random Forest importance
        rf_importance = self.models['random_forest'].feature_importances_
        
        # Average importance
        avg_importance = (xgb_importance + rf_importance) / 2
        
        self.feature_importance = pd.DataFrame({
            'feature': feature_names,
            'xgboost': xgb_importance,
            'random_forest': rf_importance,
            'average': avg_importance
        }).sort_values('average', ascending=False)
        
        return self.feature_importance
    
    def predict_with_confidence(self, X):
        """Make predictions with confidence scores"""
        
        X_scaled = self.scaler.transform(X)
        predictions = {}
        
        for name, model in self.calibrated_models.items():
            if hasattr(model, 'predict_proba'):
                predictions[name] = model.predict_proba(X_scaled)[:, 1]
            else:
                predictions[name] = model.predict(X_scaled)
        
        # Calculate average confidence
        predictions_df = pd.DataFrame(predictions)
        predictions_df['average_confidence'] = predictions_df.mean(axis=1)
        predictions_df['std_confidence'] = predictions_df.std(axis=1)
        predictions_df['prediction'] = (predictions_df['average_confidence'] >= 0.5).astype(int)
        
        return predictions_df

# ============================================================================
# PERFORMANCE ANALYSIS MODULE
# ============================================================================

class PerformanceTrendAnalyzer:
    """Analyze performance trends over time"""
    
    def __init__(self):
        self.weekly_trends = None
        self.monthly_trends = None
        self.daily_trends = None
        
    def analyze_trends(self, df):
        """Calculate weekly and monthly performance metrics"""
        
        df = df.copy()
        
        # Add time grouping columns
        df['week'] = df['Trade Date Time'].dt.isocalendar().week
        df['year_week'] = df['Trade Date Time'].dt.strftime('%Y-%W')
        df['month'] = df['Trade Date Time'].dt.to_period('M')
        df['date'] = df['Trade Date Time'].dt.date
        
        # Weekly analysis
        self.weekly_trends = df.groupby('year_week').agg({
            'Trade P&L': ['sum', 'mean', 'std', 'count'],
            'trade_success': 'mean',
            'capture_rate': 'mean',
            'trade_duration': 'mean',
            'Gap': 'mean',
            'Movement': 'mean'
        }).round(4)
        
        # Monthly analysis
        self.monthly_trends = df.groupby('month').agg({
            'Trade P&L': ['sum', 'mean', 'std', 'count'],
            'trade_success': 'mean',
            'capture_rate': 'mean',
            'Margin Req': 'sum',
            'Gap': ['mean', 'std'],
            'Movement': ['mean', 'std']
        }).round(4)
        
        # Daily analysis
        self.daily_trends = df.groupby('date').agg({
            'Trade P&L': ['sum', 'count'],
            'trade_success': 'mean',
            'Gap': 'mean',
            'Movement': 'mean'
        }).round(4)
        
        # Calculate rolling metrics
        df = df.sort_values('Trade Date Time')
        df['rolling_win_rate_7d'] = df.set_index('Trade Date Time')['trade_success'].rolling('7D').mean()
        df['rolling_pnl_30d'] = df.set_index('Trade Date Time')['Trade P&L'].rolling('30D').sum()
        
        # Identify regime changes
        df['volatility_regime'] = pd.qcut(df['Movement'].rolling(20, min_periods=1).std(), 
                                         q=3, labels=['low', 'medium', 'high'], duplicates='drop')
        
        return self.weekly_trends, self.monthly_trends, df

# ============================================================================
# VISUALIZATION MODULE
# ============================================================================

class MEICVisualizer:
    """Create visualizations for MEIC analysis"""
    
    def __init__(self):
        self.figures = {}
        
    def create_entry_time_heatmap(self, df):
        """Create heatmap of performance by entry time"""
        
        # Prepare data - aggregate by hour and day of week
        entry_performance = df.groupby(['hour', 'day_of_week']).agg({
            'pnl_pct': 'mean',
            'trade_success': 'mean',
            'capture_rate': 'mean'
        }).round(3)
        
        # Reshape for heatmap
        heatmap_data = entry_performance['pnl_pct'].unstack(fill_value=0)
        
        # Create plotly heatmap
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data.values * 100,  # Convert to percentage
            x=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][:heatmap_data.shape[1]],
            y=[f'{h:02d}:00' for h in heatmap_data.index],
            colorscale='RdBu',
            zmid=0,
            text=[[f'{val:.1f}%' for val in row] for row in heatmap_data.values * 100],
            texttemplate='%{text}',
            textfont={"size": 10},
            hovertemplate='Hour: %{y}<br>Day: %{x}<br>Avg P&L: %{z:.2f}%<extra></extra>',
            colorbar=dict(title="Avg P&L %")
        ))
        
        fig.update_layout(
            title='Average P&L by Entry Time and Day of Week',
            xaxis_title='Day of Week',
            yaxis_title='Hour of Day',
            height=600,
            width=800
        )
        
        self.figures['entry_heatmap'] = fig
        return fig
    
    def plot_feature_importance(self, feature_importance_df):
        """Plot feature importance from models"""
        
        if feature_importance_df is None or len(feature_importance_df) == 0:
            print("No feature importance data available")
            return None
        
        top_features = feature_importance_df.head(15)
        
        fig = go.Figure()
        
        # Add bars for each model
        fig.add_trace(go.Bar(
            x=top_features['xgboost'],
            y=top_features['feature'],
            orientation='h',
            name='XGBoost',
            marker_color='lightblue'
        ))
        
        fig.add_trace(go.Bar(
            x=top_features['random_forest'],
            y=top_features['feature'],
            orientation='h',
            name='Random Forest',
            marker_color='lightgreen'
        ))
        
        fig.update_layout(
            title='Top 15 Most Important Features',
            xaxis_title='Importance Score',
            yaxis_title='Feature',
            barmode='group',
            height=500,
            width=900,
            yaxis={'categoryorder': 'total ascending'}
        )
        
        self.figures['feature_importance'] = fig
        return fig
    
    def plot_calibration_curve(self, y_true, y_pred_proba, n_bins=10):
        """Create calibration plot for model confidence"""
        
        fraction_of_positives, mean_predicted_value = calibration_curve(
            y_true, y_pred_proba, n_bins=n_bins
        )
        
        fig = go.Figure()
        
        # Perfect calibration line
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1],
            mode='lines',
            name='Perfect Calibration',
            line=dict(dash='dash', color='gray')
        ))
        
        # Actual calibration
        fig.add_trace(go.Scatter(
            x=mean_predicted_value,
            y=fraction_of_positives,
            mode='lines+markers',
            name='Model Calibration',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title='Model Calibration Plot',
            xaxis_title='Mean Predicted Probability',
            yaxis_title='Fraction of Positives',
            height=400,
            width=600,
            showlegend=True,
            xaxis=dict(range=[0, 1]),
            yaxis=dict(range=[0, 1])
        )
        
        self.figures['calibration'] = fig
        return fig
    
    def plot_performance_trends(self, weekly_trends, monthly_trends):
        """Plot weekly and monthly performance trends"""
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Weekly P&L', 'Weekly Win Rate',
                          'Monthly P&L', 'Monthly Capture Rate'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Weekly P&L
        if weekly_trends is not None and len(weekly_trends) > 0:
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(weekly_trends))),
                    y=weekly_trends[('Trade P&L', 'sum')].values,
                    mode='lines+markers',
                    name='Weekly P&L',
                    line=dict(color='blue', width=2),
                    marker=dict(size=6)
                ),
                row=1, col=1
            )
            
            # Weekly Win Rate
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(weekly_trends))),
                    y=weekly_trends[('trade_success', 'mean')].values * 100,
                    mode='lines+markers',
                    name='Win Rate %',
                    line=dict(color='green', width=2),
                    marker=dict(size=6)
                ),
                row=1, col=2
            )
        
        # Monthly P&L
        if monthly_trends is not None and len(monthly_trends) > 0:
            monthly_pnl = monthly_trends[('Trade P&L', 'sum')].values
            fig.add_trace(
                go.Bar(
                    x=list(range(len(monthly_trends))),
                    y=monthly_pnl,
                    name='Monthly P&L',
                    marker_color=['green' if x > 0 else 'red' for x in monthly_pnl]
                ),
                row=2, col=1
            )
            
            # Monthly Capture Rate
            fig.add_trace(
                go.Scatter(
                    x=list(range(len(monthly_trends))),
                    y=monthly_trends[('capture_rate', 'mean')].values * 100,
                    mode='lines+markers',
                    name='Capture Rate %',
                    line=dict(color='orange', width=2),
                    marker=dict(size=6)
                ),
                row=2, col=2
            )
        
        fig.update_layout(height=800, width=1200, showlegend=False)
        fig.update_xaxes(title_text="Week Index", row=1, col=1)
        fig.update_xaxes(title_text="Week Index", row=1, col=2)
        fig.update_xaxes(title_text="Month Index", row=2, col=1)
        fig.update_xaxes(title_text="Month Index", row=2, col=2)
        
        fig.update_yaxes(title_text="P&L ($)", row=1, col=1)
        fig.update_yaxes(title_text="Win Rate (%)", row=1, col=2)
        fig.update_yaxes(title_text="P&L ($)", row=2, col=1)
        fig.update_yaxes(title_text="Capture Rate (%)", row=2, col=2)
        
        self.figures['trends'] = fig
        return fig
    
    def plot_cumulative_performance(self, df):
        """Plot cumulative P&L over time"""
        
        df_sorted = df.sort_values('Trade Date Time').copy()
        df_sorted['cumulative_pnl'] = df_sorted['Trade P&L'].cumsum()
        df_sorted['trade_number'] = range(1, len(df_sorted) + 1)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_sorted['trade_number'],
            y=df_sorted['cumulative_pnl'],
            mode='lines',
            name='Cumulative P&L',
            line=dict(color='blue', width=2)
        ))
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        fig.update_layout(
            title='Cumulative P&L Over Time',
            xaxis_title='Trade Number',
            yaxis_title='Cumulative P&L ($)',
            height=400,
            width=900
        )
        
        self.figures['cumulative_pnl'] = fig
        return fig

# ============================================================================
# SIGNAL GENERATION MODULE
# ============================================================================

class RealTimeSignalGenerator:
    """Generate real-time entry suggestions"""
    
    def __init__(self, model, scaler, feature_engineer):
        self.model = model
        self.scaler = scaler
        self.feature_engineer = feature_engineer
        self.confidence_threshold = 0.6
        self.movement_threshold = 0.5
        
    def generate_signal(self, current_market_data):
        """Generate entry signal based on current conditions"""
        
        # Extract current features
        features = {
            'hour': datetime.now().hour,
            'minute': datetime.now().minute,
            'day_of_week': datetime.now().weekday(),
            'entry_time': datetime.now().hour + datetime.now().minute/60,
            'gap': current_market_data.get('gap', 0),
            'movement': current_market_data.get('movement', 0),
            'gap_zscore': self._calculate_zscore(current_market_data.get('gap', 0), 'gap'),
            'movement_zscore': self._calculate_zscore(current_market_data.get('movement', 0), 'movement')
        }
        
        # Add derived features
        features['optimal_window'] = int(10.25 <= features['entry_time'] <= 12)
        features['morning_trade'] = int(features['hour'] < 12)
        features['trending_market'] = int(abs(features['movement']) > self.movement_threshold)
        
        # Create full feature vector matching training features
        X = pd.DataFrame([features])
        
        # Add missing features with default values
        for feat in self.feature_engineer.feature_names:
            if feat not in X.columns:
                X[feat] = 0
        
        # Reorder columns to match training
        X = X[self.feature_engineer.feature_names]
        
        # Get prediction with confidence
        X_scaled = self.scaler.transform(X)
        
        if hasattr(self.model, 'predict_proba'):
            confidence = self.model.predict_proba(X_scaled)[0, 1]
            prediction = int(confidence >= self.confidence_threshold)
        else:
            prediction = self.model.predict(X_scaled)[0]
            confidence = 1.0 if prediction == 1 else 0.0
        
        # Generate recommendation
        signal = {
            'timestamp': datetime.now(),
            'recommendation': 'ENTER' if prediction == 1 else 'SKIP',
            'confidence': confidence,
            'market_conditions': {
                'gap': current_market_data.get('gap', 0),
                'movement': current_market_data.get('movement', 0),
                'optimal_time_window': features['optimal_window']
            },
            'reasons': self._generate_reasoning(features, confidence)
        }
        
        return signal
    
    def _calculate_zscore(self, value, metric_type):
        """Calculate z-score for current value"""
        # In production, these would be calculated from recent historical data
        # Using placeholder values for now
        if metric_type == 'gap':
            return (value - 0) / 1  # Placeholder
        else:
            return (value - 0) / 1  # Placeholder
    
    def _generate_reasoning(self, features, confidence):
        """Generate human-readable reasoning for signal"""
        
        reasons = []
        
        if features['optimal_window']:
            reasons.append("Within optimal entry window (10:15 AM - 12:00 PM)")
        
        if abs(features.get('gap_zscore', 0)) > 1.5:
            reasons.append(f"Significant gap detected (z-score: {features.get('gap_zscore', 0):.2f})")
        
        if features['trending_market']:
            reasons.append("Market showing trending behavior")
        else:
            reasons.append("Market in range-bound conditions (favorable for IC)")
        
        if confidence > 0.7:
            reasons.append(f"High model confidence ({confidence:.1%})")
        elif confidence < 0.4:
            reasons.append(f"Low model confidence ({confidence:.1%})")
        
        return reasons

# ============================================================================
# THRESHOLD OPTIMIZATION MODULE
# ============================================================================

class ThresholdOptimizer:
    """Optimize confidence thresholds for trade filtering"""
    
    def __init__(self):
        self.optimal_threshold = None
        self.threshold_metrics = None
        
    def optimize_threshold(self, y_true, y_pred_proba, returns):
        """Find optimal confidence threshold"""
        
        thresholds = np.linspace(0.3, 0.9, 50)
        results = []
        
        for threshold in thresholds:
            predictions = (y_pred_proba >= threshold).astype(int)
            
            # Filter returns by predictions
            filtered_returns = returns[predictions == 1]
            
            if len(filtered_returns) == 0:
                continue
            
            # Calculate metrics
            metrics = {
                'threshold': threshold,
                'num_trades': len(filtered_returns),
                'total_return': filtered_returns.sum(),
                'avg_return': filtered_returns.mean(),
                'win_rate': (filtered_returns > 0).mean(),
                'sharpe_ratio': filtered_returns.mean() / filtered_returns.std() 
                                if filtered_returns.std() > 0 else 0,
                'max_drawdown': self._calculate_max_drawdown(filtered_returns.values)
            }
            
            results.append(metrics)
        
        self.threshold_metrics = pd.DataFrame(results)
        
        if len(self.threshold_metrics) > 0:
            # Find optimal based on Sharpe ratio
            optimal_idx = self.threshold_metrics['sharpe_ratio'].idxmax()
            self.optimal_threshold = self.threshold_metrics.loc[optimal_idx, 'threshold']
        else:
            self.optimal_threshold = 0.5
        
        return self.optimal_threshold, self.threshold_metrics
    
    def _calculate_max_drawdown(self, returns):
        """Calculate maximum drawdown"""
        if len(returns) == 0:
            return 0
            
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

# ============================================================================
# MARKET REGIME ANALYSIS MODULE
# ============================================================================

class MarketRegimeAnalyzer:
    """Analyze performance under different market conditions"""
    
    def __init__(self):
        self.regime_performance = None
        
    def analyze_regimes(self, df):
        """Analyze which entry times perform best in different regimes"""
        
        df = df.copy()
        
        # Define market regimes based on movement volatility
        df['volatility_regime'] = pd.qcut(df['Movement'].rolling(20, min_periods=1).std(), 
                                         q=3, labels=['low_vol', 'med_vol', 'high_vol'], 
                                         duplicates='drop')
        
        # Define trend regime
        df['trend_regime'] = pd.cut(df['Movement'], 
                                   bins=[-np.inf, -0.5, 0.5, np.inf],
                                   labels=['down_trend', 'range_bound', 'up_trend'])
        
        # Analyze performance by regime and entry time
        regime_analysis = df.groupby(['volatility_regime', 'trend_regime', 'hour']).agg({
            'pnl_pct': ['mean', 'std', 'count'],
            'trade_success': 'mean',
            'capture_rate': 'mean',
            'trade_duration': 'mean'
        }).round(3)
        
        # Find best entry times for each regime
        best_times = {}
        
        for vol_regime in ['low_vol', 'med_vol', 'high_vol']:
            for trend_regime in ['down_trend', 'range_bound', 'up_trend']:
                mask = (df['volatility_regime'] == vol_regime) & \
                       (df['trend_regime'] == trend_regime)
                
                if mask.sum() > 10:  # Require minimum sample size
                    hour_performance = df[mask].groupby('hour')['pnl_pct'].agg(['mean', 'count'])
                    
                    # Only consider hours with enough samples
                    valid_hours = hour_performance[hour_performance['count'] >= 3]
                    
                    if len(valid_hours) > 0:
                        best_hour = valid_hours['mean'].idxmax()
                        avg_return = valid_hours['mean'].max()
                        
                        best_times[f'{vol_regime}_{trend_regime}'] = {
                            'best_hour': best_hour,
                            'avg_return': avg_return,
                            'sample_size': mask.sum()
                        }
        
        self.regime_performance = pd.DataFrame(best_times).T if best_times else pd.DataFrame()
        
        return regime_analysis, self.regime_performance

# ============================================================================
# MAIN PIPELINE
# ============================================================================

class MEICMetaLabelingPipeline:
    """Main pipeline for MEIC meta labeling analysis"""
    
    def __init__(self, trades_path: str, performance_path: str = None):
        self.trades_path = trades_path
        self.performance_path = performance_path
        self.processor = MEICDataProcessor(trades_path, performance_path)
        self.meta_labeler = MetaLabeling()
        self.feature_engineer = IronCondorFeatures()
        self.models = MEICEnsembleModels()
        self.visualizer = MEICVisualizer()
        self.trend_analyzer = PerformanceTrendAnalyzer()
        self.regime_analyzer = MarketRegimeAnalyzer()
        
        self.labeled_df = None
        self.features = None
        self.results = []
        
    def run_full_analysis(self):
        """Execute complete meta labeling analysis"""
        
        print("\n" + "="*60)
        print("MEIC META LABELING ANALYSIS")
        print("="*60)
        
        # 1. Load and preprocess data
        print("\n[1/10] Loading data...")
        trades, performance = self.processor.load_data()
        processed_df = self.processor.preprocess_trades()
        
        # 2. Create meta labels
        print("\n[2/10] Creating meta labels...")
        labeled_df = self.meta_labeler.create_triple_barrier_labels(processed_df)
        labeled_df = self.meta_labeler.apply_cusum_filter(labeled_df)
        
        # 3. Feature engineering
        print("\n[3/10] Engineering features...")
        features = self.feature_engineer.create_features(labeled_df)
        
        # Store for later use
        self.labeled_df = labeled_df
        self.features = features
        
        # 4. Prepare train/test split with CPCV
        print("\n[4/10] Preparing combinatorial purged cross-validation...")
        X = features
        y = labeled_df['trade_success']
        
        # Add date groups for CPCV
        groups = labeled_df['Trade Date Time'].dt.date
        
        cv = CombinatorialPurgedKFold(n_splits=6, n_test_splits=2)
        
        # 5. Train models with cross-validation
        print("\n[5/10] Training ensemble models with cross-validation...")
        print("-" * 40)
        
        fold_predictions = []
        fold_indices = []
        
        for fold_num, (train_idx, test_idx) in enumerate(cv.split(X, y, groups)):
            print(f"Training fold {fold_num + 1}...")
            
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            # Skip if not enough samples
            if len(X_train) < 50 or len(X_test) < 10:
                continue
            
            # Train models
            self.models.train_models(X_train, y_train, X_test, y_test)
            
            # Get predictions
            predictions = self.models.predict_with_confidence(X_test)
            
            # Store predictions and indices for later analysis
            fold_predictions.append(predictions)
            fold_indices.append(test_idx)
            
            # Calculate metrics
            try:
                auc_score = roc_auc_score(y_test, predictions['average_confidence'])
            except:
                auc_score = 0.5
            
            accuracy = (predictions['prediction'] == y_test).mean()
            
            fold_results = {
                'fold': fold_num + 1,
                'train_size': len(train_idx),
                'test_size': len(test_idx),
                'auc': auc_score,
                'accuracy': accuracy,
                'win_rate': y_test.mean()
            }
            
            self.results.append(fold_results)
            
            print(f"  AUC: {auc_score:.3f} | Accuracy: {accuracy:.3f} | Test Size: {len(test_idx)}")
        
        # 6. Train final model on all data
        print("\n[6/10] Training final model on complete dataset...")
        self.models.train_models(X, y)
        
        # 7. Analyze trends
        print("\n[7/10] Analyzing performance trends...")
        weekly, monthly, trend_df = self.trend_analyzer.analyze_trends(labeled_df)
        
        # 8. Market regime analysis
        print("\n[8/10] Analyzing market regimes...")
        regime_analysis, best_regimes = self.regime_analyzer.analyze_regimes(labeled_df)
        
        # 9. Create visualizations
        print("\n[9/10] Creating visualizations...")
        self.visualizer.create_entry_time_heatmap(labeled_df)
        self.visualizer.plot_feature_importance(self.models.feature_importance)
        self.visualizer.plot_performance_trends(weekly, monthly)
        self.visualizer.plot_cumulative_performance(labeled_df)
        
        # Get final predictions for calibration plot
        final_predictions = self.models.predict_with_confidence(X)
        self.visualizer.plot_calibration_curve(y, final_predictions['average_confidence'])
        
        # 10. Optimize thresholds
        print("\n[10/10] Optimizing confidence thresholds...")
        optimizer = ThresholdOptimizer()
        optimal_threshold, threshold_metrics = optimizer.optimize_threshold(
            y, final_predictions['average_confidence'], labeled_df['pnl_pct']
        )
        
        # Generate summary report
        summary = self._generate_summary(labeled_df, best_regimes, optimal_threshold)
        
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        
        return summary, labeled_df, self.models, self.visualizer.figures
    
    def _generate_summary(self, labeled_df, best_regimes, optimal_threshold):
        """Generate comprehensive summary of results"""
        
        summary = {
            'data_summary': {
                'total_trades': len(labeled_df),
                'date_range': f"{labeled_df['Trade Date Time'].min().date()} to {labeled_df['Trade Date Time'].max().date()}",
                'unique_days': labeled_df['Trade Date Time'].dt.date.nunique()
            },
            'performance_metrics': {
                'overall_win_rate': f"{labeled_df['trade_success'].mean():.2%}",
                'avg_pnl_pct': f"{labeled_df['pnl_pct'].mean():.2%}",
                'total_pnl': f"${labeled_df['Trade P&L'].sum():,.2f}",
                'sharpe_ratio': labeled_df['pnl_pct'].mean() / labeled_df['pnl_pct'].std() if labeled_df['pnl_pct'].std() > 0 else 0
            },
            'model_performance': {
                'cv_auc': np.mean([r['auc'] for r in self.results]) if self.results else 0,
                'cv_accuracy': np.mean([r['accuracy'] for r in self.results]) if self.results else 0,
                'optimal_threshold': optimal_threshold
            },
            'best_entry_times': best_regimes.to_dict() if len(best_regimes) > 0 else {},
            'top_features': self.models.feature_importance.head(10)['feature'].tolist() if self.models.feature_importance is not None else []
        }
        
        return summary
    
    def get_entry_suggestions(self, current_market_data):
        """Get real-time entry suggestions"""
        
        if self.models is None or self.feature_engineer is None:
            print("Models not trained. Run analysis first.")
            return None
        
        generator = RealTimeSignalGenerator(
            self.models.models['ensemble'],
            self.models.scaler,
            self.feature_engineer
        )
        
        return generator.generate_signal(current_market_data)
    
    def save_results(self, output_dir: str = "./meic_output"):
        """Save all results to files"""
        
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # Save processed data
        if self.labeled_df is not None:
            self.labeled_df.to_csv(f"{output_dir}/processed_trades.csv", index=False)
        
        # Save feature importance
        if self.models.feature_importance is not None:
            self.models.feature_importance.to_csv(f"{output_dir}/feature_importance.csv", index=False)
        
        # Save models
        joblib.dump(self.models, f"{output_dir}/trained_models.pkl")
        
        # Save visualizations
        for name, fig in self.visualizer.figures.items():
            fig.write_html(f"{output_dir}/{name}.html")
        
        print(f"\nResults saved to {output_dir}/")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    
    print("\nMEIC Meta Labeling Framework v1.0.0")
    print("="*60)
    
    # Get file paths from user
    trades_path = input("Enter path to trades CSV file: ").strip()
    performance_path = input("Enter path to performance CSV file (optional, press Enter to skip): ").strip()
    
    if not performance_path:
        performance_path = None
    
    # Initialize pipeline
    pipeline = MEICMetaLabelingPipeline(
        trades_path=trades_path,
        performance_path=performance_path
    )
    
    # Run analysis
    try:
        summary, data, models, figures = pipeline.run_full_analysis()
        
        # Display summary
        print("\n" + "="*60)
        print("ANALYSIS SUMMARY")
        print("="*60)
        
        print("\nData Summary:")
        for key, value in summary['data_summary'].items():
            print(f"  {key}: {value}")
        
        print("\nPerformance Metrics:")
        for key, value in summary['performance_metrics'].items():
            print(f"  {key}: {value}")
        
        print("\nModel Performance:")
        for key, value in summary['model_performance'].items():
            if isinstance(value, float):
                print(f"  {key}: {value:.3f}")
            else:
                print(f"  {key}: {value}")
        
        if summary['top_features']:
            print(f"\nTop 5 Features:")
            for i, feature in enumerate(summary['top_features'][:5], 1):
                print(f"  {i}. {feature}")
        
        # Save results
        save_choice = input("\nSave results to files? (y/n): ").strip().lower()
        if save_choice == 'y':
            output_dir = input("Enter output directory (default: ./meic_output): ").strip()
            if not output_dir:
                output_dir = "./meic_output"
            pipeline.save_results(output_dir)
        
        # Test real-time signal generation
        test_signal = input("\nTest real-time signal generation? (y/n): ").strip().lower()
        if test_signal == 'y':
            print("\nEnter current market conditions:")
            gap = float(input("  Gap (%): "))
            movement = float(input("  Movement (%): "))
            
            signal = pipeline.get_entry_suggestions({
                'gap': gap,
                'movement': movement
            })
            
            print("\n" + "="*40)
            print("SIGNAL RECOMMENDATION")
            print("="*40)
            print(f"Recommendation: {signal['recommendation']}")
            print(f"Confidence: {signal['confidence']:.1%}")
            print(f"Reasoning:")
            for reason in signal['reasons']:
                print(f"  • {reason}")
        
        print("\n✅ Analysis complete!")
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
