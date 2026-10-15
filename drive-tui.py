#!/usr/bin/env python3
"""Standalone prompt_toolkit drive browser (2026-10-15).

Original request: recreate drive-tui only main screen with prompt_toolkit;
single file drive-tui-pt.py; only files view, pass all other views; no change
other files, just new one.

Run: python drive-tui.py -d /path/to/logs
     python drive-tui.py -c sqlite
Dependency: python -m pip install prompt_toolkit

Uses the existing VFS, drive.load_log and optional config.sh drive mappings.
Controls: arrows/PageUp/PageDown/Home/End, Enter to open, Escape/Backspace to
parent (restores selection), Tab to scroll file info, n display mode, t theme,
F5 refresh, q/Ctrl-C quit. h opens context help, s opens the live scanner/map,
a opens Actions, Delete queues removal, Shift+Delete queues descendants/duplicates,
and Ctrl+X copies info using wl-copy/xclip/xsel or terminal OSC 52.
Name is clipped before left-aligned Size/Dups; scrollbar is always present.
Listing merges local files through VFS without promoting them to tracked data.
Cache build/update options write storage. Scanner verification stores scan state
and promotes checksum-verified new files through the shared VFS adapter. Removal
is queued until the Actions Apply button is activated; shell exports are dry runs
unless invoked with -r. Existing Textual views are never imported.

Validation: headless prompt_toolkit smoke checks covered status markers, column
widths, rendering, Enter, parent selection, modes, themes, focus and quit.
Follow-up request (2026-10-15): screen blinking when moving the cursor and lost
quick-view circle colors. Cache immutable theme styles to retain incremental
rendering; color current-entry and duplicate circles with a marker-only lexer.
Current entry uses the listing's status color; duplicate circles use disk
existence (green/red). Paths stay plain text, including brackets and symbols.
Validation: captured headless terminal output confirmed cursor moves do not
clear the screen, theme switching still repaints, and current/duplicate marker
styles retain their colors. Literal filenames, Tab and quit also passed.
Physical terminal blinking was not visually checked.
No storage or event contract changes. Only this source file is affected.

Update history: 2026-10-15: initial Python implementation; cached theme styles
and restored quick-view colors.
Follow-up request (2026-10-15): check design-*.png and fix PT. Compared
design-orig.png and design-pt.png: use true color blue panes, cyan selection
without the default reverse style, centered title, untitled equal-width frames,
Info heading/padding and compact directory metadata. Cursor movement leaves the
current directory summary or opened file visible; Enter opens file details.
Footer shortcuts remain available via the controls documented above.
Validation: headless checks passed at 80 and 120 columns for layout, pane
colors, cyan selection without reverse video, directory summary and Enter file
details. Captured-output checks reconfirmed incremental redraw and circle colors.
2026-10-15 follow-up: compared refreshed design-pt.png with design-orig.png.
Matched sampled lime/orange marker colors, separated Info header blue, restored
pane text color instead of inherited border gray, padded metadata columns and
fixed pane widths to equal terminal halves. Title positioning uses render width.
No physical terminal screenshot comparison was performed after the changes.
Follow-up requirement (2026-10-15): "convert to pt all remaining parts".
Implemented context help/root legend, clipboard, duplicate/recursive removal queue,
Actions review/clear/export/Apply, and the live scanner/map with startup passes,
independent modes, cursor restarts, normal/expert scheduling, colored activity and
blue membership, limits/packing, filters, pagination/jumps/slider, horizontal pan,
scopes/pinned colors and saved maps. Scanner help keeps scanning active; returning
refreshes VFS metadata and preserves the main selected name. All UI stays in this
file; existing Textual code, backend code and dependency files are unchanged.

Contracts: reuse ScanEntry events (entry/stats/phase/expert/removed), ScanControls,
FileMap, ScanStore map/position/checksum records and adapter promotion unchanged.
Map snapshots retain mode/fixed/limits/entries, mode flags, read_known/new_first,
selection/scroll/page/follow/filter/order and scope/fixed colors. The map snapshot
is shared with Textual, with transient progress cleared before storing. Workers
have bounded event queues, stop/wake signals and joined shutdown before DB close.
Repacking runs in a background thread while event draining pauses; drawing only
requests visible map/table rows. Blue updates consume membership deltas without
blocking on the selector lock. Help text is a local data-only copy of the existing
help, rendered with a restricted markup lexer; filenames are always literal.
Queue paths retain original VFS identity; local paths are resolved only for Apply
and shell export. Symlink removal unlinks the link rather than its directory target.
Failed Apply operations stay queued. Shell paths are quoted and exports unique.

Controls: scanner 1/2/3 run/stop; !/@/# start at cursor; r known reads; t priority;
j normal/expert; m count/size; v fixed/scroll; [] scope; f pin; d clear; h help;
s/Esc close. Tab cycles map, inputs, filters, file table and paging controls.
Numeric inputs accept Enter to apply. Click filters, numbered pages or sliders;
arrows pan filters/files, move map or step pages according to focus. Up/Down at
file-page boundaries select previous-last/next-first rows. Actions x clears,
e exports to actions/action*.sh, t changes theme; buttons Close/Clear/Export/Apply.

Validation: temporary headless integration checks passed for actual memory and
SQLite startup/checksum promotion, worker shutdown, scanner/main-help lifecycle,
main selection retention, action queue/unique shell export/dry run/Apply using
only temporary files, page edges/filter/scopes/pins, numeric inputs/repacking,
blue membership and saved-map restore. Earlier main design/incremental-rendering
checks also pass; 45 existing scanner/backend regression tests passed. Additional
checks covered symlink cycles/unlink, failed-Apply retention, mocked clipboard,
root help/Close button and global Ctrl-C. Main widths and Actions stat rows are
cached between refreshes; uncolored buckets skip scope/member scans.
Physical terminal/clipboard/Redis and large-drive performance
have not been verified for the port. Slider dragging is local to its own row.
No Rust parity claimed; port UI bindings, persistence/lifecycle and fixtures before
claiming Rust equivalence. Keep this embedded history in the single-file port.

2026-10-15 follow-up: "jumping bug, see design1.pt; remove +1000 -1000 pages
if count less than 1000" (reference design-pt1.png). The scanner navigation row
now has a flexible filler, preventing its fixed button widths from constraining
the entire scanner body. +/-1000 buttons are conditional on total pages >=1000.
Buttons retain their existing clamped page targets; model, scanning and persisted
state contracts are unchanged. Only this file changes. Validation: headless
80/120/150-column checks confirmed full-width map and stable page/cursor/viewport
through redraws. Rendered +/-1000 visibility passed at 998/999/1000/1001 pages.
The three PT integration tests (including memory/SQLite scans) passed again.
No physical terminal or Rust validation performed for this change.

2026-10-15 follow-up: "map j expert/normal switch slow. must be fast".
The j handler updates its displayed target immediately, and a dedicated worker
applies ScanControls.toggle_order (including lock acquisition/queue cleanup).
Rapid presses coalesce to the latest requested order. Removed the synchronous
whole-map snapshot from j; order persists with the next normal save or close.
Close/exit joins the transition worker before saving. Existing startup cancellation,
epoch/wake, queue clearing and selector invalidation rules remain in the backend.
Validation: a synthetic 100k-entry check measured a 0.44ms j handler while a
separate thread held the scanner lock; it confirmed no snapshot call, immediate
target label, coalesced rapid presses and switching back to normal. This measures
UI dispatch, not backend completion or disk throughput.
Only this file changes; no Rust or hardware-throughput claims.

2026-10-15 follow-up: "j work fast now. need the same fix to 3-heavy, that slow".
Mode keys 1/2/3 now publish their requested RUN/STOP state immediately, coalesce
rapid presses per mode and apply ScanControls toggles on a dedicated worker.
Startup cancellation, mode epochs and wake signaling remain in the backend.
Removed full-map serialization from mode-key dispatch; normal snapshots and close
persist the applied flags. Close/exit join the mode worker before the final save.
Cursor-start controls remain unchanged. This change affects only this file.
Validation: synthetic 100k-entry heavy-key dispatch took 0.26ms with the scanner
lock held elsewhere; checks passed for no snapshot, immediate RUN label, rapid
independent toggles, startup cancellation, wake signaling and persisted flags.
The j contention check and three memory/SQLite/UI integration checks passed again.
Timing measures key dispatch, not completion of disk work. No Rust validation.

2026-10-15 follow-up: "why mode 2 and 3 halt on start? fix it; normal mode
works fine, but expert still halt ... move to separate thread".
The earlier changes addressed only key dispatch. Periodic UI ticks still rebuilt
the whole bucket catalog and processed blue membership; every appended entry
also forced a full remap of outstanding expert work. A dedicated
drive-pt-map-projection thread now owns catalog publication and blue-membership
bookkeeping. UI ticks signal it and continue drawing/input/event handling.
Unchanged immutable bucket tuples are reused; only the last published bucket and
new buckets are copied during append-only discovery. Repacking rebuilds the
catalog. Highlight remapping keys on model/bucket-list identity, not entry count.
Completed full blue projections are swapped into view; incremental set updates
are safe membership operations under CPython's GIL. The worker reads append-only
model/list snapshots and never performs SQLite operations. Scanner verification
and expert selection already have their own backend threads and remain unchanged.
Close/exit signal and join the projection worker before the final map save.

Validation: a temporary 100k-entry/10k-blue-bucket regression checked catalog tuple
reuse, no highlight remapping on appended entries, completion deltas and help/mode
responsiveness while the projection worker was deliberately blocked. A separate
real expert run checksum-verified 100 files across 50 buckets and joined both
workers on close. The three PT integration checks (memory/SQLite scans, actions,
map controls/paging) and heavy/j held-lock checks passed. No large-drive hardware
benchmark or Rust parity validation. Python background CPU work still shares the
GIL; this removes synchronous UI projection work, not all possible disk/setup cost.

2026-10-15 follow-up: "pt*.png; pt2: 'id' bug; paths/buckets must left
aligned input; pt3: bad design, remove < >". Inspected pt1.png, pt2.png and
pt3.png. Expert events now set a readable phase instead of stringifying their
internal id dictionary; they still do not move map/file selection. Settings use
natural-width labels directly next to left-aligned inputs and a trailing flexible
filler. Page navigation uses spaced, undecorated First/Prev/Next/Last and numeric
jump buttons; all angle-bracket wrappers/arrows are removed from that row.
The +/-1000 visibility threshold and page targets stay unchanged. Only this file
changes; event/storage schemas and backend behavior are unchanged. Validation:
headless renders at 80/150 columns checked left-aligned inputs, bracket-free
spaced navigation and readable expert phase with retained selection. Page-button
callbacks, +/-1000 threshold/width regressions and all three PT integration
checks passed. No physical terminal or Rust validation for this change.

2026-10-15 follow-up: "path/bucked and mibs is inputs in original version,
recheck and fix". Rechecked ScanSettingInput and numeric submission in the
original Textual scanner. PT retains actual single-line editable fields, now with
mouse-click focus enabled (previously disabled), distinct field backgrounds and
a focus highlight. Tab/Shift+Tab and Enter-to-apply retain existing limits and
repacking. Only this file changes; storage/events/backend remain unchanged.
Validation: headless SGR mouse-click focus, field/focus styling, actual keyboard
editing, Tab between fields, Enter application/repacking, invalid-value retention
and help focus restoration all passed. The three PT integration checks passed.
No physical terminal or Rust validation for this change.

2026-10-15 follow-up: "expert still slow ... update partially only selected
buckets cols/rows, not whole map". MapControl now caches a bounded LRU of rendered
rows (at most three viewport heights) and recomputes only dirty cells. Expert
membership transitions mark their bucket indices, file/color events mark affected
buckets, cursor movement marks old/new positions, and animation deadlines refresh
only active cells and their final settled state. Offscreen cells have no cache to
invalidate and are read fresh on scroll. A small synchronized set coalesces worker
notifications, bounded by cached cells; rendering never waits for its lock.
Full cache invalidation is reserved for model regrouping, width changes, expert
visibility changes or explicit full color refresh. Existing prompt_toolkit screen
diffing still traverses visible output but emits only changed terminal cells.
Persistence, scanner scheduling, event formats and source ownership stay unchanged.
Only this file changes, retaining the single-file constraint.
Validation: instrumented a 10k-bucket map/640 visible cells: idle redraw rebuilt 0
cells, adding three blue buckets rebuilt exactly 3, completion 1, cursor movement
2, and offscreen update 0. Active animation/expiry and bounded cache checks passed.
The three PT integration checks passed; projection-worker/expert-progress/input/
layout regressions were rerun. No hardware benchmark or Rust validation.

2026-10-15 follow-up: "lost red background for \\ - / rotation indicator;
bucket files list directory hide 0 bytes". Active one-second rotation is now
white on red in both normal and expert modes, overriding queued blue temporarily.
After expiry the cached cell restores blue if still selected, otherwise its
scope/pinned/black background. Directory rows keep their D marker and path but
omit size text; actual files retain formatted size, including zero-byte files.
Updated local scanner help; no backend/storage/event changes. Only this file.
Validation: both scan modes retain white/red rotation and restore blue or scope
background after expiry; directories omit size while zero-byte files retain it.
The partial-cell rendering regression and syntax check passed. No Rust validation.

2026-10-15 follow-up: "refactor map buckets view to custom render or
FormattedTextControl to speedup update". Extracted BucketRowRenderer behind the
virtual MapControl. It retains dirty-cell/LRU behavior but emits compact adjacent
style runs instead of one fragment per cell. Only changed rows are compacted;
unchanged rows reuse their fragment list. Animation time is sampled once per
content frame, with deadline checks once per cached row/frame. Generic
FormattedTextControl is intentionally avoided because its fragment splitting,
full-text hashing and preferred-size calculations would lose map virtualization.
Controls, colors, projection thread, storage/events and backend stay unchanged.
Only this file changes under the single-file requirement.
Validation: local 200x60 idle redraw benchmark, 10k buckets, blue ranges and 30
measured warm frames: median complete prompt_toolkit redraw 26.610ms before /
23.340ms after. Map output for 197x30 cells fell from 5910 to 90 fragments.
This is a synthetic local UI measurement, not disk throughput. Partial-cell,
compact uniform-row, animation/expiry, cache bound, expert scan/shutdown and
80/120/150-column navigation regressions passed, as did the three PT integration
checks. No physical terminal benchmark or Rust parity validation.

2026-10-15: main Shift+R clears the current directory's saved map/resume positions
via ScanStore.delete, retaining verification data and other scopes. Main help and
root legend list the shortcut. See FEATURE-realtime-drive-scanner.md for the
prompt, contracts and memory/SQLite keypress/reopen validation.

"""

import argparse
import asyncio
import base64
from collections import OrderedDict
from dataclasses import asdict, replace
import math
from queue import Empty, Queue
import random
import re
import shutil
import subprocess
from threading import Event, Lock, Thread
import time
from datetime import datetime
import os
from pathlib import Path
import shlex

try:
    from prompt_toolkit import Application
    from prompt_toolkit.application.current import get_app
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.filters import Condition, has_focus
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, VSplit, Window
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.output import ColorDepth
    from prompt_toolkit.layout.controls import FormattedTextControl, UIContent, UIControl
    from prompt_toolkit.layout.margins import ScrollbarMargin
    from prompt_toolkit.mouse_events import MouseEventType
    from prompt_toolkit.styles import DynamicStyle, Style
    from prompt_toolkit.utils import get_cwidth
    from prompt_toolkit.widgets import Button, Frame, TextArea
except ImportError as exc:
    raise SystemExit('Install prompt_toolkit: python -m pip install prompt_toolkit') from exc

from drive import load_log
from livelog2 import LiveLog
from vfs import VirtualFS, aliases, disabled_prefixes, format_size, prefixes, get_stat_info
from vfs.paths import get_real_path
from vfs.scanner import (DriveScanner, FileMap, Pagination, ScanControls, ScanEntry,
                         ScanStats, ScanStore, ScanTiming)


async def background_call(function, *args, **kwargs):
    """Run blocking work without coupling screen lifecycle to a global executor."""
    done = Event()
    outcome = []
    def work():
        try:
            outcome.append((True, function(*args, **kwargs)))
        except BaseException as exc:
            outcome.append((False, exc))
        finally:
            done.set()
    thread = Thread(target=work, name='drive-pt-background', daemon=True)
    thread.start()
    while not done.is_set():
        await asyncio.sleep(.01)
    success, value = outcome[0]
    if not success:
        raise value
    return value


def format_elapsed(seconds):
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f'{hours}:{minutes:02}:{seconds:02}'
    return f'{minutes}:{seconds:02}'


def safe_text(value):
    """Keep paths on one terminal line without interpreting control characters."""
    return ''.join(c if c.isprintable() else '?' for c in str(value))


def fit(text, width):
    text = safe_text(text)
    result, used = [], 0
    for char in text:
        cells = get_cwidth(char)
        if used + cells > width:
            break
        result.append(char)
        used += cells
    return ''.join(result) + ' ' * max(0, width - used)


class TitleControl(UIControl):
    def create_content(self, width, height):
        title = 'drive.py — file manager'
        text = ' ' * max(0, (width - get_cwidth(title)) // 2) + title
        return UIContent(get_line=lambda _: [('', text)], line_count=1,
                         show_cursor=False)


class FilesControl(UIControl):
    def __init__(self, browser, header=False):
        self.browser = browser
        self.header = header

    def is_focusable(self):
        return not self.header

    def create_content(self, width, height):
        browser = self.browser
        # Reserve metadata first; degrade gracefully in very small terminals.
        size_width, dups_width = browser.metadata_widths
        if width < size_width + dups_width + 5:
            size_width = min(size_width, max(0, (width - 2) // 2))
            dups_width = min(dups_width, max(0, width - size_width - 2))
        name_width = max(0, width - size_width - dups_width - 2)
        browser.columns = (name_width, size_width, dups_width)
        if self.header:
            return UIContent(get_line=lambda _: browser.column_header(),
                             line_count=1, show_cursor=False)

        def line(index):
            if not browser.rows:
                return [('class:muted', fit('(empty)', width))]
            row = browser.rows[index]
            selected = index == browser.selected
            base = 'class:selected' if selected else 'class:' + row['color']
            label = fit(row['label'], name_width)
            fragments = []
            if label and browser.display_mode != 3:
                fragments.append((base + ' class:' + row['indicator'], label[0]))
                fragments.append((base, label[1:]))
            else:
                fragments.append((base, label))
            fragments.append((base, ' ' + fit(' ' + row['size'], size_width) +
                              ' ' + fit(' ' + row['dups'], dups_width)))
            return fragments

        return UIContent(get_line=line, line_count=max(1, len(browser.rows)),
                         cursor_position=Point(x=0, y=browser.selected), show_cursor=False)

    def mouse_handler(self, event):
        if self.header:
            return NotImplemented
        browser = self.browser
        if event.event_type == MouseEventType.SCROLL_DOWN:
            browser.move(3)
        elif event.event_type == MouseEventType.SCROLL_UP:
            browser.move(-3)
        elif event.event_type == MouseEventType.MOUSE_UP:
            browser.app.layout.focus(self)
            browser.selected = min(event.position.y, max(0, len(browser.rows) - 1))
            browser.app.invalidate()
        else:
            return NotImplemented


class InfoLexer(Lexer):
    """Color only explicit status markers; filenames remain literal text."""
    def __init__(self):
        self.colors = {}

    def lex_document(self, document):
        colors = self.colors.copy()

        def line(index):
            if index >= len(document.lines):
                return []
            text = document.lines[index]
            if index == 0:
                return [('class:selected', text)]
            if index in colors and text.startswith('●'):
                return [('class:' + colors[index], text[:1]), ('', text[1:])]
            return [('', text)]

        return line


THEMES = [
    {'': 'bg:#12488b #eeeeec', 'border': '#d0cfcc',
     'info-header': 'bg:#3465a4 #ffff55 bold',
     'header': 'bg:#06989a #2e3436', 'table-header': 'bg:#3d6ba7 #ffff55 bold',
     'files-pane': 'bg:#1d508f #eeeeec', 'info-pane': 'bg:#12488b #eeeeec', 'selected': 'bg:#06989a #ffffff nobold noreverse'},
    {'': 'bg:#0000aa #ffffff', 'border': '#55ffff',
     'header': 'bg:#0000aa #ffff55 bold', 'table-header': 'bg:#0000aa #ffff55 bold',
     'files-pane': 'bg:#0000aa #ffffff', 'info-pane': 'bg:#0000aa #ffffff', 'selected': 'bg:#00aaaa #000000 nobold noreverse'},
    {'': 'bg:#1e1e1e #eeeeee', 'border': '#6699aa',
     'header': 'bg:#333333 #ffff55 bold', 'table-header': 'bg:#333333 #ffff55 bold',
     'files-pane': 'bg:#1e1e1e #eeeeee', 'info-pane': 'bg:#1e1e1e #eeeeee', 'selected': 'bg:#405060 #ffffff nobold noreverse'},
]


class DriveBrowser:
    def __init__(self, vfs, *, path=None, input=None, output=None):
        self.vfs = vfs
        self.selected = 0
        self.display_mode = 1
        self.theme = 0
        self.styles = [Style.from_dict({**theme,
            'green': '#98e024', 'red': '#ff5555', 'orange': '#ff8700',
            'frame.border': theme['border'],
            'scrollbar.background': 'bg:#156f8f',
            'scrollbar.button': 'bg:#06989a',
            'info-header': theme.get('info-header', theme['table-header']),
            'scan-input': theme['table-header'] + ' #ffffff nobold noreverse',
            'scan-input-focused': theme['selected'],
            'yellow': '#ffff55', 'white': '#ffffff', 'muted': '#aaaaaa',
        }) for theme in THEMES]
        self.rows = []
        self.history = []
        self.screen_stack = []
        self.actions = []
        self.info_paths = {}
        self.scanners = []
        self.columns = (20, 8, 4)
        self.metadata_widths = (5, 7)
        self.control = FilesControl(self)
        self.files = Window(self.control, right_margins=[ScrollbarMargin()],
                            wrap_lines=False, always_hide_cursor=True)
        self.info_lexer = InfoLexer()
        self.info = TextArea(read_only=True, scrollbar=True, wrap_lines=True,
                             lexer=self.info_lexer)
        self.info.window.right_margins = [ScrollbarMargin()]
        if path is None:
            self.vfs.start_in_current_directory()
        else:
            self.vfs.start_in_current_directory(path)
        self.refresh()
        bindings = KeyBindings()
        main_focused = Condition(lambda: not self.screen_stack)
        files_focused = has_focus(self.control)

        def bind(keys, handler, **kwargs):
            kwargs_filter = kwargs.pop('filter', None)
            for key in keys:
                bindings.add(key, filter=main_focused & (kwargs_filter if kwargs_filter is not None else Condition(lambda: True)), **kwargs)(handler)

        bindings.add('q', eager=True)(lambda event: event.app.exit())
        bindings.add('c-c')(lambda event: event.app.exit())
        bind(['a'], lambda event: self.push(ActionsView(self)))
        bind(['s'], lambda event: self.push(ScannerView(self)))
        bind(['R'], lambda event: self.reset_current_map())
        bind(['h'], lambda event: self.push(HelpView(self, 'File manager help', main_help(self.display_mode))))
        bind(['delete'], lambda event: self.queue_remove())
        bind(['s-delete'], lambda event: self.queue_remove(all_duplicates=True))
        bind(['c-x'], lambda event: self.copy_info())
        bind(['up'], lambda event: self.move(-1), filter=files_focused)
        bind(['down'], lambda event: self.move(1), filter=files_focused)
        bind(['pageup'], lambda event: self.move(-self.page_size()), filter=files_focused)
        bind(['pagedown'], lambda event: self.move(self.page_size()), filter=files_focused)
        bind(['home'], lambda event: self.move(-len(self.rows)), filter=files_focused)
        bind(['end'], lambda event: self.move(len(self.rows)), filter=files_focused)
        bind(['enter', 'right'], lambda event: self.open(), filter=files_focused)
        bind(['escape'], lambda event: self.parent())
        bind(['backspace'], lambda event: self.parent(), eager=True)
        bind(['left'], lambda event: self.parent(), filter=files_focused)
        bind(['tab', 's-tab'], lambda event: event.app.layout.focus(
            self.info if event.app.layout.has_focus(self.control) else self.control))
        bind(['n'], lambda event: self.cycle_mode())
        bind(['t'], lambda event: self.cycle_theme())
        bind(['f5'], lambda event: self.refresh(self.current_name()))
        layout = HSplit([
            Window(TitleControl(), height=1, style='class:header'),
            VSplit([
                Frame(VSplit([
                    Window(width=1),
                    HSplit([
                        Window(FilesControl(self, header=True), height=1,
                               style='class:table-header',
                               right_margins=[ScrollbarMargin()], always_hide_cursor=True),
                        self.files,
                    ]),
                ]), style='class:files-pane',
                      width=lambda: Dimension.exact(get_app().output.get_size().columns // 2)),
                Frame(HSplit([
                    Window(height=1),
                    VSplit([
                        Window(width=1),
                        HSplit([
                            Window(FormattedTextControl(' Info'), height=1,
                                   style='class:info-header'),
                            self.info,
                        ]),
                        Window(width=1),
                    ]),
                ]), style='class:info-pane',
                      width=lambda: Dimension.exact((get_app().output.get_size().columns + 1) // 2)),
            ]),
        ])
        self.main_layout = Layout(layout, focused_element=self.control)
        self.app = Application(layout=self.main_layout,
                               key_bindings=bindings, full_screen=True, mouse_support=True,
                               style=DynamicStyle(self.style), color_depth=ColorDepth.DEPTH_24_BIT,
                               input=input, output=output)

    def style(self):
        # A new Style on each render changes its invalidation hash and forces
        # prompt_toolkit to repaint the entire screen instead of changed cells.
        return self.styles[self.theme]

    def column_header(self):
        name, size, dups = self.columns
        return [('class:table-header', fit('Name', name) + ' ' + fit(' Size', size) + ' ' + fit(' Dups', dups))]

    def current_name(self):
        return self.rows[self.selected]['name'] if self.rows else None

    def refresh(self, target=None):
        entries = [(node.name, node) for node in self.vfs.list_nodes()]
        parent = self.vfs.get('..')
        if parent is not None:
            entries.insert(0, ('..', parent))
        self.rows = []
        for name, node in entries:
            status = node.info.get('status', 'tracked') if name != '..' else 'tracked'
            exists = self.vfs.get_full_info(node, True).get('exists', False)
            indicator = 'green' if exists else 'red'
            if self.display_mode == 1 and status == 'new':
                indicator = 'orange'
            color = {'new': 'yellow', 'deleted': 'red'}.get(status, 'white') if self.display_mode == 2 else 'white'
            marker = {'new': '*', 'deleted': '!'}.get(status, ' ') if self.display_mode == 3 else '●'
            count = node.total_files if node.is_dir else len(self.vfs.get_hash_dups(node.info.get('hashinfo')))
            self.rows.append(dict(name=name, node=node, color=color, indicator=indicator,
                                  label=f'{marker} {"📁" if node.is_dir else "📄"} {name}',
                                  size=format_size(node.size, int(not node.is_dir)).strip(),
                                  dups=f'({count})'))
        self.metadata_widths = (max([4] + [len(row['size']) for row in self.rows]) + 1,
                                max([4] + [len(row['dups']) for row in self.rows]) + 3)
        self.selected = next((i for i, row in enumerate(self.rows) if row['name'] == target), 0)
        self.show_info(directory=True)
        if hasattr(self, 'app'):
            self.app.invalidate()

    def page_size(self):
        return max(1, self.files.render_info.window_height - 1) if self.files.render_info else 10

    def move(self, delta):
        self.selected = max(0, min(max(0, len(self.rows) - 1), self.selected + delta))
        self.app.invalidate()

    def open(self):
        name = self.current_name()
        if name == '..':
            self.parent()
        elif name is not None and self.rows[self.selected]['node'].is_dir:
            self.history.append((self.vfs.pwd(), name))
            self.vfs.enter(name)
            self.refresh()
        else:
            self.show_info()

    def parent(self):
        if self.vfs.get('..') is None:
            return
        name = self.vfs.get_cwd().name
        self.vfs.enter('..')
        if self.history and self.history[-1][0] == self.vfs.pwd():
            _, name = self.history.pop()
        self.refresh(name)
        self.app.layout.focus(self.control)

    def cycle_mode(self):
        self.display_mode = self.display_mode % 3 + 1
        self.refresh(self.current_name())

    def cycle_theme(self):
        self.theme = (self.theme + 1) % len(THEMES)
        self.app.invalidate()

    def show_info(self, directory=False):
        self.info_lexer.colors = {}
        self.info_paths = {}
        if directory and self.vfs.pwd() == "/":
            lines = ["/", "╭────────╮  drive.py v0.98", "│ ━━━━ ● │  File Manager",
                     "╰────────╯  Explore • Compare • Keep", "", "h: Open help view", "",
                     *main_help(self.display_mode)]
            self.info.lexer = MarkupLexer()
            self.info.text = plain_markup("\n".join(lines))
            self.info.lexer.fragments = markup_lines(lines)
            self.info.buffer.cursor_position = 0
            return
        self.info.lexer = self.info_lexer
        if not self.rows and not directory:
            self.info.text = self.vfs.pwd() + '\n\nNo files.'
            return
        row = self.rows[self.selected] if self.rows else None
        node = self.vfs.get_cwd() if directory else row['node']
        info = self.vfs.get_full_info(node)

        def timestamp(key):
            value = info.get(key)
            try:
                return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S') if value is not None else ''
            except (ValueError, OverflowError, OSError):
                return ''

        self.info_lexer.colors[1] = (
            'green' if info.get('exists') else 'red') if directory else row['indicator']
        size = format_size(node.size, 0).strip()
        lines = [node.id or '/', '●', 'Size:   ' + size,
                 'Created:  ' + timestamp('created'),
                 'Modified: ' + timestamp('modified')]
        if not node.is_dir:
            lines.insert(2, 'Name: ' + node.name)
            hashes = node.info.get('hashinfo') or ''
            lines.extend([', '.join(sorted(hashes)) if isinstance(hashes, set) else str(hashes), '',
                          f'Other Duplicates ({len(info.get("dups", []))}):'])
            for path, state in zip(info.get('dups', []), info.get('dups_states', [])):
                self.info_lexer.colors[len(lines)] = 'green' if state.get('exists') else 'red'
                self.info_paths[len(lines)] = path
                lines.append('● ' + path)
            if info.get('exists') and info.get('size') != node.size:
                lines.append(f'Current disk size: {info.get("size")} bytes')
        self.info.text = '\n'.join(safe_text(line) for line in lines)
        self.info.buffer.cursor_position = 0

    def push(self, screen):
        self.screen_stack.append((screen, self.app.layout))
        self.app.layout = Layout(screen.container, focused_element=screen.focus)
        screen.start()
        self.app.invalidate()

    def pop(self, screen):
        if not self.screen_stack or self.screen_stack[-1][0] is not screen:
            return
        _, layout = self.screen_stack.pop()
        self.app.layout = layout
        self.app.invalidate()

    def reset_current_map(self):
        path = self.vfs.pwd().rstrip('/') or '/'
        store = ScanStore(self.vfs.db)
        store.delete('map', path)
        store.delete('position', path)
        self.info_paths = {}
        self.info_lexer.colors = {}
        self.info.lexer = self.info_lexer
        self.info.text = safe_text(path) + '\n\nSaved map and scan resume positions cleared.'
        self.info.buffer.cursor_position = 0
        self.app.invalidate()

    def selected_path(self):
        if self.app.layout.has_focus(self.info):
            return self.info_paths.get(self.info.buffer.document.cursor_position_row)
        if self.rows and self.current_name() != '..':
            return self.rows[self.selected]['node'].id
        return None

    def queue_remove(self, all_duplicates=False):
        path = self.selected_path()
        if not path:
            return
        paths = [path]
        if all_duplicates:
            pending = [path]
            visited = set()
            files = 0
            while pending and files < 100_000:
                current = pending.pop()
                node = self.vfs.get_from_path(current)
                if node is None:
                    continue
                if node.is_dir:
                    real = os.path.realpath(get_real_path(current))
                    if real in visited or os.path.islink(get_real_path(current)):
                        continue
                    visited.add(real)
                    children = self.vfs.list_nodes(node)
                    paths.extend(child.id for child in children)
                    pending.extend(child.id for child in children)
                else:
                    files += 1
                    paths.extend(self.vfs.get_full_info(node).get('dups', []))
        existing = set(self.actions)
        for item in paths:
            action = ('remove', item)
            if action not in existing:
                self.actions.append(action)
                existing.add(action)
        self.app.invalidate()

    def copy_info(self):
        text = self.info.text
        async def copy():
            try:
                command = next((command for command in (['wl-copy'], ['xclip', '-selection', 'clipboard'],
                               ['xsel', '--clipboard', '--input']) if shutil.which(command[0])), None)
                if command:
                    await background_call(subprocess.run, command, input=text,
                                                     text=True, capture_output=True, check=True)
                else:
                    encoded = base64.b64encode(text.encode()).decode()
                    from prompt_toolkit.application import run_in_terminal
                    await run_in_terminal(lambda: (self.app.output.write_raw('\x1b]52;c;' + encoded + '\x07'),
                                                    self.app.output.flush()))
            except (OSError, subprocess.CalledProcessError) as exc:
                self.push(HelpView(self, 'Clipboard error', [str(exc)]))
        self.app.create_background_task(copy())

    def run(self):
        try:
            self.app.run()
        finally:
            # Cancellation also wakes queue-backpressured workers before closing SQLite.
            for scanner in self.scanners:
                scanner.stop.set()
                scanner.controls.wake.set()
                scanner.projection_wake.set()
            for scanner in self.scanners:
                if scanner.projection_thread is not None:
                    scanner.projection_thread.join()
                if scanner.worker is not None:
                    scanner.worker.join()
                if scanner.mode_thread is not None:
                    scanner.mode_thread.join()
                if scanner.order_thread is not None:
                    scanner.order_thread.join()
                scanner.drain_all()
                scanner.save()




def main_help(display_mode):
    legend = ([
        '[white]Files in database and on disk[/white]',
        '[white]* New: on disk only[/white]',
        '[white]! Deleted: in database only[/white]',
    ] if display_mode == 3 else [
        '[green]●[/green] Available in database and on disk',
        '[red]●[/red] Not found on disk',
        '[dark_orange]●[/dark_orange] New file or directory: not in database',
    ] if display_mode == 1 else [
        '[green]●[/green] Available',
        '[red]●[/red] Not found',
        '[yellow]Yellow names[/yellow]: new paths; red names: missing paths',
    ])
    return [
        '[bold]Legend — current display mode[/bold]', *legend,
        '[dark_orange]?[/dark_orange] Maybe available; available last time',
        '[red]R[/red] In remove queue',
        '[red]D[/red] Deleted',
        '', '[bold]Shortcuts[/bold]',
        '[#ff8800]h / Esc[/#ff8800] (in help): Close help',
        '[#ff8800]Enter[/#ff8800]: Open directory or view file info',
        '[#ff8800]Esc / Backspace[/#ff8800] (main view): Go to parent directory',
        '[#ff8800]Arrows / Page Up / Page Down[/#ff8800]: Navigate the focused table',
        '[#ff8800]Ctrl+X[/#ff8800]: Copy info panel text to clipboard',
        '[#ff8800]t[/#ff8800]: Cycle MC Default, MC Blue and Textual Dark themes',
        '[#ff8800]n[/#ff8800]: Cycle circles, colored names and monochrome display',
        '[#ff8800]s[/#ff8800]: Open scanner/map for the current directory',
        '[#ff8800]Shift+R[/#ff8800]: Clear saved map and resume positions for the current directory',
        '[#ff8800]q[/#ff8800]: Quit',
        '', '[bold]Removal queue[/bold]',
        '[#ff8800]Delete[/#ff8800]: Queue selected file for removal',
        '[#ff8800]Shift+Delete[/#ff8800]: Queue file and all duplicates for removal',
        '[#ff8800]a[/#ff8800]: Open Actions to review operations',
        'In Actions: [#ff8800]x[/#ff8800] clears the queue; [#ff8800]e[/#ff8800] exports actions/action*.sh',
        'Use the Apply button to apply queued operations',
        '', '[bold]File table[/bold]',
        'Size and Dups remain visible beside clipped long names',
        'Directory Dups values retain their total-file counts',
        'The vertical scrollbar is always visible',
    ]

SCANNER_HELP = [
    '[#ff8800]q[/#ff8800]: Quit the app from any view',
    '[bold]Scanning[/bold]',
    'On open: lite → medium → heavy once, then all modes stop',
    'Changing a scan mode cancels the automatic startup sequence',
    '[#ff8800]1 / 2 / 3[/#ff8800]: Independently run/stop lite, medium, heavy',
    '[green]RUN[/green] / [red]STOP[/red]: enabled/paused mode',
    'Lite: discover paths and build buckets; directories have D state',
    'Medium: discover new paths and verify file presence/type/size without checksums',
    'Heavy: compare checksums; verified new files enter VFS and show green in main',
    'Heavy scanning keeps your map cursor and file page in place',
    'Directories are skipped by medium/heavy verification',
    'Start/stop resumes each mode at its saved pending path',
    '[#ff8800]Shift+1 / Shift+2 / Shift+3[/#ff8800] (also [#ff8800]! / @ / #[/#ff8800]): start from cursor bucket',
    '[#ff8800]r[/#ff8800]: Toggle known-file disk metadata reads in lite',
    '[#ff8800]t[/#ff8800]: Toggle heavy new-first/all priority within buckets',
    '[#ff8800]j[/#ff8800]: Heavy normal (sequential) / expert (selector queue)',
    'Expert tick: pick one random starting bucket, then mark 1–20 following buckets blue',
    '? buckets first; skip blocked/occupied buckets, wrap at end; 1–20 added per tick',
    'Skip fully green buckets until all file buckets are green; mixed ?/green still count',
    'Background additions: random 0.2–1s; empty work queue refills immediately',
    'Add new ranges while earlier ranges scan; total blue can exceed 20',
    'Completed buckets restore their normal background; pause keeps pending work',
    'Changing j also cancels startup; startup heavy is a finite normal pass',
    '', '[bold]Symbols[/bold]',
    '[white]D[/white] Directory',
    '[white]?[/white] Unverified/new file',
    '[green]?[/green] Bucket has both unverified and verified files',
    '[white]U[/white] Legacy new state',
    '[red]U[/red] Missing file',
    '[green]●[/green] Verified by the latest metadata/checksum check',
    '[#ff8800]M[/#ff8800] Modified file',
    '[white on red]\\ | / -[/white on red] Recent map update in all modes; red overrides blue until animation ends; S n% is file progress',
    '', '[bold]Map and settings[/bold]',
    '[#ff8800]m[/#ff8800]: Count/size bucket packing',
    '[#ff8800]v[/#ff8800]: Fixed/scroll packing',
    '[#ff8800]Arrows / Page Up / Page Down[/#ff8800]: Move map cursor',
    '[#ff8800]Right[/#ff8800] at last bucket: follow new buckets at >',
    '[#ff8800]Right[/#ff8800] keeps follow mode; other arrows, Page Up/Down or real-bucket click exit',
    'Paths/bucket and MiB/bucket: edit limits; [#ff8800]Enter[/#ff8800] applies',
    '', '[bold]File list and pages[/bold]',
    'Click a status count to filter; click it again or All to remove filter',
    '[#ff8800]][/#ff8800] in map or file list: select /a, then /a/b for selected file /a/b/c',
    '[#ff8800][[/#ff8800] moves back through parent directories',
    'Both directory scope keys wrap at the ends of the ancestor chain',
    'The matching directory prefix in file paths is gold; the remaining name keeps its normal color',
    'Matching buckets get a random background; symbol foregrounds stay unchanged',
    '[#ff8800]f[/#ff8800]: Fix matching bucket colors; [#ff8800]d[/#ff8800]: Clear all colors',
    '[#ff8800]c[/#ff8800]: Clear fixed colors, keeping the active directory scope',
    'Fixed colors persist through scope changes and saved-map reopening',
    'The active directory scope previews over fixed colors; leaving it reveals the saved colors',
    '[#ff8800]Left / Right[/#ff8800] in the file list: horizontal pan; scrollbar also pans',
    '[#ff8800]Up[/#ff8800] at first row: previous page, last file',
    '[#ff8800]Down[/#ff8800] at last row: next page, first file',
    'Page buttons/jumps or slider: seek; horizontal position is preserved',
    'Slider: [#ff8800]Left/Right[/#ff8800] step; [#ff8800]Home/End[/#ff8800] select first/last page',
    '', '[bold]Info and saved state[/bold]',
    'Paths/s uses completed visits over 5 seconds; MB/s–PB/s shows bytes hashed over 1 second',
    'Hash speed updates during files about every 0.1s and decays to zero after idle; totals stay cumulative',
    'Total paths/size count repeat visits; bucket N/total tracks the viewport',
    'Expert selected counts queued and processing buckets',
    'Mode time starts at zero on start/resume; map total accumulates processing time across all runs',
    'Pauses/watch delays are excluded from both timers',
    'The Lite/Medium/Heavy controls line ends with mode / map time as M:SS or H:MM:SS (hours can exceed 24)',
    'Map time totals persist across reopening; Shift+R in main resets them with the map',
    'Map settings, selection, filter and per-mode positions save per path',
    '[#ff8800]s / Esc[/#ff8800] (scanner): Close scanner; [#ff8800]h[/#ff8800]: Help',
    '[#ff8800]h / Esc[/#ff8800] (help) or Close button: Return to scanner',
]


# Prompt-toolkit screens share backend contracts; none import Textual widgets.
MARKUP_TAG = re.compile(r'\[(/?)(#[0-9a-fA-F]{6}|bold|white on red|white|green|red|yellow|dark_orange)\]')


def markup_lines(lines):
    result = []
    for line in lines:
        fragments, stack, offset = [], [], 0
        for match in MARKUP_TAG.finditer(line):
            if match.start() > offset:
                fragments.append((' '.join(stack), line[offset:match.start()]))
            if match[1]:
                if stack:
                    stack.pop()
            else:
                tag = match[2]
                style = {'white on red': 'fg:#ffffff bg:#ff0000',
                         'dark_orange': 'class:orange', 'green': 'class:green',
                         'red': 'class:red', 'white': 'class:white',
                         'yellow': 'class:yellow'}.get(tag, tag)
                stack.append(style)
            offset = match.end()
        fragments.append((' '.join(stack), line[offset:]))
        result.append(fragments)
    return result


def plain_markup(text):
    return MARKUP_TAG.sub('', text)


class MarkupLexer(Lexer):
    def __init__(self, lines=()):
        self.fragments = markup_lines(lines)

    def lex_document(self, document):
        fragments = self.fragments
        return lambda line: fragments[line] if line < len(fragments) else []


class PTScreen:
    def __init__(self, browser):
        self.browser = browser
        self.keys = KeyBindings()

    def start(self):
        pass

    def close(self):
        self.browser.pop(self)

    def bind(self, keys, callback, **kwargs):
        for key in keys:
            self.keys.add(key, **kwargs)(lambda event, callback=callback: callback())

    def invalidate(self):
        self.browser.app.invalidate()


class HelpView(PTScreen):
    def __init__(self, browser, title, lines):
        super().__init__(browser)
        self.text = TextArea(text=plain_markup('\n'.join(lines)), lexer=MarkupLexer(lines),
                             read_only=True, scrollbar=True, wrap_lines=True)
        self.focus = self.text
        self.bind(['h', 'escape'], self.close, eager=True)
        self.bind(['tab'], lambda: browser.app.layout.focus_next())
        self.bind(['s-tab'], lambda: browser.app.layout.focus_previous())
        self.container = HSplit([
            Frame(self.text, title=title, style='class:info-pane'),
            Button('Close', handler=self.close),
        ], key_bindings=self.keys)


class RowsControl(UIControl):
    """Virtual table with colored fragments and persistent horizontal pan."""
    def __init__(self, rows, changed=None, selected=None, resized=None):
        self.get_rows = rows
        self.changed = changed or (lambda: None)
        self.on_selected = selected
        self.on_resize = resized
        self.index = 0
        self.pan = 0
        self.width = 1
        self.height = 1

    def is_focusable(self):
        return True

    def create_content(self, width, height):
        if (width, height) != (self.width, self.height):
            self.width, self.height = width, height
            if self.on_resize:
                self.on_resize()
        rows = self.get_rows()
        self.index = max(0, min(self.index, len(rows) - 1))

        def line(index):
            fragments = rows[index] if rows else [('', '(empty)')]
            result, offset = [], 0
            for style, text in fragments:
                for char in safe_text(text):
                    cells = get_cwidth(char)
                    if offset >= self.pan:
                        result.append((('class:selected ' if index == self.index else '') + style, char))
                    elif offset + cells > self.pan:
                        result.append(('', ' '))
                    offset += cells
            return result
        return UIContent(get_line=line, line_count=max(1, len(rows)),
                         cursor_position=Point(x=0, y=self.index), show_cursor=False)

    def move(self, delta):
        rows = self.get_rows()
        self.index = max(0, min(max(0, len(rows) - 1), self.index + delta))
        self.changed()

    def mouse_handler(self, event):
        if event.event_type == MouseEventType.SCROLL_DOWN:
            self.move(3)
        elif event.event_type == MouseEventType.SCROLL_UP:
            self.move(-3)
        elif event.event_type == MouseEventType.MOUSE_UP:
            get_app().layout.focus(self)
            self.index = max(0, min(max(0, len(self.get_rows()) - 1), event.position.y))
            self.changed()
            if self.on_selected:
                self.on_selected()
        else:
            return NotImplemented
        get_app().invalidate()


def table_bindings(screen, control):
    focused = has_focus(control)
    for key, delta in [('up', -1), ('down', 1), ('pageup', -10), ('pagedown', 10)]:
        screen.bind([key], lambda delta=delta: control.move(delta), filter=focused)
    screen.bind(['home'], lambda: control.move(-len(control.get_rows())), filter=focused)
    screen.bind(['end'], lambda: control.move(len(control.get_rows())), filter=focused)
    screen.bind(['left'], lambda: setattr(control, 'pan', max(0, control.pan - 4)), filter=focused)
    screen.bind(['right'], lambda: setattr(control, 'pan', control.pan + 4), filter=focused)

class FilterControl(UIControl):
    """Keep long status-filter rows reachable at narrow terminal widths."""
    def __init__(self, screen):
        self.screen = screen
        self.pan = 0
        self.width = 1
        self.fragments = []

    def is_focusable(self):
        return True

    def create_content(self, width, height):
        self.width = max(1, width)
        self.fragments = self.screen.filters_text()
        total = sum(get_cwidth(text) for _, text, _ in self.fragments)
        self.pan = max(0, min(self.pan, max(0, total - width)))
        fragments, offset = [], 0
        for style, text, handler in self.fragments:
            for char in text:
                if offset >= self.pan:
                    fragments.append((style, char, handler))
                offset += get_cwidth(char)
        return UIContent(get_line=lambda _: fragments, line_count=1, show_cursor=False)

    def mouse_handler(self, event):
        if event.event_type in (MouseEventType.SCROLL_DOWN, MouseEventType.SCROLL_UP):
            self.pan = max(0, self.pan + (8 if event.event_type == MouseEventType.SCROLL_DOWN else -8))
        elif event.event_type == MouseEventType.MOUSE_UP:
            offset = 0
            for _, text, handler in self.fragments:
                end = offset + get_cwidth(text)
                if offset <= event.position.x + self.pan < end:
                    handler(event)
                    break
                offset = end
            get_app().layout.focus(self)
        else:
            return NotImplemented
        self.screen.invalidate()


class HorizontalBar(UIControl):
    def __init__(self, table):
        self.table = table
        self.width = 1
        self.maximum = 0
        self.dragging = False

    def is_focusable(self):
        return True

    def create_content(self, width, height):
        self.width = max(1, width)
        total = max((sum(get_cwidth(text) for _, text in row) for row in self.table.get_rows()), default=0)
        self.maximum = max(0, total - self.table.width)
        self.table.pan = max(0, min(self.table.pan, self.maximum))
        if not self.maximum:
            text = '─' * width
        else:
            position = round(self.table.pan * (width - 1) / self.maximum)
            text = '─' * position + '●' + '─' * (width - position - 1)
        return UIContent(get_line=lambda _: [('class:muted', text)], line_count=1, show_cursor=False)

    def mouse_handler(self, event):
        if event.event_type == MouseEventType.MOUSE_DOWN:
            self.dragging = True
        elif event.event_type not in (MouseEventType.MOUSE_UP, MouseEventType.MOUSE_MOVE):
            return NotImplemented
        if self.dragging or event.event_type == MouseEventType.MOUSE_UP:
            self.table.pan = round(max(0, min(event.position.x, self.width - 1)) * self.maximum / max(1, self.width - 1))
            get_app().layout.focus(self)
            get_app().invalidate()
        if event.event_type == MouseEventType.MOUSE_UP:
            self.dragging = False


def horizontal_keys(screen, bar):
    focused = has_focus(bar)
    screen.bind(['left'], lambda: setattr(bar.table, 'pan', max(0, bar.table.pan - 4)), filter=focused)
    screen.bind(['right'], lambda: setattr(bar.table, 'pan', min(bar.maximum, bar.table.pan + 4)), filter=focused)
    screen.bind(['home'], lambda: setattr(bar.table, 'pan', 0), filter=focused)
    screen.bind(['end'], lambda: setattr(bar.table, 'pan', bar.maximum), filter=focused)


class ActionsView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        self.message = ''
        self.cached_rows = []
        self.refresh_rows()
        self.table = RowsControl(self.rows)
        self.focus = self.table
        self.horizontal = HorizontalBar(self.table)
        horizontal_keys(self, self.horizontal)
        table_bindings(self, self.table)
        self.bind(['escape'], self.close)
        self.bind(['x'], self.clear)
        self.bind(['e'], self.export)
        self.bind(['t'], browser.cycle_theme)
        self.bind(['tab'], lambda: browser.app.layout.focus_next())
        self.bind(['s-tab'], lambda: browser.app.layout.focus_previous())
        self.container = HSplit([
            Window(FormattedTextControl(lambda: f'Actions {len(browser.actions)} — {self.message}'), height=1),
            Window(FormattedTextControl('Operation  Path'), height=1, style='class:table-header'),
            Window(self.table, right_margins=[ScrollbarMargin()], wrap_lines=False),
            Window(self.horizontal, height=1),
            VSplit([Button('Close', self.close), Button('Clear', self.clear),
                    Button('Export .sh', self.export), Button('Apply', self.apply)]),
        ], key_bindings=self.keys, style='class:info-pane')

    def rows(self):
        return self.cached_rows

    def refresh_rows(self):
        result = []
        for op, path in self.browser.actions:
            exists = get_stat_info(path).get('exists')
            result.append([('', f'{op:<10} '), ('class:green' if exists else 'class:red', '●'),
                           ('', ' ' + safe_text(path))])
        self.cached_rows = result

    def clear(self):
        self.browser.actions.clear()
        self.refresh_rows()
        self.table.index = 0
        self.invalidate()

    def export(self):
        try:
            directory = Path('actions')
            directory.mkdir(exist_ok=True)
            candidate = directory / 'action.sh'
            index = 0
            while True:
                try:
                    stream = candidate.open('x', encoding='utf-8')
                    break
                except FileExistsError:
                    index += 1
                    candidate = directory / f'action{index:04d}.sh'
            with stream:
                stream.write('#!/usr/bin/env bash\nset -euo pipefail\nREMOVE=0\n'
                             'if [[ "${1:-}" == "-r" ]]; then REMOVE=1; fi\n'
                             'remove() {\n  if [[ -e "$1" || -L "$1" ]]; then\n'
                             '    printf "remove %s\\n" "$1"\n'
                             '    if [[ "$REMOVE" == 1 ]]; then rm -rf -- "$1"; fi\n'
                             '  fi\n}\necho "Run with -r to remove"\n')
                for op, path in self.browser.actions:
                    if op == 'remove':
                        stream.write('remove ' + shlex.quote(get_real_path(path)) + '\n')
            candidate.chmod(candidate.stat().st_mode | 0o111)
            self.message = f'Exported {candidate} (dry run by default)'
        except OSError as exc:
            self.message = f'Export failed: {exc}'
        self.invalidate()

    def apply(self):
        # User-triggered Apply has the same destructive meaning as Textual Apply.
        pending, removed = [], 0
        for op, path in self.browser.actions:
            try:
                real = get_real_path(path)
                info = get_stat_info(path)
                if op != 'remove':
                    pending.append((op, path))
                elif info.get('exists') or os.path.islink(real):
                    if os.path.islink(real) or not os.path.isdir(real):
                        os.remove(real)
                    else:
                        shutil.rmtree(real)
                    removed += 1
            except OSError as exc:
                pending.append((op, path))
                self.message = f'Apply failed: {exc}'
        self.browser.actions[:] = pending
        self.refresh_rows()
        self.browser.refresh(self.browser.current_name())
        if not pending:
            self.close()
        else:
            self.message += f' · Removed {removed}; {len(pending)} remain'
        self.invalidate()


SCAN_STATES = {
    'modified': ('M', '#ff8800', 'modified'),
    'missing': ('U', '#ff0000', 'not found'),
    'new': ('U', '#ffffff', 'undefined / new'),
    'unknown': ('?', '#ffffff', 'unverified'),
    'verified': ('●', '#98e024', 'verified'),
    'directory': ('D', '#ffffff', 'directories'),
}


class BucketRowRenderer:
    """Custom map renderer: cached cells become compact runs of equal style.

    Generic FormattedTextControl reparses/hashes its entire supplied text. This
    renderer keeps virtual rows lazy and only compacts rows whose cells change.
    """
    def __init__(self, control):
        self.control = control
        self.rows = OrderedDict()
        self.frame = 0

    @staticmethod
    def compact(cells):
        runs = []
        style, text = cells[0]
        characters = [text]
        for next_style, character in cells[1:]:
            if next_style == style:
                characters.append(character)
            else:
                runs.append((style, ''.join(characters)))
                style, characters = next_style, [character]
        runs.append((style, ''.join(characters)))
        return runs

    def line(self, row, now, expert_mode, frame):
        control = self.control
        cached = self.rows.get(row)
        if cached is None:
            cells, deadlines = [], {}
            for col in range(control.columns):
                fragment, deadline = control.render_cell(row * control.columns + col, now, expert_mode)
                cells.append(fragment)
                if deadline is not None:
                    deadlines[col] = deadline
            # Runs, deadlines, dirty columns, source cells, last checked frame.
            cached = [self.compact(cells), deadlines, set(), cells, frame]
            self.rows[row] = cached
        elif cached[4] != frame:
            runs, deadlines, dirty, cells, _ = cached
            dirty.update(col for col, deadline in deadlines.items() if now >= deadline)
            if dirty:
                for col in dirty:
                    cells[col], deadline = control.render_cell(row * control.columns + col, now, expert_mode)
                    if deadline is None:
                        deadlines.pop(col, None)
                    else:
                        deadlines[col] = deadline
                cached[0] = self.compact(cells)
                dirty.clear()
            cached[4] = frame
        self.rows.move_to_end(row)
        while len(self.rows) > max(3, control.height * 3):
            self.rows.popitem(last=False)
        return cached[0]


class MapControl(UIControl):
    """Bounded visible-row cache; blue deltas invalidate individual cells."""
    def __init__(self, screen):
        self.screen = screen
        self.columns = self.height = 1
        self.renderer = BucketRowRenderer(self)
        self.row_cache = self.renderer.rows
        self.cache_signature = None
        self.last_selected = None
        self.last_follow = False
        self.last_count = 0
        self.dirty_lock = Lock()
        self.pending_cells = set()
        self.pending_all = False

    def is_focusable(self):
        return True

    def mark_buckets(self, indices=None, model=None):
        if model is not None and model is not self.screen.model:
            return
        # Offscreen cells have no cached rendering to invalidate. Coalesce
        # notifications so hidden maps/help cannot build an unbounded queue.
        cells = set() if indices is None else {
            index for index in indices if index // self.columns in self.row_cache}
        with self.dirty_lock:
            if indices is None:
                self.pending_all = True
                self.pending_cells.clear()
            elif not self.pending_all:
                self.pending_cells.update(cells)

    def render_cell(self, index, now, expert_mode):
        screen = self.screen
        symbol, color, background = '·', '#666666', '#000000'
        deadline = None
        if index < len(screen.model.buckets):
            bucket = screen.model.buckets[index]
            state = next((state for state in SCAN_STATES if bucket.counts[state]), 'unknown')
            symbol, color, _ = SCAN_STATES[state]
            if state == 'unknown' and bucket.counts['verified']:
                color = '#98e024'
            background = screen.backgrounds.get(index, '#000000')
            if expert_mode and index in screen.expert_blue:
                background = '#0000ff'
            if now - bucket.updated < 1:
                symbol, color = ('\\', '|', '/', '-')[int(now * 8) % 4], '#ffffff'
                deadline = min((int(now * 8) + 1) / 8, bucket.updated + 1)
                background = '#ff0000'
        elif screen.follow_end and index == screen.selected:
            symbol, color = '>', '#ffffff'
        style = f'fg:{color} bg:{background}'
        if index == screen.selected:
            style += ' underline'
        return (style, symbol), deadline

    def dirty_cell(self, index):
        if index is not None:
            cached = self.row_cache.get(index // self.columns)
            if cached is not None:
                cached[2].add(index % self.columns)

    def create_content(self, width, height):
        screen = self.screen
        self.columns, self.height = max(1, width), max(1, height)
        screen.fit(self.columns * self.height)
        count = len(screen.model.buckets)
        if screen.follow_end:
            screen.selected = count
        else:
            screen.selected = max(0, min(screen.selected, count - 1))
        expert_mode = screen.controls.modes[2] and screen.controls.heavy_order == 'expert'
        signature = (id(screen.model), self.columns, expert_mode)
        if signature != self.cache_signature:
            self.row_cache.clear()
            self.cache_signature = signature
        # Never wait for the projection worker in the renderer.
        if self.dirty_lock.acquire(blocking=False):
            try:
                cells, clear = self.pending_cells, self.pending_all
                self.pending_cells, self.pending_all = set(), False
            finally:
                self.dirty_lock.release()
            if clear:
                self.row_cache.clear()
            else:
                for index in cells:
                    self.dirty_cell(index)
        if self.last_selected != screen.selected or self.last_follow != screen.follow_end:
            self.dirty_cell(self.last_selected)
            self.dirty_cell(screen.selected)
        if self.last_count != count:
            # The old last row may contain cached empty cells now holding data.
            self.dirty_cell(self.last_count)
            self.dirty_cell(count)
        self.last_selected, self.last_count = screen.selected, count
        self.last_follow = screen.follow_end

        self.renderer.frame += 1
        frame = self.renderer.frame
        now = time.monotonic()
        def line(row):
            return self.renderer.line(row, now, expert_mode, frame)

        return UIContent(get_line=line,
                         line_count=max(1, math.ceil((count + int(screen.follow_end)) / self.columns)),
                         cursor_position=Point(x=screen.selected % self.columns,
                                               y=screen.selected // self.columns), show_cursor=False)

    def mouse_handler(self, event):
        screen = self.screen
        if event.event_type == MouseEventType.MOUSE_UP:
            index = event.position.y * self.columns + event.position.x
            if 0 <= index < len(screen.model.buckets):
                screen.follow_end = False
                screen.selected = index
                screen.selection_changed()
                get_app().layout.focus(self)
        elif event.event_type == MouseEventType.SCROLL_DOWN:
            screen.move_map(self.columns * 3)
        elif event.event_type == MouseEventType.SCROLL_UP:
            screen.move_map(-self.columns * 3)
        else:
            return NotImplemented
        screen.invalidate()


class PageControl(UIControl):
    def __init__(self, screen, slider=False):
        self.screen = screen
        self.slider = slider
        self.targets = []
        self.width = 1
        self.dragging = False

    def is_focusable(self):
        return True

    def create_content(self, width, height):
        self.width = max(1, width)
        screen = self.screen
        if self.slider:
            position = round((screen.pagination.page - 1) * (width - 1) / max(1, screen.pages - 1))
            fragments = [('#00aaaa', '━' * position), ('bg:#555555 #ffffff', '●'),
                         ('#888888', '─' * max(0, width - position - 1))]
        else:
            fragments, self.targets, offset = [], [], 0
            cell = len(str(screen.pages)) + 2
            for page in screen.pagination.choices(screen.pages, width):
                label = ('…' if page is None else str(page)).center(cell)
                fragments.append(('bg:#ffffff #000000' if page == screen.pagination.page else
                                  'bg:#333333 #ffffff', label))
                self.targets.append((offset, offset + cell, page))
                offset += cell
        return UIContent(get_line=lambda _: fragments, line_count=1, show_cursor=False)

    def seek(self, x):
        fraction = max(0, min(x, self.width - 1)) / max(1, self.width - 1)
        self.screen.set_page(1 + round(fraction * (self.screen.pages - 1)))

    def mouse_handler(self, event):
        if self.slider:
            if event.event_type == MouseEventType.MOUSE_DOWN:
                self.dragging = True
                self.seek(event.position.x)
            elif event.event_type == MouseEventType.MOUSE_MOVE and self.dragging:
                self.seek(event.position.x)
            elif event.event_type == MouseEventType.MOUSE_UP:
                if self.dragging:
                    self.seek(event.position.x)
                self.dragging = False
            else:
                return NotImplemented
        elif event.event_type == MouseEventType.MOUSE_UP:
            for start, end, page in self.targets:
                if start <= event.position.x < end and page is not None:
                    self.screen.set_page(page)
                    break
        else:
            return NotImplemented
        get_app().layout.focus(self)
        self.screen.invalidate()


class ScannerView(PTScreen):
    def __init__(self, browser, startup=True):
        super().__init__(browser)
        self.vfs = browser.vfs
        self.path = self.vfs.pwd().rstrip('/') or '/'
        self.return_name = browser.current_name()
        self.store = ScanStore(self.vfs.db)
        saved = self.store.get('map', self.path, {})
        self.timing = ScanTiming(saved.get('mode_elapsed', (0., 0., 0.)))
        self.controls = ScanControls(saved.get('modes', (True, False, False)),
            saved.get('read_known', False), saved.get('new_first', True), startup=startup,
            heavy_order=saved.get('heavy_order', 'normal'))
        self.model = FileMap()
        self.model.fixed = False
        for name in ('mode', 'fixed', 'limit', 'byte_limit'):
            if name in saved:
                setattr(self.model, name, saved[name])
        self.model.entries = {value['id']: ScanEntry(**dict(value, progress=None))
                              for value in saved.get('entries', [])}
        self.model.rebuild()
        self.pagination = Pagination()
        self.pagination.page = saved.get('page', 1)
        self.selected = saved.get('selected', 0)
        self.follow_end = saved.get('follow_end', False)
        self.filter = saved.get('file_filter') if saved.get('file_filter') in SCAN_STATES else None
        self.scope_path = saved.get('scope_path')
        self.scope_color = saved.get('scope_color')
        self.fixed_colors = saved.get('fixed_colors', {})
        self.scope_anchor = self.scope_depth = None
        self.backgrounds = {}
        self.scope_indices = set()
        self.expert_selected_count = 0
        self.expert_blue = set()
        self.expert_work, self.expert_counts = {}, {}
        self.expert_signature = None
        self.catalog_signature = None
        self.catalog_model = None
        self.catalog_cache = ()
        self.projection_wake = Event()
        self.projection_thread = None
        self.projection_error = None
        self.events = Queue(maxsize=2048)
        self.stop = Event()
        self.worker = None
        self.tick_task = None
        self.repack_task = None
        self.repacking = False
        self.closing = False
        self.requested_order = None
        self.order_thread = None
        self.requested_modes = {}
        self.mode_thread = None
        self.phase = 'Starting scanner'
        self.stats = ScanStats(path=self.path)
        self.detail_ids = []
        self.pages = 1
        self.page_size = 10
        self.detail_signature = None
        self.filter_fragments = []
        self.grid = MapControl(self)
        self.map_window = Window(self.grid, height=Dimension(min=3, weight=2),
                                 right_margins=[ScrollbarMargin()], style='bg:#000000',
                                 wrap_lines=False, always_hide_cursor=True)
        self.map_window.vertical_scroll = saved.get('scroll_y', 0)
        self.details = RowsControl(self.detail_rows, resized=self.details_resized)
        self.detail_window = Window(self.details, height=Dimension(min=2, weight=1),
                                    right_margins=[ScrollbarMargin()], wrap_lines=False,
                                    always_hide_cursor=True)
        self.page_control, self.slider = PageControl(self), PageControl(self, True)
        self.filters = FilterControl(self)
        self.horizontal = HorizontalBar(self.details)
        horizontal_keys(self, self.horizontal)
        self.bind(['left'], lambda: setattr(self.filters, 'pan', max(0, self.filters.pan - 8)),
                  filter=has_focus(self.filters))
        self.bind(['right'], lambda: setattr(self.filters, 'pan', self.filters.pan + 8),
                  filter=has_focus(self.filters))
        self.limit = TextArea(text=str(self.model.limit), multiline=False, width=9,
                              focus_on_click=True, style='class:scan-input', name='paths-per-bucket')
        self.byte_limit = TextArea(text=str(self.model.byte_limit // (1024 * 1024)),
                                   multiline=False, width=9, focus_on_click=True,
                                   style='class:scan-input', name='mib-per-bucket')
        for field in (self.limit, self.byte_limit):
            field.window.style = lambda field=field: ('class:text-area class:scan-input' +
                (' class:scan-input-focused' if has_focus(field)() else ''))
        self.focus = self.grid
        self.bind(['escape', 's'], self.close, eager=True)
        self.bind(['h'], lambda: browser.push(HelpView(browser, 'Drive map help', SCANNER_HELP)), eager=True)
        self.bind(['tab'], lambda: browser.app.layout.focus_next())
        self.bind(['s-tab'], lambda: browser.app.layout.focus_previous())
        not_input = ~has_focus(self.limit) & ~has_focus(self.byte_limit)
        for key, mode in [('1', 1), ('2', 2), ('3', 3)]:
            self.bind([key], lambda mode=mode: self.toggle_mode(mode), filter=not_input)
        for key, mode in [('!', 1), ('@', 2), ('#', 3)]:
            self.bind([key], lambda mode=mode: self.start_from(mode), filter=not_input)
        self.bind(['r'], lambda: self.toggle_flag('read_known'), filter=not_input)
        self.bind(['t'], lambda: self.toggle_flag('new_first'), filter=not_input)
        self.bind(['j'], self.order, filter=not_input)
        self.bind(['m'], self.mode, filter=not_input)
        self.bind(['v'], self.view, filter=not_input)
        self.bind(['['], lambda: self.scope(-1), filter=not_input)
        self.bind([']'], lambda: self.scope(1), filter=not_input)
        self.bind(['f'], self.fix_colors, filter=not_input)
        self.bind(['c'], self.clear_fixed_colors, filter=not_input)
        self.bind(['d'], self.clear_colors, filter=not_input)
        map_focused = has_focus(self.grid)
        for key, delta in [('left', -1), ('right', 1), ('up', -2), ('down', 2)]:
            self.bind([key], lambda delta=delta: self.move_map(delta, arrow=True), filter=map_focused)
        self.bind(['pageup'], lambda: self.move_map(-self.grid.columns * self.grid.height), filter=map_focused)
        self.bind(['pagedown'], lambda: self.move_map(self.grid.columns * self.grid.height), filter=map_focused)
        self.bind(['home'], lambda: self.move_map(-len(self.model.buckets)), filter=map_focused)
        self.bind(['end'], self.end, filter=map_focused)
        for control in (self.page_control, self.slider):
            focused = has_focus(control)
            self.bind(['left'], lambda: self.set_page(self.pagination.page - 1), filter=focused)
            self.bind(['right'], lambda: self.set_page(self.pagination.page + 1), filter=focused)
            self.bind(['home'], lambda: self.set_page(1), filter=focused)
            self.bind(['end'], lambda: self.set_page(self.pages), filter=focused)
        details_focused = has_focus(self.details)
        self.bind(['up'], lambda: self.move_details(-1), filter=details_focused)
        self.bind(['down'], lambda: self.move_details(1), filter=details_focused)
        self.bind(['pageup'], lambda: self.set_page(self.pagination.page - 1), filter=details_focused)
        self.bind(['pagedown'], lambda: self.set_page(self.pagination.page + 1), filter=details_focused)
        self.bind(['home'], lambda: self.details.move(-len(self.detail_ids)), filter=details_focused)
        self.bind(['end'], lambda: self.details.move(len(self.detail_ids)), filter=details_focused)
        self.bind(['left'], lambda: setattr(self.details, 'pan', max(0, self.details.pan - 4)), filter=details_focused)
        self.bind(['right'], lambda: setattr(self.details, 'pan', self.details.pan + 4), filter=details_focused)
        self.bind(['enter'], self.settings, filter=has_focus(self.limit) | has_focus(self.byte_limit))
        self.container = HSplit([
            Frame(HSplit([
                Window(FormattedTextControl('Drive map — ' + safe_text(self.path)), height=1, style='class:header'),
                Window(FormattedTextControl(self.controls_text), height=1),
                Window(FormattedTextControl(self.summary), height=1),
                Window(FormattedTextControl(self.stats_text), height=2),
                VSplit([Window(FormattedTextControl(' Paths/bucket '), width=len(' Paths/bucket ')),
                        self.limit, Window(FormattedTextControl(' MiB/bucket '), width=len(' MiB/bucket ')),
                        self.byte_limit, Window()], height=1),
                self.map_window,
                Window(FormattedTextControl(self.bucket_summary), height=lambda: 2 if self.scope_path else 1),
                Window(self.filters, height=1, wrap_lines=False, always_hide_cursor=True),
                Window(FormattedTextControl('Name / path    Size'), height=1, style='class:table-header'),
                self.detail_window,
                Window(self.horizontal, height=1),
                Window(self.page_control, height=1), Window(self.slider, height=1),
                self.navigation_row(),
            ]), style='class:info-pane'),
        ], key_bindings=self.keys)
        self.refresh_colors()
        self.update_details()

    def navigation_row(self):
        children = []
        self.jump_buttons = {}
        for label, target in [
            ('First', lambda: 1), ('-1000', lambda: self.pagination.page - 1000),
            ('-100', lambda: self.pagination.page - 100), ('-10', lambda: self.pagination.page - 10),
            ('Prev', lambda: self.pagination.page - 1), ('Next', lambda: self.pagination.page + 1),
            ('+10', lambda: self.pagination.page + 10), ('+100', lambda: self.pagination.page + 100),
            ('+1000', lambda: self.pagination.page + 1000), ('Last', lambda: self.pages),
        ]:
            button = Button(label, handler=lambda target=target: self.set_page(target()),
                            width=len(label) + 2, left_symbol='', right_symbol='')
            if label in ('-1000', '+1000'):
                button = ConditionalContainer(button, filter=Condition(lambda: self.pages >= 1000))
                self.jump_buttons[label] = button
            children.append(button)
        # Without a flexible filler, VSplit's finite maximum width (the sum of
        # button widths) constrains the enclosing HSplit and the entire map body.
        children.append(Window())
        return VSplit(children, height=1, padding=1)

    def start_projection(self):
        if self.projection_thread is not None:
            return
        def project():
            while not self.stop.is_set():
                self.projection_wake.wait(.1)
                self.projection_wake.clear()
                if self.stop.is_set():
                    break
                try:
                    self.update_catalog()
                    self.update_expert()
                except Exception as exc:
                    self.projection_error = exc
                    self.phase = f'Map projection failed: {exc}'
        self.projection_thread = Thread(target=project, name='drive-pt-map-projection', daemon=True)
        self.projection_thread.start()
        self.projection_wake.set()

    def request_projection(self):
        self.projection_wake.set()

    def start(self):
        self.browser.scanners.append(self)
        self.start_projection()
        scanner = DriveScanner(self.vfs.db, self.path, self.events, self.stop, controls=self.controls,
            timing=self.timing,
            entries=self.model.entries.values(),
            root_names=tuple(node.name for node in self.vfs.list_nodes(self.vfs.db.get_root())) if self.path == '/' else ())
        self.worker = Thread(target=scanner.run, name='drive-pt-scanner', daemon=True)
        self.worker.start()
        self.tick_task = self.browser.app.create_background_task(self.tick())

    async def tick(self):
        while not self.stop.is_set():
            if not self.repacking:
                self.drain_all(budget=.015)
                self.request_projection()
                self.update_details()
            self.invalidate()
            await asyncio.sleep(.1)

    def drain_all(self, budget=None):
        deadline = time.monotonic() + budget if budget is not None else float('inf')
        while time.monotonic() < deadline:
            try:
                kind, payload = self.events.get_nowait()
            except Empty:
                break
            if kind == 'entry':
                repack = self.model.update(payload, rebuild=False)
                self.detail_signature = None
                if repack and not self.closing and budget is not None:
                    self.repack(minimum=self.model.capacity * 2 if self.model.fixed else 1)
                    break
                if repack:
                    self.model.rebuild()
                    self.refresh_colors()
                else:
                    self.refresh_colors([self.model.locations[payload.id]])
            elif kind == 'removed':
                if not self.closing and budget is not None:
                    self.repack(removed=set(payload))
                    break
                for key in payload:
                    self.model.entries.pop(key, None)
                self.model.rebuild()
                self.refresh_colors()
            elif kind == 'stats':
                self.stats = payload
            elif kind == 'expert':
                self.phase = 'Heavy expert — processing selected bucket'
            elif kind == 'phase':
                self.phase = safe_text(payload)

    def update_catalog(self):
        # Only the projection worker publishes catalog snapshots. Discovery is
        # append-only between repacks, so old immutable buckets can be reused.
        model = self.model
        signature = (id(model), len(model.entries))
        if signature == self.catalog_signature:
            return
        if model is self.catalog_model and self.catalog_cache:
            start = len(self.catalog_cache) - 1
            catalog = self.catalog_cache[:start] + tuple(
                tuple(bucket.ids) for bucket in model.buckets[start:])
        else:
            catalog = tuple(tuple(bucket.ids) for bucket in model.buckets)
        self.controls.buckets = catalog
        self.catalog_cache = catalog
        self.catalog_model = model
        self.catalog_signature = signature

    def update_expert(self):
        model = self.model
        if not self.controls.lock.acquire(blocking=False):
            return
        try:
            changes = self.controls.selection_changes
            self.controls.selection_changes = {}
            self.expert_selected_count = len(self.controls.expert_queue) + (self.controls.expert_current is not None)
        finally:
            self.controls.lock.release()
        # Appending entries does not relocate any existing bucket anchors.
        signature = (id(model), id(model.buckets))
        remap = signature != self.expert_signature
        changed_cells = set()
        def anchor(ids):
            return next((model.locations[key] for key in ids if key in model.locations), None)
        def account(index, delta):
            if index is None:
                return
            was_blue = index in self.expert_blue
            count = self.expert_counts.get(index, 0) + delta
            if count > 0:
                self.expert_counts[index] = count
                self.expert_blue.add(index)
            else:
                self.expert_counts.pop(index, None)
                self.expert_blue.discard(index)
            if was_blue != (count > 0):
                changed_cells.add(index)
        for key, (ids, delta) in changes.items():
            previous = self.expert_work.get(key)
            count = delta + (previous[1] if previous else 0)
            index = previous[2] if previous else (None if remap else anchor(ids))
            if not remap:
                account(index, delta)
            if count:
                self.expert_work[key] = (ids, count, index)
            else:
                self.expert_work.pop(key, None)
        if remap:
            counts, blue = {}, set()
            for key, (ids, count, _) in self.expert_work.items():
                index = anchor(ids)
                self.expert_work[key] = (ids, count, index)
                if index is not None:
                    counts[index] = counts.get(index, 0) + count
                    blue.add(index)
            # Swap the completed projection; drawing never waits for a rebuild.
            self.expert_counts = counts
            self.expert_blue = blue
            self.expert_signature = signature
            self.grid.mark_buckets(model=model)
        elif changed_cells:
            self.grid.mark_buckets(changed_cells, model=model)

    def fit(self, cells):
        if self.model.cells != cells and not self.repacking:
            self.model.cells = cells
            if self.model.fixed and hasattr(self.browser, 'app') and self.browser.app.is_running:
                self.repack()

    def repack(self, minimum=1, removed=()):
        if self.repacking or self.closing:
            return
        self.repacking = True
        replacement = FileMap()
        for name in ('mode', 'fixed', 'cells', 'limit', 'byte_limit'):
            setattr(replacement, name, getattr(self.model, name))
        source = self.model
        def build():
            replacement.entries = {key: entry for key, entry in source.entries.items() if key not in removed}
            replacement.rebuild(minimum=minimum)
            return replacement
        async def install():
            try:
                self.model = await background_call(build)
                self.catalog_signature = self.detail_signature = None
                self.refresh_colors()
                self.request_projection()
                self.update_details()
            finally:
                self.repacking = False
                self.invalidate()
        self.repack_task = self.browser.app.create_background_task(install())

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop.set()
        self.controls.wake.set()
        self.projection_wake.set()
        async def finish():
            if self.projection_thread:
                await background_call(self.projection_thread.join)
            if self.mode_thread:
                await background_call(self.mode_thread.join)
            if self.order_thread:
                await background_call(self.order_thread.join)
            if self.worker:
                await background_call(self.worker.join)
            if self.repack_task:
                await self.repack_task
            self.drain_all()
            self.save()
            self.browser.vfs.cwd = self.vfs.get_from_path(self.vfs.pwd())
            self.browser.refresh(self.return_name)
            self.browser.pop(self)
            if self in self.browser.scanners:
                self.browser.scanners.remove(self)
        self.browser.app.create_background_task(finish())

    def save(self):
        snapshot = {name: getattr(self.model, name) for name in ('mode', 'fixed', 'limit', 'byte_limit')}
        snapshot.update(entries=[asdict(replace(entry, progress=None)) for entry in self.model.entries.values()],
            modes=self.controls.modes, read_known=self.controls.read_known, new_first=self.controls.new_first,
            selected=self.selected, scroll_y=self.map_window.vertical_scroll, page=self.pagination.page,
            follow_end=self.follow_end, file_filter=self.filter, heavy_order=self.controls.heavy_order,
            scope_path=self.scope_path, scope_color=self.scope_color, fixed_colors=self.fixed_colors)
        snapshot['mode_elapsed'] = self.timing.snapshot()[1]
        self.store.put('map', self.path, snapshot)

    def selected_bucket(self):
        return self.model.buckets[self.selected] if not self.follow_end and 0 <= self.selected < len(self.model.buckets) else None

    def selection_changed(self):
        self.pagination.page = 1
        self.details.index = 0
        self.detail_signature = None
        self.update_details()
        self.invalidate()

    def move_map(self, delta, arrow=False):
        if self.follow_end and arrow and delta == 1:
            return
        if arrow and delta == 1 and self.selected == max(0, len(self.model.buckets) - 1):
            self.end()
            return
        self.follow_end = False
        if arrow:
            delta = {-2: -self.grid.columns, 2: self.grid.columns}.get(delta, delta)
        self.selected = max(0, min(max(0, len(self.model.buckets) - 1), self.selected + delta))
        self.selection_changed()

    def end(self):
        self.follow_end = True
        self.selected = len(self.model.buckets)
        self.selection_changed()

    def details_resized(self):
        self.page_size = max(1, min(100, self.details.height))
        self.detail_signature = None
        self.update_details()

    def update_details(self):
        bucket = self.selected_bucket()
        signature = (id(bucket), self.filter, self.pagination.page, self.page_size, len(self.model.entries))
        if signature == self.detail_signature:
            return
        ids = ([] if bucket is None else bucket.ids if self.filter is None else
               [key for key in bucket.ids if self.model.entries[key].state == self.filter])
        self.pages = max(1, math.ceil(len(ids) / self.page_size))
        self.pagination.select(self.pagination.page, self.pages)
        first = (self.pagination.page - 1) * self.page_size
        self.detail_ids = ids[first:first + self.page_size]
        self.filtered_count = len(ids)
        self.details.index = max(0, min(self.details.index, len(self.detail_ids) - 1))
        self.detail_signature = (id(bucket), self.filter, self.pagination.page, self.page_size, len(self.model.entries))

    def detail_rows(self):
        result = []
        for key in self.detail_ids:
            entry = self.model.entries.get(key)
            if entry is None:
                continue
            symbol, color, _ = SCAN_STATES.get(entry.state, SCAN_STATES['unknown'])
            progress = f'S {entry.progress}% ' if entry.progress is not None else ''
            path = entry.path + ('/' if entry.is_dir else '')
            prefix = ''
            if self.scope_path:
                scope = self.scope_path.rstrip('/') + '/'
                if not path.startswith('/'):
                    scope = scope.lstrip('/')
                if scope and path.startswith(scope):
                    prefix = scope
            result.append([('', progress), ('fg:' + color, symbol), ('', ' '),
                ('fg:#ffd700', safe_text(prefix)),
                ('', safe_text(path[len(prefix):]) +
                 ('' if entry.is_dir else '  ' + format_size(entry.size, 0).strip()))])
        return result

    def set_page(self, page):
        self.pagination.select(page, self.pages)
        self.details.index = 0
        self.detail_signature = None
        self.update_details()
        self.invalidate()

    def move_details(self, delta):
        if delta < 0 and self.details.index == 0 and self.pagination.page > 1:
            self.set_page(self.pagination.page - 1)
            self.details.index = max(0, len(self.detail_ids) - 1)
        elif delta > 0 and self.details.index >= len(self.detail_ids) - 1 and self.pagination.page < self.pages:
            self.set_page(self.pagination.page + 1)
        else:
            self.details.move(delta)
        self.invalidate()

    def toggle_mode(self, mode):
        if self.closing:
            return
        current = self.requested_modes.get(mode, self.controls.modes[mode - 1])
        self.requested_modes = {**self.requested_modes, mode: not current}
        self.invalidate()
        self.apply_requested_modes()

    def apply_requested_modes(self):
        if self.mode_thread is not None and self.mode_thread.is_alive():
            return

        def switch():
            while True:
                targets = self.requested_modes
                if not targets:
                    return
                with self.controls.lock:
                    # A manual mode key cancels startup even if rapid presses
                    # coalesce back to the existing enabled state.
                    self.controls.cancel_startup()
                    for mode, enabled in targets.items():
                        if self.controls.modes[mode - 1] != enabled:
                            self.controls.toggle(mode)
                    self.controls.wake.set()
                if self.requested_modes == targets:
                    return

        thread = Thread(target=switch, name='drive-pt-modes', daemon=True)
        self.mode_thread = thread
        thread.start()

        async def finish():
            while thread.is_alive():
                await asyncio.sleep(.01)
            if self.mode_thread is thread:
                if any(self.controls.modes[mode - 1] != enabled
                       for mode, enabled in self.requested_modes.items()):
                    self.apply_requested_modes()
                else:
                    self.requested_modes = {}
                self.invalidate()
        self.browser.app.create_background_task(finish())
        # Like j, mode keys persist on the next normal snapshot or close.


    def start_from(self, mode):
        bucket = self.selected_bucket()
        if bucket and bucket.ids:
            self.controls.start_from(mode, bucket.ids[0])
            self.save()
            self.invalidate()

    def toggle_flag(self, name):
        setattr(self.controls, name, not getattr(self.controls, name))
        self.controls.wake.set()
        self.invalidate()

    def order(self):
        if self.closing:
            return
        current = self.requested_order or self.controls.heavy_order
        self.requested_order = 'expert' if current == 'normal' else 'normal'
        self.invalidate()
        self.apply_requested_order()

    def apply_requested_order(self):
        if self.order_thread is not None and self.order_thread.is_alive():
            return

        def switch():
            # Lock contention and clearing a large expert queue must not run
            # inside the key handler. Rapid presses coalesce to the latest mode.
            while True:
                target = self.requested_order
                if target is None:
                    return
                with self.controls.lock:
                    if self.controls.heavy_order != target:
                        self.controls.toggle_order()
                if self.requested_order == target:
                    return

        thread = Thread(target=switch, name='drive-pt-order', daemon=True)
        self.order_thread = thread
        thread.start()

        async def finish():
            while thread.is_alive():
                await asyncio.sleep(.01)
            if self.order_thread is thread:
                if self.requested_order != self.controls.heavy_order:
                    self.apply_requested_order()
                else:
                    self.requested_order = None
                self.invalidate()
        self.browser.app.create_background_task(finish())
        # Persist with the next ordinary snapshot or close, rather than
        # serializing every map entry for a single order-setting change.

    def mode(self):
        self.model.mode = 'size' if self.model.mode == 'count' else 'count'
        self.repack()

    def view(self):
        self.model.fixed = not self.model.fixed
        self.repack()

    def settings(self):
        try:
            limit, size = int(self.limit.text), int(self.byte_limit.text)
            if not (1 <= limit <= 1_000_000 and 1 <= size <= 1_048_576):
                raise ValueError
        except ValueError:
            self.phase = 'Use positive integers: paths ≤ 1000000; MiB ≤ 1048576'
            self.invalidate()
            return
        self.model.limit, self.model.byte_limit = limit, size * 1024 * 1024
        self.repack()
        self.browser.app.layout.focus(self.grid)

    def filter_click(self, state):
        self.filter = None if self.filter == state else state
        self.selection_changed()

    def filters_text(self):
        bucket = self.selected_bucket()
        result = []
        for state, label, color in [(None, 'All', '#ffffff')] + [
                (state, f'{symbol} {label}: {bucket.counts[state] if bucket else 0}', color)
                for state, (symbol, color, label) in SCAN_STATES.items()
                if (bucket and bucket.counts[state]) or state == self.filter]:
            def click(event, state=state):
                if event.event_type == MouseEventType.MOUSE_UP:
                    self.filter_click(state)
            result.append(('bg:#ffffff #000000' if state == self.filter else 'fg:' + color,
                           ' ' + label + ' ', click))
        return result

    def scope(self, direction):
        if not self.detail_ids:
            return
        key = self.detail_ids[min(self.details.index, len(self.detail_ids) - 1)]
        entry = self.model.entries[key]
        parts = entry.path.strip('/').split('/')
        if not entry.is_dir:
            parts = parts[:-1]
        chain = ['/' + '/'.join(parts[:i]) for i in range(1, len(parts) + 1)] or ['/']
        if self.scope_anchor != key:
            self.scope_anchor, self.scope_depth = key, None
        depth = (0 if direction > 0 else len(chain) - 1) if self.scope_depth is None else (
            self.scope_depth + direction) % len(chain)
        self.scope_depth = depth
        if self.scope_path == chain[depth]:
            return
        self.scope_path = chain[depth]
        self.scope_color = '#' + ''.join(f'{random.randint(32, 96):02x}' for _ in range(3))
        self.refresh_colors()
        self.invalidate()

    def refresh_colors(self, indices=None):
        if indices is not None:
            indices = tuple(indices)
        self.grid.mark_buckets(indices)
        if indices is None:
            self.backgrounds = {}
            self.scope_indices.clear()
            indices = range(len(self.model.buckets))
        for index in indices:
            bucket = self.model.buckets[index]
            if not self.fixed_colors and not self.scope_color:
                self.backgrounds.pop(index, None)
                self.scope_indices.discard(index)
                continue
            scoped = any(self.scope_path and (self.scope_path == '/' or
                self.model.entries[key].path == self.scope_path or
                self.model.entries[key].path.startswith(self.scope_path + '/')) for key in bucket.ids)
            if scoped:
                self.scope_indices.add(index)
            else:
                self.scope_indices.discard(index)
            fixed = next((self.fixed_colors[key] for key in reversed(bucket.ids) if key in self.fixed_colors), None)
            background = (self.scope_color if scoped else None) or fixed
            if background:
                self.backgrounds[index] = background
            else:
                self.backgrounds.pop(index, None)

    def fix_colors(self):
        if self.scope_path and self.scope_color:
            for index in self.scope_indices:
                for key in self.model.buckets[index].ids:
                    self.fixed_colors[key] = self.scope_color
            self.refresh_colors()
            self.save()
            self.invalidate()

    def clear_fixed_colors(self):
        self.fixed_colors.clear()
        self.refresh_colors()
        self.save()
        self.invalidate()

    def clear_colors(self):
        self.scope_path = self.scope_color = None
        self.fixed_colors.clear()
        self.refresh_colors()
        self.save()
        self.invalidate()

    def controls_text(self):
        result = []
        for i, (label, running) in enumerate(zip(('Lite', 'Medium', 'Heavy'), self.controls.modes), 1):
            running = self.requested_modes.get(i, running)
            result.extend([('', f'{i} {label} '), ('class:green' if running else 'class:red', 'RUN' if running else 'STOP'), ('', ' · ')])
        result.append(('', f'r {"on" if self.controls.read_known else "off"} · t {"new" if self.controls.new_first else "all"} · j {self.requested_order or self.controls.heavy_order}'))
        if (self.requested_order or self.controls.heavy_order) == 'expert':
            result.append(('', f' · Expert selected {self.expert_selected_count} buckets'))
        current, total = self.timing.display_snapshot()
        result.append(('', f' · {format_elapsed(current)} / {format_elapsed(total)}'))
        return result

    def summary(self):
        return (f'{self.phase} | {self.model.mode} | {"fixed" if self.model.fixed else "scroll"} | '
                f'{len(self.model.entries)} paths · {len(self.model.buckets)} buckets')

    def stats_text(self):
        rate = self.stats.mb_per_second
        for unit in ('MB/s', 'GB/s', 'TB/s', 'PB/s'):
            if rate < 1000 or unit == 'PB/s':
                break
            rate /= 1000
        first = min(self.map_window.vertical_scroll * self.grid.columns + 1, len(self.model.buckets)) if self.model.buckets else 0
        return (f'{self.stats.paths_per_second:.1f} paths/s · {rate:.2f} {unit} · '
                f'Total {self.stats.paths} paths / {format_size(self.stats.size_scanned or 0, 0).strip()} · '
                f'bucket {first}/{len(self.model.buckets)}\n'
                f'{"Scanning" if self.stats.active else "Last path"}: {safe_text(self.stats.path)}')

    def bucket_summary(self):
        bucket = self.selected_bucket()
        if bucket is None:
            return 'End of buckets > — following new buckets' if self.follow_end else 'Waiting for paths…'
        errors = [self.model.entries[key].error for key in self.detail_ids if self.model.entries[key].error]
        text = (f'Bucket {self.selected + 1} · {bucket.files} files · '
                f'{len(bucket.ids) - bucket.files} dirs · {format_size(bucket.size, 0).strip()} · '
                f'M {bucket.file_states["modified"]} / deleted {bucket.file_states["missing"]} / green {bucket.file_states["verified"]} · '
                f'page {self.pagination.page}/{self.pages} · shown {self.filtered_count}/{len(bucket.ids)}')
        if self.scope_path:
            text += f'\nScope {safe_text(self.scope_path)} · {len(self.scope_indices)} buckets'
        elif errors:
            text += ' · ' + safe_text(errors[0])
        return text


def load_config():
    if not Path('config.sh').is_file():
        return
    log = LiveLog('config.sh')
    log.load()
    mappings = log._tree._items.get('MAP DRIVES')
    if mappings is not None:
        for line in mappings._ss:
            parts = shlex.split(line)
            if len(parts) < 2:
                continue
            prefix, local = parts[0], os.path.expanduser(parts[1])
            alias = parts[2] if len(parts) > 2 else prefix
            aliases[alias] = local
            if local == '0':
                disabled_prefixes[prefix] = prefix
            else:
                prefixes[prefix] = {'local': local, 'alias': alias}


def load_vfs(args):
    files = []
    if args.cache == 'memory' or args.build or args.update:
        for root in args.db or ['.']:
            files.extend(sorted(Path(root).rglob('llog-llogfiles.sh')))
    if args.cache == 'sqlite':
        fs = VirtualFS(None, 'sqlite')
        try:
            if args.build:
                fs.db.rebuild_db()
                fs.cwd = fs.db.get_root()
            for path in files:
                data = {'hashes': {}, 'files': {}, 'file_types': {}, 'modified': {}}
                print(f'Loading {path}')
                load_log(data, path)
                fs.update(data)
            return fs
        except BaseException:
            fs.db.conn.close()
            raise
    data = {'hashes': {}, 'files': {}, 'file_types': {}, 'modified': {}}
    for path in files:
        print(f'Loading {path}')
        load_log(data, path)
    return VirtualFS(data, args.cache, args.build)


def main():
    parser = argparse.ArgumentParser(
        description='Browse disk catalogs and live drive maps with prompt_toolkit.',
        epilog='Example: ./drive-tui.py ~/mypath\nUses config.sh drive aliases when available.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', nargs='?', help='Startup directory (default: current directory; supports ~)')
    parser.add_argument('-d', '--db', action='append', help='Directory containing LLOG files (repeatable)')
    parser.add_argument('-c', '--cache', choices=['memory', 'sqlite', 'redis'], default='memory')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('-b', '--build', '--rebuild', action='store_true', help='Rebuild cache from logs')
    modes.add_argument('-u', '--update', action='store_true', help='Update SQLite cache from logs')
    args = parser.parse_args()
    if args.update and args.cache != 'sqlite':
        parser.error('--update requires -c sqlite')
    if args.path is not None and not Path(args.path).expanduser().is_dir():
        parser.error(f'Startup path is not a directory: {args.path}')
    load_config()
    fs = load_vfs(args)
    try:
        try:
            browser = DriveBrowser(fs, path=args.path)
        except ValueError as error:
            parser.error(str(error))
        browser.run()
    finally:
        if args.cache == 'sqlite':
            fs.db.conn.close()


if __name__ == '__main__':
    main()
