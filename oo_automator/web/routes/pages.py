"""HTML page routes."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from ...db.connection import get_engine, get_session
from ...db.queries import get_recent_tests
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
