import curses

class Input:
    UP = 'UP'
    DOWN = 'DOWN'
    LEFT = 'LEFT'
    RIGHT = 'RIGHT'
    SELECT = 'SELECT'
    def from_key(letter):
        if letter in ('k', curses.KEY_UP):
            return Input.UP
        elif letter in ('j', curses.KEY_DOWN):
            return Input.DOWN
        elif letter in ('h', curses.KEY_LEFT):
            return Input.LEFT
        elif letter in ('l', curses.KEY_RIGHT):
            return Input.RIGHT
        elif letter in (curses.KEY_ENTER, ' ', '\n'):
            return Input.SELECT

class List:
    def __init__(self, root):
        self.root = root
        self.items = list(self.root)
        self.cursor = 0
        self.scroll = 0
    def scroll_to(self, height, line):
        if line < self.scroll:
            self.scroll = line
        elif line >= (self.scroll + height):
            self.scroll = line - height + 1
    def input(self, window, input):
        if input in (Input.UP, Input.DOWN):
            self.cursor = (
                self.cursor
                + (input == Input.DOWN)
                - (input == Input.UP)
            )
            self.cursor = max(0, min(self.cursor, len(self.items)-1))
        else:
            _, item = self.items[self.cursor]
            if input == Input.SELECT:
                item.toggle()
                height, _ = window.getmaxyx()
                self.scroll_to(height,
                    self.cursor - 1 + sum(1 for _ in item))
                self.scroll_to(height, self.cursor)
            else:
                item.input(input)
            self.items = list(self.root)
    def draw(self, window, focused):
        height, _ = window.getmaxyx()
        self.scroll_to(height, self.cursor)
        window.clear()
        for i, (level, item) in enumerate(
            self.items[self.scroll : self.scroll+height]
        ):
            form = (
                curses.A_REVERSE
                if i + self.scroll == self.cursor and focused
                else curses.A_NORMAL
            )
            window.addstr(i, 2 * level, item.get_title(), form)

class ListItem:
    def __init__(self):
        self.expanded = False
        self.children = None
    def toggle(self):
        self.expanded = not self.expanded
    def input(self, input):
        pass
    def get_children(self):
        return []
    def update_children(self):
        if self.children is None:
            self.children = self.get_children()
    def get_title(self):
        return self.title
    def __iter__(self):
        yield (0, self)
        if self.expanded:
            self.update_children()
            for child in self.children:
                for (level, item) in child:
                    yield (level + 1, item)
