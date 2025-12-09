#!/usr/bin/env python

import curses
import getpass
import psycopg
import argparse
import collections

from curseslist import *
import units

class MinecraftNode(ListItem):
    def get_ingredients(self):
        self.update_children()
        reqs, left = [], []
        for child in self.children:
            reqs_child, left_child = child.get_ingredients()
            reqs, left = reqs + reqs_child, left + left_child
        return reqs, left

class ChooserNode(MinecraftNode):
    def __init__(self):
        super().__init__()
        self.choices = []
        self.select = 0
    def input(self, input):
        if len(self.choices) > 1 and input in (Input.LEFT, Input.RIGHT):
            dir = (input == Input.RIGHT) - (input == Input.LEFT)
            self.select += dir
            self.select %= len(self.choices)
            self.children = None
    def get_chosen(self):
        if len(self.choices):
            return self.choices[self.select]

class ItemRecipeNode(ChooserNode):
    def __init__(self, cur, item, count):
        super().__init__()
        self.cur = cur
        self.item = item
        self.count = count
        cur.execute('''
            SELECT id, type, result_count
            FROM recipe
            WHERE result_item = %s
            ORDER BY id
        ''', (item,))
        self.choices = cur.fetchall()
    def get_title(self):
        recipe = self.get_chosen()
        if recipe is None:
            return '(no recipes)'
        id, type, _ = recipe
        if len(self.choices) == 1:
            return f'[{id} via {type}]'
        else:
            return f'< [{id} via {type}] >'
    def get_children(self):
        recipe = self.get_chosen()
        if recipe is None:
            return []
        id, _, result_count = recipe
        require = (self.count + result_count - 1) // result_count
        self.cur.execute('''
            SELECT item, tag
            FROM recipe_ingredient
            WHERE recipe = %s
            ORDER BY position
        ''', (id,))
        self.ingredients = collections.Counter(self.cur.fetchall())
        return [
            ItemOrTagNode(self.cur, item or tag, count*require)
            for (item, tag), count in self.ingredients.items()
        ]
    def get_ingredients(self):
        recipe = self.get_chosen()
        if recipe is None:
            return ([(self.item, self.count)], [])
        _, _, result_count = recipe
        reqs, left = super().get_ingredients()
        remainder = (-self.count) % result_count
        if remainder:
            left.append((self.item, remainder))
        return (reqs, left)

class TagChooseItemNode(ChooserNode):
    def __init__(self, cur, tag, count):
        super().__init__()
        self.cur = cur
        self.tag = tag
        self.count = count
        cur.execute('''
            SELECT item
            FROM item_tag
            WHERE tag = %s
            ORDER BY item
        ''', (tag,))
        self.choices = [item for (item,) in cur.fetchall()]
    def get_title(self):
        item = self.get_chosen()
        if item is None:
            return '(no items)'
        if len(self.choices) == 1:
            return f'{item}'
        else:
            return f'< {item} >'
    def get_children(self):
        item = self.get_chosen()
        if item is None:
            return []
        return [ ItemOrTagNode(self.cur, item, self.count) ]

class ItemOrTagNode(MinecraftNode):
    def __init__(self, cur, item, count):
        super().__init__()
        self.cur = cur
        self.item = item
        self.count = count
        english = units.to_minecraft(count)
        self.title = f'{count} ({english}) {item}'
        self.split = None
    def input(self, input):
        if input == 's':
            if self.split:
                self.split = None
            else:
                # todo - ask where to split
                self.split = [self.count//2, self.count-self.count//2]
                self.expanded = True
            self.children = None
    def get_children(self):
        if self.split:
            return [
                ItemOrTagNode(self.cur, self.item, count)
                for count in self.split
            ]
        else:
            if self.item.startswith('#'):
                return [ TagChooseItemNode(self.cur, self.item, self.count) ]
            else:
                return [ ItemRecipeNode(self.cur, self.item, self.count) ]
    def get_ingredients(self):
        if not self.expanded:
            return ([(self.item, self.count)], [])
        return super().get_ingredients()

def collapse(requirements):
    items = {}
    for item, count in requirements:
        if item not in items:
            items[item] = 0
        items[item] += count
    return items

class SimpleItemNode(ListItem):
    def __init__(self, item, count):
        super().__init__()
        english = units.to_minecraft(count)
        self.title = f'{count} ({english}) {item}'

class ItemListNode(ListItem):
    def __init__(self, title, items):
        super().__init__()
        self.title = title
        self.items = items
        self.expanded = True
    def get_children(self):
        return [
            SimpleItemNode(item, count)
            for item, count in sorted(self.items.items())
        ]

class RequirementsNode(ListItem):
    def __init__(self, name, require, leftover):
        super().__init__()
        self.title = f'Items for {name}'
        self.require = require
        self.leftover = leftover
        self.expanded = True
    def get_children(self):
        return [
            ItemListNode('Required items', self.require),
            ItemListNode('Leftover items', self.leftover)
        ]

def curse(stdscr, cur):
    split = curses.LINES * 2 // 3
    pane_top = curses.newwin(split, curses.COLS, 0, 0)
    pane_bot = curses.newwin(curses.LINES-split, curses.COLS, split, 0)

    items = List(ItemOrTagNode(cur, 'minecraft:sticky_piston', 100))
    def update_reqs():
        return List(RequirementsNode(
            '<plan>',
            *map(collapse, items.root.get_ingredients())
        ))
    reqs = update_reqs()

    # start with focus on top pane
    focus = 0

    items.draw(stdscr, focus == 0)
    while True:
        key = stdscr.getkey()
        input = Input.from_key(key) or key
        if input == 'q':
            break
        if input == 'r':
            focus = 1-focus

        if focus == 0:
            items.input(pane_top, input)
            reqs = update_reqs()
        else:
            reqs.input(pane_bot, input)

        pane_top.clear()
        items.draw(pane_top, focus == 0)
        pane_top.refresh()

        pane_bot.clear()
        reqs.draw(pane_bot, focus == 1)
        pane_bot.refresh()

def main():
    parser = argparse.ArgumentParser(
        prog = 'recipe-browse.py',
        description = 'Browse and plan Minecraft recipes',
        epilog = '''
key bindings:
  J, K, Up, Down       --    navigate list
  Space, Enter, Return --    unravel or collapse node
  H, L, Left, Right    --    cycle recipe or tag item
  S                    --    split or unsplit tag or item
  R                    --    swap focus between plan and summary
  Q                    --    quit
        '''.strip(),
        formatter_class = argparse.RawDescriptionHelpFormatter
    );
    parser.add_argument('-l', '--local',
        help='connect to local PostgreSQL db',
        action='store_true');
    parser.add_argument('-d', '--dbname',
        help='database name or url')
    parser.add_argument('-u', '--user',
        help='database username')
    parser.add_argument('--password',
        help='database password')
    args = parser.parse_args()

    if args.local or args.dbname and ('://' not in args.dbname):
        dbname = args.dbname or input('Database name: ')
        conn = 'dbname='+dbname
        args = {}
        schema = 'minecraft_recipes'
    else:
        user = args.user or input('User: ')
        password = args.password or getpass.getpass()
        conn = args.dbname or 'postgresql://ada.mines.edu/csci403'
        args = {'user':user, 'password':password}
        schema = user
    with psycopg.connect(conn, **args) as conn:
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO {schema};')
            curses.wrapper(curse, cur)

if __name__ == '__main__':
    main()
