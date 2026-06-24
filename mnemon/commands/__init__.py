"""
Commands Package
================
Central registration point for all CLI commands.

Commands are organized and registered here for better maintainability
and discoverability.
"""

from typing import TYPE_CHECKING

# List of all registered command names
COMMAND_NAMES = [
    "serve",
    "init",
    "install",
    "log-commit",
    "read",
    "graph",
    "prune",
    "projects",
]

if TYPE_CHECKING:
    import click
    # Import the main CLI app for type checking only
    from mnemon.cli import cli as main_app

__all__ = ["COMMAND_NAMES"]