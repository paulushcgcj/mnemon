"""
Commands Utilities
=================
Shared utilities for CLI commands.

This module provides reusable functions for:
- File loading and validation
- Output formatting and writing
- Error handling
- Common patterns
"""

import sys
from pathlib import Path
from typing import Any, Optional, Union

import click

from pydantic import BaseModel


class CLIError(Exception):
    """
    CLIError
    ========
    Base exception for CLI errors.
    
    When raised, the CLI should exit with code 1 and display the message.
    """
    pass


def load_file(path: Path) -> str:
    """
    Load content from a file.
    
    Args:
        path: Path to the file to load
        
    Returns:
        File content as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        CLIError: If file cannot be read
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        raise CLIError(f"Failed to read {path}: {e}")


def load_files(paths: list[Path]) -> list[str]:
    """
    Load content from multiple files.
    
    Args:
        paths: List of file paths to load
        
    Returns:
        List of file contents as strings
        
    Raises:
        FileNotFoundError: If any file doesn't exist
        CLIError: If any file cannot be read
    """
    return [load_file(p) for p in paths]


def write_output(
    data: Union[str, BaseModel],
    output_path: Optional[Path] = None,
    format: str = "text",
) -> None:
    """
    Write output to stdout or file.
    
    Args:
        data: Data to write (string or Pydantic model)
        output_path: Path to output file (None for stdout)
        format: Output format ('text' or 'json')
        
    Raises:
        CLIError: If file cannot be written
    """
    # Convert Pydantic models to appropriate format
    if isinstance(data, BaseModel):
        if format == "json":
            data = data.model_dump_json(by_alias=True)
        else:
            data = str(data.model_dump())
    
    if output_path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(str(data), encoding="utf-8")
        except Exception as e:
            raise CLIError(f"Failed to write {output_path}: {e}")
    else:
        # For click, use echo to ensure proper output
        click.echo(data)


def format_output(
    data: Any,
    format: str = "text",
    model_class: Optional[type[BaseModel]] = None,
) -> str:
    """
    Format data for output based on the specified format.
    
    Args:
        data: Data to format
        format: Output format ('text' or 'json')
        model_class: Optional Pydantic model class to validate/serialize with
        
    Returns:
        Formatted string
        
    Raises:
        CLIError: If format is invalid or serialization fails
    """
    if format == "json":
        if model_class and not isinstance(data, model_class):
            # Try to validate and create model instance
            try:
                data = model_class.model_validate(data)
            except Exception as e:
                raise CLIError(f"Failed to validate data as {model_class.__name__}: {e}")
        
        if isinstance(data, BaseModel):
            return data.model_dump_json(by_alias=True)
        else:
            import json
            return json.dumps(data, indent=2, default=str)
    elif format == "text":
        if isinstance(data, BaseModel):
            return str(data.model_dump())
        else:
            return str(data)
    else:
        raise CLIError(f"Invalid format: {format}. Must be 'text' or 'json'.")


def format_error(message: str) -> None:
    """
    Format and print an error message to stderr.
    
    Args:
        message: Error message to display
    """
    click.echo(f"Error: {message}", file=sys.stderr, err=True)


def handle_cli_error(e: Exception, exit_code: int = 1) -> None:
    """
    Handle a CLI error by printing to stderr and exiting.
    
    Args:
        e: Exception that occurred
        exit_code: Exit code to use (default: 1)
    """
    if isinstance(e, CLIError):
        format_error(str(e))
    else:
        format_error(f"Unexpected error: {e}")
    sys.exit(exit_code)


def get_project_id_from_cwd(cwd: Optional[str] = None) -> str:
    """
    Get the project ID from the current working directory or specified directory.
    
    Args:
        cwd: Directory to use (default: current working directory)
        
    Returns:
        Project ID string
        
    Raises:
        CLIError: If project ID cannot be determined
    """
    from mnemon.core.git import get_project_id
    try:
        return get_project_id(cwd or ".")
    except Exception as e:
        raise CLIError(f"Could not detect project: {e}")


def get_branch_from_cwd(cwd: Optional[str] = None) -> str:
    """
    Get the current git branch from the current working directory or specified directory.
    
    Args:
        cwd: Directory to use (default: current working directory)
        
    Returns:
        Branch name string
        
    Raises:
        CLIError: If branch cannot be determined
    """
    from mnemon.core.git import get_branch
    try:
        return get_branch(cwd or ".")
    except Exception as e:
        raise CLIError(f"Could not detect branch: {e}")


def validate_format(format: str) -> str:
    """
    Validate output format.
    
    Args:
        format: Format string to validate
        
    Returns:
        Validated format string
        
    Raises:
        CLIError: If format is invalid
    """
    valid_formats = ["text", "json"]
    if format not in valid_formats:
        raise CLIError(f"Invalid format: {format}. Must be one of: {valid_formats}")
    return format