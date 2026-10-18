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
import json
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
    from prompt_toolkit.layout.screen import Char
    from prompt_toolkit.mouse_events import MouseEventType, MouseButton
    from prompt_toolkit.styles import DynamicStyle, Style
    from prompt_toolkit.utils import get_cwidth
    from prompt_toolkit.widgets import Button, Frame, TextArea
except ImportError as exc:
    raise SystemExit('Install prompt_toolkit: python -m pip install prompt_toolkit') from exc

from drive import load_log
from livelog2 import LiveLog
from vfs import VirtualFS, aliases, disabled_prefixes, format_size, prefixes, get_stat_info
from vfs.video_preview import VideoPreview
from vfs.paths import get_real_path
from vfs.thumbnails import thumbnail, IMAGE_SUFFIXES, THUMBNAIL_SUFFIXES, MEDIA_SUFFIXES, VIDEO_SUFFIXES, AUDIO_SUFFIXES
from vfs.scanner import (DriveScanner, FileMap, Pagination, ScanControls, ScanEntry,
                         ScanStats, ScanStore, ScanTiming)


NUMBER_TEXT = re.compile(r'\d+(?:[.,]\d+)*')


class NumberHighlight(HSplit):
    """Color final visible numeric text across every widget and screen."""

    def __init__(self, container):
        super().__init__([container])

    def write_to_screen(self, screen, mouse_handlers, write_position,
                        parent_style, erase_bg, z_index):
        super().write_to_screen(screen, mouse_handlers, write_position,
                                parent_style, erase_bg, z_index)
        screen.draw_with_z_index(10**9, lambda: self.highlight(screen))

    @staticmethod
    def highlight(screen):
        for row in screen.data_buffer.values():
            columns = sorted(row)
            text = ''
            positions = []
            previous = None
            for column in columns:
                # Separate nonadjacent cells; keep wide/combining glyph offsets.
                if previous is not None and column != previous + 1:
                    text += '\n'
                    positions.append(None)
                cell = row[column]
                char = cell.char
                if 'class:literal' in cell.style:
                    char = ' ' * len(char)
                if 'class:hash' in cell.style:
                    row[column] = Char(cell.char, cell.style + ' fg:#ffd700')
                text += char
                positions.extend([column] * len(char))
                previous = column
            for match in NUMBER_TEXT.finditer(text):
                for column in set(positions[match.start():match.end()]):
                    if column is not None:
                        cell = row[column]
                        row[column] = Char(cell.char, cell.style + ' fg:#ffd700')


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




def configure_image_terminal(probe=False):
    """Probe before prompt_toolkit starts reading input, then cache capabilities."""
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='It seems this process is not running within a terminal.*', category=UserWarning)
        from term_image import disable_queries, enable_queries
        from term_image.image import auto_image_class
    if probe:
        enable_queries()
        try:
            auto_image_class()
            from term_image.utils import get_cell_size
            get_cell_size()
        finally:
            disable_queries()
    else:
        disable_queries()


def ascii_image_preview(path, width=60, height=24, *, color=False, native=None, z_index=731):
    """Render a bounded term-image frame; ANSI is consumed only by InfoLexer."""
    import warnings
    from contextlib import redirect_stdout
    from io import StringIO
    configure_image_terminal()
    from term_image.image import AutoImage, BlockImage, KittyImage
    from term_image.exceptions import TermImageError
    from PIL import Image, ImageOps, UnidentifiedImageError

    width, height = max(1, width), max(1, height)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as source:
                original_size = source.size
                # Refuse huge decompressions, including warning-sized images.
                if source.width * source.height > 20_000_000:
                    return ['Image preview unavailable: image exceeds 20 megapixels.']
                image = ImageOps.exif_transpose(source).convert('RGBA')
                from term_image.utils import get_cell_size
                cell_width, cell_height = get_cell_size() or (8, 16)
                scale = min(width * cell_width / image.width,
                            height * cell_height / image.height, 1.)
                target = (max(1, int(image.width * scale / cell_width)),
                          max(1, int(image.height * scale / cell_height)))
                with AutoImage(image, width=target[0], height=target[1]) as preview:
                    is_native = isinstance(preview, KittyImage) and native is not None
                    # Graphics protocols cannot pass through the text lexer.
                    # Other graphics styles retain the embedded block fallback.
                    renderer = preview
                    if not is_native and not isinstance(preview, BlockImage):
                        renderer = BlockImage(image.copy(), width=target[0], height=target[1])
                    try:
                        output = StringIO()
                        with redirect_stdout(output):
                            options = {'method': 'whole', 'z_index': z_index, 'mix': True} if is_native else {}
                            renderer.draw(h_align='left', pad_width=1, v_align='top',
                                          pad_height=1, animate=False, check_size=False,
                                          **options)
                        art = output.getvalue().rstrip('\n')
                        if is_native:
                            native(art, target)
                            return [f'Image: {original_size[0]} x {original_size[1]}',
                                    *[' ' * target[0] for _ in range(target[1])]]
                    finally:
                        if renderer is not preview:
                            renderer.close()
                if not color:
                    from prompt_toolkit.formatted_text import ANSI, to_formatted_text
                    art = ''.join(text for _, text in to_formatted_text(ANSI(art)))
                return [f'Image: {original_size[0]} x {original_size[1]}',
                        *art.splitlines()]
    except (OSError, ValueError, UnidentifiedImageError, TermImageError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        return ['Image preview unavailable: unreadable or unsupported image.']


def prepare_grid_thumbnail(path, file_id, size, bounds, cell_ratio):
    """Decode, cache, fit and serialize on a worker without redirecting stdout."""
    from PIL import Image
    from term_image.image import AutoImage, BlockImage, KittyImage
    from prompt_toolkit.formatted_text import ANSI, to_formatted_text
    record = thumbnail(path, file_id, size)
    with Image.open(record['path']) as source:
        image = source.convert('RGB')
    width, height = bounds
    scale = min(width / image.width, height / (image.height * cell_ratio))
    target = (max(1, min(width, round(image.width * scale))),
              max(1, min(height, round(image.height * scale * cell_ratio))))
    with AutoImage(image, width=target[0], height=target[1]) as preview:
        if isinstance(preview, KittyImage):
            # Public string formatting performs the same protocol serialization
            # without draw()'s process-global stdout writes from a worker thread.
            art = format(preview, '1.1+Wz732m1')
            return {'record': record, 'native': (art, target), 'lines': [], 'dimensions': target}
        if isinstance(preview, BlockImage):
            art = str(preview)
        else:
            with BlockImage(image.copy(), width=target[0], height=target[1]) as fallback:
                art = str(fallback)
    return {'record': record, 'native': None,
            'lines': [to_formatted_text(ANSI(line)) for line in art.splitlines()],
            'dimensions': target}


class KittyReplyFilter:
    """Consume graphics APC responses before PT can turn them into app keys."""
    def __init__(self, parser):
        self.parser = parser
        self.pending = ''

    def feed(self, data):
        self.pending += data
        while self.pending:
            start = self.pending.find('\x1b_G')
            if start < 0:
                keep = 2 if self.pending.endswith('\x1b_') else 1 if self.pending.endswith('\x1b') else 0
                ready = self.pending[:-keep] if keep else self.pending
                if ready:
                    self.parser.feed(ready)
                self.pending = self.pending[-keep:] if keep else ''
                return
            if start:
                self.parser.feed(self.pending[:start])
                self.pending = self.pending[start:]
            end = self.pending.find('\x1b\\', 3)
            if end < 0:
                if len(self.pending) > 8192:
                    self.pending = ''  # Bound malformed response buffering.
                return
            self.pending = self.pending[end + 2:]

    def flush(self):
        if self.pending and not self.pending.startswith('\x1b_G'):
            self.parser.feed(self.pending)
            self.pending = ''
        self.parser.flush()

    def __getattr__(self, name):
        return getattr(self.parser, name)


def native_graphics_payload(art):
    """Keep only Kitty APC packets; text-layout cursor moves must not reach the TUI."""
    packets = re.findall(r'\x1b_G.*?\x1b\\', art, flags=re.DOTALL)
    if not packets:
        return ''
    # C=1 prevents Kitty's own placement from moving the terminal cursor.
    for index, packet in enumerate(packets):
        header, payload = packet[3:].split(';', 1)
        controls = [value for value in header.split(',') if not value.startswith('q=')]
        if index == 0:
            controls = [value for value in controls if not value.startswith('C=')]
            controls.append('C=1')
        controls.append('q=2')  # Suppress both successful and failed terminal replies.
        packets[index] = '\x1b_G' + ','.join(controls) + ';' + payload
    return ''.join(packets)


def serialize_video_frame(image, dimensions):
    """Serialize one software-decoded frame on the playback worker."""
    from term_image.image import AutoImage, BlockImage, KittyImage
    from prompt_toolkit.formatted_text import ANSI, to_formatted_text
    width, height = dimensions
    with AutoImage(image, width=width, height=height) as preview:
        if isinstance(preview, KittyImage):
            return {'native': (format(preview, '1.1+Wz731m1'), dimensions), 'lines': []}
        if isinstance(preview, BlockImage):
            art = str(preview)
        else:
            with BlockImage(image.copy(), width=width, height=height) as fallback:
                art = str(fallback)
    return {'native': None, 'lines': [to_formatted_text(ANSI(line)) for line in art.splitlines()]}


def fit_filename(text, width):
    """Keep the filename ending when a tile cannot display its full name."""
    text = safe_text(text)
    if get_cwidth(text) <= width:
        return fit(text, width)
    if width <= 1:
        return '…'[:width]
    suffix = []
    used = 0
    for char in reversed(text):
        cells = get_cwidth(char)
        if used + cells > width - 1:
            break
        suffix.append(char)
        used += cells
    return '…' + ' ' * (width - 1 - used) + ''.join(reversed(suffix))


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


def bookmark_label(style, text, marked, offset=1):
    """Highlight only the bookmark marker, retaining row background and widths."""
    if not marked or len(text) <= offset or text[offset] != 'B':
        return [(style + ' class:literal', text)]
    style += ' class:literal'
    return [(style, text[:offset]), (style + ' class:bookmark', 'B'),
            (style, text[offset + 1:])]


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
        if browser.graphics_mode:
            return browser.grid_content(width, height, header=self.header)
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
            if row['color'] == 'muted':
                base += ' class:muted'
            expanded = row['node'].is_dir and row['node'].id in browser.expanded_dirs
            if expanded and not selected:
                base += ' class:expanded-dir'
            name_style = base + ' class:literal' + (' class:expanded-dir-name' if expanded else '')
            label = row['label']
            marked = browser.bookmark_path(row) in browser.bookmarks
            if marked:
                label = label[:2] + 'B ' + label[2:]
            label = fit(label, name_width)
            fragments = []
            if label and browser.display_mode != 3:
                fragments.append((base + ' class:' + row['indicator'], label[0]))
                fragments.extend(bookmark_label(name_style, label[1:], marked))
            else:
                fragments.extend(bookmark_label(name_style, label, marked, 2))
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
            browser.move_grid_row(1) if browser.graphics_mode else browser.move(3)
        elif event.event_type == MouseEventType.SCROLL_UP:
            browser.move_grid_row(-1) if browser.graphics_mode else browser.move(-3)
        elif event.event_type == MouseEventType.MOUSE_UP:
            browser.app.layout.focus(self)
            index = event.position.y
            if browser.graphics_mode:
                if event.position.y >= len(browser.grid_lines):
                    return
                entries, _, media = browser.grid_lines[event.position.y]
                column = min(len(entries) - 1, event.position.x // (browser.grid_tile_width + 1)) if media else 0
                index = entries[column]
            browser.select(min(index, max(0, len(browser.rows) - 1)))
        else:
            return NotImplemented


class VideoSeekControl(UIControl):
    def __init__(self, browser):
        self.browser = browser
        self.keys = KeyBindings()
        for key, seconds in [('left', -5), ('right', 5)]:
            self.keys.add(key)(lambda event, seconds=seconds: browser.seek_video(seconds, relative=True))
        self.keys.add('home')(lambda event: browser.seek_video(0))
        self.keys.add('end')(lambda event: browser.seek_video(browser.video_duration))
        self.width = 1

    def is_focusable(self):
        return True

    def get_key_bindings(self):
        return self.keys

    def create_content(self, width, height):
        self.width = max(1, width - 20)
        duration = self.browser.video_duration
        fraction = min(1., self.browser.video_position / duration) if duration else 0
        filled = round(fraction * self.width)
        text = '[' + '=' * filled + '-' * (self.width - filled) + '] '
        text += format_elapsed(self.browser.video_position) + ' / ' + format_elapsed(duration)
        return UIContent(get_line=lambda _: [('class:header', fit(text, width))], line_count=1,
                         show_cursor=False)

    def mouse_handler(self, event):
        browser = self.browser
        if event.event_type in (MouseEventType.SCROLL_UP, MouseEventType.SCROLL_DOWN):
            browser.seek_video(5 if event.event_type == MouseEventType.SCROLL_UP else -5, relative=True)
        elif event.event_type == MouseEventType.MOUSE_UP:
            browser.app.layout.focus(self)
            browser.seek_video(max(0., min(1., (event.position.x - 1) / self.width)) * browser.video_duration)
        else:
            return NotImplemented


class InfoLexer(Lexer):
    """Color only explicit status markers; filenames remain literal text."""
    def __init__(self):
        self.colors = {}
        self.image_lines = {}
        self.hash_lines = set()

    def lex_document(self, document):
        colors = self.colors.copy()
        image_lines = self.image_lines.copy()
        hash_lines = self.hash_lines.copy()

        def line(index):
            if index >= len(document.lines):
                return []
            text = document.lines[index]
            if index in hash_lines:
                return [('class:hash', text)]
            if index == 0 and not text.startswith(('Other Duplicates', 'Current disk size:')):
                return [('class:selected class:literal', text)]
            if index in image_lines:
                return image_lines[index]
            if index in colors and text.startswith('●'):
                return [('class:' + colors[index], text[:1]), ('class:literal', text[1:])]
            generated = text.startswith(('Size:', 'Dirs:', 'Created:', 'Modified:',
                                         'Image:', 'Other Duplicates', 'Current disk size:'))
            return [('' if generated else 'class:literal', text)]

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


BOOKMARKS_PATH = Path(".bookmarks.json")


def normalize_bookmark_path(path):
    """Use configured VFS identity for aliases, mount paths and report prefixes."""
    path = os.path.normpath(os.path.expanduser(path))
    if not path.startswith('/'):
        return path
    # An explicit alias is authoritative, including aliases such as /root.
    for alias in aliases:
        virtual = '/' + alias.strip('/')
        if path == virtual or path.startswith(virtual + '/'):
            return path
    mappings = [(os.path.abspath(os.path.expanduser(local)), alias)
                for alias, local in aliases.items() if local != '0']
    mappings.extend(('/' + prefix.strip('/'), mapping['alias'])
                    for prefix, mapping in prefixes.items() if mapping.get('local') != '0')
    for prefix, alias in sorted(mappings, key=lambda item: len(item[0]), reverse=True):
        prefix = prefix.rstrip('/')
        if path == prefix or path.startswith(prefix + '/'):
            return '/' + alias.strip('/') + path[len(prefix):]
    return path


class DriveBrowser:
    def __init__(self, vfs, *, path=None, input=None, output=None):
        import sys
        configure_image_terminal(probe=output is None and sys.stdout.isatty())
        self.native_preview = None
        self.native_visible = False
        self.native_drawn = None
        self.auto_quick_view = False
        self.image_previews = True
        self.info_directory = True
        self.graphics_mode = False
        self.files_scrollbar_dragging = False
        self.expanded_dirs = set()
        self.expansion_cwd = None
        self.expand_all_levels = False
        self.media_only = False
        self.hide_dotfiles = False
        self.video_path = None
        self.video_epoch = 0
        self.video_position = 0.
        self.video_duration = 0.
        self.video_image_id = None
        self.video_area = TextArea(read_only=True, wrap_lines=False, lexer=InfoLexer(),
                                   height=lambda: Dimension(min=1, preferred=self.video_frame_height(),
                                                            max=self.video_frame_height()))
        self.seek_control = VideoSeekControl(self)
        self.video_player = None
        self.video_status = ''
        self.video_first_row = 0
        self.video_dimensions = (1, 1)
        self.video_render_dimensions = (1, 1)
        self.video_metadata = TextArea(read_only=True, wrap_lines=True, lexer=InfoLexer(),
                                       height=Dimension(min=1, preferred=7, max=7))
        self.video_task = None
        self.video_workers = []
        self.play_button = Button('Play', handler=self.play_video)
        self.stop_button = Button('Stop', handler=self.stop_video)
        self.grid_layout_key = None
        self.grid_lines = []
        self.grid_positions = {}
        self.icon_size = 128
        self.icon_lines = 8
        self.grid_columns = 1
        self.grid_tile_width = 14
        self.grid_tile_height = 3
        self.thumbnail_epoch = 0
        self.thumbnail_task = None
        self.thumbnail_executor = None
        self.thumbnails = {}
        self.grid_native_drawn = None
        self.thumbnail_errors = 0
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
            'audio-play': '#bb66ff bold', 'bookmark': '#00ffff bold',
            'expanded-dir': 'bg:#707090', 'expanded-dir-name': '#e0b0ff bold',
        }) for theme in THEMES]
        self.rows = []
        self.history = []
        self.screen_stack = []
        self.actions = []
        self.bookmark_index = 0
        try:
            saved = json.loads(BOOKMARKS_PATH.read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                index = saved.get('selected_index', 0)
                self.bookmark_index = index if type(index) is int else 0
                saved = saved.get('bookmarks', [])
            paths = [normalize_bookmark_path(path) for path in saved
                     if isinstance(path, str) and path.startswith('/')] if isinstance(saved, list) else []
            selected_path = paths[max(0, min(self.bookmark_index, len(paths) - 1))] if paths else None
            self.bookmarks = list(dict.fromkeys(paths))
            self.bookmark_index = self.bookmarks.index(selected_path) if selected_path is not None else 0
        except (OSError, ValueError):
            self.bookmarks = []
        self.bookmark_index = max(0, min(self.bookmark_index, len(self.bookmarks) - 1))
        self.pending_bookmark = None
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
        self.info.window.height = lambda: Dimension(min=4 if self.video_path and
            hasattr(self, 'app') and self.app.output.get_size().rows >= 18 else 1)
        self.info.window.right_margins = [ScrollbarMargin()]
        self.info.window.cursorline = has_focus(self.info)
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

        bindings.add('b', eager=True)(lambda event: self.toggle_bookmark())
        bindings.add('j', eager=True)(lambda event: self.push(BookmarksView(self)))
        bindings.add('q', eager=True)(lambda event: event.app.exit())
        bindings.add('c-c')(lambda event: event.app.exit())
        bindings.add('p', filter=Condition(lambda: (not self.screen_stack or
            isinstance(self.screen_stack[-1][0], BookmarksView)) and bool(self.video_path) and
            not (self.screen_stack and (self.app.layout.has_focus(self.screen_stack[-1][0].path) or
                                       self.app.layout.has_focus(self.screen_stack[-1][0].number)))))(lambda event: self.toggle_playback())
        bind(['a'], lambda event: self.push(ActionsView(self)))
        bind(['s'], lambda event: self.push(ScannerView(self)))
        bind(['R'], lambda event: self.reset_current_map())
        bind(['h'], lambda event: self.push(HelpView(self, 'File manager help', main_help(self.display_mode))))
        bind(['delete'], lambda event: self.queue_remove())
        bind(['s-delete'], lambda event: self.queue_remove(all_duplicates=True))
        bind(['c-x'], lambda event: self.copy_info())
        bind(['up'], lambda event: self.move_grid_row(-1) if self.graphics_mode else self.move(-1), filter=files_focused)
        bind(['down'], lambda event: self.move_grid_row(1) if self.graphics_mode else self.move(1), filter=files_focused)
        bind(['pageup'], lambda event: self.move_grid_page(-1) if self.graphics_mode else self.move(-self.page_size()), filter=files_focused)
        bind(['pagedown'], lambda event: self.move_grid_page(1) if self.graphics_mode else self.move(self.page_size()), filter=files_focused)
        bind(['home'], lambda event: self.move(-len(self.rows)), filter=files_focused)
        bind(['end'], lambda event: self.move(len(self.rows)), filter=files_focused)
        bind(['enter'], lambda event: self.open(), filter=files_focused)
        bind(['right'], lambda event: self.move(1) if self.graphics_mode else self.open(), filter=files_focused)
        bind(['escape'], lambda event: self.parent())
        bind(['backspace'], lambda event: self.parent(), eager=True)
        bind(['left'], lambda event: self.move(-1) if self.graphics_mode else self.parent(), filter=files_focused)
        bind(['tab'], lambda event: self.focus_main(1))
        bind(['s-tab'], lambda event: self.focus_main(-1))
        bind(['g'], lambda event: self.toggle_graphics())
        bind(['u'], lambda event: self.expand_subdirs(), eager=True)
        bind(['o'], lambda event: self.toggle_expansion_depth(), eager=True)
        bind(['enter'], lambda event: self.open_duplicate(), filter=has_focus(self.info), eager=True)
        bind(['v'], lambda event: self.toggle_media_filter())
        bind(['.'], lambda event: self.toggle_dotfiles(), filter=files_focused)
        bind(['+', '='], lambda event: self.resize_icons(1), filter=files_focused)
        bind(['-'], lambda event: self.resize_icons(-1), filter=files_focused)
        bind(['y'], lambda event: self.toggle_auto_quick_view())
        bind(['i'], lambda event: self.toggle_image_previews())
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
                            Window(FormattedTextControl(self.info_title), height=1,
                                   style='class:info-header'),
                            ConditionalContainer(self.video_metadata,
                                                 filter=Condition(lambda: self.video_path is not None)),
                            ConditionalContainer(HSplit([
                                ConditionalContainer(self.video_area, filter=Condition(lambda: not self.audio_selected())),
                                VSplit([self.play_button, self.stop_button,
                                        Window(FormattedTextControl(lambda: safe_text(self.video_status)), height=1)], height=1),
                                Window(self.seek_control, height=1),
                            ]), filter=Condition(self.video_panel_visible)),
                            self.info,
                        ]),
                        Window(width=1),
                    ]),
                ]), style='class:info-pane',
                      width=lambda: Dimension.exact((get_app().output.get_size().columns + 1) // 2)),
            ]),
        ])
        self.main_layout = Layout(NumberHighlight(layout), focused_element=self.control)
        self.app = Application(layout=self.main_layout,
                               key_bindings=bindings, full_screen=True, mouse_support=True,
                               style=DynamicStyle(self.style), color_depth=ColorDepth.DEPTH_24_BIT,
                               input=input, output=output,
                               after_render=self.draw_native_preview)
        if hasattr(self.app.input, 'vt100_parser'):
            self.app.input.vt100_parser = KittyReplyFilter(self.app.input.vt100_parser)

    def info_title(self):
        return (f' Info · y:{"auto" if self.auto_quick_view else "off"}'
                f' · o:{"all" if self.expand_all_levels else "one"}'
                f' · .:{"hide" if self.hide_dotfiles else "show"}'
                f' · i:{"on" if self.image_previews else "off"}')

    def video_frame_height(self):
        # Keep controls, hashes, duplicate heading and its first row below frames.
        rows = self.app.output.get_size().rows if hasattr(self, 'app') else 27
        return max(1, min(self.video_dimensions[1], rows - 18))

    def audio_selected(self):
        return bool(self.video_path and os.path.splitext(self.video_path)[1].lower() in AUDIO_SUFFIXES)

    def video_panel_visible(self):
        if not self.video_path or not hasattr(self, 'app'):
            return False
        size = self.app.output.get_size()
        return size.rows >= 12 and size.columns >= 60

    def focus_main(self, direction):
        controls = [self.control, self.info]
        if self.video_panel_visible():
            controls.extend([self.play_button, self.stop_button, self.seek_control])
        index = next((i for i, control in enumerate(controls)
                      if self.app.layout.has_focus(control)), 0)
        self.app.layout.focus(controls[(index + direction) % len(controls)])

    def seek_video(self, seconds, relative=False):
        target = self.video_position + seconds if relative else seconds
        target = max(0., min(self.video_duration, target)) if self.video_duration else max(0., target)
        self.video_position = target
        if self.video_player is not None:
            self.video_player.seek(target)
        self.app.invalidate()

    async def load_video_poster(self, path, epoch):
        file_id = self.video_file_id
        try:
            from term_image.utils import get_cell_size
            cell_width, cell_height = get_cell_size() or (8, 16)
            item = await background_call(prepare_grid_thumbnail, path, file_id, 256,
                                         self.video_dimensions, cell_width / cell_height)
            if self.video_epoch != epoch or self.video_player is not None:
                return
            ScanStore(self.vfs.db).put('thumbnail', f'256:{file_id}', item['record'])
            self.apply_video_frame(item)
            self.app.invalidate()
        except Exception as exc:
            # Preview failures must remain local, never invoke PT's blocking
            # background-task exception dialog while navigating the file list.
            if self.video_epoch == epoch:
                self.video_status = 'Still unavailable: ' + safe_text(str(exc))[:100]
                self.app.invalidate()

    def apply_video_frame(self, value):
        if value['native']:
            art, dimensions = value['native']
            # Grid serialization uses its own layer; posters belong to quick view.
            self.native_preview = (art.replace('z=732', 'z=731'), dimensions,
                                   max(0, (self.video_dimensions[1] - dimensions[1]) // 2))
        else:
            self.native_preview = None
            self.video_area.lexer.image_lines = dict(enumerate(value['lines']))
            self.video_area.text = '\n'.join(''.join(text for _, text in row) for row in value['lines'])

    def stop_video(self):
        if self.video_player is not None:
            self.video_player.close()
            self.video_player = None
        self.video_status = 'Stopped'
        if hasattr(self, 'app'):
            self.app.invalidate()

    def toggle_playback(self):
        if self.video_player is None:
            self.play_video()
        else:
            self.stop_video()

    def play_video(self):
        if not self.video_path or self.video_player is not None:
            return
        if self.video_status == 'Finished' or (self.video_duration and
                self.video_position >= self.video_duration - .1):
            self.video_position = 0.
        self.video_epoch += 1  # Ignore an unfinished still-preview request.
        width, height = self.video_dimensions
        from term_image.utils import get_cell_size
        cell_width, cell_height = get_cell_size() or (8, 16)
        player = VideoPreview(self.video_path, (min(1280, width * cell_width),
                                              min(720, height * cell_height)),
                              lambda image: serialize_video_frame(image, self.video_render_dimensions))
        self.video_player = player
        self.video_workers = [worker for worker in self.video_workers if worker.thread.is_alive()]
        self.video_workers.append(player)
        self.video_status = 'Starting…'
        player.start()
        if self.video_position:
            player.seek(self.video_position)
        self.video_task = self.app.create_background_task(self.receive_video(player))
        self.app.invalidate()

    async def receive_video(self, player):
        from queue import Empty
        try:
            while self.video_player is player:
                try:
                    kind, value = player.events.get_nowait()
                except Empty:
                    await asyncio.sleep(.03)
                    continue
                if kind == 'error':
                    self.video_status = value
                elif kind == 'end':
                    if self.video_status in ('Starting…', 'Playing'):
                        self.video_status = 'Finished'
                    self.video_player = None
                    break
                elif kind == 'progress':
                    self.video_status = 'Playing'
                    self.video_position, self.video_duration = value
                elif kind == 'frame':
                    self.video_status = 'Playing'
                    self.video_position = value.get('_position', self.video_position)
                    self.video_duration = value.get('_duration', self.video_duration)
                    self.apply_video_frame(value)
                self.app.invalidate()
        except Exception as exc:
            if self.video_player is player:
                self.video_status = 'Video preview error: ' + safe_text(str(exc))[:100]
                self.video_player = None
        finally:
            player.close()
            self.app.invalidate()

    def icon_dimensions(self):
        from term_image.utils import get_cell_size
        cell_width, cell_height = get_cell_size() or (8, 16)
        return (max(1, math.ceil(self.icon_lines * cell_height / cell_width)),
                self.icon_lines)

    @staticmethod
    def is_media(row):
        return not row['node'].is_dir and os.path.splitext(row['name'])[1].lower() in MEDIA_SUFFIXES

    def toggle_dotfiles(self):
        self.hide_dotfiles = not self.hide_dotfiles
        self.refresh(self.current_name(), update_info=self.video_player is None)

    def toggle_media_filter(self):
        self.media_only = not self.media_only
        self.refresh(self.current_name())

    def move_grid_row(self, direction):
        if not self.rows or self.selected not in self.grid_positions:
            return
        x, y, _, _ = self.grid_positions[self.selected]
        line = y - 1 if direction < 0 else y + 1
        while 0 <= line < len(self.grid_lines):
            entries = self.grid_lines[line][0]
            if self.grid_positions[entries[0]][1] != y:
                self.select(min(entries, key=lambda index: abs(self.grid_positions[index][0] - x)))
                return
            line += direction

    def move_grid_page(self, direction):
        if self.selected not in self.grid_positions:
            return
        x, y, _, _ = self.grid_positions[self.selected]
        height = self.files.render_info.window_height if self.files.render_info else 10
        target = max(0, min(len(self.grid_lines) - 1, y + direction * height))
        entries = self.grid_lines[target][0]
        self.select(min(entries, key=lambda index: abs(self.grid_positions[index][0] - x)))

    def toggle_graphics(self):
        self.graphics_mode = not self.graphics_mode
        self.refresh(self.current_name(), update_info=False)
        self.app.invalidate()

    def toggle_expansion_depth(self):
        self.app.layout.focus(self.control)
        self.expand_all_levels = not self.expand_all_levels
        self.app.invalidate()

    def expand_subdirs(self):
        if not self.rows:
            return
        row = self.rows[self.selected]
        if not row['node'].is_dir:
            return
        self.app.layout.focus(self.control)
        roots = (self.vfs.list_nodes() if row['name'] == '..' else [row['node']])
        roots = [node for node in roots if node.is_dir]
        if roots and all(node.id in self.expanded_dirs for node in roots):
            # Collapsing a subtree clears its descendant expansion state as well.
            prefixes = [node.id.rstrip('/') + '/' for node in roots]
            root_ids = {node.id for node in roots}
            self.expanded_dirs = {path for path in self.expanded_dirs
                                  if path not in root_ids and not any(path.startswith(prefix) for prefix in prefixes)}
            self.refresh(row['name'], update_info=False)
            return
        pending = roots.copy()
        visited = set()
        while pending:
            node = pending.pop()
            # Directory symlinks stay visible but never recurse into cycles or aliases.
            if node.id in visited or os.path.islink(get_real_path(node.id)):
                continue
            visited.add(node.id)
            self.expanded_dirs.add(node.id)
            if self.expand_all_levels:
                pending.extend(child for child in self.vfs.list_nodes(node) if child.is_dir)
        self.refresh(row['name'], update_info=False)

    def resize_icons(self, direction):
        if not self.graphics_mode:
            return
        from term_image.utils import get_cell_size
        _, cell_height = get_cell_size() or (8, 16)
        lines = max(1, min(max(1, 256 // cell_height), self.icon_lines + direction))
        if lines != self.icon_lines:
            self.icon_lines = lines
            # Keep JPEG resolution independent from the display zoom.
            self.icon_size = 128 if lines * cell_height <= 128 else 256
            self.start_thumbnails()
            self.app.invalidate()

    def start_thumbnails(self):
        self.thumbnail_epoch += 1
        self.thumbnails = {}
        self.thumbnail_errors = 0
        if self.thumbnail_task is not None and not self.thumbnail_task.done():
            return  # Existing worker finishes its current conversion, then restarts.
        if not self.graphics_mode or not self.image_previews or self.app.is_done:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        if self.thumbnail_executor is None:
            from concurrent.futures import ThreadPoolExecutor
            self.thumbnail_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='drive-thumbnails')
        self.thumbnail_task = self.app.create_background_task(self.generate_thumbnails())

    async def generate_thumbnails(self):
        from term_image.exceptions import TermImageError
        epoch = self.thumbnail_epoch
        size = self.icon_size
        icon_width, icon_height = self.icon_dimensions()
        dimensions = (max(14, icon_width + 2) - 2, icon_height)
        from term_image.utils import get_cell_size
        cell_width, cell_height = get_cell_size() or (8, 16)
        cell_ratio = cell_width / cell_height
        store = ScanStore(self.vfs.db)
        try:
            for row in list(self.rows):
                if epoch != self.thumbnail_epoch or not self.graphics_mode or not self.image_previews:
                    break
                node = row['node']
                if node.is_dir or os.path.splitext(node.name)[1].lower() not in THUMBNAIL_SUFFIXES:
                    continue
                try:
                    item = await asyncio.get_running_loop().run_in_executor(
                        self.thumbnail_executor, prepare_grid_thumbnail, get_real_path(node.id),
                        node.id, size, dimensions, cell_ratio)
                    if epoch != self.thumbnail_epoch:
                        break
                    # Attach only complete worker results; keep DB writes on UI thread.
                    store.put('thumbnail', f'{size}:{node.id}', item['record'])
                    self.thumbnails[node.id] = item
                except (OSError, ValueError, Warning, TermImageError):
                    self.thumbnail_errors += 1
                    self.thumbnails[node.id] = {'native': None, 'lines': [],
                                                'dimensions': (0, 0), 'failed': True}
                self.app.invalidate()  # Append the finished icon without reordering files.
                await asyncio.sleep(0)
        finally:
            self.thumbnail_task = None
            if self.app.is_done or not self.graphics_mode or not self.image_previews:
                if self.thumbnail_executor is not None:
                    self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
                    self.thumbnail_executor = None
            if epoch != self.thumbnail_epoch and self.graphics_mode and self.image_previews and not self.app.is_done:
                self.start_thumbnails()

    def grid_content(self, width, height, header=False):
        icon_width, icon_height = self.icon_dimensions()
        self.grid_tile_width = max(14, icon_width + 2)
        self.grid_tile_height = icon_height + 2
        self.grid_columns = max(1, (width + 1) // (self.grid_tile_width + 1))
        columns, tile_width, tile_height = self.grid_columns, self.grid_tile_width, self.grid_tile_height
        key = (id(self.rows), len(self.rows), width, columns, tile_width, tile_height)
        if self.grid_layout_key != key:
            self.grid_lines, self.grid_positions = [], {}
            pending = []
            def flush():
                if not pending:
                    return
                first = len(self.grid_lines)
                entries = pending.copy()
                for column, index in enumerate(entries):
                    self.grid_positions[index] = (column * (tile_width + 1), first, tile_width, True)
                self.grid_lines.extend((entries, offset, True) for offset in range(tile_height))
                pending.clear()
            for index, row in enumerate(self.rows):
                if self.is_media(row):
                    pending.append(index)
                    if len(pending) == columns:
                        flush()
                else:
                    flush()
                    self.grid_positions[index] = (0, len(self.grid_lines), width, False)
                    self.grid_lines.append(([index], 0, False))
            flush()
            self.grid_layout_key = key
        if header:
            title = f' Graphics u:show/hide o:{"all" if self.expand_all_levels else "one"} · {"media" if self.media_only else "all"} · {self.icon_lines} lines · cache {self.icon_size}x{self.icon_size} · {len(self.thumbnails)} previews'
            if self.thumbnail_errors:
                title += f' · {self.thumbnail_errors} unavailable'
            return UIContent(get_line=lambda _: [('class:table-header', fit(title, width))], line_count=1)

        def line(index):
            if not self.grid_lines:
                return [('', '(empty)')]
            entries, subrow, media = self.grid_lines[index]
            if not media:
                row = self.rows[entries[0]]
                style = 'class:selected' if entries[0] == self.selected else 'class:' + row['color']
                if not row['node'].is_dir:
                    style += ' class:muted'
                prefix = ' B ' if self.bookmark_path(row) in self.bookmarks else ' '
                label = prefix + fit_filename(row['name'] + ('/' if row['node'].is_dir and row['name'] != '..' else ''), max(0, width - len(prefix)))
                if row['node'].is_dir and row['node'].id in self.expanded_dirs:
                    if entries[0] != self.selected:
                        style += ' class:expanded-dir'
                    name = label.rstrip()
                    return bookmark_label(style + ' class:expanded-dir-name', name, prefix == ' B ') + [(style, ' ' * (width - get_cwidth(name)))]
                return bookmark_label(style, label, prefix == ' B ')
            fragments = []
            for column, entry in enumerate(entries):
                if column:
                    fragments.append(('', ' '))
                row = self.rows[entry]
                style = 'class:selected' if entry == self.selected else 'class:' + row['color']
                item = self.thumbnails.get(row['node'].id) if self.image_previews else None
                if subrow == icon_height:
                    prefix = ' B ' if self.bookmark_path(row) in self.bookmarks else ' '
                    fragments.extend(bookmark_label(style, prefix + fit_filename(row['name'], max(0, tile_width - len(prefix) - 1)) + ' ', prefix == ' B '))
                elif subrow < icon_height:
                    image_width, image_height = item['dimensions'] if item else (0, 0)
                    top = (icon_height - image_height) // 2
                    left = (tile_width - image_width) // 2
                    image_row = subrow - top
                    if item and not item['native'] and 0 <= image_row < len(item['lines']):
                        image_line = item['lines'][image_row]
                        used = sum(get_cwidth(text) for _, text in image_line)
                        fragments.append((style, ' ' * left))
                        fragments.extend((style + ' ' + color, text) for color, text in image_line)
                        fragments.append((style, ' ' * max(0, tile_width - left - used)))
                    else:
                        eligible = (not row['node'].is_dir and
                                    os.path.splitext(row['name'])[1].lower() in THUMBNAIL_SUFFIXES)
                        pending = self.image_previews and eligible and item is None
                        audio = os.path.splitext(row['name'])[1].lower() in AUDIO_SUFFIXES
                        label = '▶' if audio and subrow == icon_height // 2 else ('.' if pending and subrow == icon_height // 2 else '')
                        fragments.append((style + (' class:audio-play' if audio else ''), fit(label.center(tile_width), tile_width)))
                else:
                    fragments.append((style, ' ' * tile_width))
            return fragments or [('', '(empty)')]

        x, y, _, media = self.grid_positions.get(self.selected, (0, 0, 0, False))
        # Keep the filename visible when scrolling to the final tile row.
        if media:
            y += icon_height
        return UIContent(get_line=line, line_count=max(1, len(self.grid_lines)),
                         cursor_position=Point(x=x, y=y), show_cursor=False)

    def clear_grid_native(self):
        if getattr(self, 'grid_native_drawn', None):
            self.app.output.write_raw('\x1b_Ga=d,d=Z,z=732,q=2;\x1b\\')
            self.app.output.flush()
        self.grid_native_drawn = None

    def draw_grid_native(self, app):
        if not getattr(self, 'graphics_mode', False) or not self.image_previews or self.screen_stack or app.is_done:
            self.clear_grid_native()
            return
        render = self.files.render_info
        screen = app.renderer._last_screen
        position = screen.visible_windows_to_write_positions.get(self.files) if screen else None
        if not render or not position:
            self.clear_grid_native()
            return
        overlays = []
        visible_inputs = render.input_line_to_visible_line
        visible_entries = set()
        for line in visible_inputs:
            if 0 <= line < len(self.grid_lines):
                visible_entries.update(self.grid_lines[line][0])
        for index in sorted(visible_entries):
            row = self.rows[index]
            item = self.thumbnails.get(row['node'].id)
            if not item or not item['native']:
                continue
            art, (width, height) = item['native']
            icon_height = self.grid_tile_height - 2
            top = (icon_height - height) // 2
            tile_x, tile_y, _, _ = self.grid_positions[index]
            first = tile_y + top
            visible = [render.input_line_to_visible_line.get(first + offset) for offset in range(height)]
            x = tile_x + (self.grid_tile_width - width) // 2
            if (any(y is None for y in visible) or visible[-1] >= render.window_height
                    or x + width > render.window_width - 1):
                continue
            overlays.append((art, position.xpos + x, position.ypos + visible[0]))
        signature = tuple((id(art), x, y) for art, x, y in overlays)
        if signature == self.grid_native_drawn:
            return
        self.clear_grid_native()
        if overlays:
            app.output.write_raw('\x1b7' + ''.join(f'\x1b[{y+1};{x+1}H' + native_graphics_payload(art) for art, x, y in overlays) + '\x1b8')
            app.output.flush()
            self.grid_native_drawn = signature


    def clear_native_preview(self):
        if self.native_visible:
            # Delete only this pane's Kitty z-index, retaining other graphics.
            self.app.output.write_raw('\x1b_Ga=d,d=Z,z=731,q=2;\x1b\\')
            self.app.output.flush()
            self.native_visible = False
        self.native_drawn = None
        self.video_image_id = None

    def install_files_scrollbar(self, app):
        """Margins have no default PT mouse handler; bind the painted column."""
        screen = app.renderer._last_screen
        position = screen.visible_windows_to_write_positions.get(self.files) if screen else None
        if not position or self.screen_stack or not self.files.render_info or app.is_done:
            self.files_scrollbar_dragging = False
            return
        def click(event):
            active = self.files_scrollbar_dragging
            if event.event_type == MouseEventType.MOUSE_DOWN:
                if event.button != MouseButton.LEFT:
                    return NotImplemented
                self.files_scrollbar_dragging = True
                # Capture immediately, even if more input arrives before redraw.
                self.install_files_scrollbar(app)
            elif event.event_type == MouseEventType.MOUSE_MOVE:
                if not active:
                    return NotImplemented
                if event.button != MouseButton.LEFT:
                    self.files_scrollbar_dragging = False
                    app.invalidate()
                    return
            elif event.event_type == MouseEventType.MOUSE_UP:
                if not active:
                    return NotImplemented
                self.files_scrollbar_dragging = False
            else:
                return NotImplemented
            y = max(0, min(position.height - 1, event.position.y - position.ypos))
            if self.graphics_mode and self.grid_lines:
                line = round(y * (len(self.grid_lines) - 1) / max(1, position.height - 1))
                entries = self.grid_lines[line][0]
                index = entries[-1] if y == position.height - 1 else entries[0]
            else:
                index = round(y * max(0, len(self.rows) - 1) / max(1, position.height - 1))
            app.layout.focus(self.control)
            self.select(index)
        if self.files_scrollbar_dragging:
            size = app.output.get_size()
            # Keep the drag captured when the pointer leaves the narrow track.
            bounds = dict(x_min=0, x_max=size.columns, y_min=0, y_max=size.rows)
        else:
            bounds = dict(x_min=position.xpos + position.width - 1,
                          x_max=position.xpos + position.width,
                          y_min=position.ypos, y_max=position.ypos + position.height)
        app.renderer.mouse_handlers.set_mouse_handler_for_range(**bounds, handler=click)

    def refit_image_on_resize(self, app):
        node = getattr(self, 'image_preview_node', None)
        if node is None or app.is_done or (self.screen_stack and
                not isinstance(self.screen_stack[-1][0], BookmarksView)):
            return False
        size = app.output.get_size()
        render = self.info.window.render_info
        geometry = (size.columns, size.rows, render.window_width if render else 37)
        if geometry == getattr(self, 'image_preview_geometry', None):
            return False
        self.show_info(preview_node=node)
        app.invalidate()
        return True

    def draw_native_preview(self, app):
        if hasattr(self, 'files'):
            self.install_files_scrollbar(app)
        if self.refit_image_on_resize(app):
            self.clear_native_preview()
            return
        self.draw_grid_native(app)
        if getattr(self, 'video_path', None) and self.video_area.window.render_info:
            visible = self.video_area.window.render_info
            width, height = self.video_dimensions
            scale = min(1., max(1, visible.window_width - 1) / width,
                        max(1, visible.window_height) / height)
            self.video_render_dimensions = (max(1, int(width * scale)), max(1, int(height * scale)))
        if (getattr(self, 'video_path', None) and not self.video_panel_visible()
                and any(app.layout.has_focus(control)
                        for control in (self.play_button, self.stop_button, self.seek_control))):
            app.layout.focus(self.screen_stack[-1][0].table if self.screen_stack and isinstance(self.screen_stack[-1][0], BookmarksView) else self.control)
        if app.is_done:
            self.stop_video()
        if (self.screen_stack and not isinstance(self.screen_stack[-1][0], BookmarksView)) or not self.native_preview or app.is_done:
            self.clear_native_preview()
            return
        art, (width, height), first_row = self.native_preview
        window = self.video_area.window if getattr(self, 'video_path', None) else self.info.window
        render = window.render_info
        screen = app.renderer._last_screen
        position = screen.visible_windows_to_write_positions.get(window) if screen else None
        if getattr(self, 'video_path', None) and render and position:
            available_width = max(1, render.window_width - 1)
            available_height = max(1, render.window_height)
            first_row = max(0, (available_height - height) // 2)
            scale = min(1., available_width / width, available_height / height)
            fitted = (max(1, int(width * scale)), max(1, int(height * scale)))
            if fitted != (width, height):
                self.video_render_dimensions = fitted
                width, height = fitted
                # c/r are Kitty placement cell dimensions, not decoded pixels.
                art = re.sub(r'(?<=[,G])c=\d+', f'c={width}', art)
                art = re.sub(r'(?<=[,G])r=\d+', f'r={height}', art)
                self.native_preview = (art, fitted, first_row)
        if not render or not position or width > render.window_width - 1:
            self.clear_native_preview()
            return
        # Only draw when all reserved image rows are visible. This avoids
        # graphics spilling into borders/metadata during scrolling or resize.
        rows = [render.input_line_to_visible_line.get(first_row + offset)
                for offset in range(height)]
        if any(row is None for row in rows) or rows != list(range(rows[0], rows[0] + height)):
            self.clear_native_preview()
            return
        if rows[-1] >= render.window_height:
            self.clear_native_preview()
            return
        left = max(0, (render.window_width - 1 - width) // 2)
        placement = (id(art), position.xpos + left, position.ypos + rows[0], width, height)
        if self.native_visible and self.native_drawn == placement:
            return
        art = native_graphics_payload(art)
        video = bool(getattr(self, 'video_path', None))
        previous_id = getattr(self, 'video_image_id', None)
        if video:
            image_id = 731002 if previous_id == 731001 else 731001
            art = art.replace('\x1b_G', f'\x1b_Gi={image_id},', 1)
            # Transmit/display the next frame before releasing the previous one.
            # Never clear the video layer between frames.
            cleanup = f'\x1b_Ga=d,d=I,i={previous_id},q=2;\x1b\\' if previous_id else ''
            self.video_image_id = image_id
        else:
            self.clear_native_preview()
            cleanup = ''
        app.output.write_raw('\x1b7' + f'\x1b[{position.ypos + rows[0] + 1};{position.xpos + left + 1}H'
                             + art + cleanup + '\x1b8')
        app.output.flush()
        self.native_visible = True
        self.native_drawn = placement

    def style(self):
        # A new Style on each render changes its invalidation hash and forces
        # prompt_toolkit to repaint the entire screen instead of changed cells.
        return self.styles[self.theme]

    def column_header(self):
        name, size, dups = self.columns
        return [('class:table-header', fit('Media' if self.media_only else 'Name', name) + ' ' + fit(' Size', size) + ' ' + fit(' Dups', dups))]

    def current_name(self):
        return self.rows[self.selected]['name'] if self.rows else None

    def refresh(self, target=None, *, update_info=True):
        if self.expansion_cwd != self.vfs.pwd():
            self.expanded_dirs.clear()
            self.expansion_cwd = self.vfs.pwd()
        entries = []
        pending = [(node.name, node) for node in reversed(self.vfs.list_nodes())]
        seen = set()
        while pending:
            name, node = pending.pop()
            if self.hide_dotfiles and node.name.startswith('.'):
                continue
            if node.id in seen:
                continue
            seen.add(node.id)
            entries.append((name, node))
            if node.is_dir and node.id in self.expanded_dirs:
                pending.extend((name + '/' + child.name, child)
                               for child in reversed(self.vfs.list_nodes(node)))
        parent = self.vfs.get('..')
        if parent is not None:
            entries.insert(0, ('..', parent))
        self.rows = []
        for name, node in entries:
            media = not node.is_dir and os.path.splitext(name)[1].lower() in MEDIA_SUFFIXES
            if self.media_only and not node.is_dir and not media:
                continue
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
        self.grid_layout_key = None
        self.grid_positions = {}
        self.metadata_widths = (max([4] + [len(row['size']) for row in self.rows]) + 1,
                                max([4] + [len(row['dups']) for row in self.rows]) + 3)
        self.selected = next((i for i, row in enumerate(self.rows) if row['name'] == target), 0)
        if update_info:
            self.show_info(directory=not self.auto_quick_view or self.current_name() == '..')
        else:
            self.update_listing_stats()
        if hasattr(self, 'app'):
            self.start_thumbnails()
            self.app.invalidate()

    def page_size(self):
        if self.graphics_mode:
            height = self.files.render_info.window_height if self.files.render_info else 10
            return max(1, height // self.grid_tile_height) * self.grid_columns
        return max(1, self.files.render_info.window_height - 1) if self.files.render_info else 10

    def select(self, index):
        selected = max(0, min(max(0, len(self.rows) - 1), index))
        if selected != self.selected:
            self.selected = selected
            if self.video_player is None and self.auto_quick_view:
                self.show_info(directory=self.current_name() == '..')
        self.app.invalidate()

    def move(self, delta):
        self.select(self.selected + delta)

    def toggle_auto_quick_view(self):
        self.auto_quick_view = not self.auto_quick_view
        if self.auto_quick_view and self.video_player is None:
            self.show_info(directory=self.current_name() == '..')
        self.app.invalidate()

    def toggle_image_previews(self):
        self.image_previews = not self.image_previews
        self.show_info(directory=self.info_directory)
        self.start_thumbnails()
        self.app.invalidate()

    def open(self):
        name = self.current_name()
        if name == '..':
            self.parent()
        elif name is not None and self.rows[self.selected]['node'].is_dir:
            self.history.append((self.vfs.pwd(), name))
            self.vfs.cwd = self.rows[self.selected]['node']
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

    def listing_stats(self):
        visible = [row for row in self.rows if row['name'] != '..']
        directories = sum(row['node'].is_dir for row in visible)
        files = len(visible) - directories
        return f'Dirs: {directories} · Files: {files}'

    def update_listing_stats(self):
        # Update a fixed logical row without replacing the opened preview/player.
        for area in (self.info, self.video_metadata):
            lines = area.text.split('\n')
            for index, line in enumerate(lines):
                if line.startswith('Dirs: '):
                    text = self.listing_stats()
                    if line != text:
                        cursor = area.buffer.cursor_position
                        lines[index] = text
                        area.text = '\n'.join(lines)
                        area.buffer.cursor_position = min(cursor, len(area.text))
                    break

    def show_info(self, directory=False, preview_node=None):
        self.stop_video()
        self.video_epoch += 1
        self.video_position = self.video_duration = 0.
        self.video_path = None
        if hasattr(self, 'app') and any(self.app.layout.has_focus(control)
                                       for control in (self.play_button, self.stop_button, self.seek_control)):
            self.app.layout.focus(self.screen_stack[-1][0].table if self.screen_stack and isinstance(self.screen_stack[-1][0], BookmarksView) else self.control)
        self.info_directory = directory
        self.image_preview_node = None
        self.native_preview = None
        self.info_lexer.hash_lines = set()
        self.info_lexer.colors = {}
        self.info_lexer.image_lines = {}
        self.info_paths = {}
        if directory and self.vfs.pwd() == "/":
            lines = ["/", "╭────────╮  drive.py v0.992", "│ ━━━━ ● │  File Manager",
                     "╰────────╯  Explore • Compare • Keep", "", "h: Open help view", "",
                     *main_help(self.display_mode)]
            from term_image.image import KittyImage, auto_image_class
            if self.image_previews and issubclass(auto_image_class(), KittyImage):
                render = self.info.window.render_info
                width = max(1, (render.window_width - 1) // 2) if render else 18
                height = max(1, (render.window_height - 10) // 2) if render else 7

                def native_logo(art, dimensions):
                    self.native_preview = (art, dimensions, 1)

                logo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'assets', 'info-logo.png')
                preview_lines = ascii_image_preview(logo, width, height,
                                                   color=True, native=native_logo)
                if self.native_preview:
                    # Keep the title/help below the real logo; no block fallback.
                    lines = ['/', *preview_lines[1:], '', 'drive.py — File Manager',
                             'Explore • Compare • Keep', '', 'h: Open help view', '',
                             *main_help(self.display_mode)]
            self.info.lexer = MarkupLexer()
            self.info.text = plain_markup("\n".join(lines))
            self.info.lexer.fragments = markup_lines(lines)
            self.info.buffer.cursor_position = 0
            return
        self.info.lexer = self.info_lexer
        if not self.rows and not directory and preview_node is None:
            self.info.text = self.vfs.pwd() + '\n\nNo files.'
            return
        row = self.rows[self.selected] if self.rows else None
        node = preview_node if preview_node is not None else (self.vfs.get_cwd() if directory else row['node'])
        info = self.vfs.get_full_info(node)

        def timestamp(key):
            value = info.get(key)
            try:
                return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S') if value is not None else ''
            except (ValueError, OverflowError, OSError):
                return ''

        self.info_lexer.colors[1] = (
            'green' if info.get('exists') else 'red') if directory or preview_node is not None else row['indicator']
        size = format_size(node.size, 0).strip()
        lines = [node.id or '/', '●', 'Size:   ' + size, self.listing_stats(),
                 'Created:  ' + timestamp('created'),
                 'Modified: ' + timestamp('modified')]
        if not node.is_dir:
            lines.insert(2, 'Name: ' + node.name)
            if os.path.splitext(node.name)[1].lower() in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
                self.video_file_id = node.id
                self.video_path = os.path.abspath(get_real_path(node.id))
                self.video_status = 'Press Play'
                render = self.info.window.render_info
                width = max(1, min(80, render.window_width - 1)) if render else 36
                height = max(1, min(30, self.app.output.get_size().rows - 18)) if hasattr(self, 'app') else 10
                self.video_dimensions = (width, height)
                self.video_render_dimensions = (width, height)
                self.video_first_row = 0
                self.video_area.lexer.image_lines = {}
                self.video_area.text = '\n'.join([' ' * width] * height)
                if hasattr(self, 'app') and self.image_previews and not self.audio_selected():
                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        pass
                    else:
                        self.app.create_background_task(self.load_video_poster(self.video_path, self.video_epoch))
            if self.image_previews and os.path.splitext(node.name)[1].lower() in IMAGE_SUFFIXES:
                self.image_preview_node = node
                size = self.app.output.get_size()
                render = self.info.window.render_info
                self.image_preview_geometry = (size.columns, size.rows, render.window_width if render else 37)
                width = max(1, render.window_width - 1) if render else 36
                # Reserve bottom metadata and the first duplicate as well as chrome.
                height = max(1, self.app.output.get_size().rows - 20) if hasattr(self, 'app') else 14
                from prompt_toolkit.formatted_text import ANSI, to_formatted_text
                lines.append('')
                def native(art, dimensions):
                    self.native_preview = (art, dimensions, len(lines) + 1 + max(0, (height - dimensions[1]) // 2))
                preview_lines = ascii_image_preview(get_real_path(node.id), width, height,
                                                    color=True, native=native)
                image_height = len(preview_lines) - 1
                top = max(0, (height - image_height) // 2)
                preview_lines = preview_lines[:1] + [''] * top + preview_lines[1:] + [''] * max(0, height - image_height - top)
                for index, image_line in enumerate(preview_lines):
                    fragments = to_formatted_text(ANSI(image_line))
                    if index and not self.native_preview:
                        used = sum(get_cwidth(text) for _, text in fragments)
                        fragments.insert(0, ('', ' ' * max(0, (width - used) // 2)))
                    self.info_lexer.image_lines[len(lines)] = fragments
                    lines.append(''.join(text for _, text in fragments))
                lines.append('')
            self.info_lexer.hash_lines.add(len(lines))
            hashes = node.info.get('hashinfo') or ''
            lines.extend([', '.join(sorted(hashes)) if isinstance(hashes, set) else str(hashes), '',
                          f'Other Duplicates ({len(info.get("dups", []))}):'])
            for path, state in zip(info.get('dups', []), info.get('dups_states', [])):
                self.info_lexer.colors[len(lines)] = 'green' if state.get('exists') else 'red'
                self.info_paths[len(lines)] = path
                lines.append('● ' + path)
            if info.get('exists') and info.get('size') != node.size:
                lines.append(f'Current disk size: {info.get("size")} bytes')
        if self.video_path:
            # Path/status/name/size/created/modified stay above the video.
            boundary = next(index for index, line in enumerate(lines) if line.startswith('Modified:')) + 1
            self.video_metadata.text = '\n'.join(safe_text(line) for line in lines[:boundary])
            lines = lines[boundary:]
            self.info_lexer.hash_lines = {index - boundary for index in self.info_lexer.hash_lines if index >= boundary}
            self.info_paths = {index - boundary: path for index, path in self.info_paths.items()
                               if index >= boundary}
            self.info_lexer.colors = {index - boundary: color for index, color in self.info_lexer.colors.items()
                                      if index >= boundary}
        self.info.text = '\n'.join(safe_text(line) for line in lines)
        self.info.buffer.cursor_position = 0

    def bookmark_path(self, row):
        # The parent-navigation row represents the current directory for bookmarks.
        return normalize_bookmark_path(self.vfs.pwd() if row['name'] == '..' else row['node'].id)

    def save_bookmarks(self):
        temporary = BOOKMARKS_PATH.with_suffix('.json.tmp')
        self.bookmark_index = max(0, min(self.bookmark_index, len(self.bookmarks) - 1))
        state = {'bookmarks': self.bookmarks, 'selected_index': self.bookmark_index}
        temporary.write_text(json.dumps(state, ensure_ascii=False) + '\n', encoding='utf-8')
        temporary.replace(BOOKMARKS_PATH)

    def toggle_bookmark(self):
        if self.screen_stack and isinstance(self.screen_stack[-1][0], BookmarksView):
            self.screen_stack[-1][0].remove()
            return
        path = None
        for screen, _ in reversed(self.screen_stack):
            if isinstance(screen, ScannerView) and screen.detail_ids:
                entry = screen.model.entries[screen.detail_ids[screen.details.index]]
                path = entry.path
                break
        if path is None:
            if self.main_layout.has_focus(self.info):
                path = self.info_paths.get(self.info.buffer.document.cursor_position_row)
            elif self.rows:
                path = self.bookmark_path(self.rows[self.selected])
        path = normalize_bookmark_path(path or self.vfs.pwd())
        if path in self.bookmarks:
            self.bookmarks.remove(path)
        else:
            self.bookmarks.append(path)
        self.save_bookmarks()
        for screen, _ in self.screen_stack:
            if isinstance(screen, BookmarksView):
                screen.refresh()
        self.app.invalidate()

    def go_bookmark(self, index):
        if 0 <= index < len(self.bookmarks):
            path = normalize_bookmark_path(self.bookmarks[index])
            if self.vfs.get_from_path(path) is None:
                if self.screen_stack and isinstance(self.screen_stack[-1][0], BookmarksView):
                    self.screen_stack[-1][0].details.text = (safe_text(path) +
                        '\nBookmark unavailable. Check the drive mapping in config.sh or edit its path.')
                return
            self.bookmarks[index] = path
            self.bookmark_index = index
            self.save_bookmarks()
            self.pending_bookmark = self.bookmarks[index]
            self.finish_bookmark()

    def finish_bookmark(self):
        if self.pending_bookmark is None:
            return
        if self.screen_stack:
            self.screen_stack[-1][0].close()
            return
        path = self.pending_bookmark
        self.pending_bookmark = None
        node = self.vfs.get_from_path(path)
        if node is not None:
            self.vfs.cwd = node if node.is_dir else self.vfs.get_from_path(path.rpartition('/')[0] or '/')
            self.history.clear()
            self.media_only = False
            self.refresh(None if node.is_dir else node.name)
            if not node.is_dir:
                self.show_info()
            self.app.layout.focus(self.control)

    def open_duplicate(self):
        path = self.selected_path()
        if not path:
            return
        parent, _, name = path.rpartition('/')
        node = self.vfs.get_from_path(parent or '/')
        if node is not None and node.is_dir:
            self.vfs.cwd = node
            self.history.clear()
            self.refresh(name)
            self.show_info()
            self.app.layout.focus(self.control)

    def push(self, screen):
        self.files_scrollbar_dragging = False
        self.stop_video()
        self.screen_stack.append((screen, self.app.layout))
        self.app.layout = Layout(NumberHighlight(screen.container), focused_element=screen.focus)
        screen.start()
        self.app.invalidate()

    def pop(self, screen):
        if not self.screen_stack or self.screen_stack[-1][0] is not screen:
            return
        _, layout = self.screen_stack.pop()
        self.app.layout = layout
        self.app.invalidate()
        self.finish_bookmark()

    def reset_current_map(self):
        self.video_epoch += 1
        self.stop_video()
        self.video_path = None
        self.native_preview = None
        self.image_preview_node = None
        path = self.vfs.pwd().rstrip('/') or '/'
        store = ScanStore(self.vfs.db)
        store.delete('map', path)
        store.delete('position', path)
        self.info_paths = {}
        self.info_lexer.hash_lines = set()
        self.info_lexer.colors = {}
        self.info_lexer.image_lines = {}
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
            self.stop_video()
            for player in self.video_workers:
                player.thread.join(timeout=2)
            self.clear_native_preview()
            self.clear_grid_native()
            self.thumbnail_epoch += 1
            if self.thumbnail_executor is not None:
                self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
                self.thumbnail_executor = None
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
        '[#ff8800]b / j[/#ff8800]: Toggle selected file/directory bookmark / editable bookmarks (all screens)',
        'Info duplicates: Tab to info, arrows or click to select; Enter opens the duplicate location',
        '[#ff8800]h / Esc[/#ff8800] (in help): Close help',
        '[#ff8800]Enter[/#ff8800]: Open directory or view file info / ASCII image preview',
        'Media quick view: p toggles Play / Stop; seek bar click/wheel or focused Left/Right (5s)',
        '[#ff8800]v[/#ff8800]: Toggle media files only / all (images, videos and audio)',
        '[#ff8800].[/#ff8800]: Toggle dotfiles and hidden directories (shown by default)',
        '[#ff8800]g[/#ff8800]: Toggle thumbnail grid; +/- display height (minimum 1 line), cache 128/256 pixels',
        '[#ff8800]u / o[/#ff8800]: Table/graphics: show/hide selected subtree (..: all current subdirs) / toggle one or all levels',
        '[#ff8800]y[/#ff8800]: Toggle automatic quick view on file selection (default off)',
        '[#ff8800]i[/#ff8800]: Toggle image previews, including the logo (default on)',
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
    '[#ff8800]b / j[/#ff8800]: Toggle selected file/directory bookmark / editable bookmarks',
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
    '[#ff8800]J[/#ff8800]: Heavy normal (sequential) / expert (selector queue)',
    'Expert tick: pick one random starting bucket, then mark 1–20 following buckets blue',
    '? buckets first; skip blocked/occupied buckets, wrap at end; 1–20 added per tick',
    'Skip fully green buckets until all file buckets are green; mixed ?/green still count',
    'Background additions: random 0.2–1s; empty work queue refills immediately',
    'Add new ranges while earlier ranges scan; total blue can exceed 20',
    'Completed buckets restore their normal background; pause keeps pending work',
    'Changing J also cancels startup; startup heavy is a finite normal pass',
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


class BookmarksView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        self.table = RowsControl(self.rows, changed=self.preview)
        self.table.index = browser.bookmark_index
        self.list = TextArea(read_only=True)  # Plain snapshot for accessible text.
        self.details = browser.info
        self.original_info_directory = browser.info_directory
        self.number = TextArea(height=1, multiline=False, prompt='Number: ')
        self.path = TextArea(height=1, multiline=False, prompt='Path: ', style='class:literal')
        self.focus = self.table
        self.bind(['escape'], self.close, eager=True)
        self.bind(['tab'], lambda: browser.app.layout.focus_next())
        self.bind(['s-tab'], lambda: browser.app.layout.focus_previous())
        self.bind(['enter'], self.choose, filter=has_focus(self.table) | has_focus(self.number), eager=True)
        self.bind(['enter'], self.save, filter=has_focus(self.path), eager=True)
        self.bind(['delete'], self.remove, filter=has_focus(self.table), eager=True)
        self.bind(['e'], lambda: browser.app.layout.focus(self.path), filter=has_focus(self.table))
        table_bindings(self, self.table)
        for digit in '123456789':
            self.bind([digit], lambda digit=digit: browser.go_bookmark(int(digit) - 1),
                      eager=True, filter=has_focus(self.table) & Condition(lambda: len(browser.bookmarks) <= 9))
        self.container = HSplit([
            VSplit([
                Frame(Window(self.table, right_margins=[ScrollbarMargin()]), title='Bookmarks'),
                Frame(HSplit([
                    ConditionalContainer(browser.video_metadata, filter=Condition(lambda: browser.video_path is not None)),
                    ConditionalContainer(HSplit([
                        ConditionalContainer(browser.video_area, filter=Condition(lambda: not browser.audio_selected())),
                        VSplit([browser.play_button, browser.stop_button,
                                Window(FormattedTextControl(lambda: safe_text(browser.video_status)), height=1)], height=1),
                        Window(browser.seek_control, height=1),
                    ]), filter=Condition(browser.video_panel_visible)),
                    self.details,
                ]), title='Quick view · e edit path · Delete remove'),
            ]),
            self.number, self.path,
            VSplit([Button('Go', handler=self.choose), Button('Save path', handler=self.save),
                    Button('Remove', handler=self.remove), Button('Close', handler=self.close)], height=1),
            Window(FormattedTextControl('Arrows/click: preview · Enter: go · e: edit path · b/Delete: remove · Tab: fields'), height=1),
        ], key_bindings=self.keys)
        self.refresh()

    def start(self):
        self.refresh()

    def close(self):
        jumping = self.browser.pending_bookmark is not None
        self.browser.stop_video()
        self.browser.video_epoch += 1
        self.browser.pop(self)
        if not jumping:
            self.browser.show_info(directory=self.original_info_directory)

    def rows(self):
        return [[('', f'{i}. '), ('class:literal', safe_text(path))] for i, path in enumerate(self.browser.bookmarks, 1)]

    def refresh(self):
        self.table.index = max(0, min(self.table.index, len(self.browser.bookmarks) - 1))
        self.list.text = '\n'.join(f'{i}. {safe_text(path)}' for i, path in enumerate(self.browser.bookmarks, 1)) or 'No bookmarks.'
        self.preview()

    def preview(self):
        if self.browser.bookmark_index != self.table.index:
            self.browser.bookmark_index = self.table.index
            self.browser.save_bookmarks()
        if not self.browser.bookmarks:
            self.browser.stop_video()
            self.browser.video_epoch += 1
            self.browser.video_path = None
            self.browser.native_preview = None
            self.browser.image_preview_node = None
            self.path.text = ''
            self.details.text = 'No bookmarks. Select a file and press b.'
            return
        path = self.browser.bookmarks[self.table.index]
        self.path.text = path
        self.number.text = ''
        node = self.browser.vfs.get_from_path(path)
        if node is None:
            self.browser.stop_video()
            self.browser.video_epoch += 1
            self.browser.video_path = None
            self.browser.native_preview = None
            self.browser.image_preview_node = None
            self.details.text = safe_text(path) + '\nUnavailable in VFS. Edit the path or remove this bookmark.'
            return
        self.browser.show_info(preview_node=node)
        if not node.is_dir and os.path.splitext(node.name)[1].lower() not in IMAGE_SUFFIXES | VIDEO_SUFFIXES | AUDIO_SUFFIXES:
            try:
                local = get_real_path(path)
                if os.path.isfile(local):
                    with open(local, 'rb') as source:
                        data = source.read(8192)
                    if b'\x00' not in data:
                        self.details.text += '\n\n' + '\n'.join(safe_text(line) for line in data.decode('utf-8').splitlines()[:60])
            except (OSError, UnicodeError):
                pass
        self.invalidate()

    def remove(self):
        if self.browser.bookmarks:
            self.browser.bookmarks.pop(self.table.index)
            self.browser.save_bookmarks()
            self.refresh()
            self.invalidate()

    def save(self):
        path = normalize_bookmark_path(self.path.text.strip())
        if not path.startswith('/') or self.browser.vfs.get_from_path(path) is None:
            self.details.text = 'Enter an existing absolute VFS path (file or directory).'
            return
        if path in self.browser.bookmarks and self.browser.bookmarks.index(path) != self.table.index:
            self.details.text = 'That path is already bookmarked.'
            return
        if self.browser.bookmarks:
            self.browser.bookmarks[self.table.index] = path
        else:
            self.browser.bookmarks.append(path)
        self.browser.save_bookmarks()
        self.refresh()
        self.browser.app.layout.focus(self.table)

    def choose(self):
        index = int(self.number.text) - 1 if self.number.text.isdecimal() else self.table.index
        self.browser.go_bookmark(index)


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
                           ('class:literal', ' ' + safe_text(path))])
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
            style += ' bg:#00ffff fg:#000000 underline'
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
        self.bind(['J'], self.order, filter=not_input)
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
                Window(FormattedTextControl([('', 'Drive map — '), ('class:literal', safe_text(self.path))]), height=1, style='class:header'),
                Window(FormattedTextControl(self.controls_text), height=1),
                Window(FormattedTextControl(self.summary), height=1),
                Window(FormattedTextControl(lambda: self.path_fragments(self.stats_text())), height=2),
                VSplit([Window(FormattedTextControl(' Paths/bucket '), width=len(' Paths/bucket ')),
                        self.limit, Window(FormattedTextControl(' MiB/bucket '), width=len(' MiB/bucket ')),
                        self.byte_limit, Window()], height=1),
                self.map_window,
                Window(FormattedTextControl(lambda: self.path_fragments(self.bucket_summary())), height=lambda: 2 if self.scope_path else 1),
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
                ('class:literal', safe_text(path[len(prefix):])),
                ('', '' if entry.is_dir else '  ' + format_size(entry.size, 0).strip())])
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
        result.append(('', f'r {"on" if self.controls.read_known else "off"} · t {"new" if self.controls.new_first else "all"} · J {self.requested_order or self.controls.heavy_order}'))
        if (self.requested_order or self.controls.heavy_order) == 'expert':
            result.append(('', f' · Expert selected {self.expert_selected_count} buckets'))
        current, total = self.timing.display_snapshot()
        result.append(('', f' · {format_elapsed(current)} / {format_elapsed(total)}'))
        return result

    def summary(self):
        return (f'{self.phase} | {self.model.mode} | {"fixed" if self.model.fixed else "scroll"} | '
                f'{len(self.model.entries)} paths · {len(self.model.buckets)} buckets')

    def path_fragments(self, text):
        for path in (safe_text(self.stats.path), safe_text(self.scope_path or '')):
            if path and path in text:
                before, after = text.split(path, 1)
                return [('', before), ('class:literal', path), ('', after)]
        return [('', text)]

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
