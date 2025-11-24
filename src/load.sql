SET search_path TO minecraft_recipes;


DROP TABLE IF EXISTS recipes_json;
CREATE TABLE recipes_json (name TEXT, json JSON);
\copy recipes_json from './mc-data/recipes.csv' (FORMAT CSV);

DROP TABLE IF EXISTS tags_json;
CREATE TABLE tags_json(name TEXT, json JSON);
\copy tags_json from './mc-data/tags.csv' (FORMAT CSV);


DROP TABLE IF EXISTS category;
CREATE TABLE category (id TEXT PRIMARY KEY);
INSERT INTO category (
    SELECT id FROM (
        SELECT DISTINCT (json ->> 'category') AS id
        FROM recipes_json
    ) WHERE id IS NOT NULL
);

DROP TABLE IF EXISTS recipe_group;
CREATE TABLE recipe_group (id TEXT PRIMARY KEY);
INSERT INTO recipe_group (
    SELECT id FROM (
        SELECT DISTINCT (json ->> 'group') AS id
        FROM recipes_json
    ) WHERE id IS NOT NULL
);

DROP TABLE IF EXISTS tag;
CREATE TABLE tag (id TEXT PRIMARY KEY);
INSERT INTO tag (
    SELECT name FROM tags_json
);
