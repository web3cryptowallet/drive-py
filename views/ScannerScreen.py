"""Live drive map popup. Only visible map rows and 100 detail rows are drawn."""
from dataclasses import asdict, replace
import asyncio
import math
import random
from queue import Empty, Queue
from threading import Event, Thread
import time

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalScroll, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.scroll_view import ScrollView
from textual.geometry import Size
from textual.strip import Strip
from textual.widgets import Button, DataTable, Input, Label, Static

from vfs.scanner import DriveScanner, FileMap, Pagination, ScanStats, ScanControls, ScanEntry, ScanStore
from vfs.utils import format_size
from .HelpScreen import HelpScreen, SCANNER_HELP


STATES = {
    'modified': ('M', '#ff8800', 'modified'),
    'missing': ('U', '#ff0000', 'not found'),
    'new': ('U', '#ffffff', 'undefined / new'),
    'unknown': ('?', '#ffffff', 'unverified'),
    'verified': ('●', 'green', 'verified'),
    'directory': ('D', '#ffffff', 'directories'),
}


class BucketMap(ScrollView, can_focus=True):
    BINDINGS = [(key, f'move({delta})', '') for key, delta in
                [('left', -1), ('right', 1), ('up', -2), ('down', 2)]] + [
                    ('pageup', 'page(-1)', 'Map up'),
                    ('pagedown', 'page(1)', 'Map down')]

    def __init__(self, model):
        super().__init__(id='bucket-map')
        self.model = model
        self.columns = 1
        self.rows = 1
        self.selected = 0
        self.follow_end = False
        self.backgrounds = []
        self.expert_selected = set()
        self.expert_mode = False

    @property
    def cells(self):
        return self.columns * max(1, self.scrollable_content_region.height)

    def sync(self):
        self.columns = max(1, self.scrollable_content_region.width)
        count = len(self.model.buckets)
        self.rows = max(1, math.ceil((count + int(self.follow_end)) / self.columns))
        self.virtual_size = Size(self.columns, self.rows)
        self.selected = count if self.follow_end else max(0, min(self.selected, count - 1))
        if self.follow_end:
            self.reveal_selection()
        self.refresh()

    def watch_scroll_y(self, old_value, new_value):
        super().watch_scroll_y(old_value, new_value)
        if self.is_mounted:
            self.screen.update_stats()

    def reveal_selection(self):
        row = self.selected // self.columns
        height = max(1, self.scrollable_content_region.height)
        if row < self.scroll_y:
            self.scroll_to(y=row, animate=False)
        elif row >= self.scroll_y + height:
            self.scroll_to(y=row - height + 1, animate=False)

    def on_resize(self):
        self.sync()
        self.screen.call_after_refresh(self.screen.fit_map)

    def action_move(self, delta):
        if self.follow_end and delta == 1:
            return
        if self.follow_end:
            self.follow_end = False
        elif delta == 1 and self.selected == max(0, len(self.model.buckets) - 1):
            self.follow_end = True
            self.sync()
            self.screen.selection_changed()
            return
        delta = {-2: -self.columns, 2: self.columns}.get(delta, delta)
        self.selected = max(0, min(len(self.model.buckets) - 1, self.selected + delta))
        self.reveal_selection()
        self.screen.selection_changed()
        self.refresh()

    def action_page(self, direction):
        self.follow_end = False
        self.selected = max(0, min(len(self.model.buckets) - 1,
                                   self.selected + direction * self.columns * max(1, self.scrollable_content_region.height)))
        self.reveal_selection()
        self.screen.selection_changed()
        self.refresh()

    def on_click(self, event):
        x, y = event.offset
        index = (y + int(self.scroll_y)) * self.columns + x
        if 0 <= x < self.columns and 0 <= y < self.rows and index < len(self.model.buckets):
            self.follow_end = False
            self.selected = index
            self.screen.selection_changed()
            self.focus()
            self.refresh()

    def render_line(self, y):
        if y + int(self.scroll_y) >= self.rows:
            return Strip.blank(self.size.width, Style(bgcolor='#000000'))
        segments = []
        now = time.monotonic()
        for column in range(self.columns):
            index = (y + int(self.scroll_y)) * self.columns + column
            symbol, color, background = '·', '#666666', '#000000'
            selected = index == self.selected
            if index < len(self.model.buckets):
                bucket = self.model.buckets[index]
                if index < len(self.backgrounds):
                    background = self.backgrounds[index]
                state = next((key for key in STATES if bucket.counts[key]), 'unknown')
                symbol, color, _ = STATES[state]
                if state == 'unknown' and bucket.counts['unknown'] and bucket.counts['verified']:
                    color = 'green'
                if now - bucket.updated < 1:
                    symbol = ('\\', '|', '/', '-')[int(now * 8) % 4]
                    color = '#ffffff'
                    if not self.expert_mode:
                        background = '#ff0000'
                if index in self.expert_selected:
                    background = '#0000ff'
            elif self.follow_end and index == self.selected:
                symbol, color = '>', '#ffffff'
            segments.append(Segment(symbol, Style(color=color, bgcolor=background,
                                                   underline=selected)))
        return Strip(segments)


class FileDetails(DataTable):
    """Only mount the file rows that fit; page controls expose the remainder."""
    BINDINGS = [('left', 'scroll_left', 'Scroll left'),
                ('right', 'scroll_right', 'Scroll right'),
                ('left_square_bracket', 'directory_scope(-1)', 'Parent scope'),
                ('right_square_bracket', 'directory_scope(1)', 'Deeper scope')]

    def action_directory_scope(self, direction):
        self.screen.action_directory_scope(direction)

    def sync_rows(self, rows):
        keys = [row.key.value for row in self.ordered_rows]
        if keys == [key for key, _, _ in rows]:
            for key, name, size in rows:
                for column, value in zip(self.ordered_columns, (name, size)):
                    if self.get_cell(key, column.key) != value:
                        self.update_cell(key, column.key, value, update_width=True)
            return

        cursor = self.cursor_row
        offset, target = self.scroll_x, self.scroll_target_x
        self.clear()
        for key, name, size in rows:
            self.add_row(name, size, key=key)
        if self.row_count:
            self.move_cursor(row=min(cursor, self.row_count - 1), animate=False, scroll=False)
        # clear() resets horizontal scroll; restore before a frame can draw it.
        self.scroll_x, self.scroll_target_x = offset, target

    def action_cursor_up(self):
        if self.row_count and self.cursor_row == 0 and self.screen.pagination.page > 1:
            self.screen.set_page(self.screen.pagination.page - 1)
            self.move_cursor(row=max(0, self.row_count - 1), animate=False, scroll=False)
        else:
            super().action_cursor_up()

    def action_cursor_down(self):
        if (self.row_count and self.cursor_row == self.row_count - 1 and
                self.screen.pagination.page < self.screen.pages):
            self.screen.set_page(self.screen.pagination.page + 1)
        else:
            super().action_cursor_down()

    def on_resize(self):
        self.screen.call_after_refresh(self.screen.show_details)

    def watch_show_horizontal_scrollbar(self, visible):
        if self.is_mounted:
            self.screen.call_after_refresh(self.screen.show_details)


class ScanSettingInput(Input):
    def check_consume_key(self, key, character):
        return key != 'h' and super().check_consume_key(key, character)


class PageButtons(Widget, can_focus=True):
    """Draw only the numbered buttons that fit the current terminal width."""
    BINDINGS = [('left', 'step(-1)', 'Previous page'), ('right', 'step(1)', 'Next page')]

    def __init__(self):
        super().__init__(id='scan-pages')
        self.targets = []

    def render(self):
        screen = self.screen
        choices = screen.pagination.choices(screen.pages, self.content_size.width)
        width = len(str(screen.pages)) + 2
        result = Text()
        self.targets = []
        for page in choices:
            start = len(result)
            label = '…' if page is None else str(page)
            result.append(label.center(width), style=(
                'bold #000000 on #ffffff' if page == screen.pagination.page
                else '#ffffff on #333333' if page is not None else '#888888'))
            self.targets.append((start, len(result), page))
        return result

    def on_click(self, event):
        for start, end, page in self.targets:
            if start <= event.x < end and page is not None:
                self.screen.set_page(page)
                self.focus()
                break

    def action_step(self, delta):
        self.screen.set_page(self.screen.pagination.page + delta)


class PageSlider(Widget, can_focus=True):
    """Click or drag to a page; keyboard arrows give exact single-page steps."""
    BINDINGS = [('left', 'step(-1)', 'Previous page'), ('right', 'step(1)', 'Next page'),
                ('home', 'edge(False)', 'First page'), ('end', 'edge(True)', 'Last page')]

    def __init__(self):
        super().__init__(id='scan-slider')
        self.dragging = False

    def render(self):
        width = max(1, self.content_size.width)
        pages = self.screen.pages
        position = round((self.screen.pagination.page - 1) * (width - 1) / max(1, pages - 1))
        result = Text('━' * position, style='#00aaaa')
        result.append('●', style='bold #ffffff on #555555')
        result.append('─' * (width - position - 1), style='#888888')
        return result

    def seek(self, x):
        fraction = max(0, min(x, self.content_size.width - 1)) / max(1, self.content_size.width - 1)
        self.screen.set_page(1 + round(fraction * (self.screen.pages - 1)))

    def on_mouse_down(self, event):
        self.dragging = True
        self.capture_mouse()
        self.focus()
        self.seek(event.x)
        event.stop()

    def on_mouse_move(self, event):
        if self.dragging:
            self.seek(event.x)

    def on_mouse_up(self, event):
        if self.dragging:
            self.seek(event.x)
            self.dragging = False
            self.release_mouse()

    def action_step(self, delta):
        self.screen.set_page(self.screen.pagination.page + delta)

    def action_edge(self, last):
        self.screen.set_page(self.screen.pages if last else 1)


class ScannerScreen(ModalScreen):
    CSS = '''
    ScannerScreen { align: center middle; }
    #scanner-dialog { width: 96%; height: 96%; border: solid green; background: $surface; }
    #scanner-dialog.border-mc-default { border: solid #d0cfcc; }
    #scanner-dialog.border-mc-blue { border: solid #55ffff; }
    #scan-title, #scan-summary, #scan-controls, #scan-stats { height: 1; }
    #scan-stats { height: 2; }
    #bucket-summary { height: auto; max-height: 3; }
    #scan-settings { height: 1; }
    #scan-settings Label { width: auto; height: 1; padding: 0 1; }
    #scan-settings Input { width: 9; height: 1; min-height: 1; border: none; padding: 0 1; }
    #bucket-map { height: 2fr; min-height: 3; width: 100%; overflow: hidden scroll; background: #000000; }
    #scan-details { height: 1fr; min-height: 2; width: 100%; overflow: auto hidden; scrollbar-size-horizontal: 1; }
    #scan-pages, #scan-slider, #scan-nav { height: 1; width: 100%; }
    #scan-nav Button { min-width: 2; width: 1fr; height: 1; border: none; padding: 0; }
    #scan-filters { height: 1; align: left top; overflow: auto hidden; scrollbar-size-horizontal: 0; }
    #scan-filters Button { width: auto; min-width: 0; height: 1; border: none; padding: 0 1; text-align: left; content-align: left middle; }
    #scan-filters Button.filter-selected { background: #ffffff; color: #000000; text-style: bold; }
    '''
    BINDINGS = [Binding('escape', 'close', 'Close', priority=True),
                Binding('s', 'close', 'Close'), Binding('h', 'help', 'Help', priority=True), ('m', 'mode', 'Count / size'),
                ('v', 'view', 'Fixed / scroll'),
                ('1', 'scan_mode(1)', 'Lite run/stop'),
                ('2', 'scan_mode(2)', 'Medium run/stop'),
                ('3', 'scan_mode(3)', 'Heavy run/stop'),
                ('shift+1,exclamation_mark', 'scan_from_cursor(1)', 'Lite from cursor'),
                ('shift+2,at', 'scan_from_cursor(2)', 'Medium from cursor'),
                ('shift+3,number_sign', 'scan_from_cursor(3)', 'Heavy from cursor'),
                ('r', 'read_known', 'Read DB files'),
                ('t', 'priority', 'New / all priority'),
                ('j', 'heavy_order', 'Normal / expert'),
                ('left_square_bracket', 'directory_scope(-1)', 'Parent scope'),
                ('right_square_bracket', 'directory_scope(1)', 'Deeper scope'),
                ('f', 'fix_colors', 'Fix bucket colors'),
                ('d', 'clear_colors', 'Clear bucket colors')]

    def __init__(self, vfs, path, startup=True):
        super().__init__()
        self.vfs = vfs
        self.path = path.rstrip('/') or '/'
        self.store = ScanStore(vfs.db)
        self.saved = self.store.get('map', self.path, {})
        self.controls = ScanControls(
            self.saved.get('modes', (True, False, False)),
            self.saved.get('read_known', False), self.saved.get('new_first', True),
            startup=startup, heavy_order=self.saved.get('heavy_order', 'normal'))
        self.scope_path = self.saved.get('scope_path')
        self.scope_color = self.saved.get('scope_color')
        self.scope_anchor = None
        self.scope_depth = None
        self.fixed_colors = self.saved.get('fixed_colors', {})
        self.colored_model = None
        self.scope_indices = set()
        self.catalog_signature = None
        self.model = FileMap()
        self.model.fixed = False
        for name in ('mode', 'fixed', 'limit', 'byte_limit'):
            if name in self.saved:
                setattr(self.model, name, self.saved[name])
        self.model.entries = {value['id']: ScanEntry(**dict(value, progress=None))
                              for value in self.saved.get('entries', [])}
        self.model.rebuild()
        self.pagination = Pagination()
        self.file_filter = self.saved.get('file_filter')
        if self.file_filter not in STATES:
            self.file_filter = None
        self.events = Queue(maxsize=2048)
        self.stop = Event()
        self.phase = 'Starting scanner'
        self.repacking = False
        self.pages = 1
        self.scan_stats = ScanStats(path=path)

    def compose(self):
        with Vertical(id='scanner-dialog'):
            yield Static(Text(f'Drive map — {self.path}'), id='scan-title')
            yield Static(id='scan-controls')
            yield Static(id='scan-summary')
            yield Static(id='scan-stats')
            with Horizontal(id='scan-settings'):
                yield Label('Paths/bucket')
                yield ScanSettingInput(str(self.model.limit), type='integer', id='scan-limit')
                yield Label('MiB/bucket')
                yield ScanSettingInput(str(self.model.byte_limit // (1024 * 1024)), type='integer', id='scan-bytes')
            yield BucketMap(self.model)
            yield Static(id='bucket-summary')
            with HorizontalScroll(id='scan-filters'):
                yield Button('All', id='scan-filter-all')
                for state in STATES:
                    yield Button('', id=f'scan-filter-{state}')
            yield FileDetails(id='scan-details', cursor_type='row',
                              cursor_foreground_priority='renderable')
            yield PageButtons()
            yield PageSlider()
            with Horizontal(id='scan-nav'):
                for label, name in [('|<', 'first'), ('<-1000', 'back1000'),
                                    ('<-100', 'back100'), ('<-10', 'back10'), ('<', 'prev'), ('>', 'next'),
                                    ('>+10', 'ahead10'), ('>+100', 'ahead100'),
                                    ('>+1000', 'ahead1000'), ('>|', 'last')]:
                    yield Button(label, id=f'scan-{name}')


    def on_mount(self):
        self.query_one('#scanner-dialog').add_class(f'border-{self.app.theme}')
        self.grid = self.query_one(BucketMap)
        self.query_one('#scan-details', DataTable).add_columns('Name / path', 'Size')
        self.worker_thread = Thread(target=DriveScanner(
            self.vfs.db, self.path, self.events, self.stop, controls=self.controls,
            entries=self.model.entries.values(),
            root_names=tuple(node.name for node in self.vfs.list_nodes(self.vfs.db.get_root()))
            if self.path == "/" else ()).run,
                                    name='drive-scanner', daemon=True)
        self.worker_thread.start()
        self.set_interval(.1, self.drain_events)
        self.query_one(BucketMap).focus()
        self.redraw()
        self.call_after_refresh(self.restore_view)

    def restore_view(self):
        grid = self.query_one(BucketMap)
        grid.follow_end = self.saved.get("follow_end", False)
        grid.selected = min(self.saved.get("selected", 0), max(0, len(self.model.buckets) - 1))
        grid.scroll_to(y=self.saved.get("scroll_y", 0), animate=False)
        self.pagination.page = self.saved.get("page", 1)
        self.redraw()

    def on_unmount(self):
        self.stop.set()
        self.save_map()

    def action_help(self):
        self.app.push_screen(HelpScreen("Drive map help", SCANNER_HELP))

    def action_close(self):
        self.stop.set()
        self.dismiss()

    def save_map(self):
        grid = self.grid
        snapshot = {name: getattr(self.model, name)
                    for name in ('mode', 'fixed', 'limit', 'byte_limit')}
        snapshot.update(entries=[asdict(replace(entry, progress=None))
                                 for entry in self.model.entries.values()],
                        modes=self.controls.modes, read_known=self.controls.read_known,
                        new_first=self.controls.new_first, selected=grid.selected,
                        scroll_y=int(grid.scroll_y), page=self.pagination.page,
                        follow_end=grid.follow_end, file_filter=self.file_filter,
                        heavy_order=self.controls.heavy_order, scope_path=self.scope_path,
                        scope_color=self.scope_color, fixed_colors=self.fixed_colors)
        self.store.put('map', self.path, snapshot)

    def action_scan_mode(self, mode):
        self.controls.toggle(mode)
        self.save_map()
        self.redraw()

    def action_scan_from_cursor(self, mode):
        grid = self.query_one(BucketMap)
        if not self.model.buckets or grid.follow_end:
            return
        bucket = self.model.buckets[grid.selected]
        if not bucket.ids:
            return
        self.controls.start_from(mode, bucket.ids[0])
        self.save_map()
        self.redraw()

    def action_read_known(self):
        self.controls.read_known = not self.controls.read_known
        self.controls.wake.set()
        self.redraw()

    def action_priority(self):
        self.controls.new_first = not self.controls.new_first
        self.controls.wake.set()
        self.redraw()

    def action_heavy_order(self):
        self.controls.toggle_order()
        self.save_map()
        self.redraw()

    def new_scope_color(self):
        return '#' + ''.join(f'{random.randint(32, 96):02x}' for _ in range(3))

    def path_matches_scope(self, path):
        return bool(self.scope_path and (self.scope_path == '/' or
                    path == self.scope_path or path.startswith(self.scope_path + '/')))

    def scoped_buckets(self):
        return sorted(self.scope_indices)

    def refresh_bucket_colors(self, indices=None):
        grid = self.query_one(BucketMap)
        count = len(self.model.buckets)
        if indices is None:
            self.scope_indices.clear()
        if len(grid.backgrounds) < count:
            grid.backgrounds.extend(['#000000'] * (count - len(grid.backgrounds)))
        elif len(grid.backgrounds) > count:
            del grid.backgrounds[count:]
        for index in range(count) if indices is None else indices:
            if index >= count:
                continue
            bucket = self.model.buckets[index]
            matches = bool(self.scope_path and any(
                self.path_matches_scope(self.model.entries[key].path) for key in bucket.ids))
            if matches:
                self.scope_indices.add(index)
            else:
                self.scope_indices.discard(index)
            background = '#000000'
            if not self.fixed_colors and not self.scope_color:
                grid.backgrounds[index] = background
                continue
            for key in bucket.ids:
                if key in self.fixed_colors:
                    background = self.fixed_colors[key]
            if background == '#000000' and self.scope_color and matches:
                background = self.scope_color
            grid.backgrounds[index] = background
        self.colored_model = self.model
        grid.refresh()

    def action_directory_scope(self, direction):
        table = self.query_one('#scan-details', DataTable)
        if not table.row_count:
            return
        key = table.ordered_rows[table.cursor_row].key.value
        entry = self.model.entries.get(key)
        if entry is None:
            return
        parts = entry.path.strip('/').split('/')
        if not entry.is_dir:
            parts = parts[:-1]
        chain = ['/' + '/'.join(parts[:i]) for i in range(1, len(parts) + 1)] or ['/']
        if self.scope_anchor != key:
            self.scope_anchor, self.scope_depth = key, None
        if self.scope_depth is None:
            depth = 0 if direction > 0 else len(chain) - 1
        else:
            depth = max(0, min(len(chain) - 1, self.scope_depth + direction))
        path = chain[depth]
        self.scope_depth = depth
        if path == self.scope_path:
            return
        self.scope_path, self.scope_color = path, self.new_scope_color()
        self.refresh_bucket_colors()
        self.show_details()

    def action_fix_colors(self):
        if not self.scope_path or not self.scope_color:
            return
        for index in self.scoped_buckets():
            for key in self.model.buckets[index].ids:
                self.fixed_colors[key] = self.query_one(BucketMap).backgrounds[index]
        self.save_map()
        self.query_one(BucketMap).refresh()

    def action_clear_colors(self):
        self.scope_path = self.scope_color = self.scope_anchor = self.scope_depth = None
        self.fixed_colors = {}
        self.refresh_bucket_colors()
        self.save_map()
        self.show_details()

    def action_mode(self):
        self.model.mode = 'size' if self.model.mode == 'count' else 'count'
        self.repack()

    def action_view(self):
        self.model.fixed = not self.model.fixed
        self.repack()

    def on_input_submitted(self, event):
        try:
            limit, size = [int(self.query_one(f'#scan-{name}', Input).value)
                           for name in ('limit', 'bytes')]
            if not (1 <= limit <= 1_000_000 and 1 <= size <= 1_048_576):
                raise ValueError
        except ValueError:
            self.notify('Use positive integers: paths ≤ 1000000, MiB ≤ 1048576', severity='warning')
            return
        grid = self.query_one(BucketMap)
        grid.sync()
        self.model.cells, self.model.limit, self.model.byte_limit = grid.cells, limit, size * 1024 * 1024
        self.repack()
        grid.focus()

    def fit_map(self):
        grid = self.query_one(BucketMap)
        grid.sync()
        self.update_stats()
        if self.model.cells != grid.cells:
            self.model.cells = grid.cells
            if self.model.fixed:
                self.repack()

    def repack(self, minimum=1, removed=()):
        # Repacking a million IDs must not pause map navigation or animation.
        # Queue backpressure pauses scanning until the replacement is ready.
        self.repacking = True
        source = self.model
        replacement = FileMap()
        for name in ('mode', 'fixed', 'cells', 'limit', 'byte_limit'):
            setattr(replacement, name, getattr(source, name))

        def build():
            replacement.entries = {key: entry for key, entry in source.entries.items()
                                   if key not in removed}
            replacement.rebuild(minimum=minimum)
            return replacement

        async def install():
            model = await asyncio.to_thread(build)
            self.model = model
            self.query_one(BucketMap).model = model
            self.repacking = False
            self.pagination = Pagination()
            self.redraw()

        self.run_worker(install(), group='map-packing', exclusive=True)


    def selection_changed(self):
        self.pagination = Pagination()
        self.redraw()

    def drain_events(self):
        if self.repacking:
            self.query_one(BucketMap).refresh()
            return
        changed = False
        deadline = time.monotonic() + .015
        while time.monotonic() < deadline:
            try:
                kind, payload = self.events.get_nowait()
            except Empty:
                break
            changed = True
            if kind == 'entry':
                if self.model.update(payload, rebuild=False):
                    self.repack(minimum=self.model.capacity * 2 if self.model.fixed else 1)
                    break
                self.refresh_bucket_colors({self.model.locations[payload.id]})
            elif kind == 'expert':
                self.phase = 'Heavy expert — processing selected bucket'
            elif kind == 'stats':
                self.scan_stats = payload
            elif kind == 'removed':
                self.repack(removed=set(payload))
                break
            else:
                self.phase = payload
        if changed:
            self.redraw()
        else:
            self.update_stats()
            self.query_one(BucketMap).refresh()

    def redraw(self):
        grid = self.query_one(BucketMap)
        grid.sync()
        signature = (id(self.model), len(self.model.entries))
        if self.catalog_signature != signature:
            self.controls.buckets = tuple(tuple(bucket.ids) for bucket in self.model.buckets)
            self.catalog_signature = signature
        if self.colored_model is not self.model or len(grid.backgrounds) != len(self.model.buckets):
            self.refresh_bucket_colors()
        controls = Text()
        for index, (name, running) in enumerate(
                zip(('Lite', 'Medium', 'Heavy'), self.controls.modes), start=1):
            controls.append(f'{index} {name} ')
            controls.append('RUN' if running else 'STOP',
                            style='bold green' if running else 'bold red')
            controls.append(' · ')
        controls.append(f'r {"on" if self.controls.read_known else "off"} · '
                        f't {"new" if self.controls.new_first else "all"} · '
                        f'j {self.controls.heavy_order}')
        self.query_one('#scan-controls', Static).update(controls)
        self.query_one('#scan-summary', Static).update(Text(
            f'{self.phase} | {self.model.mode} | {"fixed" if self.model.fixed else "scroll"} | '
            f'{len(self.model.entries)} paths · {len(self.model.buckets)} buckets · '
            f'{grid.rows} map rows'))
        self.update_stats()
        self.show_details()

    def update_expert_selection(self):
        grid = self.query_one(BucketMap)
        visible = self.controls.modes[2] and self.controls.heavy_order == 'expert'
        if not self.controls.lock.acquire(blocking=False):
            return
        try:
            queue = self.controls.expert_queue
            signature = (visible, id(self.model), id(self.model.buckets), len(self.model.entries),
                         self.controls.expert_current, len(queue),
                         queue[0] if queue else None, queue[-1] if queue else None)
            if signature == getattr(self, '_expert_highlight_signature', None):
                return
            buckets = self.controls.selected_buckets if visible else ()
        finally:
            self.controls.lock.release()
        self._expert_highlight_signature = signature
        seen = set()
        for ids in buckets:
            # Keep one visual anchor per selected work bucket after regrouping.
            index = next((self.model.locations[key] for key in ids
                          if key in self.model.locations), None)
            if index is not None and index not in seen:
                seen.add(index)
        grid.expert_selected = seen
        grid.expert_mode = visible

    def update_stats(self):
        self.update_expert_selection()
        grid = self.query_one(BucketMap)
        total = len(grid.model.buckets)
        first = min(int(grid.scroll_y) * grid.columns + 1, total) if total else 0
        stats = self.scan_stats
        label = 'Scanning' if stats.active else 'Last path'
        rate = stats.mb_per_second
        for unit in ('MB/s', 'GB/s', 'TB/s', 'PB/s'):
            if rate < 1000 or unit == 'PB/s':
                break
            rate /= 1000
        throughput = f'{rate:.2f} {unit}'
        status = self.query_one('#scan-stats', Static)
        status.update(Text(
            f'{stats.paths_per_second:.1f} paths/s · {throughput} · '
            f'Total {stats.paths} paths / {format_size(stats.size_scanned or 0, 0).strip()} · '
            f'bucket {first}/{total}\n'
            f'{label}: {stats.path}'))
        status.tooltip = stats.path

    def update_filters(self, bucket=None):
        all_button = self.query_one('#scan-filter-all', Button)
        all_button.set_class(self.file_filter is None, 'filter-selected')
        all_button.disabled = bucket is None
        for state, (symbol, color, label) in STATES.items():
            button = self.query_one(f'#scan-filter-{state}', Button)
            count = bucket.counts[state] if bucket else 0
            label_text = Text(f'{symbol} {label}: {count}',
                              style='#000000' if state == self.file_filter else color)
            # Content equality ignores spans; force style-only label changes.
            label_changed = button.label.plain != label_text.plain
            button.set_reactive(Button.label, Content.from_text(label_text))
            button.refresh(layout=label_changed)
            button.display = bool(count) or state == self.file_filter
            button.disabled = bucket is None
            button.set_class(state == self.file_filter, 'filter-selected')

    def show_details(self):
        grid = self.query_one(BucketMap)
        table = self.query_one('#scan-details', DataTable)
        rows = []
        height = table.scrollable_content_region.height
        table.show_header = height > 1
        self.page_size = max(1, min(100, height - int(table.show_header)))
        pages = 1
        bucket = self.model.buckets[grid.selected] if self.model.buckets and not grid.follow_end else None
        self.update_filters(bucket)
        if bucket is not None:
            ids = bucket.ids if self.file_filter is None else [
                node_id for node_id in bucket.ids
                if self.model.entries[node_id].state == self.file_filter]
            pages = max(1, math.ceil(len(ids) / self.page_size))
            self.pagination.select(self.pagination.page, pages)
            activity = ' · A — scanning' if bucket.active else ''
            if self.scope_path:
                activity += f'\nScope {self.scope_path} · {len(self.scope_indices)} buckets'
            self.query_one('#bucket-summary', Static).update(Text(
                f'Bucket {grid.selected + 1} · {bucket.files} files · {len(bucket.ids) - bucket.files} dirs · '
                f'{format_size(bucket.size, 0)} · M {bucket.file_states["modified"]} / deleted {bucket.file_states["missing"]} / green {bucket.file_states["verified"]} · page {self.pagination.page}/{pages} · shown {len(ids)}/{len(bucket.ids)}' + activity))
            for node_id in ids[(self.pagination.page - 1) * self.page_size:self.pagination.page * self.page_size]:
                entry = self.model.entries[node_id]
                prefix = f'S {entry.progress}% ' if entry.progress is not None else ''
                symbol, color, _ = STATES.get(entry.state, STATES['unknown'])
                name = Text(prefix)
                name.append(symbol, style=color)
                name.append(' ' + entry.path + ('/' if entry.is_dir else ''))
                rows.append((entry.id, name, Text(format_size(entry.size, 0))))
            # Errors explain unverified symbols without adding status columns.
            errors = [self.model.entries[i].error for i in ids[(self.pagination.page - 1) * self.page_size:self.pagination.page * self.page_size]
                      if self.model.entries[i].error]
            if errors:
                self.query_one('#bucket-summary', Static).update(Text(
                    f'Bucket {grid.selected + 1} · {bucket.files} files · {format_size(bucket.size, 0)} · '
                    f'page {self.pagination.page}/{pages} · shown {len(ids)}/{len(bucket.ids)}' + activity + '\n' + errors[0]))
        else:
            self.query_one('#bucket-summary', Static).update(
                'End of buckets > — following new buckets; move cursor to exit'
                if grid.follow_end else 'Waiting for paths…')
        table.sync_rows(rows)
        self.pages = pages
        self.pagination.select(self.pagination.page, pages)
        self.query_one(PageButtons).refresh()
        self.query_one(PageSlider).refresh()
        for button in self.query('#scan-nav Button'):
            backward = button.id in ('scan-first', 'scan-prev') or 'back' in button.id
            button.disabled = self.pagination.page == (1 if backward else pages)

    def set_page(self, page):
        self.pagination.select(page, self.pages)
        table = self.query_one('#scan-details', DataTable)
        table.move_cursor(row=0, animate=False, scroll=False)
        self.show_details()

    def on_button_pressed(self, event):
        name = event.button.id or ''
        if name.startswith('scan-filter-'):
            state = name.removeprefix('scan-filter-')
            self.file_filter = None if state == 'all' or self.file_filter == state else state
            self.pagination = Pagination()
            self.query_one('#scan-details', DataTable).move_cursor(row=0, animate=False)
            self.show_details()
        elif name == 'scan-first':
            self.set_page(1)
        elif name == 'scan-last':
            self.set_page(self.pages)
        else:
            delta = {'scan-back1000': -1000, 'scan-back100': -100, 'scan-back10': -10,
                     'scan-prev': -1, 'scan-next': 1, 'scan-ahead10': 10, 'scan-ahead100': 100,
                     'scan-ahead1000': 1000}.get(name)
            if delta is not None:
                self.set_page(self.pagination.page + delta)
