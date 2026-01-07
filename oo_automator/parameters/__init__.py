"""Parameter plugin system with auto-discovery."""
import importlib
import pkgutil
from pathlib import Path
from typing import Optional

from .base import Parameter, ParameterConfig


def discover_parameters() -> dict[str, type[Parameter]]:
    """Auto-discover all parameter classes in this package."""
    parameters = {}
    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name in ("__init__", "base"):
            continue

        try:
            module = importlib.import_module(f".{module_info.name}", __package__)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, Parameter) and
                    attr is not Parameter and
                    hasattr(attr, "name")):
                    parameters[attr.name] = attr
        except Exception as e:
            print(f"Warning: Failed to load parameter module {module_info.name}: {e}")

    return parameters


def get_parameter(name: str) -> Optional[Parameter]:
    """Get a parameter instance by name."""
    param_class = PARAMETERS.get(name)
    if param_class:
        return param_class()
    return None


def list_parameters() -> list[dict]:
    """List all available parameters with metadata."""
    result = []
    for name, param_class in PARAMETERS.items():
        param = param_class()
        result.append({
            "name": param.name,
            "display_name": param.display_name,
            "description": param.description,
        })
    return result


# Auto-discover on import
PARAMETERS = discover_parameters()

__all__ = [
    "Parameter",
    "ParameterConfig",
    "discover_parameters",
    "get_parameter",
    "list_parameters",
    "PARAMETERS",
]
