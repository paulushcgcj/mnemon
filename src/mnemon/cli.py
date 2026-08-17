"""Mnemon — persistent project memory and knowledge graph for AI agents.

Command-line entry point. The Click group is defined here; the individual
command modules register themselves via :func:`_register_commands`.
"""

import click


@click.group()
def cli() -> None:
    """Mnemon — persistent project memory and knowledge graph for AI agents."""


def _register_commands() -> None:
    """Import and register all command modules on the Click group.

    Imports are deferred to avoid circular imports (command modules import
    from :mod:`mnemon.core` and :mod:`mnemon.commands._utils`).
    """
    from .commands import graph as _graph_commands
    from .commands import projects as _project_commands
    from .commands import sessions as _session_commands
    from .commands import setup as _setup_commands

    for module in (_setup_commands, _session_commands, _graph_commands, _project_commands):
        module.register(cli)


_register_commands()
