"""Structured JSON logging configuration using structlog."""

import logging
import sys
from typing import cast

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structlog JSON logging to stderr.

    The MCP server speaks JSON-RPC over stdio, so all log output MUST go to
    stderr to avoid corrupting the protocol stream.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    """Return a bound structlog logger for ``name``."""
    return cast(structlog.typing.FilteringBoundLogger, structlog.get_logger(name))
