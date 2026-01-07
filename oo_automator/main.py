# oo_automator/main.py
import typer

from .cli.run import app as run_app

app = typer.Typer(
    name="oo-automator",
    help="OptionOmega backtesting automation with live dashboard",
    add_completion=False,
)

# Add subcommands
app.add_typer(run_app, name="run")


@app.command()
def version():
    """Show version information."""
    from . import __version__
    typer.echo(f"OO Automator v{__version__}")


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", "-p", help="Port to run on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
):
    """Start the dashboard server."""
    typer.echo(f"Starting dashboard at http://{host}:{port}")
    # TODO: Implement server


if __name__ == "__main__":
    app()
