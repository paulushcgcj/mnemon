"""
Graph Contracts
===============
Pydantic models for knowledge graph-related JSON output.
"""


from pydantic import BaseModel, Field


class GraphEntity(BaseModel):
    """
    GraphEntity
    ==========
    A single entity in the knowledge graph for JSON output.

    Args:
        id: Unique entity identifier
        projectId: Associated project ID
        name: Entity name
        entityType: Type of entity (component, concept, person, file, system, custom)
        importance: Importance score (0.0-1.0)
        branch: Branch name if branch-scoped, null otherwise
        observations: List of observations for this entity
        relations: List of relations for this entity
        createdAt: ISO 8601 timestamp when entity was created
        updatedAt: ISO 8601 timestamp when entity was last updated
    """
    id: str = Field(..., serialization_alias="id")
    projectId: str = Field(..., serialization_alias="projectId")
    name: str = Field(..., serialization_alias="name")
    entityType: str = Field(..., serialization_alias="entityType")
    importance: float = Field(..., serialization_alias="importance")
    branch: str | None = Field(None, serialization_alias="branch")
    observations: list[str] = Field(default_factory=list, serialization_alias="observations")
    relations: list[dict] = Field(default_factory=list, serialization_alias="relations")
    createdAt: str = Field(..., serialization_alias="createdAt")
    updatedAt: str = Field(..., serialization_alias="updatedAt")


class GraphRelation(BaseModel):
    """
    GraphRelation
    =============
    A single relation in the knowledge graph.

    Args:
        id: Unique relation identifier
        projectId: Associated project ID
        fromId: Source entity ID
        toId: Target entity ID
        relation: Type of relation
        createdAt: ISO 8601 timestamp when relation was created
    """
    id: str = Field(..., serialization_alias="id")
    projectId: str = Field(..., serialization_alias="projectId")
    fromId: str = Field(..., serialization_alias="fromId")
    toId: str = Field(..., serialization_alias="toId")
    relation: str = Field(..., serialization_alias="relation")
    createdAt: str = Field(..., serialization_alias="createdAt")


class GraphResult(BaseModel):
    """
    GraphResult
    ==========
    Complete graph result with entities and relations.

    Args:
        projectId: Associated project ID
        branch: Branch name (null for project-wide)
        entities: List of entities in the graph
        relations: List of relations in the graph
        entityCount: Total number of entities
        relationCount: Total number of relations
    """
    projectId: str = Field(..., serialization_alias="projectId")
    branch: str | None = Field(None, serialization_alias="branch")
    entities: list[GraphEntity] = Field(default_factory=list, serialization_alias="entities")
    relations: list[GraphRelation] = Field(default_factory=list, serialization_alias="relations")
    entityCount: int = Field(..., serialization_alias="entityCount")
    relationCount: int = Field(..., serialization_alias="relationCount")


class EntitySearchResult(BaseModel):
    """
    EntitySearchResult
    ==================
    Results from searching entities in the knowledge graph.

    Args:
        query: The search query
        projectId: Associated project ID
        results: List of matching entities
        total: Total number of results
        limit: Maximum number of results returned
    """
    query: str = Field(..., serialization_alias="query")
    projectId: str = Field(..., serialization_alias="projectId")
    results: list[GraphEntity] = Field(default_factory=list, serialization_alias="results")
    total: int = Field(..., serialization_alias="total")
    limit: int = Field(..., serialization_alias="limit")


class GraphPruneResult(BaseModel):
    """
    GraphPruneResult
    ================
    Result of pruning stale entities from the knowledge graph.

    Args:
        projectId: Associated project ID
        prunedCount: Number of entities pruned
        belowImportance: Importance threshold used
        olderThanDays: Age threshold in days used
        dryRun: Whether this was a dry run
        candidates: List of entities that would be pruned (for dry runs)
    """
    projectId: str = Field(..., serialization_alias="projectId")
    prunedCount: int = Field(0, serialization_alias="prunedCount")
    belowImportance: float = Field(..., serialization_alias="belowImportance")
    olderThanDays: int = Field(..., serialization_alias="olderThanDays")
    dryRun: bool = Field(..., serialization_alias="dryRun")
    candidates: list[dict] = Field(default_factory=list, serialization_alias="candidates")
