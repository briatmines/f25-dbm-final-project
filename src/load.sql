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
    SELECT ('#' || name) FROM tags_json
);


  -- create item/tag join table
DROP TABLE IF EXISTS item_tag CASCADE;
CREATE TABLE item_tag (
    item TEXT NOT NULL,
    tag  TEXT NOT NULL REFERENCES tag(id),
    PRIMARY KEY (item, tag)
);

WITH RECURSIVE unexpanded_tags AS (
    SELECT ('#' || name) AS tag, json_table.*
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
    JOIN unexpanded_tags sub ON base.item = sub.tag
)
INSERT INTO item_tag (
    SELECT DISTINCT item, tag
    FROM expanded_tags
    WHERE item NOT LIKE '#%'
);


  -- create recipe table
DROP TABLE IF EXISTS recipe CASCADE;
CREATE TABLE recipe (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    category TEXT REFERENCES category(id),
    recipe_group TEXT REFERENCES recipe_group(id),
    result_item TEXT NOT NULL,
    result_count SMALLINT NOT NULL
);
INSERT INTO recipe (
    SELECT name AS id, jt.*
    FROM recipes_json, JSON_TABLE(json, '$' COLUMNS (
        type TEXT PATH '$.type',
        category TEXT PATH '$.category',
        recipe_group TEXT PATH '$.group',
        result_item TEXT PATH '$.result.id',
        result_count SMALLINT PATH '$.result.count' DEFAULT 1 ON EMPTY
    )) AS jt
    WHERE type IN (
      'minecraft:crafting_shaped',
      'minecraft:crafting_shapeless',
      'minecraft:crafting_transmute',
      'minecraft:smelting',
      'minecraft:smoking',
      'minecraft:blasting',
      'minecraft:campfire_cooking',
      'minecraft:stonecutting'
    )
);

  -- create ingredient table
DROP TABLE IF EXISTS recipe_ingredient;
CREATE TABLE recipe_ingredient (
    recipe TEXT NOT NULL REFERENCES recipe(id),
    position SMALLINT,
    item TEXT,
    tag TEXT REFERENCES tag(id)
);
WITH ingredient_intermediate AS (
    SELECT name AS recipe, jt.*
    FROM recipes_json, JSON_TABLE(json, '$.ingredients[*]' COLUMNS (
        position FOR ORDINALITY,
        item_or_tag TEXT PATH '$'
    )) as jt
    WHERE json ->> 'type' = 'minecraft:crafting_shapeless'
)
INSERT INTO recipe_ingredient (
    SELECT recipe, position, NULL, item_or_tag
    FROM ingredient_intermediate
    WHERE item_or_tag LIKE '#%'
    UNION
    SELECT recipe, position, item_or_tag, NULL
    FROM ingredient_intermediate
    WHERE item_or_tag NOT LIKE '#%'
);
