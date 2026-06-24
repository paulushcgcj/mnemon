"""
Project Contracts
================
Pydantic models for project-related JSON output.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ProjectInfo(BaseModel):
    """
    ProjectInfo
    ==========
    Information about a single project.
    
    Args:
        id: Project identifier (owner/repo format)
        parentId: Parent project ID if this is a subproject
        context: Global project context/description
        entityCount: Number of entities in the project
        decisionCount: Number of decisions recorded
        taskCount: Number of tasks
        createdAt: ISO 8601 timestamp when project was first recorded
        updatedAt: ISO 8601 timestamp when project was last updated
    """
    id: str = Field(..., serialization_alias="id")
    parentId: Optional[str] = Field(None, serialization_alias="parentId")
    context: Optional[str] = Field(None, serialization_alias="context")
    entityCount: int = Field(0, serialization_alias="entityCount")
    decisionCount: int = Field(0, serialization_alias="decisionCount")
    taskCount: int = Field(0, serialization_alias="taskCount")
    createdAt: str = Field(..., serialization_alias="createdAt")
    updatedAt: str = Field(..., serialization_alias="updatedAt")


class ProjectList(BaseModel):
    """
    ProjectList
    ==========
    List of all projects in the memory store.
    
    Args:
        projects: List of projects
        total: Total number of projects
    """
    projects: list[ProjectInfo] = Field(default_factory=list, serialization_alias="projects")
    total: int = Field(..., serialization_alias="total")


class ProjectContext(BaseModel):
    """
    ProjectContext
    =============
    Full context for a project including all related data.
    
    Args:
        project: Project information
        branches: List of branch states
        decisions: List of decisions
        tasks: List of tasks
        sessions: List of recent sessions
        knowledgeGraph: Knowledge graph for the project
    """
    project: ProjectInfo = Field(..., serialization_alias="project")
    branches: list[dict] = Field(default_factory=list, serialization_alias="branches")
    decisions: list[dict] = Field(default_factory=list, serialization_alias="decisions")
    tasks: list[dict] = Field(default_factory=list, serialization_alias="tasks")
    sessions: list[dict] = Field(default_factory=list, serialization_alias="sessions")
    knowledgeGraph: dict = Field(default_factory=dict, serialization_alias="knowledgeGraph")