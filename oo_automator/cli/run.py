# oo_automator/cli/run.py
"""Interactive run command for OO Automator."""
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.panel import Panel
from sqlmodel import Session

from ..db.connection import init_db, get_session
from ..db.queries import (
    get_or_create_test,
    get_recent_tests,
    find_test_by_name_or_url,
    create_run,
    create_tasks_for_run,
)
from ..parameters import list_parameters, get_parameter
from ..core.run_manager import generate_combinations

console = Console()
app = typer.Typer()


def show_recent_tests(session: Session) -> list:
    """Display recent tests and return them."""
    tests = get_recent_tests(session, limit=5)

    if tests:
        console.print("\n[bold]Recent tests:[/bold]")
        for i, test in enumerate(tests, 1):
            name = test.name or "(unnamed)"
            last_run = test.last_run_at.strftime("%Y-%m-%d") if test.last_run_at else "never"
            console.print(f"  [{i}] {name} - last run: {last_run}")
            console.print(f"      [dim]{test.url}[/dim]")

    return tests


def select_test(session: Session) -> tuple[str, Optional[str]]:
    """Interactive test selection."""
    recent = show_recent_tests(session)

    console.print()
    query = Prompt.ask(
        "Enter test URL, name, or number",
        default="1" if recent else ""
    )

    # Check if it's a number selection
    if query.isdigit() and recent:
        idx = int(query) - 1
        if 0 <= idx < len(recent):
            return recent[idx].url, recent[idx].name

    # Check if it's a URL
    if query.startswith("http"):
        name = Prompt.ask("Name this test (optional)", default="")
        return query, name if name else None

    # Try to find by name
    test = find_test_by_name_or_url(session, query)
    if test:
        return test.url, test.name

    # Treat as new URL
    console.print("[yellow]Test not found. Treating as new URL.[/yellow]")
    return query, None


def select_mode() -> str:
    """Select test mode."""
    console.print("\n[bold]Test mode:[/bold]")
    console.print("  [1] Single parameter sweep")
    console.print("  [2] Grid search (multiple parameters)")
    console.print("  [3] Staged optimization")

    choice = IntPrompt.ask("Select mode", default=1)
    modes = {1: "sweep", 2: "grid", 3: "staged"}
    return modes.get(choice, "sweep")


def select_parameters() -> list[str]:
    """Select parameters to test."""
    params = list_parameters()

    console.print("\n[bold]Available parameters:[/bold]")
    for i, p in enumerate(params, 1):
        console.print(f"  [{i}] {p['display_name']} - {p['description']}")

    selection = Prompt.ask("Select parameter(s) (comma-separated numbers)")

    try:
        indices = [int(x.strip()) - 1 for x in selection.split(",") if x.strip()]
    except ValueError:
        console.print("[red]Invalid selection. Please enter comma-separated numbers.[/red]")
        return []

    return [params[i]["name"] for i in indices if 0 <= i < len(params)]


def configure_parameter(param_name: str) -> dict:
    """Configure a parameter interactively."""
    param = get_parameter(param_name)
    if not param:
        return {}

    config_schema = param.configure()
    config = {}

    console.print(f"\n[bold]{param.display_name} configuration:[/bold]")

    for field in config_schema.fields:
        if hasattr(field, 'choices'):
            console.print(f"  Options: {', '.join(field.choices)}")
            value = Prompt.ask(f"  {field.label}", default=str(field.default))
        elif hasattr(field, 'min_val'):
            value = IntPrompt.ask(
                f"  {field.label} ({field.min_val}-{field.max_val})",
                default=field.default
            )
        else:
            value = Prompt.ask(f"  {field.label}", default=str(field.default))

        config[field.name] = value

    return config


def build_run_config(mode: str, param_names: list[str]) -> dict:
    """Build run configuration interactively."""
    if mode == "sweep":
        param_name = param_names[0]
        param_config = configure_parameter(param_name)

        param = get_parameter(param_name)
        values = param.generate_values(param_config)

        return {
            "mode": "sweep",
            "parameter": param_name,
            "values": values,
            "param_config": param_config,
        }

    elif mode == "grid":
        parameters = {}
        for param_name in param_names:
            param_config = configure_parameter(param_name)
            param = get_parameter(param_name)
            parameters[param_name] = param.generate_values(param_config)

        return {
            "mode": "grid",
            "parameters": parameters,
        }

    return {"mode": mode}


@app.command()
def interactive(
    browsers: int = typer.Option(2, "--browsers", "-b", help="Number of browsers"),
    headless: bool = typer.Option(False, "--headless", help="Run browsers headless"),
):
    """Start an interactive run session."""
    console.print(Panel.fit(
        "[bold blue]OO Automator v2[/bold blue]\n"
        "Interactive Backtesting Automation",
        border_style="blue"
    ))

    # Initialize database
    engine = init_db()
    session = get_session(engine)

    try:
        # Select test
        test_url, test_name = select_test(session)
        test = get_or_create_test(session, test_url, test_name)
        console.print(f"\n[green]✓[/green] Using test: {test.name or test.url}")

        # Select mode
        mode = select_mode()
        console.print(f"[green]✓[/green] Mode: {mode}")

        # Select parameters
        param_names = select_parameters()
        if not param_names:
            console.print("[red]No parameters selected. Exiting.[/red]")
            return

        # Configure parameters
        run_config = build_run_config(mode, param_names)

        # Show summary
        combinations = generate_combinations(run_config)
        console.print(f"\n[bold]Run Summary:[/bold]")
        console.print(f"  Test: {test.name or test.url}")
        console.print(f"  Mode: {mode}")
        console.print(f"  Parameters: {', '.join(param_names)}")
        console.print(f"  Total tests: {len(combinations)}")
        console.print(f"  Browsers: {browsers}")

        if not Confirm.ask("\nStart run?", default=True):
            console.print("[yellow]Run cancelled.[/yellow]")
            return

        # Get credentials
        console.print("\n[bold]Credentials:[/bold]")
        email = Prompt.ask("  Email")
        password = Prompt.ask("  Password", password=True)

        # Create run in database
        run = create_run(session, test.id, mode, run_config)
        create_tasks_for_run(session, run.id, combinations)

        console.print(f"\n[green]✓[/green] Run created: #{run.id}")
        console.print(f"  Dashboard: http://localhost:8000/runs/{run.id}")

        # TODO: Start actual run execution
        console.print("\n[yellow]Run execution not yet implemented.[/yellow]")
        console.print("Use 'oo-automator serve' to start the dashboard.")

    finally:
        session.close()


@app.command()
def quick(
    url: str = typer.Argument(..., help="Test URL"),
    param: str = typer.Option(..., "--param", "-p", help="Parameter to sweep"),
    start: int = typer.Option(..., "--start", "-s", help="Start value"),
    end: int = typer.Option(..., "--end", "-e", help="End value"),
    step: int = typer.Option(1, "--step", help="Step value"),
    browsers: int = typer.Option(2, "--browsers", "-b", help="Number of browsers"),
):
    """Quick run with command-line parameters."""
    console.print(f"Quick run: {param} from {start} to {end}")
    # TODO: Implement quick run
