"""Mnemon — persistent project memory and knowledge graph for AI agents.

Command-line entry point. The Click group is defined here; the individual
command modules register themselves via :func:`_register_commands`.
"""

import click

from .update import check_for_update, installed_version


def _notify_update() -> None:
    """Print a non-blocking update notice when a newer release is available."""
    status = check_for_update()
    if status.update_available and status.latest_version:
        click.echo(
            f"Update available: {status.installed_version} → {status.latest_version}. "
            "Run `mnemon update` to upgrade.",
            err=True,
        )


@click.group(
    help=(
        "Mnemon — persistent project memory and knowledge graph for AI agents.\n\n"
        f"Version: {installed_version()}"
    )
)
@click.version_option(version=installed_version(), prog_name="mnemon")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Mnemon — persistent project memory and knowledge graph for AI agents."""
    if ctx.invoked_subcommand not in (None, "update"):
        _notify_update()


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
