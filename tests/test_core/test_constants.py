"""Tests for constants and validation functions."""

import pytest

from mnemon.core.constants import (
    # Thresholds
    CONTEXT_IMPORTANCE_THRESHOLD,
    # Default values
    DEFAULT_ENTITY_TYPE,
    DEFAULT_IMPORTANCE,
    DEFAULT_TASK_STATUS,
    # Icons
    ENTITY_ICON,
    # Entity types
    ENTITY_TYPES,
    STATUS_ICON,
    # Task statuses
    TASK_STATUSES,
    validate_entity_type,
    # Importance
    validate_importance,
    validate_task_status,
)


class TestEntityTypes:
    """Tests for entity type validation."""

    def test_validate_valid_entity_types(self):
        """Test that all valid entity types are accepted."""
        for entity_type in ENTITY_TYPES:
            result = validate_entity_type(entity_type)
            assert result == entity_type

    def test_validate_invalid_entity_type(self):
        """Test that invalid entity type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid entity_type"):
            validate_entity_type("invalid_type")

    def test_validate_none_entity_type(self):
        """Test that None entity type returns default."""
        result = validate_entity_type(None)
        assert result == DEFAULT_ENTITY_TYPE

    def test_default_entity_type(self):
        """Test that default entity type is in valid types."""
        assert DEFAULT_ENTITY_TYPE in ENTITY_TYPES


class TestImportance:
    """Tests for importance validation."""

    def test_validate_valid_importance(self):
        """Test that valid importance values are accepted."""
        for value in [0.0, 0.5, 1.0, 0.25, 0.75]:
            result = validate_importance(value)
            assert result == value

    def test_validate_importance_out_of_range(self):
        """Test that out-of-range importance raises ValueError."""
        with pytest.raises(ValueError, match="Importance must be between"):
            validate_importance(-0.5)
        with pytest.raises(ValueError, match="Importance must be between"):
            validate_importance(1.5)

    def test_validate_none_importance(self):
        """Test that None importance returns default."""
        result = validate_importance(None)
        assert result == DEFAULT_IMPORTANCE

    def test_default_importance(self):
        """Test that default importance is valid."""
        assert 0.0 <= DEFAULT_IMPORTANCE <= 1.0


class TestTaskStatuses:
    """Tests for task status validation."""

    def test_validate_valid_task_statuses(self):
        """Test that all valid task statuses are accepted."""
        for status in TASK_STATUSES:
            result = validate_task_status(status)
            assert result == status

    def test_validate_invalid_task_status(self):
        """Test that invalid task status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            validate_task_status("invalid_status")

    def test_validate_none_task_status(self):
        """Test that None task status returns default."""
        result = validate_task_status(None)
        assert result == DEFAULT_TASK_STATUS

    def test_default_task_status(self):
        """Test that default task status is in valid statuses."""
        assert DEFAULT_TASK_STATUS in TASK_STATUSES


class TestConstantsValues:
    """Tests for constant values."""

    def test_entity_types_set(self):
        """Test that ENTITY_TYPES is a non-empty set."""
        assert isinstance(ENTITY_TYPES, set)
        assert len(ENTITY_TYPES) > 0

    def test_task_statuses_set(self):
        """Test that TASK_STATUSES is a non-empty set."""
        assert isinstance(TASK_STATUSES, set)
        assert len(TASK_STATUSES) > 0

    def test_context_importance_threshold(self):
        """Test that context importance threshold is valid."""
        assert 0.0 <= CONTEXT_IMPORTANCE_THRESHOLD <= 1.0

    def test_entity_icon_dict(self):
        """Test that ENTITY_ICON is a dict with expected keys."""
        assert isinstance(ENTITY_ICON, dict)
        for entity_type in ENTITY_TYPES:
            assert entity_type in ENTITY_ICON

    def test_status_icon_dict(self):
        """Test that STATUS_ICON is a dict with expected keys."""
        assert isinstance(STATUS_ICON, dict)
        for status in TASK_STATUSES:
            assert status in STATUS_ICON
