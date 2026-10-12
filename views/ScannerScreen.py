"""Live drive map popup. Only visible map rows and 100 detail rows are drawn."""
import asyncio
import math
from queue import Empty, Queue
from threading import Event, Thread
import time

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.scroll_view import ScrollView
from textual.geometry import Size
from textual.strip import Strip
from textual.widgets import Button, DataTable, Input, Label, Static

from vfs.scanner import DriveScanner, FileMap, Pagination, ScanStats
from vfs.utils import format_size


STATES = {
    'modified': ('M', '#ff8800', 'modified'),
    'missing': ('U', '#ff0000', 'not found'),
    'new': ('U', '#ffffff', 'undefined / new'),
    'unknown': ('?', '#ffffff', 'unverified'),
    'verified': ('●', 'green', 'verified'),
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

    @property
    def cells(self):
        return self.columns * max(1, self.scrollable_content_region.height)

    def sync(self):
        self.columns = max(1, self.scrollable_content_region.width)
        self.rows = max(1, math.ceil(len(self.model.buckets) / self.columns))
        self.virtual_size = Size(self.columns, self.rows)
        self.selected = max(0, min(self.selected, len(self.model.buckets) - 1))
        self.refresh()

    def watch_scroll_y(self, old_value, new_value):
        super().watch_scroll_y(old_value, new_value)
        if self.is_mounted:
            self.screen.update_view_start()

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
        delta = {-2: -self.columns, 2: self.columns}.get(delta, delta)
        self.selected = max(0, min(len(self.model.buckets) - 1, self.selected + delta))
        self.reveal_selection()
        self.screen.selection_changed()
        self.refresh()

    def action_page(self, direction):
        self.selected = max(0, min(len(self.model.buckets) - 1,
                                   self.selected + direction * self.columns * max(1, self.scrollable_content_region.height)))
        self.reveal_selection()
        self.screen.selection_changed()
        self.refresh()

    def on_click(self, event):
        x, y = event.offset
        index = (y + int(self.scroll_y)) * self.columns + x
        if 0 <= x < self.columns and 0 <= y < self.rows and index < len(self.model.buckets):
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
                state = next((key for key in STATES if bucket.counts[key]), 'unknown')
                symbol, color, _ = STATES[state]
                if now - bucket.updated < 1:
                    symbol = ('\\', '|', '/', '-')[int(now * 8) % 4]
                    # Activity always takes precedence over cursor colors.
                    color, background = '#ffffff', '#ff0000'
            if selected:
                color, background = '#000000', '#ffffff'
            segments.append(Segment(symbol, Style(color=color, bgcolor=background,
                                                   underline=selected)))
        return Strip(segments)


class FileDetails(DataTable):
    """Only mount the file rows that fit; page controls expose the remainder."""
    def on_resize(self):
        self.screen.call_after_refresh(self.screen.show_details)


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
    #scanner-dialog { width: 96%; height: 96%; border: thick $accent; background: $surface; }
    #scan-title, #scan-summary, #map-start, #scan-stats { height: 1; }
    #bucket-summary { height: auto; max-height: 3; }
    #scan-settings { height: 3; }
    #scan-settings Label { width: auto; padding: 1 1; }
    #scan-settings Input { width: 9; }
    #bucket-map { height: 2fr; min-height: 3; width: 100%; overflow: hidden scroll; background: #000000; }
    #scan-details { height: 1fr; min-height: 1; width: 100%; overflow: hidden hidden; }
    #scan-pages, #scan-slider, #scan-nav { height: 1; width: 100%; }
    #scan-nav Button { min-width: 2; width: 1fr; height: 1; border: none; padding: 0; }
    #scan-help { height: auto; }
    '''
    BINDINGS = [Binding('escape', 'close', 'Close', priority=True),
                Binding('s', 'close', 'Close'), ('m', 'mode', 'Count / size'),
                ('v', 'view', 'Fixed / scroll')]

    def __init__(self, vfs, path):
        super().__init__()
        self.vfs = vfs
        self.path = path
        self.model = FileMap()
        self.model.fixed = False
        self.model.rebuild()
        self.pagination = Pagination()
        self.events = Queue(maxsize=2048)
        self.stop = Event()
        self.phase = 'Starting scanner'
        self.repacking = False
        self.pages = 1
        self.scan_stats = ScanStats(path=path)

    def compose(self):
        with Vertical(id='scanner-dialog'):
            yield Static(Text(f'Drive map — {self.path}'), id='scan-title')
            yield Static(id='scan-summary')
            yield Static(id='scan-stats')
            with Horizontal(id='scan-settings'):
                yield Label('Cols')
                yield Input('Auto', disabled=True, id='scan-cols')
                yield Label('Paths/bucket')
                yield Input('100', type='integer', id='scan-limit')
                yield Label('MiB/bucket')
                yield Input('64', type='integer', id='scan-bytes')
            yield Static(id='map-start')
            yield BucketMap(self.model)
            yield Static(id='bucket-summary')
            yield FileDetails(id='scan-details', cursor_type='row')
            yield PageButtons()
            yield PageSlider()
            with Horizontal(id='scan-nav'):
                for label, name in [('|<', 'first'), ('<-1000', 'back1000'),
                                    ('<-100', 'back100'), ('<-10', 'back10'), ('<', 'prev'), ('>', 'next'),
                                    ('>+10', 'ahead10'), ('>+100', 'ahead100'),
                                    ('>+1000', 'ahead1000'), ('>|', 'last')]:
                    yield Button(label, id=f'scan-{name}')
            yield Static('s/Esc close • m count/size • v fixed/scroll • arrows/PgUp/PgDn move • Enter applies inputs\n'
                         'U white new • U red missing • ● green verified • M orange modified • ? unverified • white-on-red animation scanning', id='scan-help')

    def on_mount(self):
        self.query_one('#scan-details', DataTable).add_columns('Name / path', 'Size')
        self.worker_thread = Thread(target=DriveScanner(self.vfs.db, self.path, self.events, self.stop).run,
                                    name='drive-scanner', daemon=True)
        self.worker_thread.start()
        self.set_interval(.1, self.drain_events)
        self.query_one(BucketMap).focus()
        self.redraw()

    def on_resize(self, event):
        self.query_one('#scan-help', Static).display = event.size.height >= 30

    def on_unmount(self):
        self.stop.set()

    def action_close(self):
        self.stop.set()
        self.dismiss()

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
        self.query_one('#scan-cols', Input).value = str(grid.columns)
        self.update_view_start()
        if self.model.cells != grid.cells:
            self.model.cells = grid.cells
            if self.model.fixed:
                self.repack()

    def repack(self, minimum=1):
        # Repacking a million IDs must not pause map navigation or animation.
        # Queue backpressure pauses scanning until the replacement is ready.
        self.repacking = True
        source = self.model
        replacement = FileMap()
        for name in ('mode', 'fixed', 'cells', 'limit', 'byte_limit'):
            setattr(replacement, name, getattr(source, name))

        def build():
            replacement.entries = dict(source.entries)
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
            elif kind == 'stats':
                self.scan_stats = payload
            elif kind == 'removed':
                for node_id in payload:
                    self.model.entries.pop(node_id, None)
                self.repack()
                break
            else:
                self.phase = payload
        if changed:
            self.redraw()
        else:
            self.query_one(BucketMap).refresh()

    def redraw(self):
        grid = self.query_one(BucketMap)
        grid.sync()
        self.query_one('#scan-summary', Static).update(Text(
            f'{self.phase} | {self.model.mode} | {"fixed" if self.model.fixed else "scroll"} | '
            f'{len(self.model.entries)} paths · {len(self.model.buckets)} buckets · '
            f'{grid.rows} map rows'))
        stats = self.scan_stats
        label = 'Scanning' if stats.active else 'Last path'
        status = self.query_one('#scan-stats', Static)
        status.update(Text(f'{stats.mb_per_second:.2f} MB/s (read avg) · {label}: {stats.path}'))
        status.tooltip = stats.path
        self.update_view_start()
        self.show_details()

    def update_view_start(self):
        grid = self.query_one(BucketMap)
        index = min(int(grid.scroll_y) * grid.columns, len(grid.model.buckets) - 1)
        text = 'View start: no buckets'
        if index >= 0:
            bucket = grid.model.buckets[index]
            entry = grid.model.entries.get(bucket.ids[0]) if bucket.ids else None
            text = (f'View start: bucket {index + 1}/{len(grid.model.buckets)} · '
                    f'{bucket.files} files · {format_size(bucket.size, 0)} · '
                    f'{entry.path if entry else ""}')
        self.query_one('#map-start', Static).update(Text(text))

    def show_details(self):
        grid = self.query_one(BucketMap)
        table = self.query_one('#scan-details', DataTable)
        cursor = table.cursor_row
        table.show_header = table.content_size.height > 1
        self.page_size = max(1, min(100, table.content_size.height - int(table.show_header)))
        table.clear()
        pages = 1
        if self.model.buckets:
            bucket = self.model.buckets[grid.selected]
            pages = max(1, math.ceil(len(bucket.ids) / self.page_size))
            self.pagination.select(self.pagination.page, pages)
            labels = [f'{symbol} — {label}: {bucket.counts[state]}'
                      for state, (symbol, color, label) in STATES.items() if bucket.counts[state]]
            active = bucket.active > 0
            if active:
                labels.append('A — scanning')
            self.query_one('#bucket-summary', Static).update(Text(
                f'Bucket {grid.selected + 1} · {bucket.files} files · {len(bucket.ids) - bucket.files} dirs · '
                f'{format_size(bucket.size, 0)} · M {bucket.file_states["modified"]} / deleted {bucket.file_states["missing"]} / green {bucket.file_states["verified"]} · page {self.pagination.page}/{pages}\n' + ' | '.join(labels)))
            for node_id in bucket.ids[(self.pagination.page - 1) * self.page_size:self.pagination.page * self.page_size]:
                entry = self.model.entries[node_id]
                prefix = f'S {entry.progress}% ' if entry.progress is not None else ''
                table.add_row(Text(prefix + entry.path + ('/' if entry.is_dir else '')),
                              Text(format_size(entry.size, 0)), key=entry.id)
            # Errors explain unverified symbols without adding status columns.
            errors = [self.model.entries[i].error for i in bucket.ids[(self.pagination.page - 1) * self.page_size:self.pagination.page * self.page_size]
                      if self.model.entries[i].error]
            if errors:
                self.query_one('#bucket-summary', Static).update(Text(
                    f'Bucket {grid.selected + 1} · {bucket.files} files · {format_size(bucket.size, 0)} · '
                    f'page {self.pagination.page}/{pages}\n' + ' | '.join(labels) + '\n' + errors[0]))
        else:
            self.query_one('#bucket-summary', Static).update('Waiting for paths…')
        if table.row_count:
            table.move_cursor(row=min(cursor, table.row_count - 1), animate=False)
            table.scroll_home(animate=False)
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
        table.move_cursor(row=0, animate=False)
        table.scroll_home(animate=False)
        self.show_details()

    def on_button_pressed(self, event):
        name = event.button.id or ''
        if name == 'scan-first':
            self.set_page(1)
        elif name == 'scan-last':
            self.set_page(self.pages)
        else:
            delta = {'scan-back1000': -1000, 'scan-back100': -100, 'scan-back10': -10,
                     'scan-prev': -1, 'scan-next': 1, 'scan-ahead10': 10, 'scan-ahead100': 100,
                     'scan-ahead1000': 1000}.get(name)
            if delta is not None:
                self.set_page(self.pagination.page + delta)
