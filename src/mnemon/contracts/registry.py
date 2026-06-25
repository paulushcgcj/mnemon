"""
Contract Registry
================
Registry of all Pydantic models used for JSON output contracts.

This enables:
- Discovery of all available contracts
- Type hints for IDE autocomplete
- Documentation generation
- Runtime validation of contract usage
"""

from pydantic import BaseModel

from mnemon.contracts.graph_contracts import (
    EntitySearchResult,
    GraphEntity,
    GraphPruneResult,
    GraphRelation,
    GraphResult,
)
from mnemon.contracts.memory_contracts import (
    DecisionResult,
    EntityResult,
    KnowledgeGraph,
    ObservationResult,
    SessionInfo,
    SessionList,
    TaskList,
    TaskResult,
)
from mnemon.contracts.project_contracts import (
    ProjectContext,
    ProjectInfo,
    ProjectList,
)

# Type alias for contract types
ContractType = type[BaseModel]

# All contract models organized by category
CONTRACTS: dict[str, dict[str, ContractType]] = {
    # Memory contracts
    "memory": {
        "KnowledgeGraph": KnowledgeGraph,
        "EntityResult": EntityResult,
        "ObservationResult": ObservationResult,
        "TaskResult": TaskResult,
        "TaskList": TaskList,
        "DecisionResult": DecisionResult,
        "SessionInfo": SessionInfo,
        "SessionList": SessionList,
    },

    # Project contracts
    "project": {
        "ProjectInfo": ProjectInfo,
        "ProjectList": ProjectList,
        "ProjectContext": ProjectContext,
    },

    # Graph contracts
    "graph": {
        "GraphEntity": GraphEntity,
        "GraphRelation": GraphRelation,
        "GraphResult": GraphResult,
        "EntitySearchResult": EntitySearchResult,
        "GraphPruneResult": GraphPruneResult,
    },
}

# Flattened list of all contract model names
__all__ = [
    # Memory contracts
    "KnowledgeGraph",
    "EntityResult",
    "ObservationResult",
    "TaskResult",
    "TaskList",
    "DecisionResult",
    "SessionInfo",
    "SessionList",
    # Project contracts
    "ProjectInfo",
    "ProjectList",
    "ProjectContext",
    # Graph contracts
    "GraphEntity",
    "GraphRelation",
    "GraphResult",
    "EntitySearchResult",
    "GraphPruneResult",
]


def get_contract(category: str, name: str):
    """
    Get a contract model by category and name.

    Args:
        category: Contract category ('memory', 'project', 'graph')
        name: Contract model name

    Returns:
        The Pydantic model class

    Raises:
        KeyError: If category or contract name is not found
    """
    try:
        return CONTRACTS[category][name]
    except KeyError:
        available = list(CONTRACTS.keys())
        raise KeyError(
            f"Contract '{name}' not found in category '{category}'. "
            f"Available categories: {available}"
        ) from None


def list_contracts(category: str | None = None) -> list[str]:
    """
    List all available contract names, optionally filtered by category.

    Args:
        category: Optional category filter ('memory', 'project', 'graph')

    Returns:
        List of contract model names
    """
    if category:
        try:
            return list(CONTRACTS[category].keys())
        except KeyError:
            available = list(CONTRACTS.keys())
            raise KeyError(f"Category '{category}' not found. Available: {available}") from None

    # Return all contracts from all categories
    all_contracts: list[str] = []
    for cat_contracts in CONTRACTS.values():
        all_contracts.extend(cat_contracts.keys())
    return all_contracts


def get_all_contracts() -> dict[str, dict[str, ContractType]]:
    """
    Get all contracts organized by category.

    Returns:
        Dictionary of all contracts organized by category
    """
    return CONTRACTS.copy()
