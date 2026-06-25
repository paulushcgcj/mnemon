"""Tests for knowledge graph operations."""

import pytest

from mnemon.core.graph import (
    add_observation,
    add_relation,
    delete_entity,
    delete_observation,
    delete_relation,
    get_entity_by_name,
    get_observations,
    get_relations_for,
    list_entities,
    search_entities,
    upsert_entity,
)


@pytest.mark.asyncio
class TestEntities:
    """Tests for entity operations."""

    async def test_upsert_and_get_entity(self, db, project_id):
        """Test upserting and retrieving entities."""
        name = "TestComponent"
        entity_type = "component"
        importance = 0.8

        await upsert_entity(db, project_id, name, entity_type, importance)

        entity = await get_entity_by_name(db, project_id, name)
        assert entity is not None
        assert entity["name"] == name
        assert entity["entity_type"] == entity_type
        assert entity["importance"] == importance

    async def test_upsert_entity_updates_existing(self, db, project_id):
        """Test that upsert updates existing entity."""
        name = "TestComponent"
        importance1 = 0.5
        importance2 = 0.9

        await upsert_entity(db, project_id, name, "component", importance1)
        await upsert_entity(db, project_id, name, "component", importance2)

        entity = await get_entity_by_name(db, project_id, name)
        assert entity["importance"] == importance2

    async def test_delete_entity(self, db, project_id):
        """Test deleting an entity."""
        name = "ToDelete"

        await upsert_entity(db, project_id, name, "component")

        result = await delete_entity(db, project_id, name)
        assert result is True

        entity = await get_entity_by_name(db, project_id, name)
        assert entity is None

    async def test_list_entities_empty(self, db, project_id):
        """Test listing entities when none exist."""
        entities = await list_entities(db, project_id)
        assert entities == []

    async def test_list_entities_with_filter(self, db, project_id):
        """Test listing entities with type filter."""
        await upsert_entity(db, project_id, "Component1", "component", 0.8)
        await upsert_entity(db, project_id, "Person1", "person", 0.6)
        await upsert_entity(db, project_id, "Component2", "component", 0.7)

        entities = await list_entities(db, project_id, entity_type="component")
        assert len(entities) == 2
        assert all(e["entity_type"] == "component" for e in entities)

    async def test_list_entities_ordered_by_importance(self, db, project_id):
        """Test that entities are ordered by importance descending."""
        await upsert_entity(db, project_id, "Low", "component", 0.3)
        await upsert_entity(db, project_id, "High", "component", 0.9)
        await upsert_entity(db, project_id, "Medium", "component", 0.6)

        entities = await list_entities(db, project_id)
        assert len(entities) == 3
        assert entities[0]["importance"] == 0.9
        assert entities[1]["importance"] == 0.6
        assert entities[2]["importance"] == 0.3

    async def test_entity_scoped_to_project(self, db, project_id):
        """Test that entities are scoped to project."""
        other_project = "other-owner/other-repo"

        # Create both projects first
        from mnemon.core.projects import upsert_project
        await upsert_project(db, other_project)

        await upsert_entity(db, project_id, "Component", "component", 0.8)
        await upsert_entity(db, other_project, "Component", "component", 0.8)

        entity = await get_entity_by_name(db, project_id, "Component")
        assert entity is not None

        entity_other = await get_entity_by_name(db, other_project, "Component")
        assert entity_other is not None

        # Should not find in wrong project
        entity_wrong = await get_entity_by_name(db, "wrong/project", "Component")
        assert entity_wrong is None


@pytest.mark.asyncio
class TestObservations:
    """Tests for observation operations."""

    async def test_add_and_get_observation(self, db, project_id):
        """Test adding and retrieving observations."""
        entity_id = await upsert_entity(db, project_id, "Component", "component")
        content = "This is an observation"

        await add_observation(db, entity_id, content)

        observations = await get_observations(db, entity_id)
        assert len(observations) == 1
        assert observations[0]["content"] == content

    async def test_add_multiple_observations(self, db, project_id):
        """Test adding multiple observations to same entity."""
        entity_id = await upsert_entity(db, project_id, "Component", "component")

        await add_observation(db, entity_id, "First observation")
        await add_observation(db, entity_id, "Second observation")

        observations = await get_observations(db, entity_id)
        assert len(observations) == 2

    async def test_delete_observation(self, db, project_id):
        """Test deleting an observation."""
        entity_id = await upsert_entity(db, project_id, "Component", "component")
        observation_id = await add_observation(db, entity_id, "To delete")

        result = await delete_observation(db, observation_id)
        assert result is True

        observations = await get_observations(db, entity_id)
        assert len(observations) == 0


@pytest.mark.asyncio
class TestRelations:
    """Tests for relation operations."""

    async def test_add_and_get_relation(self, db, project_id):
        """Test adding and retrieving relations."""
        from_id = await upsert_entity(db, project_id, "ComponentA", "component")
        to_id = await upsert_entity(db, project_id, "ComponentB", "component")
        relation = "depends_on"

        await add_relation(db, project_id, from_id, to_id, relation)

        relations = await get_relations_for(db, from_id)
        assert len(relations) == 1
        assert relations[0]["relation"] == relation
        assert relations[0]["direction"] == "out"
        assert relations[0]["other_name"] == "ComponentB"

    async def test_bidirectional_relations(self, db, project_id):
        """Test relations in both directions."""
        from_id = await upsert_entity(db, project_id, "ComponentA", "component")
        to_id = await upsert_entity(db, project_id, "ComponentB", "component")

        await add_relation(db, project_id, from_id, to_id, "depends_on")

        # Check from perspective
        relations_from = await get_relations_for(db, from_id)
        assert len(relations_from) == 1
        assert relations_from[0]["direction"] == "out"

        # Check to perspective
        relations_to = await get_relations_for(db, to_id)
        assert len(relations_to) == 1
        assert relations_to[0]["direction"] == "in"

    async def test_delete_relation(self, db, project_id):
        """Test deleting a relation."""
        from_id = await upsert_entity(db, project_id, "ComponentA", "component")
        to_id = await upsert_entity(db, project_id, "ComponentB", "component")
        relation_id = await add_relation(db, project_id, from_id, to_id, "depends_on")

        result = await delete_relation(db, relation_id)
        assert result is True

        relations = await get_relations_for(db, from_id)
        assert len(relations) == 0


@pytest.mark.asyncio
class TestSearch:
    """Tests for search operations."""

    async def test_search_by_name(self, db, project_id):
        """Test searching entities by name."""
        await upsert_entity(db, project_id, "ImportantComponent", "component", 0.8)
        await upsert_entity(db, project_id, "OtherComponent", "component", 0.5)

        results = await search_entities(db, project_id, "Important")
        assert len(results) >= 1
        assert any(r["name"] == "ImportantComponent" for r in results)

    async def test_search_by_observation(self, db, project_id):
        """Test searching entities by observation content."""
        entity_id = await upsert_entity(db, project_id, "Component", "component", 0.8)
        await add_observation(db, entity_id, "Handles authentication")

        results = await search_entities(db, project_id, "authentication")
        assert len(results) >= 1
        assert any(r["name"] == "Component" for r in results)

    async def test_search_with_type_filter(self, db, project_id):
        """Test searching with entity type filter."""
        await upsert_entity(db, project_id, "Component", "component", 0.8)
        await upsert_entity(db, project_id, "Person", "person", 0.8)

        results = await search_entities(db, project_id, "Component", entity_type="component")
        assert len(results) == 1
        assert results[0]["entity_type"] == "component"

    async def test_search_limit(self, db, project_id):
        """Test that search respects limit."""
        for i in range(10):
            await upsert_entity(db, project_id, f"Component{i}", "component", 0.5)

        results = await search_entities(db, project_id, "Component", limit=5)
        assert len(results) == 5

    async def test_search_empty_result(self, db, project_id):
        """Test search with no matches."""
        results = await search_entities(db, project_id, "NonExistent")
        assert results == []
