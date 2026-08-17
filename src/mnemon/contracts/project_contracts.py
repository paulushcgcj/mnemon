"""Pydantic models for project-related JSON output."""

from typing import Any

from pydantic import BaseModel, Field


class ProjectInfo(BaseModel):
    """Information about a single project.

    Attributes:
        id: The project ID (owner/repo).
        parentId: The parent project ID, or None for root projects.
        context: Optional project context text.
        entityCount: Number of knowledge graph entities for this project.
        decisionCount: Number of decisions recorded for this project.
        taskCount: Number of tasks recorded for this project.
        createdAt: Timestamp when the project was created.
        updatedAt: Timestamp when the project was last updated.
    """

    id: str = Field(..., serialization_alias="id")
    parentId: str | None = Field(None, serialization_alias="parentId")
    context: str | None = Field(None, serialization_alias="context")
    entityCount: int = Field(0, serialization_alias="entityCount")
    decisionCount: int = Field(0, serialization_alias="decisionCount")
    taskCount: int = Field(0, serialization_alias="taskCount")
    createdAt: str = Field(..., serialization_alias="createdAt")
    updatedAt: str = Field(..., serialization_alias="updatedAt")


class ProjectList(BaseModel):
    """List of all projects in the memory store.

    Attributes:
        projects: List of project information entries.
        total: Total number of projects.
    """

    projects: list[ProjectInfo] = Field(default_factory=list, serialization_alias="projects")
    total: int = Field(..., serialization_alias="total")


class ProjectContext(BaseModel):
    """Full context for a project including all related data.

    Attributes:
        project: The project information.
        branches: List of branch state dictionaries for the project.
        decisions: List of decision dictionaries for the project.
        tasks: List of task dictionaries for the project.
        sessions: List of session log dictionaries for the project.
        knowledgeGraph: The project's knowledge graph data.
    """

    project: ProjectInfo = Field(..., serialization_alias="project")
    branches: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="branches")
    decisions: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="decisions")
    tasks: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="tasks")
    sessions: list[dict[str, Any]] = Field(default_factory=list, serialization_alias="sessions")
    knowledgeGraph: dict[str, Any] = Field(
        default_factory=dict, serialization_alias="knowledgeGraph"
    )
