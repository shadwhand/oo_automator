"""Templates configuration for web app."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

# Paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Templates instance
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_templates():
    """Get templates instance for use in routes."""
    return templates
