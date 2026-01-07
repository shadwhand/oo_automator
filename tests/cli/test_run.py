# tests/cli/test_run.py
"""Tests for CLI run command."""
import pytest
from typer.testing import CliRunner
from oo_automator.main import app


runner = CliRunner()


def test_version_command():
    """Test version command works."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "OO Automator v" in result.stdout


def test_help_command():
    """Test help command shows run subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout


def test_run_help():
    """Test run subcommand help."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "interactive" in result.stdout
    assert "quick" in result.stdout


def test_serve_command():
    """Test serve command exists."""
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.stdout
