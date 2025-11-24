SET search_path TO minecraft_recipes;


DROP TABLE IF EXISTS recipes_json;
CREATE TABLE recipes_json (name TEXT, json JSON);

DROP TABLE IF EXISTS tags_json;
CREATE TABLE tags_json(name TEXT, json JSON);

\copy recipes_json from './mc-data/recipes.csv' (FORMAT CSV);
\copy tags_json from './mc-data/tags.csv' (FORMAT CSV);
