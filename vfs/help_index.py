"""Compact shortcut entries, searchable highlights and three-column help rendering."""
from dataclasses import dataclass
import re
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.controls import UIControl, UIContent
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.keys import Keys
from prompt_toolkit.mouse_events import MouseEventType


@dataclass
class HelpEntry:
    key: str
    short: str
    description: str
    section: str = 'Files'
    local: bool = False


def shortcut_key(label):
    """Translate a displayed shortcut into its normal application key."""
    key = {'Space': ' ', 'Enter': 'c-m', 'Tab': 'c-i', 'Esc': 'escape',
           'Backspace': 'c-h'}.get(label, label)
    if key.startswith('Ctrl+'):
        key = 'c-' + key[5:].lower()
    elif key.startswith('Shift+'):
        suffix = key[6:]
        if len(suffix) == 1:
            key = dict(zip('1234567890', '!@#$%^&*()')).get(suffix, suffix.upper())
        else:
            key = 's-' + suffix.lower()
    elif len(key) > 1:
        key = key.lower()
    try:
        return Keys(key)
    except ValueError:
        return key if len(key) == 1 else None


def help_entries(lines, strip):
    entries, notes = [], []
    section, active = '', None
    for raw in lines:
        text = strip(raw).strip()
        if not text:
            continue
        if raw.startswith('[bold]'):
            section, active = text, None
            continue
        match = re.match(r'^\[#ff8800\](.*?)\[/#ff8800\](.*)', raw)
        if match and ':' in strip(match[2]):
            key = strip(match[1])
            description = strip(match[2]).split(':', 1)[1].strip()
        elif text.startswith('Ctrl+') and ':' in text:
            key, description = text.split(':', 1)
        elif text.startswith('Shift+Left / Right:'):
            key, description = 'Shift+Left/Right', 'Pan filenames one character; Shift+Home/End moves to the beginning/end'
        elif text.startswith('Media quick view:'):
            key, description = 'p', text.split(':', 1)[1].strip()
        else:
            if active is not None:
                entries[active].description += '\n' + text
            else:
                notes.append((section + ': ' if section else '') + text)
            continue
        short = re.split(r';| · |\(', description, maxsplit=1)[0].strip()
        short = re.sub(r'^(Toggle|Cycle|Independently)\s+', '', short, flags=re.I)
        entries.append(HelpEntry(key.strip(), short, '\n'.join(filter(None, (section, text))), section or 'Files'))
        active = len(entries) - 1
    if entries:
        # List independent bindings separately, keeping the full original
        # explanation available in the description panel.
        scanner = any(strip(line) == 'Scanning' for line in lines)
        short_names = {'b': 'Bookmark on/off', 'j': 'Open bookmarks', 'u': 'Expand/collapse',
                       'o': 'One/all levels', 'Ctrl+D': 'Trash DB entry', 'D': 'Database trash',
                       'Ctrl+P': 'Pause/resume scan', 'Ctrl+K': 'Stop scanning',
                       'Ctrl+E': 'Convert video', 'Q': 'Conversion queue',
                       'Space': 'Mark folder', 'Insert': 'Mark and move', '*': 'Invert marks',
                       '1': 'Lite scan on/off', '2': 'Verify on/off', '3': 'Heavy scan on/off'}
        expanded = []
        for entry in entries:
            # These labels abbreviate shared modifiers and parenthesized aliases;
            # splitting on '/' alone would produce 'PageDown)' and bare 'End'.
            aliases = {
                'Shift+Home / End (or Shift+PageUp / PageDown)':
                    ('Shift+Home', 'Shift+End', 'Shift+PageUp', 'Shift+PageDown'),
                'Shift+Left / Right': ('Shift+Left', 'Shift+Right'),
                'Shift+Left/Right': ('Shift+Left', 'Shift+Right'),
            }
            for key in aliases.get(entry.key, re.split(r'\s+/\s+', entry.key)):
                expanded.append(HelpEntry(key, short_names.get(key, entry.short), entry.description, entry.section))
        entries = expanded
        if not scanner:
            entries += [HelpEntry(key, short, description) for key, short, description in (
                ('G', 'Thumbnail order', 'G: Cycle page/selection-priority thumbnail generation.'),
                ('k', 'Clear folder cache', 'k: Clear thumbnails for the current directory subtree.'),
                ('K', 'Clear all cache', 'K: Clear all thumbnail caches.'),
                ('+', 'Grow thumbnails', '+ or =: Increase thumbnail display height.'),
                ('🔊/🔇', 'Mute preview', 'Click the speaker button to mute/unmute preview audio. Exports are unaffected.'))]
        else:
            entries += [HelpEntry('Ctrl+P', 'Pause/resume scan', 'Ctrl+P: Pause/resume background scanning.'),
                        HelpEntry('Ctrl+K', 'Stop scanning', 'Ctrl+K: Stop workers and save scan progress.')]
        if scanner:
            entries += [HelpEntry('!', 'Lite from cursor', '!: Start Lite from the selected bucket (Shift+1).'),
                        HelpEntry('@', 'Verify from cursor', '@: Start metadata verification from the selected bucket (Shift+2).'),
                        HelpEntry('#', 'Heavy from cursor', '#: Start checksum work from the selected bucket (Shift+3).')]
        entries += [HelpEntry(alias, short, description, 'Help', local=True) for key, short, description in (
            ('Up / Down', 'Previous/next help entry', 'Up/Down: previous/next entry, down each column then to the next column top. Past the last/first entry wraps to the first/last.'),
            ('Left / Right', 'Previous/next help column', 'Left/Right: Move to the previous/next populated column at the same row, or the nearest shortcut when that row is a heading or blank. Wrap between the outer columns.'),
            ('Home / End', 'First/last help entry', 'Home/End: Select the first/last help shortcut and scroll it into view.'),
            ('PageUp / PageDown', 'Top/bottom of current column', 'PageUp/PageDown: Jump to the first/last shortcut in the current column, skipping headings and blanks. Home/End jump to the first/last shortcut across all columns.'),
            ('Tab / Shift+Tab', 'Focus help controls', 'Tab/Shift+Tab: Move focus between shortcut index, description, search and Close.'),
            ('Enter', 'Run selected shortcut', 'Enter: Apply the selected shortcut in its original view, including from search.'),
        ) for alias in re.split(r'\s+/\s+', key)]
        if notes:
            entries.append(HelpEntry('Info', 'Legend and notes', '\n'.join(notes)))
        entries.append(HelpEntry('/', 'Search shortcuts',
            '/: Focus the search field. Type to filter keys and descriptions.\n'
            'Up/Down browse matches; Enter runs the selected shortcut. Esc leaves search, then closes help.',
            'Help', local=True))
    if entries:
        # Keep related controls together without changing their descriptions.
        groups = {}
        for entry in entries:
            if not scanner:
                entry.section = ('Scan view' if entry.key in ('s', 'Ctrl+P', 'Ctrl+K', 'Ctrl+S', 'Shift+R') else
                                 'Cache' if entry.key in ('k', 'K', 'G') else
                                 'Media' if entry.key in ('p', 'g', 'y', 'i', '+', '🔊/🔇') else
                                 'Conversion' if entry.key in ('Ctrl+E', 'Q') else
                                 'Bookmarks and history' if entry.key in ('b', 'j', 'l') else
                                 'Help' if entry.key in ('h', '/', 'Info') else
                                 entry.section if entry.section not in ('Shortcuts', '') else 'Files')
            elif entry.key in ('Ctrl+P', 'Ctrl+K', '!', '@', '#'):
                entry.section = 'Scanning'
            elif entry.key in ('/', 'Info'):
                entry.section = 'Help'
            groups.setdefault(entry.section, []).append(entry)
        entries = [entry for group in groups.values() for entry in group]
    return entries


def highlighted(text, query, style=''):
    if not query:
        return [(style, text)]
    fragments, offset = [], 0
    for match in re.finditer(re.escape(query), text, re.I):
        fragments.append((style, text[offset:match.start()]))
        fragments.append((style + ' class:literal bg:#ffff00 fg:#000000 bold', match[0]))
        offset = match.end()
    fragments.append((style, text[offset:]))
    return fragments


class HelpSearchLexer(Lexer):
    def __init__(self, view):
        self.view = view

    def lex_document(self, document):
        lines = document.lines
        return lambda index: highlighted(lines[index] if index < len(lines) else '', self.view.query)


class HelpIndexControl(UIControl):
    def __init__(self, view):
        self.view = view
        self.widths = [1, 1, 1]
        self.column_height = 1

    def is_focusable(self):
        return True

    def layout_rows(self):
        cells, positions = [], {}
        section = None
        for index, entry in enumerate(self.view.filtered):
            if entry.section != section:
                section = entry.section
                cells.append(section)
            cells.append(index)
        # Keep one continuous column-major layout under the shared scrollbar.
        # Long columns scroll fully before reading continues in the next column.
        limit = max(self.column_height, (len(cells) + 2) // 3)
        rows = []
        for offset, cell in enumerate(cells):
            column, y = divmod(offset, limit)
            while len(rows) <= y:
                rows.append([-1, -1, -1])
            rows[y][column] = cell
            if isinstance(cell, int):
                positions[cell] = (y + 1, column)
        return [tuple(row) for row in rows] or [()], positions

    def create_content(self, width, height):
        from prompt_toolkit.utils import get_cwidth
        available = max(3, width - 4)
        self.widths = [available // 3 + int(column < available % 3) for column in range(3)]
        self.column_height = max(1, height - 2)
        entries = self.view.filtered
        display_rows, positions = self.layout_rows()
        rows = len(display_rows)
        def border(left, join, right):
            return [('class:frame.border', left + join.join('─' * value for value in self.widths) + right)]
        def clip(text, size):
            result, used = '', 0
            for char in text:
                count = get_cwidth(char)
                if used + count > size:
                    break
                result += char
                used += count
            return result + ' ' * max(0, size - used)
        def line(y):
            if y == 0:
                return border('┌', '┬', '┐')
            if y == rows + 1:
                return border('└', '┴', '┘')
            row = display_rows[y - 1]
            fragments = [('class:frame.border', '│')]
            for column, cell_width in enumerate(self.widths):
                index = row[column] if column < len(row) else -1
                style = 'bg:#00ffff fg:#000000' if index == self.view.index else ''
                if isinstance(index, str):
                    fragments += highlighted(clip(' ' + index, cell_width), self.view.query,
                                             'class:literal fg:#ffff00 bold')
                elif 0 <= index < len(entries):
                    entry = entries[index]
                    key_width = min(12, max(1, cell_width // 3))
                    fragments += highlighted(clip(entry.key, key_width), self.view.query,
                                             style + (' bold' if style else ' fg:#ff8800'))
                    fragments.append((style, ' '))
                    fragments += highlighted(clip(entry.short, max(0, cell_width - key_width - 1)), self.view.query, style)
                else:
                    fragments.append((style, clip('No matches' if not entries and column == 0 else '', cell_width)))
                fragments.append(('class:frame.border', '│'))
            return fragments
        cursor_y, column = positions.get(self.view.index, (1, 0))
        x = 1 + sum(self.widths[:column]) + column
        return UIContent(get_line=line, line_count=rows + 2,
                         cursor_position=Point(x, cursor_y), show_cursor=False)

    def mouse_handler(self, event):
        if event.event_type == MouseEventType.SCROLL_UP:
            self.view.move(-3)
        elif event.event_type == MouseEventType.SCROLL_DOWN:
            self.view.move(3)
        elif event.event_type == MouseEventType.MOUSE_UP:
            x, column = event.position.x - 1, 0
            for size in self.widths[:-1]:
                if x < size + 1:
                    break
                x -= size + 1
                column += 1
            rows, _ = self.layout_rows()
            y = event.position.y - 1
            if 0 <= y < len(rows) and column < len(rows[y]) and isinstance(rows[y][column], int) and rows[y][column] >= 0:
                self.view.select(rows[y][column])
                self.view.browser.app.layout.focus(self)
        else:
            return NotImplemented
