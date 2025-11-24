SET search_path TO minecraft_recipes;


  -- load raw accumulated json csv files
DROP TABLE IF EXISTS recipes_json;
CREATE TABLE recipes_json (name TEXT, json JSON);
\copy recipes_json from './mc-data/recipes.csv' (FORMAT CSV);

DROP TABLE IF EXISTS tags_json;
CREATE TABLE tags_json(name TEXT, json JSON);
\copy tags_json from './mc-data/tags.csv' (FORMAT CSV);


  -- extract categories
DROP TABLE IF EXISTS category CASCADE;
CREATE TABLE category (id TEXT PRIMARY KEY);
INSERT INTO category (
    SELECT id FROM (
        SELECT DISTINCT (json ->> 'category') AS id
        FROM recipes_json
    ) WHERE id IS NOT NULL
);

  -- extract groups
DROP TABLE IF EXISTS recipe_group CASCADE;
CREATE TABLE recipe_group (id TEXT PRIMARY KEY);
INSERT INTO recipe_group (
    SELECT id FROM (
        SELECT DISTINCT (json ->> 'group') AS id
        FROM recipes_json
    ) WHERE id IS NOT NULL
);

  -- extract tags
DROP TABLE IF EXISTS tag CASCADE;
CREATE TABLE tag (id TEXT PRIMARY KEY);
INSERT INTO tag (
    SELECT name FROM tags_json
);


  -- create item/tag join table
DROP TABLE IF EXISTS item_tag CASCADE;
CREATE TABLE item_tag (
    item TEXT NOT NULL,
    tag  TEXT NOT NULL REFERENCES tag(id),
    PRIMARY KEY (item, tag)
);

WITH RECURSIVE unexpanded_tags AS (
    SELECT name AS tag, json_table.*
    FROM tags_json, JSON_TABLE (json, '$.values[*]' COLUMNS (
        item TEXT PATH '$'
    )) AS json_table
),
expanded_tags AS (
    SELECT *
    FROM unexpanded_tags
    UNION ALL
    SELECT base.tag, sub.item
    FROM expanded_tags base
    JOIN unexpanded_tags sub ON base.item = ('#' || sub.tag)
)
INSERT INTO item_tag (
    SELECT DISTINCT item, tag
    FROM expanded_tags
    WHERE item NOT LIKE '#%'
);
