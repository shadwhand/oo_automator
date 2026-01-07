"""REST API endpoints with htmx partial support."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import select

from ...db.connection import get_engine, get_session, init_db
from ...db.models import Run, Task, Result
from ...db.queries import get_or_create_test, create_run, create_tasks_for_run
from ...core.run_manager import generate_combinations
from ..templates_config import get_templates

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
async def create_new_run(data: NewRunRequest):
    """Create a new run with tasks."""
    init_db()
    engine = get_engine()
    session = get_session(engine)

    try:
        # Create or get test
        test = get_or_create_test(session, data.url, data.name)

        # Build run config based on mode
        if data.mode == "sweep":
            # For sweep, use the first parameter
            param_name = list(data.parameters.keys())[0]
            param_config = data.parameters[param_name]

            # Generate values
            values = list(range(
                param_config["start"],
                param_config["end"] + 1,
                param_config["step"]
            ))

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
                values = list(range(
                    param_config["start"],
                    param_config["end"] + 1,
                    param_config["step"]
                ))
                parameters[param_name] = values

            run_config = {
                "mode": "grid",
                "parameters": parameters,
                "browsers": data.browsers,
                "headless": data.headless,
            }

        # Create run in database
        run = create_run(session, test.id, data.mode, run_config)

        # Generate task combinations
        combinations = generate_combinations(run_config)

        # Create tasks
        create_tasks_for_run(session, run.id, combinations)

        return {
            "run_id": run.id,
            "test_id": test.id,
            "total_tasks": len(combinations),
            "status": "created",
            "message": f"Run #{run.id} created with {len(combinations)} tasks"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


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
