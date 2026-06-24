-- Multiple entities with relationships
INSERT INTO entities VALUES ('e1', 'test/proj', 'Entity1', 'component', 0.9);
INSERT INTO entities VALUES ('e2', 'test/proj', 'Entity2', 'service', 0.8);
INSERT INTO entities VALUES ('e3', 'test/proj', 'Entity3', 'module', 0.7);
INSERT INTO observations VALUES ('o1', 'e1', 'Observation about Entity1');
INSERT INTO observations VALUES ('o2', 'e2', 'Observation about Entity2');
