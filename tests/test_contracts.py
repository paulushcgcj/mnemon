"""Tests for public JSON contract models and registry helpers."""

import pytest

from mnemon.contracts import (
    DecisionResult,
    EntityResult,
    EntitySearchResult,
    GraphEntity,
    GraphPruneResult,
    GraphRelation,
    GraphResult,
    KnowledgeGraph,
    ObservationResult,
    ProjectContext,
    ProjectInfo,
    ProjectList,
    SessionInfo,
    SessionList,
    TaskList,
    TaskResult,
)
from mnemon.contracts.registry import get_all_contracts, get_contract, list_contracts

NOW = "2024-01-01T00:00:00Z"


def graph_entity() -> GraphEntity:
    return GraphEntity(
        id="entity-1",
        projectId="owner/repo",
        name="Api",
        entityType="component",
        importance=0.9,
        createdAt=NOW,
        updatedAt=NOW,
        observations=["Handles requests"],
        relations=[{"relation": "uses"}],
    )


def project_info() -> ProjectInfo:
    return ProjectInfo(
        id="owner/repo",
        parentId="owner/root",
        context="Project context",
        entityCount=1,
        decisionCount=2,
        taskCount=3,
        createdAt=NOW,
        updatedAt=NOW,
    )


def test_graph_contract_aliases_and_defaults():
    entity = graph_entity()
    relation = GraphRelation(
        id="rel-1",
        projectId="owner/repo",
        fromId="entity-1",
        toId="entity-2",
        relation="uses",
        createdAt=NOW,
    )
    graph = GraphResult(
        projectId="owner/repo",
        branch="main",
        entities=[entity],
        relations=[relation],
        entityCount=1,
        relationCount=1,
    )
    search = EntitySearchResult(query="Api", projectId="owner/repo", results=[entity], total=1, limit=10)
    prune = GraphPruneResult(
        projectId="owner/repo",
        belowImportance=0.2,
        olderThanDays=30,
        dryRun=True,
        candidates=[{"name": "OldLow"}],
    )

    dumped = graph.model_dump(by_alias=True)
    assert dumped["projectId"] == "owner/repo"
    assert dumped["entities"][0]["entityType"] == "component"
    assert dumped["relations"][0]["fromId"] == "entity-1"
    assert search.model_dump(by_alias=True)["results"][0]["createdAt"] == NOW
    assert prune.model_dump(by_alias=True)["prunedCount"] == 0


def test_memory_contract_aliases_and_defaults():
    entity = EntityResult(
        id="entity-1",
        projectId="owner/repo",
        name="Api",
        entityType="component",
        importance=0.9,
        createdAt=NOW,
        updatedAt=NOW,
    )
    graph = KnowledgeGraph(projectId="owner/repo", branch=None, entities=[entity], totalCount=1)
    observation = ObservationResult(
        id="obs-1",
        entityId="entity-1",
        content="Fact",
        source="ai",
        createdAt=NOW,
    )
    task = TaskResult(
        id="task-1",
        projectId="owner/repo",
        title="Do thing",
        status="todo",
        createdAt=NOW,
        updatedAt=NOW,
    )
    decision = DecisionResult(
        id="decision-1",
        projectId="owner/repo",
        title="Decision",
        rationale="Because",
        createdAt=NOW,
    )
    session = SessionInfo(
        sessionId="session-1",
        projectId="owner/repo",
        branch="main",
        summary="Worked",
        createdAt=NOW,
        source="ai",
    )

    assert graph.model_dump(by_alias=True)["totalCount"] == 1
    assert observation.model_dump(by_alias=True)["entityId"] == "entity-1"
    assert TaskList(tasks=[task], total=1, byStatus={"todo": 1}).model_dump(by_alias=True)["byStatus"]["todo"] == 1
    assert decision.model_dump(by_alias=True)["projectId"] == "owner/repo"
    assert SessionList(sessions=[session], total=1).model_dump(by_alias=True)["sessions"][0]["sessionId"] == "session-1"


def test_project_contract_aliases_and_registry():
    project = project_info()
    project_list = ProjectList(projects=[project], total=1)
    context = ProjectContext(
        project=project,
        branches=[{"branch": "main"}],
        decisions=[{"title": "Decision"}],
        tasks=[{"title": "Task"}],
        sessions=[{"summary": "Session"}],
        knowledgeGraph={"entities": []},
    )

    assert project.model_dump(by_alias=True)["parentId"] == "owner/root"
    assert project_list.model_dump(by_alias=True)["projects"][0]["entityCount"] == 1
    assert context.model_dump(by_alias=True)["knowledgeGraph"] == {"entities": []}

    assert get_contract("graph", "GraphEntity") is GraphEntity
    assert "TaskResult" in list_contracts("memory")
    assert "ProjectInfo" in list_contracts()
    all_contracts = get_all_contracts()
    assert all_contracts["project"]["ProjectList"] is ProjectList
    all_contracts["project"] = {}
    assert get_contract("project", "ProjectList") is ProjectList

    with pytest.raises(KeyError, match="Available categories"):
        get_contract("missing", "GraphEntity")
    with pytest.raises(KeyError, match="Available categories"):
        get_contract("graph", "Missing")
    with pytest.raises(KeyError, match="Category 'missing'"):
        list_contracts("missing")

