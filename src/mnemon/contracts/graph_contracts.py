"""Pydantic models for knowledge graph-related JSON output."""

from typing import Any

from pydantic import BaseModel, Field


class GraphEntity(BaseModel):
    """A single entity in the knowledge graph for JSON output.

    Attributes:
        id: The unique identifier of the entity.
        projectId: The project ID this entity belongs to.
        name: The entity name.
        entityType: The entity type (component, concept, person, file, system).
        importance: The entity importance score between 0.0 and 1.0.
        branch: The branch this entity is scoped to, or None for project-wide.
        observations: List of observation strings attached to the entity.
        relations: List of relation dictionaries attached to the entity.
        createdAt: Timestamp when the entity was created.
        updatedAt: Timestamp when the entity was last updated.
    """

    id: str = Field(..., serialization_alias="id")
    projectId: str = Field(..., serialization_alias="projectId")
    name: str = Field(..., serialization_alias="name")
    entityType: str = Field(..., serialization_alias="entityType")
    importance: float = Field(..., serialization_alias="importance")
    branch: str | None = Field(None, serialization_alias="branch")
    observations: list[str] = Field(default_factory=list, serialization_alias="observations")
    relations: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="relations")
    createdAt: str = Field(..., serialization_alias="createdAt")
    updatedAt: str = Field(..., serialization_alias="updatedAt")


class GraphRelation(BaseModel):
    """A single relation in the knowledge graph.

    Attributes:
        id: The unique identifier of the relation.
        projectId: The project ID this relation belongs to.
        fromId: The ID of the source entity.
        toId: The ID of the target entity.
        relation: The relation type (e.g. calls, depends_on, uses).
        createdAt: Timestamp when the relation was created.
    """

    id: str = Field(..., serialization_alias="id")
    projectId: str = Field(..., serialization_alias="projectId")
    fromId: str = Field(..., serialization_alias="fromId")
    toId: str = Field(..., serialization_alias="toId")
    relation: str = Field(..., serialization_alias="relation")
    createdAt: str = Field(..., serialization_alias="createdAt")


class GraphResult(BaseModel):
    """Complete graph result with entities and relations.

    Attributes:
        projectId: The project ID the graph belongs to.
        branch: The branch the graph is scoped to, or None for project-wide.
        entities: List of entities in the graph.
        relations: List of relations in the graph.
        entityCount: Total number of entities.
        relationCount: Total number of relations.
    """

    projectId: str = Field(..., serialization_alias="projectId")
    branch: str | None = Field(None, serialization_alias="branch")
    entities: list[GraphEntity] = Field(default_factory=list, serialization_alias="entities")
    relations: list[GraphRelation] = Field(default_factory=list, serialization_alias="relations")
    entityCount: int = Field(..., serialization_alias="entityCount")
    relationCount: int = Field(..., serialization_alias="relationCount")


class EntitySearchResult(BaseModel):
    """Results from searching entities in the knowledge graph.

    Attributes:
        query: The search query that produced these results.
        projectId: The project ID the search ran against.
        results: List of matching entities.
        total: Total number of matching entities.
        limit: The maximum number of results returned.
    """

    query: str = Field(..., serialization_alias="query")
    projectId: str = Field(..., serialization_alias="projectId")
    results: list[GraphEntity] = Field(default_factory=list, serialization_alias="results")
    total: int = Field(..., serialization_alias="total")
    limit: int = Field(..., serialization_alias="limit")


class GraphPruneResult(BaseModel):
    """Result of pruning stale entities from the knowledge graph.

    Attributes:
        projectId: The project ID the prune ran against.
        prunedCount: Number of entities pruned (or candidates in dry-run mode).
        belowImportance: The importance threshold used for pruning.
        olderThanDays: The age threshold in days used for pruning.
        dryRun: Whether this was a dry run (preview only).
        candidates: List of candidate entity dictionaries when dry-run is True.
    """

    projectId: str = Field(..., serialization_alias="projectId")
    prunedCount: int = Field(0, serialization_alias="prunedCount")
    belowImportance: float = Field(..., serialization_alias="belowImportance")
    olderThanDays: int = Field(..., serialization_alias="olderThanDays")
    dryRun: bool = Field(..., serialization_alias="dryRun")
    candidates: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="candidates")
