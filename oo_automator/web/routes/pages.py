"""HTML page routes."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...db.connection import get_engine, get_session
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
async def new_run(request: Request):
    """New run form page."""
    templates = get_templates()
    config = get_config()
    parameters = list_parameters()

    return templates.TemplateResponse(
        request,
        "new_run.html",
        {
            "parameters": parameters,
            "config_email": config.email,
        }
    )
