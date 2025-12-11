SET search_path TO minecraft_recipes;

\o 'recipe.json';
COPY (
    WITH recipe AS (
        SELECT
            json_object(
                'id': id,
                'type': type,
                'category': category,
                'group': recipe_group,
                'result':
                    json_object(
                        'id': result_item,
                        'count': result_count
                    ),
                'ingredients':
                    json_agg(
                        json_object(
                            'position': position,
                            'item': item,
                            'tag': tag
                        )
                    )
                ) AS obj
        FROM recipe
        JOIN recipe_ingredient ON id = recipe
        GROUP BY id
    )
    SELECT json_agg(obj)
    FROM recipe
) TO STDOUT WITH (FORMAT TEXT);

\o 'tag.json';
COPY (
    WITH tag AS (
        SELECT
            json_object(
                'tag': tag,
                'items': json_agg(item)
            ) AS obj
        FROM item_tag
        GROUP BY tag
    )
    SELECT json_agg(obj)
    FROM tag
) TO STDOUT WITH (FORMAT TEXT);

\o 'item.json';
COPY (
    SELECT json_agg(id)
    FROM item
) TO STDOUT WITH (FORMAT TEXT);

\o
