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
        children = self.get_children()
        make, left = [], []
        for child in children:
            smake, sleft = child.get_ingredients()
            make, left = make + smake, left + sleft
        return make, left

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
        else:
            return super().get_ingredients()

def curse(stdscr, cur):
    items = List(ItemOrTagNode(cur, 'minecraft:sticky_piston', 100))
    items.draw(stdscr)
    while True:
        key = stdscr.getkey()
        input = Input.from_key(key) or key
        if input == 'q':
            break
        items.input(stdscr, input)
        stdscr.clear()
        items.draw(stdscr)
        stdscr.refresh()

def main():
    parser = argparse.ArgumentParser(
        prog = 'recipe-browse.py',
        description = 'Browse and plan Minecraft recipes'
    );
    parser.add_argument('-l', '--local',
        help='connect to local PostgreSQL db',
        action='store_true');
    args = parser.parse_args()

    if args.local:
        dbname = input('Database name: ')
        conn = 'dbname='+dbname
        args = {}
        schema = 'minecraft_recipes'
    else:
        user = input('User: ')
        password = getpass.getpass()
        conn = 'postgresql://ada.mines.edu/csci403'
        args = {'user':user, 'password':password}
        schema = user
    with psycopg.connect(conn, **args) as conn:
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO {schema};')
            curses.wrapper(curse, cur)

if __name__ == '__main__':
    main()
