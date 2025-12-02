"""Basic tests for CLI functionality."""

import pytest
from typer.testing import CliRunner
from pathlib import Path
import sys

# Add parent directory to path to import wear module
sys.path.insert(0, str(Path(__file__).parent.parent))

from wear import app

runner = CliRunner()


def test_help_command():
    """Test that help command works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Synheart Wear CLI" in result.stdout


def test_version_command():
    """Test that version command works."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_start_command_help():
    """Test that start command help works."""
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "Start" in result.stdout or "start" in result.stdout


def test_webhook_command_help():
    """Test that webhook command help works."""
    result = runner.invoke(app, ["webhook", "--help"])
    assert result.exit_code == 0
    assert "webhook" in result.stdout.lower()


def test_pull_command_help():
    """Test that pull command help works."""
    result = runner.invoke(app, ["pull", "--help"])
    assert result.exit_code == 0
    assert "pull" in result.stdout.lower()


def test_tokens_command_help():
    """Test that tokens command help works."""
    result = runner.invoke(app, ["tokens", "--help"])
    assert result.exit_code == 0
    assert "token" in result.stdout.lower()
