#!/usr/bin/env python

import curses, curses.textpad
import re
import string
import getpass
import psycopg
import argparse
import collections

from curseslist import *
import units

class Colors:
    ITEM = 2
    TAG = 5
    RECIPE = 4
    TYPE = 3

def dialog(question):
    margin = 4
    dims = (6, curses.COLS - margin * 2)
    outer = curses.newwin(*dims, 3, margin)
    curses.textpad.rectangle(outer, 0, 0, dims[0]-2, dims[1]-1)
    outer.addstr(1, 1, question)
    outer.addstr(3, 1, '>')
    outer.refresh()
    inner = curses.newwin(1, dims[1]-4, 6, margin + 3)
    box = curses.textpad.Textbox(inner)
    box.edit()
    return box.gather()

def ask_split(item, count):
    english = units.to_minecraft(count)
    split = dialog(f'Split {count} ({english}) {item} at:')
    try:
        split = int(split)
        if split > 0 and split < count:
            return split
    except:
        pass

def edit_plan(name, value = None):
    margin = 2
    dims = (curses.LINES - margin * 2, curses.COLS - margin * 2)
    outer = curses.newwin(*dims, margin, margin)
    curses.textpad.rectangle(outer, 0, 0, dims[0]-2, dims[1]-1)
    outer.addstr(1, 1, f'Editing list of items for plan "{name}"')
    outer.addstr(2, 1, "Each line is of the form '<amount> <item>'")
    outer.addstr(3, 1, f'  {'-'*(dims[1]-6)}  ')
    outer.refresh()
    inner = curses.newwin(dims[0]-6, dims[1]-2, margin + 4, margin + 1)
    box = curses.textpad.Textbox(inner)
    box.edit()
    plan = box.gather()
    def parse_item(line):
        line = line.strip()
        total = 0
        running = 1
        item = ''
        for word in line.split(' '):
            try:
                num = int(word)
                total += running
                running = num
            except:
                if ':' in word:
                    item = word
                elif re.match('.*c.*s.*b.*', word):
                    running *= 27 * 27 * 64
                elif re.match('.*s.*b.*', word):
                    running *= 27 * 64
                elif re.match('.*s.*', word):
                    running *= 64
        total += running
        if item and total:
            return (item, total)
    return [*filter(bool, map(parse_item, plan.split('\n')))]

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
        text = [
            (id, curses.color_pair(Colors.RECIPE)),
            (' via ', 0),
            (type, curses.color_pair(Colors.TYPE)),
        ]
        if len(self.choices) == 1:
            return [('[', 0), *text, (']', 0)]
        else:
            return [('< [', 0), *text, ('] >', 0)]
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
        text = [(item, curses.color_pair(Colors.ITEM))]
        if len(self.choices) == 1:
            return text
        else:
            return [('< ', 0), *text, (' >', 0)]
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
        self.title = [
            (f'{count} ({english}) ', 0),
            (f'{item}', curses.color_pair(
                Colors.TAG if item.startswith('#') else Colors.ITEM
            ))
        ]
        self.split = None
    def input(self, input):
        if input == 's':
            if self.split:
                self.split = None
            else:
                # todo - ask where to split
                where = ask_split(self.item, self.count)
                if where:
                    self.split = [where, self.count-where]
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

class PlanNode(MinecraftNode):
    def __init__(self, cur, name):
        super().__init__()
        self.cur = cur
        self.name = name
        cur.execute('''
            SELECT item, count FROM plan_items
            WHERE plan = %s
            ORDER BY item
        ''', (name,))
        self.items = cur.fetchall()
        self.title = f'Plan "{name}"'
    def get_children(self):
        return [
            ItemOrTagNode(self.cur, item, count)
            for item, count in self.items
        ]

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

def curse(stdscr, cur, plan = None):
    curses.use_default_colors()
    for i in range(0, curses.COLORS):
        curses.init_pair(i+1, i, -1)
    split = curses.LINES * 2 // 3
    pane_top = curses.newwin(split, curses.COLS, 0, 0)
    pane_bot = curses.newwin(curses.LINES-split-1, curses.COLS, split+1, 0)

    if plan is None:
        plan = dialog('Plan to open:').strip()

    def update_list():
        return List(PlanNode(cur, plan))
    items = update_list()
    def update_reqs():
        return List(RequirementsNode(
            plan,
            *map(collapse, items.root.get_ingredients())
        ))
    reqs = update_reqs()

    # start with focus on top pane
    focus = 0

    items.draw(stdscr, focus == 0)
    while True:
        key = stdscr.getkey()
        input = Input.from_key(key) or key
        if input == Input.QUIT:
            break
        elif input == 'r':
            focus = 1-focus
        # due to time constraints, loading and storing
        # plans is very basic and does not do much checking.
        # this can be improved in a later version
        elif input == 'p':
            plan = dialog('Name for new plan:').strip()
            ings = edit_plan(plan)
            ingredients = collapse(ings).items()
            cur.execute('''
                INSERT INTO plan (name)
                VALUES (%s)
            ''', (plan,))
            cur.executemany('''
                INSERT INTO plan_items (plan, count, item)
                VALUES (%s, %s, %s)
            ''', [
                (plan, count, item)
                for item, count in ingredients
            ])
            items = update_list()
        elif input == 'e':
            ingredients = collapse(edit_plan(plan)).items()
            if ingredients:
                cur.execute('''
                    DELETE FROM plan_items
                    WHERE plan = %s
                ''', (plan,))
                cur.executemany('''
                    INSERT INTO plan_items (plan, count, item)
                    VALUES (%s, %s, %s)
                ''', [
                    (plan, count, item)
                    for item, count in ingredients
                ])
                items = update_list()
        elif input == 'o':
            plan = dialog('Open plan:').strip()
            items = update_list()

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
  Space, Enter, Return --    expand or collapse item tree
  H, L, Left, Right    --    cycle recipe or tag item
  S                    --    split or unsplit tag or item
  R                    --    swap focus between plan and summary
  Q                    --    quit
  P                    --    create a new plan
  E                    --    edit the current plan
  O                    --    open a plan
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
    parser.add_argument('-P', '--password',
        help='database password')
    parser.add_argument('-p', '--plan',
        help='plan to open')
    args = parser.parse_args()

    if args.local or args.dbname and ('://' not in args.dbname):
        dbname = args.dbname or input('Database name: ')
        conn = 'dbname='+dbname
        dbargs = {}
        schema = 'minecraft_recipes'
    else:
        user = args.user or input('User: ')
        password = args.password or getpass.getpass()
        conn = args.dbname or 'postgresql://ada.mines.edu/csci403'
        dbargs = {'user':user, 'password':password}
        schema = user
    with psycopg.connect(conn, **dbargs) as conn:
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO {schema};')
            curses.wrapper(curse, cur, plan = args.plan)
        conn.commit()

if __name__ == '__main__':
    main()
