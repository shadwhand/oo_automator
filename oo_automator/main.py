import typer

app = typer.Typer(
    name="oo-automator",
    help="OptionOmega backtesting automation with live dashboard",
    add_completion=False,
)


@app.command()
def version():
    """Show version information."""
    from . import __version__
    typer.echo(f"OO Automator v{__version__}")


if __name__ == "__main__":
    app()
