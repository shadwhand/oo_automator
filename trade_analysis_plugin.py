"""
Trade Analysis Plugin for OptionOmega Automation
Enhances backtest results with detailed trade metrics and statistics
Updated with corrected Kelly criterion and trade stability metrics
"""

import csv
import statistics
from datetime import datetime
from typing import List, Dict, Any
import os


def enhance_results_with_trade_metrics(config: Dict, backtest_results: List[Dict], trade_logs: List[Dict]) -> str:
    """
    Enhance backtest results with specified trade metrics
    
    Args:
        config: Configuration dictionary with test run manager
        backtest_results: List of backtest result dictionaries
        trade_logs: List of all trade log entries
        
    Returns:
        str: Path to the enhanced CSV file
    """
    try:
        # Group trades by parameter value
        trades_by_parameter = {}
        for trade in trade_logs:
            param_value = str(trade.get('backtest_parameter_value', ''))
            if param_value not in trades_by_parameter:
                trades_by_parameter[param_value] = []
            trades_by_parameter[param_value].append(trade)
        
        # Enhance each backtest result with trade metrics
        enhanced_results = []
        for result in backtest_results:
            param_value = str(result.get('parameter_value', ''))
            trades = trades_by_parameter.get(param_value, [])
            
            # Calculate trade metrics
            metrics = calculate_trade_metrics(trades)
            
            # Add CAGR to MDD ratio from backtest results
            cagr = result.get('cagr', 0)
            max_dd = abs(result.get('maxDrawdown', 0))
            if max_dd != 0:
                metrics['cagr_to_mdd'] = cagr / max_dd
            else:
                metrics['cagr_to_mdd'] = 0
            
            # Combine backtest results with trade metrics
            enhanced_result = {**result, **metrics}
            enhanced_results.append(enhanced_result)
        
        # Export enhanced results to CSV
        return export_enhanced_csv(config, enhanced_results)
        
    except Exception as e:
        print(f"Error enhancing results with trade metrics: {e}")
        return None


def kelly_fraction(trades, contracts_key="num_contracts", pnl_key="trade_pnl", 
                   risk_key="max_loss", frac=0.25):
    """
    Kelly criterion on normalized outcomes.
    
    Priority:
      1) If max_loss exists and is non-zero: use pnl / max_loss (capital-at-risk normalization)
      2) Else: use pnl per contract (size-neutral fallback)
    
    Args:
        trades: List of trade dictionaries
        contracts_key: Key for number of contracts
        pnl_key: Key for P/L value
        risk_key: Key for max loss (capital at risk)
        frac: Fractional Kelly multiplier (default 0.25 for quarter-Kelly)
    
    Returns:
        float: Kelly fraction (0 to 1, already multiplied by frac)
    """
    norm = []
    
    for t in trades:
        pnl = float(t.get(pnl_key, 0) or 0)
        
        # Prefer risk-based normalization (pnl / max_loss)
        rk = t.get(risk_key)
        if rk and abs(float(rk)) > 0.001:
            r = pnl / abs(float(rk))
        else:
            # Fallback: per-contract normalization
            n = float(t.get(contracts_key, 0) or 0)
            if n <= 0:
                continue
            r = pnl / n
        
        norm.append(r)
    
    wins = [x for x in norm if x > 0]
    losses = [abs(x) for x in norm if x < 0]
    
    if not wins or not losses or len(norm) < 2:
        return 0.0
    
    p = len(wins) / len(norm)
    b = (sum(wins)/len(wins)) / (sum(losses)/len(losses))
    k = max(0.0, (p * b - (1 - p)) / b) if b > 0 else 0.0
    
    return k * frac


def trade_stability_ratio(trades, pnl_key="trade_pnl", contracts_key="num_contracts"):
    """
    Per-trade return stability (NOT time-series Sharpe ratio).
    Measures consistency of per-contract returns.
    
    This is a cross-sectional measure of trade outcome consistency,
    not a time-series risk-adjusted return measure.
    
    Args:
        trades: List of trade dictionaries
        pnl_key: Key for P/L value
        contracts_key: Key for number of contracts
    
    Returns:
        float: Trade stability ratio (mean / std of per-contract returns)
    """
    rets = []
    
    for t in trades:
        n = float(t.get(contracts_key, 0) or 0)
        if n > 0:
            rets.append(float(t.get(pnl_key, 0) or 0) / n)
    
    if len(rets) < 2:
        return 0.0
    
    mu = sum(rets) / len(rets)
    sd = statistics.stdev(rets)
    
    return (mu / sd) if sd > 0 else 0.0


def calculate_trade_metrics(trades: List[Dict]) -> Dict:
    """
    Calculate specific trade metrics requested by user
    
    Args:
        trades: List of trade dictionaries for a specific parameter value
        
    Returns:
        Dict: Dictionary of calculated metrics
    """
    metrics = {
        # Core counting metrics
        'total_trades': len(trades),
        # Additional metrics to be calculated
        'avg_profit_factor': 0.0,
        'expected_value': 0.0,
        'expectancy': 0.0,
        'cagr_to_mdd': 0.0,
        'loser_ratio': 0.0,
        'recovery_ratio': 0.0,
        'sharpe_ratio': 0.0,
        'sortino_ratio': 0.0,
        'kelly_criterion': 0.0,
        'calmar_ratio': 0.0,
        'trade_stability': 0.0,
    }
    
    if not trades:
        return metrics
    
    # Lists for calculations
    pnl_values = []
    winning_pnl = []
    losing_pnl = []
    winning_trades = 0
    losing_trades = 0
    
    for trade in trades:
        pnl = float(trade.get('trade_pnl', 0) or 0)
        pnl_values.append(pnl)
        
        # Categorize trades
        if pnl > 0:
            winning_trades += 1
            winning_pnl.append(pnl)
        elif pnl < 0:
            losing_trades += 1
            losing_pnl.append(pnl)
    
    # Calculate basic statistics
    total_trades = len(trades)
    win_rate = (winning_trades / total_trades) if total_trades > 0 else 0
    
    # Average win and loss
    avg_win = sum(winning_pnl) / len(winning_pnl) if winning_pnl else 0
    avg_loss = sum(losing_pnl) / len(losing_pnl) if losing_pnl else 0
    
    # Loser Ratio (percentage of losing trades)
    metrics['loser_ratio'] = (losing_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Average Profit Factor (average of individual profit factors)
    if losing_pnl:
        total_wins = sum(winning_pnl) if winning_pnl else 0
        total_losses = abs(sum(losing_pnl))
        if total_losses > 0:
            metrics['avg_profit_factor'] = total_wins / total_losses
    
    # Expected Value (same as expectancy - average expected return per trade)
    # Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss)
    if total_trades > 0:
        loss_rate = losing_trades / total_trades
        metrics['expectancy'] = (win_rate * avg_win) - (loss_rate * abs(avg_loss))
        metrics['expected_value'] = metrics['expectancy']  # Same calculation
    
    # CAGR to MDD ratio (will be calculated from backtest results, placeholder here)
    metrics['cagr_to_mdd'] = 0.0  # This will be overridden in enhance_results_with_trade_metrics
    
    # Recovery Ratio (net profit / max drawdown)
    # Calculate max drawdown from P&L series
    if pnl_values:
        cumulative_pnl = []
        running_total = 0
        for pnl in pnl_values:
            running_total += pnl
            cumulative_pnl.append(running_total)
        
        # Find maximum drawdown
        peak = cumulative_pnl[0]
        max_dd = 0
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
        
        # Recovery Ratio
        if max_dd > 0:
            net_profit = sum(pnl_values)
            metrics['recovery_ratio'] = net_profit / max_dd
        
        # Calmar Ratio (using trade-based calculation)
        if max_dd > 0 and len(trades) > 0:
            # Estimate annualized return from trades
            total_days = len(trades)  # Rough estimate
            annual_factor = 252 / max(total_days, 1)
            annualized_return = sum(pnl_values) * annual_factor
            metrics['calmar_ratio'] = annualized_return / max_dd
    
    # Risk-adjusted metrics
    if len(pnl_values) > 2:
        # Sharpe Ratio (simplified - assuming risk-free rate = 0)
        try:
            pnl_std = statistics.stdev(pnl_values)
            if pnl_std > 0:
                avg_pnl = sum(pnl_values) / len(pnl_values)
                metrics['sharpe_ratio'] = (avg_pnl / pnl_std) * (252 ** 0.5)  # Annualized
        except:
            pass
        
        # Sortino Ratio (downside deviation)
        try:
            downside_returns = [pnl for pnl in pnl_values if pnl < 0]
            if len(downside_returns) > 1:
                downside_std = statistics.stdev(downside_returns)
                if downside_std > 0:
                    avg_pnl = sum(pnl_values) / len(pnl_values)
                    metrics['sortino_ratio'] = (avg_pnl / downside_std) * (252 ** 0.5)
        except:
            pass
    
    # Kelly Criterion (normalized)
    metrics['kelly_criterion'] = kelly_fraction(trades) * 100  # As percentage
    
    # Trade Stability Ratio
    metrics['trade_stability'] = trade_stability_ratio(trades)
    
    # Round all metrics to reasonable precision
    for key, value in metrics.items():
        if isinstance(value, float):
            if 'ratio' in key or 'factor' in key or 'kelly' in key:
                metrics[key] = round(value, 4)
            elif 'percentage' in key or 'rate' in key:
                metrics[key] = round(value, 2)
            else:
                metrics[key] = round(value, 2)
    
    return metrics


def export_enhanced_csv(config: Dict, enhanced_results: List[Dict]) -> str:
    """
    Export enhanced results to CSV with specified metrics only
    
    Args:
        config: Configuration dictionary
        enhanced_results: List of enhanced result dictionaries
        
    Returns:
        str: Path to the exported CSV file
    """
    try:
        # Use test run manager for organized file location
        test_run_manager = config.get('test_run_manager')
        parameter_type = config.get('parameter_type', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create filename
        filename = f'enhanced_results_{parameter_type}_{timestamp}.csv'
        
        # Get full file path
        if test_run_manager:
            filepath = test_run_manager.get_results_file(filename)
        else:
            filepath = filename
        
        # Sort results by parameter value
        sorted_results = sorted(enhanced_results, key=lambda x: str(x.get('parameter_value', '')))
        
        # Define column order - ONLY the requested metrics
        columns = [
            'parameter_type', 
            'parameter_value',
            # Primary metrics (bolded in request)
            'cagr',
            'maxDrawdown',
            'winPercentage',
            'captureRate', 
            'mar',
            'avg_profit_factor',
            'expected_value',
            'expectancy',
            'cagr_to_mdd',
            'loser_ratio',
            'recovery_ratio',
            # Secondary metrics
            'sharpe_ratio',
            'sortino_ratio',
            'kelly_criterion',
            'calmar_ratio',
            'trade_stability',
            # Metadata
            'total_trades',
            'timestamp'
        ]
        
        # Write CSV
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            
            # Write header with more readable names
            header_mapping = {
                'parameter_type': 'Parameter Type',
                'parameter_value': 'Parameter Value',
                # Primary metrics (bold in request)
                'cagr': 'CAGR',
                'maxDrawdown': 'Max Drawdown',
                'winPercentage': 'Win Percentage',
                'captureRate': 'Capture Rate',
                'mar': 'MAR',
                'avg_profit_factor': 'Avg Profit Factor',
                'expected_value': 'Expected Value',
                'expectancy': 'Expectancy',
                'cagr_to_mdd': 'CAGR to MDD',
                'loser_ratio': 'Loser Ratio %',
                'recovery_ratio': 'Recovery Ratio',
                # Secondary metrics
                'sharpe_ratio': 'Sharpe',
                'sortino_ratio': 'Sortino', 
                'kelly_criterion': 'Kelly %',
                'calmar_ratio': 'CalMAR',
                'trade_stability': 'Trade Stability',
                # Metadata
                'total_trades': 'Total Trades',
                'timestamp': 'Timestamp'
            }
            
            writer.writerow({col: header_mapping.get(col, col) for col in columns})
            
            # Write data rows
            for row in sorted_results:
                # Format numeric values
                formatted_row = {}
                for col in columns:
                    value = row.get(col, '')
                    if col in ['cagr', 'maxDrawdown', 'winPercentage', 'captureRate', 'mar', 'cagr_to_mdd']:
                        # Format original metrics with 6 decimal places
                        if isinstance(value, (int, float)):
                            formatted_row[col] = f"{value:.6f}"
                        else:
                            formatted_row[col] = value
                    elif col in ['sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'recovery_ratio', 'avg_profit_factor', 'trade_stability']:
                        # Format ratios with 4 decimal places
                        if isinstance(value, (int, float)):
                            formatted_row[col] = f"{value:.4f}"
                        else:
                            formatted_row[col] = value
                    elif col in ['kelly_criterion', 'loser_ratio']:
                        # Format percentages with 2 decimal places
                        if isinstance(value, (int, float)):
                            formatted_row[col] = f"{value:.2f}"
                        else:
                            formatted_row[col] = value
                    elif col in ['expectancy', 'expected_value']:
                        # Format dollar values with 2 decimal places
                        if isinstance(value, (int, float)):
                            formatted_row[col] = f"{value:.2f}"
                        else:
                            formatted_row[col] = value
                    else:
                        formatted_row[col] = value
                
                writer.writerow(formatted_row)
        
        print(f"Enhanced results exported to: {filepath}")
        print(f"  - Contains {len(sorted_results)} parameter tests")
        print(f"  - Includes {len(columns) - 3} metrics (corrected Kelly & trade stability)")
        
        return filepath
        
    except Exception as e:
        print(f"Error exporting enhanced CSV: {e}")
        import traceback
        print(traceback.format_exc())
        return None


def generate_performance_summary(enhanced_results: List[Dict]) -> Dict:
    """
    Generate a performance summary across all parameter values
    
    Args:
        enhanced_results: List of enhanced result dictionaries
        
    Returns:
        Dict: Summary statistics
    """
    if not enhanced_results:
        return {}
    
    summary = {
        'best_cagr_params': None,
        'best_mar_params': None,
        'best_win_rate_params': None,
        'best_profit_factor_params': None,
        'best_sharpe_params': None,
        'most_trades_params': None,
        'least_drawdown_params': None
    }
    
    # Find best performing parameter values
    best_cagr = max(enhanced_results, key=lambda x: x.get('cagr', 0))
    best_mar = max(enhanced_results, key=lambda x: x.get('mar', 0))
    best_win_rate = max(enhanced_results, key=lambda x: x.get('winPercentage', 0))
    best_profit_factor = max(enhanced_results, key=lambda x: x.get('avg_profit_factor', 0))
    best_sharpe = max(enhanced_results, key=lambda x: x.get('sharpe_ratio', 0))
    most_trades = max(enhanced_results, key=lambda x: x.get('total_trades', 0))
    least_drawdown = min(enhanced_results, key=lambda x: abs(x.get('maxDrawdown', 0)))
    
    summary['best_cagr_params'] = {
        'value': best_cagr.get('parameter_value'),
        'cagr': best_cagr.get('cagr'),
        'mar': best_cagr.get('mar')
    }
    
    summary['best_mar_params'] = {
        'value': best_mar.get('parameter_value'),
        'mar': best_mar.get('mar'),
        'cagr': best_mar.get('cagr')
    }
    
    summary['best_win_rate_params'] = {
        'value': best_win_rate.get('parameter_value'),
        'win_rate': best_win_rate.get('winPercentage'),
        'total_trades': best_win_rate.get('total_trades')
    }
    
    summary['best_profit_factor_params'] = {
        'value': best_profit_factor.get('parameter_value'),
        'profit_factor': best_profit_factor.get('avg_profit_factor'),
        'win_rate': best_profit_factor.get('winPercentage')
    }
    
    summary['best_sharpe_params'] = {
        'value': best_sharpe.get('parameter_value'),
        'sharpe_ratio': best_sharpe.get('sharpe_ratio'),
        'sortino_ratio': best_sharpe.get('sortino_ratio')
    }
    
    summary['most_trades_params'] = {
        'value': most_trades.get('parameter_value'),
        'total_trades': most_trades.get('total_trades'),
        'win_rate': most_trades.get('winPercentage')
    }
    
    summary['least_drawdown_params'] = {
        'value': least_drawdown.get('parameter_value'),
        'max_drawdown': least_drawdown.get('maxDrawdown'),
        'cagr': least_drawdown.get('cagr')
    }
    
    # Calculate overall statistics
    cagr_values = [r.get('cagr', 0) for r in enhanced_results]
    mar_values = [r.get('mar', 0) for r in enhanced_results]
    win_rates = [r.get('winPercentage', 0) for r in enhanced_results if r.get('winPercentage', 0) > 0]
    
    summary['overall_stats'] = {
        'avg_cagr': sum(cagr_values) / len(cagr_values) if cagr_values else 0,
        'avg_mar': sum(mar_values) / len(mar_values) if mar_values else 0,
        'avg_win_rate': sum(win_rates) / len(win_rates) if win_rates else 0,
        'total_parameters_tested': len(enhanced_results)
    }
    
    return summary


def print_performance_summary(enhanced_results: List[Dict]):
    """
    Print a formatted performance summary to console
    
    Args:
        enhanced_results: List of enhanced result dictionaries
    """
    summary = generate_performance_summary(enhanced_results)
    
    if not summary:
        return
    
    print("\n" + "="*80)
    print("PERFORMANCE OPTIMIZATION SUMMARY")
    print("="*80)
    
    if summary.get('best_cagr_params'):
        data = summary['best_cagr_params']
        print(f"\n📈 Best CAGR: {data['value']}")
        print(f"   CAGR: {data['cagr']:.4f}, MAR: {data['mar']:.2f}")
    
    if summary.get('best_mar_params'):
        data = summary['best_mar_params']
        print(f"\n⚖️  Best Risk-Adjusted (MAR): {data['value']}")
        print(f"   MAR: {data['mar']:.2f}, CAGR: {data['cagr']:.4f}")
    
    if summary.get('best_win_rate_params'):
        data = summary['best_win_rate_params']
        print(f"\n🎯 Best Win Rate: {data['value']}")
        print(f"   Win Rate: {data['win_rate']:.1f}%, Trades: {data['total_trades']}")
    
    if summary.get('best_profit_factor_params'):
        data = summary['best_profit_factor_params']
        print(f"\n💰 Best Profit Factor: {data['value']}")
        print(f"   Profit Factor: {data['profit_factor']:.2f}, Win Rate: {data['win_rate']:.1f}%")
    
    if summary.get('best_sharpe_params'):
        data = summary['best_sharpe_params']
        print(f"\n📊 Best Sharpe Ratio: {data['value']}")
        print(f"   Sharpe: {data['sharpe_ratio']:.2f}, Sortino: {data['sortino_ratio']:.2f}")
    
    if summary.get('least_drawdown_params'):
        data = summary['least_drawdown_params']
        print(f"\n🛡️  Lowest Drawdown: {data['value']}")
        print(f"   Max DD: {data['max_drawdown']:.4f}, CAGR: {data['cagr']:.4f}")
    
    if summary.get('overall_stats'):
        stats = summary['overall_stats']
        print(f"\n📈 Overall Statistics:")
        print(f"   Parameters Tested: {stats['total_parameters_tested']}")
        print(f"   Average CAGR: {stats['avg_cagr']:.4f}")
        print(f"   Average MAR: {stats['avg_mar']:.2f}")
        print(f"   Average Win Rate: {stats['avg_win_rate']:.1f}%")
    
    print("\n" + "="*80)
