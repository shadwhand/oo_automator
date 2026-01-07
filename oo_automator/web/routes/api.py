"""REST API endpoints with htmx partial support."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select

from ...db.connection import get_engine, get_session
from ...db.models import Run, Task, Result
from ..templates_config import get_templates

router = APIRouter()


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
