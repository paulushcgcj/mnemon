"""
Contracts Package
=================
JSON output contracts for mnemon CLI.

This package contains Pydantic models that define the JSON output contracts
for all mnemon CLI commands, providing:
- Type safety for command outputs
- Standardized JSON schemas
- IDE autocomplete support
- Documentation generation
"""

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
from mnemon.contracts.registry import (
    CONTRACTS,
    get_all_contracts,
    get_contract,
    list_contracts,
)

# All available contract model names
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
    # Registry functions
    "CONTRACTS",
    "get_contract",
    "list_contracts",
    "get_all_contracts",
]
