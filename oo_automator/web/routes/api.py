"""REST API endpoints."""
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from ...db.connection import get_engine, get_session
from ...db.models import Run, Task, Result

router = APIRouter()


@router.get("/runs")
async def list_runs(limit: int = 10):
    """List recent runs."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Run).order_by(Run.created_at.desc()).limit(limit)
        runs = list(session.exec(statement).all())
        return {"runs": [run.model_dump() for run in runs]}
    finally:
        session.close()


@router.get("/runs/{run_id}")
async def get_run(run_id: int):
    """Get run details."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Run).where(Run.id == run_id)
        run = session.exec(statement).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.model_dump()
    finally:
        session.close()


@router.get("/runs/{run_id}/tasks")
async def get_run_tasks(run_id: int):
    """Get tasks for a run."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = select(Task).where(Task.run_id == run_id)
        tasks = list(session.exec(statement).all())
        return {"tasks": [task.model_dump() for task in tasks]}
    finally:
        session.close()


@router.get("/runs/{run_id}/results")
async def get_run_results(run_id: int):
    """Get results for a run."""
    engine = get_engine()
    session = get_session(engine)

    try:
        statement = (
            select(Result)
            .join(Task)
            .where(Task.run_id == run_id)
        )
        results = list(session.exec(statement).all())
        return {"results": [result.model_dump() for result in results]}
    finally:
        session.close()
