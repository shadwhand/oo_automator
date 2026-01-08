"""REST API endpoints with htmx partial support."""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from sqlmodel import select

from ...db.connection import get_engine, get_session, init_db
from ...db.models import Run, Task, Result, Test
from ...db.queries import get_or_create_test, create_run, create_tasks_for_run, increment_test_run_count
from ...core.run_manager import generate_combinations
from ...core.executor import start_run_execution, stop_run_execution, pause_run_execution, get_executor
from ...analysis.recommendations import generate_recommendations
from ..templates_config import get_templates
from .websocket import notify_run_update

router = APIRouter()


class NewRunRequest(BaseModel):
    """Request body for creating a new run."""
    url: str
    name: Optional[str] = None
    mode: str = "sweep"
    email: str
    password: str
    browsers: int = 2
    headless: bool = False
    parameters: dict  # e.g. {"delta": {"start": 5, "end": 25, "step": 5}}


def wants_html(request: Request) -> bool:
    """Check if client wants HTML response (htmx request)."""
    accept = request.headers.get("Accept", "")
    return "text/html" in accept


@router.get("/runs")
async def list_runs(request: Request, limit: int = 10, status: Optional[str] = None):
    """List recent runs."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Run).order_by(Run.created_at.desc())
        if status:
            statement = statement.where(Run.status == status)
        statement = statement.limit(limit)
        runs = list(session.exec(statement).all())

        # Check if client wants HTML (htmx request)
        if wants_html(request):
            templates = get_templates()
            return HTMLResponse(
                templates.get_template("partials/runs_list.html").render(runs=runs)
            )

        return {"runs": [run.model_dump() for run in runs]}
    finally:
        session.close()


@router.post("/runs")
async def create_new_run(data: NewRunRequest, background_tasks: BackgroundTasks):
    """Create a new run with tasks and start execution."""
    init_db()
    engine = get_engine()
    session = get_session(engine)

    try:
        # Create or get test
        test = get_or_create_test(session, data.url, data.name)

        def generate_param_values(param_name: str, param_config: dict) -> list:
            """Generate values for a parameter, handling special cases."""
            start = param_config["start"]
            end = param_config["end"]
            step = param_config["step"]

            if param_name == "entry_time":
                # Convert military time (HHMM) to HH:MM format
                # e.g., 930 → "09:30", 1500 → "15:00"
                values = []
                # Convert start/end from HHMM to minutes
                start_hour, start_min = start // 100, start % 100
                end_hour, end_min = end // 100, end % 100
                current_minutes = start_hour * 60 + start_min
                end_minutes = end_hour * 60 + end_min

                while current_minutes <= end_minutes:
                    hour = current_minutes // 60
                    minute = current_minutes % 60
                    values.append(f"{hour:02d}:{minute:02d}")
                    current_minutes += step
                return values
            else:
                # Standard numeric range
                return list(range(start, end + (1 if step > 0 else -1), step))

        # Build run config based on mode
        if data.mode == "sweep":
            # For sweep, use the first parameter
            param_name = list(data.parameters.keys())[0]
            param_config = data.parameters[param_name]

            # Generate values
            values = generate_param_values(param_name, param_config)

            run_config = {
                "mode": "sweep",
                "parameter": param_name,
                "values": values,
                "param_config": param_config,
                "browsers": data.browsers,
                "headless": data.headless,
            }
        else:
            # Grid mode - all parameters
            parameters = {}
            for param_name, param_config in data.parameters.items():
                values = generate_param_values(param_name, param_config)
                parameters[param_name] = values

            run_config = {
                "mode": "grid",
                "parameters": parameters,
                "browsers": data.browsers,
                "headless": data.headless,
            }

        # Create run in database
        run = create_run(session, test.id, data.mode, run_config)

        # Update test run count and last_run_at
        increment_test_run_count(session, test.id)

        # Generate task combinations
        combinations = generate_combinations(run_config)

        # Create tasks
        create_tasks_for_run(session, run.id, combinations)

        # Store IDs and config for response (before session closes)
        run_id = run.id
        test_id = test.id
        total_tasks = len(combinations)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

    # Start execution in background
    async def run_executor():
        print(f"[Executor] Starting run {run_id}...")
        try:
            await start_run_execution(
                run_id=run_id,
                email=data.email,
                password=data.password,
                num_browsers=data.browsers,
                headless=data.headless,
                update_callback=notify_run_update,
            )
            print(f"[Executor] Run {run_id} completed")
        except Exception as e:
            import traceback
            print(f"[Executor] Run {run_id} execution failed: {e}")
            traceback.print_exc()

    background_tasks.add_task(run_executor)

    return {
        "run_id": run_id,
        "test_id": test_id,
        "total_tasks": total_tasks,
        "status": "starting",
        "message": f"Run #{run_id} created with {total_tasks} tasks - execution starting"
    }


@router.get("/runs/{run_id}")
async def get_run(request: Request, run_id: int):
    """Get run details."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Run).where(Run.id == run_id)
        run = session.exec(statement).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Check if client wants HTML (htmx request)
        if wants_html(request):
            # Calculate progress
            task_statement = select(Task).where(Task.run_id == run_id)
            tasks = list(session.exec(task_statement).all())
            total_tasks = len(tasks)
            completed_tasks = len([t for t in tasks if t.status == "completed"])
            percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

            progress = {
                "total": total_tasks,
                "completed": completed_tasks,
                "percentage": percentage
            }

            templates = get_templates()
            return HTMLResponse(
                templates.get_template("partials/run_details.html").render(
                    run=run,
                    progress=progress
                )
            )

        return run.model_dump()
    finally:
        session.close()


@router.get("/runs/{run_id}/tasks")
async def get_run_tasks(request: Request, run_id: int):
    """Get tasks for a run."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Task).where(Task.run_id == run_id).order_by(Task.id)
        tasks = list(session.exec(statement).all())

        # Check if client wants HTML (htmx request)
        if wants_html(request):
            templates = get_templates()
            return HTMLResponse(
                templates.get_template("partials/tasks_table.html").render(tasks=tasks)
            )

        return {"tasks": [task.model_dump() for task in tasks]}
    finally:
        session.close()


@router.get("/runs/{run_id}/results")
async def get_run_results(request: Request, run_id: int):
    """Get results for a run."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = (
            select(Result)
            .join(Task)
            .where(Task.run_id == run_id)
            .order_by(Result.task_id)
        )
        results = list(session.exec(statement).all())

        # Check if client wants HTML (htmx request)
        if wants_html(request):
            templates = get_templates()
            return HTMLResponse(
                templates.get_template("partials/results_table.html").render(results=results)
            )

        return {"results": [result.model_dump() for result in results]}
    finally:
        session.close()


@router.get("/runs/{run_id}/recommendations")
async def get_run_recommendations(run_id: int, goal: str = "balanced"):
    """Get recommendations for a run based on backtesting results.

    Args:
        run_id: The run ID to get recommendations for.
        goal: Optimization goal - 'balanced', 'maximize_returns', or 'protect_capital'.

    Returns:
        Recommendations dict with top_pick, alternatives, avoid, and goal.
    """
    engine = get_engine()
    session = get_session(engine)

    try:
        # Check if run exists
        statement = select(Run).where(Run.id == run_id)
        run = session.exec(statement).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Get all results for this run joined with tasks
        statement = (
            select(Result, Task)
            .join(Task)
            .where(Task.run_id == run_id)
            .order_by(Result.task_id)
        )
        rows = list(session.exec(statement).all())

        # Build results list with calculated metrics
        results = []
        for result, task in rows:
            # Convert CAGR and max_drawdown from percentage to decimal
            cagr_decimal = (result.cagr or 0) / 100
            max_dd_decimal = (result.max_drawdown or 0) / 100

            # Calculate Sharpe ratio: (cagr - risk_free_rate) / volatility_proxy
            # Using max_dd / 2 as volatility proxy
            if max_dd_decimal > 0:
                sharpe = (cagr_decimal - 0.05) / (max_dd_decimal / 2)
            else:
                sharpe = 0

            # Calculate Kelly criterion
            # kelly = (win_pct - ((1 - win_pct) / win_loss_ratio)) * 100
            win_pct = (result.win_percentage or 0) / 100
            avg_winner = result.avg_winner or 0
            avg_loser = abs(result.avg_loser or 1)  # Ensure positive denominator
            win_loss_ratio = avg_winner / avg_loser if avg_loser != 0 else 0

            if win_loss_ratio > 0:
                kelly = (win_pct - ((1 - win_pct) / win_loss_ratio)) * 100
            else:
                kelly = 0

            # Extract parameter info from task
            param_values = task.parameter_values or {}
            param_name = list(param_values.keys())[0] if param_values else None
            param_value = param_values.get(param_name) if param_name else None

            results.append({
                "task_id": task.id,
                "param_name": param_name,
                "param_value": param_value,
                "cagr": result.cagr or 0,
                "max_drawdown": result.max_drawdown or 0,
                "win_percentage": result.win_percentage or 0,
                "sharpe": sharpe,
                "kelly": kelly,
                "avg_winner": result.avg_winner or 0,
                "avg_loser": result.avg_loser or 0,
                "capture_rate": result.capture_rate or 0,
            })

        # Generate recommendations
        recommendations = generate_recommendations(results, goal)

        return recommendations
    finally:
        session.close()


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: int):
    """Stop a running execution."""
    executor = get_executor(run_id)
    if not executor:
        # Check if run exists
        engine = get_engine()
        session = get_session(engine)
        try:
            statement = select(Run).where(Run.id == run_id)
            run = session.exec(statement).first()
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            if run.status != "running":
                raise HTTPException(status_code=400, detail=f"Run is not running (status: {run.status})")
            # Run exists but executor not active - might have already stopped
            return {"status": "stopped", "message": "Run was not actively executing"}
        finally:
            session.close()

    # Stop the executor
    stop_run_execution(run_id)

    # Update run status
    engine = get_engine()
    session = get_session(engine)
    try:
        from ...db.queries import update_run_status
        update_run_status(session, run_id, "stopped")
    finally:
        session.close()

    return {"status": "stopped", "message": f"Run #{run_id} stopped"}


@router.post("/runs/{run_id}/rerun")
async def rerun(run_id: int, background_tasks: BackgroundTasks):
    """Create a new run with the same configuration - refreshes all data (bypasses cache)."""
    import os
    engine = get_engine()
    session = get_session(engine)

    try:
        # Get the original run
        statement = select(Run).where(Run.id == run_id)
        original_run = session.exec(statement).first()
        if not original_run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Get credentials
        email = os.environ.get("OO_EMAIL")
        password = os.environ.get("OO_PASSWORD")
        if not email or not password:
            raise HTTPException(status_code=500, detail="Missing credentials")

        num_browsers = int(os.environ.get("OO_MAX_BROWSERS", "2"))
        headless = os.environ.get("OO_HEADLESS", "false").lower() == "true"

        # Create new config with skip_cache flag to force fresh data
        new_config = {**original_run.config, "skip_cache": True}

        # Create new run with updated config
        new_run = create_run(session, original_run.test_id, original_run.mode, new_config)

        # Update test run count
        increment_test_run_count(session, original_run.test_id)

        # Generate task combinations from config
        combinations = generate_combinations(original_run.config)

        # Create tasks
        create_tasks_for_run(session, new_run.id, combinations)

        new_run_id = new_run.id
        test_id = original_run.test_id
        total_tasks = len(combinations)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

    # Start execution in background
    import traceback

    async def run_executor():
        try:
            await start_run_execution(
                new_run_id,
                email,
                password,
                num_browsers=num_browsers,
                headless=headless,
                update_callback=notify_run_update,
            )
        except Exception as e:
            print(f"Execution error for run {new_run_id}: {e}")
            traceback.print_exc()

    background_tasks.add_task(run_executor)

    return {
        "run_id": new_run_id,
        "original_run_id": run_id,
        "test_id": test_id,
        "total_tasks": total_tasks,
        "status": "starting",
        "message": f"Rerun started as Run #{new_run_id} with {total_tasks} tasks"
    }


@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: int):
    """Pause a running execution."""
    executor = get_executor(run_id)
    if not executor:
        engine = get_engine()
        session = get_session(engine)
        try:
            statement = select(Run).where(Run.id == run_id)
            run = session.exec(statement).first()
            if not run:
                raise HTTPException(status_code=404, detail="Run not found")
            if run.status != "running":
                raise HTTPException(status_code=400, detail=f"Run is not running (status: {run.status})")
            return {"status": "error", "message": "Run was not actively executing"}
        finally:
            session.close()

    # Pause the executor
    pause_run_execution(run_id)

    # Update run status
    engine = get_engine()
    session = get_session(engine)
    try:
        from ...db.queries import update_run_status
        update_run_status(session, run_id, "paused")
    finally:
        session.close()

    return {"status": "paused", "message": f"Run #{run_id} paused"}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: int, background_tasks: BackgroundTasks):
    """Resume a paused or stopped run from where it left off."""
    import os
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Run).where(Run.id == run_id)
        run = session.exec(statement).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        if run.status not in ["paused", "stopped", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Can only resume paused, stopped, or failed runs (current: {run.status})"
            )

        # Check if there are pending tasks
        pending_stmt = select(Task).where(
            Task.run_id == run_id,
            Task.status.in_(["pending", "running"])
        )
        pending_tasks = list(session.exec(pending_stmt).all())

        if not pending_tasks:
            raise HTTPException(
                status_code=400,
                detail="No pending tasks to resume - run is already complete"
            )

        # Get credentials
        email = os.environ.get("OO_EMAIL")
        password = os.environ.get("OO_PASSWORD")
        if not email or not password:
            raise HTTPException(status_code=500, detail="Missing credentials")

        num_browsers = int(os.environ.get("OO_MAX_BROWSERS", "2"))
        headless = os.environ.get("OO_HEADLESS", "false").lower() == "true"

        run_id_copy = run.id
        pending_count = len(pending_tasks)

    finally:
        session.close()

    # Start execution in background
    import traceback

    async def run_executor():
        try:
            await start_run_execution(
                run_id_copy,
                email,
                password,
                num_browsers=num_browsers,
                headless=headless,
                update_callback=notify_run_update,
            )
        except Exception as e:
            print(f"Execution error for run {run_id_copy}: {e}")
            traceback.print_exc()

    background_tasks.add_task(run_executor)

    return {
        "run_id": run_id_copy,
        "pending_tasks": pending_count,
        "status": "resuming",
        "message": f"Resuming run #{run_id_copy} with {pending_count} pending tasks"
    }


@router.get("/results/{result_id}/artifacts/{artifact_type}")
async def download_artifact(result_id: int, artifact_type: str):
    """Download artifact file (chart, screenshot, trade_log)."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Result).where(Result.id == result_id)
        result = session.exec(statement).first()
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")

        # Get the appropriate path based on artifact type
        path_map = {
            "chart": result.chart_path,
            "screenshot": result.results_screenshot,
            "trade_log": result.trade_log_csv,
        }

        file_path = path_map.get(artifact_type)
        if not file_path:
            raise HTTPException(status_code=404, detail=f"Artifact type '{artifact_type}' not found")

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Artifact file not found on disk")

        # Determine media type
        media_type = "image/png" if artifact_type in ["chart", "screenshot"] else "text/csv"
        filename = os.path.basename(file_path)

        return FileResponse(
            file_path,
            media_type=media_type,
            filename=filename,
        )
    finally:
        session.close()


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: int):
    """Get result for a specific task including artifact paths."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Result).where(Result.task_id == task_id)
        result = session.exec(statement).first()
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")

        result_dict = result.model_dump()

        # Add download URLs for artifacts
        if result.chart_path:
            result_dict["chart_url"] = f"/api/results/{result.id}/artifacts/chart"
        if result.results_screenshot:
            result_dict["screenshot_url"] = f"/api/results/{result.id}/artifacts/screenshot"
        if result.trade_log_csv:
            result_dict["trade_log_url"] = f"/api/results/{result.id}/artifacts/trade_log"

        return result_dict
    finally:
        session.close()


class TestRenameRequest(BaseModel):
    """Request body for renaming a test."""
    name: str


@router.patch("/tests/{test_id}")
async def rename_test(test_id: int, data: TestRenameRequest):
    """Rename a test."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Test).where(Test.id == test_id)
        test = session.exec(statement).first()
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

        test.name = data.name.strip() if data.name.strip() else None
        session.commit()
        session.refresh(test)

        return {"id": test.id, "name": test.name, "message": "Test renamed successfully"}
    finally:
        session.close()
