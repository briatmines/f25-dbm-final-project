-- create the tables used by the app for storing plans

set search_path to minecraft_recipes;

CREATE TABLE IF NOT EXISTS plan (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS plan_items (
	plan TEXT REFERENCES plan(name),
	count INTEGER NOT NULL,
	item TEXT REFERENCES item(id) NOT NULL,
	PRIMARY KEY (plan, item)
);
