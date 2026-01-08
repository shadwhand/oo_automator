"""HTML page routes."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import select

from ...db.connection import get_engine, get_session
from ...db.models import Test, Run
from ...db.queries import get_recent_tests
from ...parameters import list_parameters
from ...config import get_config
from ..templates_config import get_templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page showing recent tests and runs."""
    templates = get_templates()
    engine = get_engine()
    session = get_session(engine)

    try:
        tests = get_recent_tests(session, limit=10)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"tests": tests}
        )
    finally:
        session.close()


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: int):
    """Run detail page."""
    templates = get_templates()
    return templates.TemplateResponse(
        request,
        "run.html",
        {"run_id": run_id}
    )


@router.get("/new-run", response_class=HTMLResponse)
async def new_run(request: Request, url: str = None, test_id: int = None):
    """New run form page."""
    templates = get_templates()
    config = get_config()
    parameters = list_parameters()

    # Default values
    prefill = {
        "url": url or "",
        "name": "",
        "mode": "sweep",
        "browsers": 2,
        "headless": False,
        "selected_params": [],
        "param_values": {},
    }

    # If test_id provided, get test info and last run config
    if test_id or url:
        engine = get_engine()
        session = get_session(engine)
        try:
            # Find test by ID or URL
            if test_id:
                test_stmt = select(Test).where(Test.id == test_id)
            else:
                test_stmt = select(Test).where(Test.url == url)
            test = session.exec(test_stmt).first()

            if test:
                prefill["url"] = test.url
                prefill["name"] = test.name or ""

                # Get last run config for this test
                run_stmt = select(Run).where(Run.test_id == test.id).order_by(Run.created_at.desc()).limit(1)
                last_run = session.exec(run_stmt).first()

                if last_run and last_run.config:
                    run_config = last_run.config
                    prefill["mode"] = run_config.get("mode", "sweep")
                    prefill["browsers"] = run_config.get("browsers", 2)
                    prefill["headless"] = run_config.get("headless", False)

                    # Extract parameter values from last run
                    if prefill["mode"] == "sweep":
                        param_name = run_config.get("parameter")
                        param_config = run_config.get("param_config", {})
                        if param_name and param_config:
                            prefill["selected_params"] = [param_name]
                            prefill["param_values"][param_name] = param_config
                    else:
                        # Grid mode
                        params = run_config.get("parameters", {})
                        prefill["selected_params"] = list(params.keys())
                        # Convert values list back to start/end/step
                        for param_name, values in params.items():
                            if values and len(values) >= 2:
                                prefill["param_values"][param_name] = {
                                    "start": values[0] if isinstance(values[0], (int, float)) else values[0],
                                    "end": values[-1] if isinstance(values[-1], (int, float)) else values[-1],
                                    "step": values[1] - values[0] if len(values) > 1 and isinstance(values[0], (int, float)) else 1,
                                }
        finally:
            session.close()

    return templates.TemplateResponse(
        request,
        "new_run.html",
        {
            "parameters": parameters,
            "config_email": config.email,
            "config_password": config.password,
            "prefill": prefill,
        }
    )


@router.get("/runs/{run_id}/results", response_class=HTMLResponse)
async def run_results_page(request: Request, run_id: int):
    """Results analysis page with heatmap table."""
    templates = get_templates()
    engine = get_engine()
    session = get_session(engine)

    try:
        from ...db.models import Task, Result

        # Get run info
        run_stmt = select(Run).where(Run.id == run_id)
        run = session.exec(run_stmt).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Get test info
        test_stmt = select(Test).where(Test.id == run.test_id)
        test = session.exec(test_stmt).first()

        # Get all results for this run with task info
        results_stmt = (
            select(Result, Task)
            .join(Task, Result.task_id == Task.id)
            .where(Task.run_id == run_id)
            .order_by(Task.id)
        )
        results_data = list(session.exec(results_stmt).all())

        # Build results list with computed metrics
        results = []
        for result, task in results_data:
            # Get parameter info
            param_values = task.parameter_values or {}
            param_name = list(param_values.keys())[0] if param_values else "unknown"
            param_value = param_values.get(param_name, "")

            # Compute derived metrics
            cagr = result.cagr or 0
            max_dd = abs(result.max_drawdown or 0)
            win_pct = (result.win_percentage or 0) / 100
            capture_rate = (result.capture_rate or 0) / 100
            avg_winner = result.avg_winner or 0
            avg_loser = abs(result.avg_loser or 1)
            total_trades = result.total_trades or result.winners or 0
            winners = result.winners or 0

            # MAR ratio (CAGR / Max Drawdown)
            mar = cagr / max_dd if max_dd > 0 else 0

            # Profit factor (avg_winner * win_rate) / (avg_loser * loss_rate)
            loss_pct = 1 - win_pct
            profit_factor = (avg_winner * win_pct) / (avg_loser * loss_pct) if loss_pct > 0 and avg_loser > 0 else 0

            # Expected value per trade
            expected_value = (avg_winner * win_pct) - (avg_loser * loss_pct)

            # CAGR to MDD ratio
            cagr_to_mdd = cagr / max_dd if max_dd > 0 else 0

            # Loser ratio (avg_loser / avg_winner)
            loser_ratio = avg_loser / avg_winner if avg_winner > 0 else 0

            # Recovery ratio (simplified)
            recovery_ratio = avg_winner / max_dd if max_dd > 0 else 0

            results.append({
                "task_id": task.id,
                "param_name": param_name,
                "param_value": param_value,
                "pl": result.pl or 0,
                "cagr": cagr,
                "max_drawdown": result.max_drawdown or 0,
                "win_percentage": result.win_percentage or 0,
                "capture_rate": result.capture_rate or 0,
                "mar": mar,
                "profit_factor": profit_factor,
                "expected_value": expected_value,
                "cagr_to_mdd": cagr_to_mdd,
                "loser_ratio": loser_ratio,
                "recovery_ratio": recovery_ratio,
                "total_trades": total_trades,
                "winners": winners,
                "avg_winner": avg_winner,
                "avg_loser": result.avg_loser or 0,
                "created_at": result.created_at,
            })

        return templates.TemplateResponse(
            request,
            "results_analysis.html",
            {"run": run, "test": test, "results": results}
        )
    finally:
        session.close()


@router.get("/runs/{run_id}/advanced", response_class=HTMLResponse)
async def run_advanced_metrics(request: Request, run_id: int):
    """Advanced metrics page with Sharpe, Sortino, Kelly, CalMAR."""
    templates = get_templates()
    engine = get_engine()
    session = get_session(engine)

    try:
        from ...db.models import Task, Result
        import math

        # Get run info
        run_stmt = select(Run).where(Run.id == run_id)
        run = session.exec(run_stmt).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Get test info
        test_stmt = select(Test).where(Test.id == run.test_id)
        test = session.exec(test_stmt).first()

        # Get all results for this run with task info
        results_stmt = (
            select(Result, Task)
            .join(Task, Result.task_id == Task.id)
            .where(Task.run_id == run_id)
            .order_by(Task.id)
        )
        results_data = list(session.exec(results_stmt).all())

        # Build results list with advanced metrics
        results = []
        risk_free_rate = 0.02  # Assume 2% risk-free rate

        for result, task in results_data:
            # Get parameter info
            param_values = task.parameter_values or {}
            param_name = list(param_values.keys())[0] if param_values else "unknown"
            param_value = param_values.get(param_name, "")

            # Basic metrics
            cagr = (result.cagr or 0) / 100  # Convert to decimal
            max_dd = abs(result.max_drawdown or 0) / 100  # Convert to decimal
            win_pct = (result.win_percentage or 0) / 100
            capture_rate = (result.capture_rate or 0) / 100
            avg_winner = result.avg_winner or 0
            avg_loser = abs(result.avg_loser or 1)
            total_trades = result.total_trades or result.winners or 0

            # MAR ratio
            mar = cagr / max_dd if max_dd > 0 else 0

            # Profit factor
            loss_pct = 1 - win_pct
            profit_factor = (avg_winner * win_pct) / (avg_loser * loss_pct) if loss_pct > 0 and avg_loser > 0 else 0

            # Expected value per trade
            expected_value = (avg_winner * win_pct) - (avg_loser * loss_pct)

            # Expectancy (same as expected value)
            expectancy = expected_value

            # CAGR to MDD
            cagr_to_mdd = cagr / max_dd if max_dd > 0 else 0

            # Loser ratio % (loss rate as percentage)
            loser_ratio_pct = loss_pct * 100

            # Recovery ratio
            recovery_ratio = avg_winner / (max_dd * 10000) if max_dd > 0 else 0  # Scaled

            # Sharpe Ratio approximation
            # Using max_dd as proxy for volatility (rough approximation)
            volatility = max_dd * 2 if max_dd > 0 else 0.1  # Estimate annualized vol
            sharpe = (cagr - risk_free_rate) / volatility if volatility > 0 else 0

            # Sortino Ratio approximation
            # Downside deviation is typically lower than total volatility
            downside_vol = max_dd * 1.5 if max_dd > 0 else 0.1
            sortino = (cagr - risk_free_rate) / downside_vol if downside_vol > 0 else 0

            # Kelly Criterion %
            # Kelly = W - [(1-W) / R] where W = win rate, R = win/loss ratio
            win_loss_ratio = avg_winner / avg_loser if avg_loser > 0 else 1
            kelly = (win_pct - ((1 - win_pct) / win_loss_ratio)) * 100 if win_loss_ratio > 0 else 0

            # CalMAR (typically 3-year CAGR / Max DD, we use CAGR)
            calmar = cagr / max_dd if max_dd > 0 else 0

            results.append({
                "task_id": task.id,
                "param_name": param_name,
                "param_value": param_value,
                "cagr": cagr * 100,  # Back to percentage for display
                "max_drawdown": result.max_drawdown or 0,
                "win_percentage": result.win_percentage or 0,
                "capture_rate": result.capture_rate or 0,
                "mar": mar,
                "profit_factor": profit_factor,
                "expected_value": expected_value,
                "expectancy": expectancy,
                "cagr_to_mdd": cagr_to_mdd,
                "loser_ratio_pct": loser_ratio_pct,
                "recovery_ratio": recovery_ratio,
                "sharpe": sharpe,
                "sortino": sortino,
                "kelly": kelly,
                "calmar": calmar,
                "created_at": result.created_at,
            })

        return templates.TemplateResponse(
            request,
            "advanced_metrics.html",
            {"run": run, "test": test, "results": results}
        )
    finally:
        session.close()


@router.get("/tests/{test_id}", response_class=HTMLResponse)
async def test_detail(request: Request, test_id: int):
    """Test detail page showing all runs for a test."""
    templates = get_templates()
    engine = get_engine()
    session = get_session(engine)

    try:
        # Get test info
        statement = select(Test).where(Test.id == test_id)
        test = session.exec(statement).first()
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        # Get all runs for this test
        runs_statement = select(Run).where(Run.test_id == test_id).order_by(Run.created_at.desc())
        runs = list(session.exec(runs_statement).all())

        return templates.TemplateResponse(
            request,
            "test.html",
            {"test": test, "runs": runs}
        )
    finally:
        session.close()
