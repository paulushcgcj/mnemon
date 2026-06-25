"""Module-level entry point for mnemon.

This allows running mnemon as `python -m mnemon` which is useful for
PyInstaller and other packaging tools.
"""

from mnemon.cli import cli

if __name__ == "__main__":
    cli()
