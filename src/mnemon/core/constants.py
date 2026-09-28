"""
Constants for Mnemon.

All magic strings and valid value sets should be defined here.
"""

import re

# ── Entity Types ──────────────────────────────────────────────────────────────

ENTITY_TYPES = {
    "component",
    "concept",
    "person",
    "file",
    "system",
    "custom",
}

# Default entity type
DEFAULT_ENTITY_TYPE = "concept"

# ── Task Statuses ─────────────────────────────────────────────────────────────

TASK_STATUSES = {
    "todo",
    "in-progress",
    "done",
    "blocked",
}

# Default task status
DEFAULT_TASK_STATUS = "todo"

# ── Importance ────────────────────────────────────────────────────────────────

MIN_IMPORTANCE = 0.0
MAX_IMPORTANCE = 1.0
DEFAULT_IMPORTANCE = 0.5

# Threshold for including entities in context block
CONTEXT_IMPORTANCE_THRESHOLD = 0.4

# ── Task Status Priority ──────────────────────────────────────────────────────

# Order for displaying tasks (higher priority first)
TASK_STATUS_PRIORITY = {
    "in-progress": 1,
    "blocked": 2,
    "todo": 3,
    "done": 4,
}

# ── Sources ───────────────────────────────────────────────────────────────────

# Source types for session logs
SESSION_LOG_SOURCES = {
    "ai",
    "git-commit",
}

DEFAULT_SESSION_LOG_SOURCE = "ai"

# Source types for observations
OBSERVATION_SOURCES = {
    "ai",
    "git-commit",
    "manual",
}

DEFAULT_OBSERVATION_SOURCE = "ai"

# ── Status Icons (for CLI output) ────────────────────────────────────────────

STATUS_ICON = {
    "in-progress": "▶",
    "blocked": "✗",
    "todo": "○",
    "done": "✓",
}

# ── Entity Icons (for CLI output) ────────────────────────────────────────────

ENTITY_ICON = {
    "component": "⬡",
    "concept": "◈",
    "person": "◉",
    "file": "◻",
    "system": "◆",
    "custom": "◇",
}

# ── Hybrid Search ─────────────────────────────────────────────────────────────

# Reciprocal rank fusion constant: higher values flatten the rank differences
# between signals (standard RRF tuning value).
RRF_K = 60

# Cap on rows fetched per signal before ranking, so large stores stay bounded.
SEARCH_CANDIDATE_LIMIT = 50

# FTS5 mirror tables backing hybrid search, keyed by result category.
FTS_TABLES = {
    "entities": "entities_fts",
    "decisions": "decisions_fts",
    "tasks": "tasks_fts",
    "sessions": "sessions_fts",
}

# PRAGMA user_version marker set after the FTS backfill migration runs once.
FTS_MIGRATION_VERSION = 1


def prepare_fts_text(text: str | None) -> str:
    """
    Normalize text for FTS5 indexing and query building.

    Splits camelCase and acronym boundaries into separate words so prefix
    queries can match them (e.g. 'WasteVolumeController' becomes
    'Waste Volume Controller'). Returns an empty string for None so callers
    never need their own null handling.
    """
    if not text:
        return ""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return text


# ── Validation Helpers ────────────────────────────────────────────────────────


def validate_entity_type(entity_type: str | None) -> str:
    """
    Validate entity type.

    Args:
        entity_type: The entity type to validate

    Returns:
        The validated entity type

    Raises:
        ValueError: If entity_type is not in ENTITY_TYPES
    """
    if entity_type is None:
        return DEFAULT_ENTITY_TYPE
    if entity_type not in ENTITY_TYPES:
        valid = ", ".join(sorted(ENTITY_TYPES))
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be one of: {valid}")
    return entity_type


def validate_task_status(status: str | None) -> str:
    """
    Validate task status.

    Args:
        status: The status to validate

    Returns:
        The validated status

    Raises:
        ValueError: If status is not in TASK_STATUSES
    """
    if status is None:
        return DEFAULT_TASK_STATUS
    if status not in TASK_STATUSES:
        valid = ", ".join(sorted(TASK_STATUSES))
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid}")
    return status


def validate_importance(importance: float | None) -> float:
    """
    Validate importance value.

    Args:
        importance: The importance value to validate

    Returns:
        The validated importance (clamped to range)

    Raises:
        ValueError: If importance is not between MIN_IMPORTANCE and MAX_IMPORTANCE
    """
    if importance is None:
        return DEFAULT_IMPORTANCE
    if not (MIN_IMPORTANCE <= importance <= MAX_IMPORTANCE):
        raise ValueError(
            f"Importance must be between {MIN_IMPORTANCE} and {MAX_IMPORTANCE}. Got: {importance}"
        )
    return importance
