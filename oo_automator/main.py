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
    import uvicorn
    from .db.connection import init_db

    # Initialize database
    init_db()

    typer.echo(f"Starting dashboard at http://{host}:{port}")
    uvicorn.run("oo_automator.web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
