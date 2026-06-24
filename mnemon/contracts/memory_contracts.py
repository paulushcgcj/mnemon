"""
Memory Contracts
================
Pydantic models for memory and knowledge-related JSON output.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EntityResult(BaseModel):
    """
    EntityResult
    ==========
    Information about a single entity in the knowledge graph.
    
    Args:
        id: Unique entity identifier
        projectId: Associated project ID
        name: Entity name
        entityType: Type of entity (component, concept, person, file, system, custom)
        importance: Importance score (0.0-1.0)
        branch: Branch name if branch-scoped, null otherwise
        createdAt: ISO 8601 timestamp when entity was created
        updatedAt: ISO 8601 timestamp when entity was last updated
        observations: List of observations associated with this entity
        relations: List of relations for this entity
    """
    id: str = Field(..., serialization_alias="id")
    projectId: str = Field(..., serialization_alias="projectId")
    name: str = Field(..., serialization_alias="name")
    entityType: str = Field(..., serialization_alias="entityType")
    importance: float = Field(..., serialization_alias="importance")
    branch: Optional[str] = Field(None, serialization_alias="branch")
    createdAt: str = Field(..., serialization_alias="createdAt")
    updatedAt: str = Field(..., serialization_alias="updatedAt")
    observations: list[str] = Field(default_factory=list, serialization_alias="observations")
    relations: list[dict] = Field(default_factory=list, serialization_alias="relations")


class KnowledgeGraph(BaseModel):
    """
    KnowledgeGraph
    =============
    Complete knowledge graph for a project/branch.
    
    Args:
        projectId: Associated project ID
        branch: Branch name (null for project-wide)
        entities: List of entities in the graph
        totalCount: Total number of entities
    """
    projectId: str = Field(..., serialization_alias="projectId")
    branch: Optional[str] = Field(None, serialization_alias="branch")
    entities: list[EntityResult] = Field(default_factory=list, serialization_alias="entities")
    totalCount: int = Field(..., serialization_alias="totalCount")


class ObservationResult(BaseModel):
    """
    ObservationResult
    =================
    Information about an observation.
    
    Args:
        id: Unique observation identifier
        entityId: Associated entity ID
        content: Observation content
        source: Source of the observation (ai, manual, git-commit)
        createdAt: ISO 8601 timestamp when observation was created
    """
    id: str = Field(..., serialization_alias="id")
    entityId: str = Field(..., serialization_alias="entityId")
    content: str = Field(..., serialization_alias="content")
    source: str = Field(..., serialization_alias="source")
    createdAt: str = Field(..., serialization_alias="createdAt")


class TaskResult(BaseModel):
    """
    TaskResult
    ==========
    Information about a single task.
    
    Args:
        id: Unique task identifier
        projectId: Associated project ID
        title: Task title
        status: Task status (todo, in-progress, done, blocked)
        notes: Task notes
        branch: Branch name if branch-scoped, null otherwise
        createdAt: ISO 8601 timestamp when task was created
        updatedAt: ISO 8601 timestamp when task was last updated
    """
    id: str = Field(..., serialization_alias="id")
    projectId: str = Field(..., serialization_alias="projectId")
    title: str = Field(..., serialization_alias="title")
    status: str = Field(..., serialization_alias="status")
    notes: Optional[str] = Field(None, serialization_alias="notes")
    branch: Optional[str] = Field(None, serialization_alias="branch")
    createdAt: str = Field(..., serialization_alias="createdAt")
    updatedAt: str = Field(..., serialization_alias="updatedAt")


class TaskList(BaseModel):
    """
    TaskList
    ========
    List of tasks with summary information.
    
    Args:
        tasks: List of tasks
        total: Total number of tasks
        byStatus: Count of tasks by status
    """
    tasks: list[TaskResult] = Field(default_factory=list, serialization_alias="tasks")
    total: int = Field(..., serialization_alias="total")
    byStatus: dict[str, int] = Field(default_factory=dict, serialization_alias="byStatus")


class DecisionResult(BaseModel):
    """
    DecisionResult
    ==============
    Information about a decision.
    
    Args:
        id: Unique decision identifier
        projectId: Associated project ID
        title: Decision title
        rationale: Decision rationale
        branch: Branch name if branch-scoped, null otherwise
        createdAt: ISO 8601 timestamp when decision was created
    """
    id: str = Field(..., serialization_alias="id")
    projectId: str = Field(..., serialization_alias="projectId")
    title: str = Field(..., serialization_alias="title")
    rationale: str = Field(..., serialization_alias="rationale")
    branch: Optional[str] = Field(None, serialization_alias="branch")
    createdAt: str = Field(..., serialization_alias="createdAt")


class SessionInfo(BaseModel):
    """
    SessionInfo
    ==========
    Information about a session.
    
    Args:
        sessionId: Unique session identifier
        projectId: Associated project ID
        branch: Associated branch
        summary: Session summary
        createdAt: ISO 8601 timestamp
        source: Session source (ai, git-commit)
        sha: Git commit SHA if source is git-commit
    """
    sessionId: str = Field(..., serialization_alias="sessionId")
    projectId: str = Field(..., serialization_alias="projectId")
    branch: str = Field(..., serialization_alias="branch")
    summary: str = Field(..., serialization_alias="summary")
    createdAt: str = Field(..., serialization_alias="createdAt")
    source: str = Field(..., serialization_alias="source")
    sha: Optional[str] = Field(None, serialization_alias="sha")


class SessionList(BaseModel):
    """
    SessionList
    ==========
    List of sessions with summary information.
    
    Args:
        sessions: List of sessions
        total: Total number of sessions
    """
    sessions: list[SessionInfo] = Field(default_factory=list, serialization_alias="sessions")
    total: int = Field(..., serialization_alias="total")