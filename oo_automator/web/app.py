"""FastAPI web application for OO Automator dashboard."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import pages, api, websocket
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
app.include_router(websocket.router)

# Re-export for backwards compatibility
__all__ = ["app", "templates", "get_templates"]
