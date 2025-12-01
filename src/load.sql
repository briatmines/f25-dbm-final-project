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

DROP TABLE IF EXISTS ingredient_intermediate;
CREATE TEMP TABLE ingredient_intermediate AS (
    SELECT name AS recipe, jt.*
    FROM recipes_json, JSON_TABLE(json, '$.ingredients[*]' COLUMNS (
        position FOR ORDINALITY,
        item_or_tag JSON PATH '$'
    )) as jt
    WHERE json ->> 'type' = 'minecraft:crafting_shapeless'
    UNION ALL
    SELECT name AS recipe, 1 as position, json -> 'ingredient' AS item_or_tag
    FROM recipes_json
    WHERE json ->> 'type' IN (
        'minecraft:smelting',
        'minecraft:smoking',
        'minecraft:blasting',
        'minecraft:campfire_cooking',
        'minecraft:stonecutting'
    )
    UNION ALL
    SELECT name AS recipe, position, json -> key AS item_or_tag
    FROM recipes_json
    CROSS JOIN (VALUES (1, 'input'), (2, 'material')) AS x (position, key)
    WHERE json ->> 'type' = 'minecraft:crafting_transmute'
    UNION ALL
    (
        WITH coords(coord) AS (VALUES (0), (1), (2))
        SELECT
            name AS recipe,
            (cy.coord*3 + cx.coord + 1) AS position,
            json -> 'key' -> (
                substring(
                    (json -> 'pattern' ->> cy.coord)
                    FROM (cx.coord+1) FOR 1
                )
            ) AS item_or_tag
        FROM recipes_json, coords AS cy, coords AS cx
        WHERE json ->> 'type' = 'minecraft:crafting_shaped'
    )
);

  -- sometimes, an ingredient is a list instead of a tag,
  -- so we must create synthetic tags in this case.
DROP TABLE IF EXISTS ingredient_lists;
CREATE TEMP TABLE ingredient_lists (
    id SERIAL,
    list JSONB
);
INSERT INTO ingredient_lists (list) (
    SELECT DISTINCT (item_or_tag::jsonb)
    FROM ingredient_intermediate
    WHERE item_or_tag IS JSON ARRAY
);
INSERT INTO tag (
    SELECT '#synthetic:' || id
    FROM ingredient_lists
);
INSERT INTO item_tag (
    SELECT item, ('#synthetic:' || id) as tag
    FROM ingredient_lists, JSON_TABLE(list, '$[*]' COLUMNS(
        item TEXT PATH '$'
    ))
);
UPDATE ingredient_intermediate
    SET item_or_tag = json_scalar('#synthetic:' || id)
    FROM ingredient_lists
    WHERE item_or_tag::jsonb = ingredient_lists.list;
ALTER TABLE ingredient_intermediate
    ALTER COLUMN item_or_tag
    TYPE TEXT
    USING item_or_tag #>> '{}';

  -- create ingredient table
DROP TABLE IF EXISTS recipe_ingredient;
CREATE TABLE recipe_ingredient (
    recipe TEXT NOT NULL REFERENCES recipe(id),
    position SMALLINT,
    item TEXT,
    tag TEXT REFERENCES tag(id),
    PRIMARY KEY (recipe, position),
    CHECK ((item IS NOT NULL AND tag IS NULL) OR (item IS NULL AND tag IS NOT NULL))
);
INSERT INTO recipe_ingredient (
    SELECT recipe, position, NULL, item_or_tag
    FROM ingredient_intermediate
    WHERE item_or_tag LIKE '#%'
    UNION
    SELECT recipe, position, item_or_tag, NULL
    FROM ingredient_intermediate
    WHERE item_or_tag NOT LIKE '#%'
);
