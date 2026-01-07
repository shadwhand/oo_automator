"""FastAPI web application for OO Automator dashboard."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routes import pages, api
from .templates_config import STATIC_DIR, templates, get_templates

# Create app
app = FastAPI(
    title="OO Automator",
    description="OptionOmega backtesting automation dashboard",
    version="2.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(pages.router)
app.include_router(api.router, prefix="/api")

# Re-export for backwards compatibility
__all__ = ["app", "templates", "get_templates"]
