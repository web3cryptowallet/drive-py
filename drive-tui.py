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
and Ctrl+Y copies info using wl-copy/xclip/xsel or terminal OSC 52.
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

# IMPORT DRIVE-TUI DEPENDENCIES [
import argparse
import asyncio
from collections import OrderedDict
from dataclasses import asdict, replace
import math
import json
from queue import Empty, Queue
import random
import re
import shutil
import subprocess
import sys
from threading import Event, Lock, Thread
import time
from datetime import datetime
import os
from pathlib import Path
import shlex
# IMPORT DRIVE-TUI DEPENDENCIES ]
# LOAD PROMPT TOOLKIT WITH A CLEAR MISSING DEPENDENCY ERROR [
try:
    from prompt_toolkit import Application
    from prompt_toolkit.application.current import get_app
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.filters import Condition, has_focus
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.key_binding.key_processor import KeyPress
    from prompt_toolkit.lexers import Lexer
    from prompt_toolkit.layout import ConditionalContainer, DynamicContainer, Float, FloatContainer, HSplit, Layout, VSplit, Window
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.output import ColorDepth
    from prompt_toolkit.layout.controls import FormattedTextControl, UIContent, UIControl
    from prompt_toolkit.layout.margins import Margin, ScrollbarMargin
    from prompt_toolkit.layout.screen import Char
    from prompt_toolkit.mouse_events import MouseEventType, MouseButton
    from prompt_toolkit.styles import DynamicStyle, Style
    from prompt_toolkit.utils import get_cwidth
    from prompt_toolkit.widgets import Box, Button, Frame, TextArea
except ImportError as exc:
    raise SystemExit('Install prompt_toolkit: python -m pip install prompt_toolkit') from exc
# LOAD PROMPT TOOLKIT WITH A CLEAR MISSING DEPENDENCY ERROR ]
# IMPORT DRIVE-TUI DEPENDENCIES [
from drive import load_log
from vfs import VirtualFS, aliases, disabled_prefixes, format_size, prefixes, get_stat_info
from vfs.video_preview import VideoPreview, probe_media_type
from vfs.paths import get_real_path
from vfs.thumbnails import thumbnail, IMAGE_SUFFIXES, THUMBNAIL_SUFFIXES, MEDIA_SUFFIXES, VIDEO_SUFFIXES, AUDIO_SUFFIXES
from vfs.scanner import (DriveScanner, FileMap, Pagination, ScanControls, ScanEntry,
                         ScanStats, ScanStore, ScanTiming)
from vfs.conversion import (ConversionQueue, ConversionOptions, NETWORKS, RESOLUTIONS,
                            command as conversion_command, video_files as conversion_files, probe_media, parse_time)
from vfs.scan_statistics import ScanStatistics
from vfs.directory_counts import DirectoryCounts, catalog_directory_counts
from vfs.adapter.sqlite import SQLiteDBAdapter
from vfs.history_index import HistoryIndex, HistoryRows
from collections import deque
from bisect import bisect_left
from vfs.help_index import help_entries, shortcut_key, HelpIndexControl, HelpSearchLexer, highlighted
from vfs.db_trash import DBTrash
import sqlite3
# IMPORT DRIVE-TUI DEPENDENCIES ]
# Buttons use their labels without angle-bracket decorations throughout the UI.
from prompt_toolkit.widgets import Button as _PTButton


class Button(_PTButton):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('left_symbol', '')
        kwargs.setdefault('right_symbol', '')
        super().__init__(*args, **kwargs)


# MATCH DECIMAL AND GROUPED NUMERIC DISPLAY TEXT [
NUMBER_TEXT = re.compile(r'(?<!\w)(?<!\d[.,])\d+(?:[.,]\d+)*(?!\w|[.,]\d)')
# MATCH DECIMAL AND GROUPED NUMERIC DISPLAY TEXT ]
# COLOR FINAL VISIBLE NUMERIC TEXT ACROSS EVERY WIDGET AND SCREEN [
class NumberHighlight(HSplit):
    """Color final visible numeric text across every widget and screen."""

    # INITIALIZE NUMBER HIGHLIGHT [
    def __init__(self, container):
        super().__init__([container])
    # INITIALIZE NUMBER HIGHLIGHT ]
    # WRITE TO SCREEN [
    def write_to_screen(self, screen, mouse_handlers, write_position,
                        parent_style, erase_bg, z_index):
        super().write_to_screen(screen, mouse_handlers, write_position,
                                parent_style, erase_bg, z_index)
        screen.draw_with_z_index(10**9, lambda: self.highlight(screen))
    # WRITE TO SCREEN ]
    # COLOR NUMERIC TEXT WHILE PRESERVING LITERAL PATHS [
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
    # COLOR NUMERIC TEXT WHILE PRESERVING LITERAL PATHS ]
# COLOR FINAL VISIBLE NUMERIC TEXT ACROSS EVERY WIDGET AND SCREEN ]
# RUN BLOCKING WORK WITHOUT COUPLING SCREEN LIFECYCLE TO A GLOBAL EXECUTOR [
async def background_call(function, *args, **kwargs):
    """Run blocking work without coupling screen lifecycle to a global executor."""
    done = Event()
    outcome = []
    # RETURN WORKER RESULTS WITHOUT DIRECTORY-SIZED SCHEDULING DELAYS [
    def work():
        try:
            outcome.append((True, function(*args, **kwargs)))
        except BaseException as exc:
            outcome.append((False, exc))
        finally:
            done.set()
    # RETURN WORKER RESULTS WITHOUT DIRECTORY-SIZED SCHEDULING DELAYS ]
    thread = Thread(target=work, name='drive-pt-background', daemon=True)
    thread.start()
    while not done.is_set():
        await asyncio.sleep(.0001)
    success, value = outcome[0]
    if not success:
        raise value
    return value
# RUN BLOCKING WORK WITHOUT COUPLING SCREEN LIFECYCLE TO A GLOBAL EXECUTOR ]
# WAIT FOR THE OWNED THUMBNAIL WORKER WITHOUT A GLOBAL EXECUTOR [
async def thumbnail_worker_call(executor, function, *args):
    result = executor.submit(function, *args)
    while not result.done():
        await asyncio.sleep(.0001)
    return result.result()
# WAIT FOR THE OWNED THUMBNAIL WORKER WITHOUT A GLOBAL EXECUTOR ]
# FORMAT ELAPSED FOR THE DRIVE-TUI WORKFLOW [
def shutdown_step(label, callback):
    """Keep blocking cleanup visible after the terminal UI has exited."""
    started = time.monotonic()
    done = Event()
    print(f'Quitting: {safe_text(label)}…', file=sys.stderr, flush=True)
    def heartbeat():
        while not done.wait(1.):
            elapsed = time.monotonic() - started
            print(f'  Still waiting: {safe_text(label)} ({elapsed:.0f}s)', file=sys.stderr, flush=True)
    reporter = Thread(target=heartbeat, name='drive-shutdown-status', daemon=True)
    reporter.start()
    try:
        result = callback()
    except BaseException:
        print(f'  Failed: {safe_text(label)}', file=sys.stderr, flush=True)
        raise
    else:
        print(f'  Done ({time.monotonic() - started:.1f}s)', file=sys.stderr, flush=True)
        return result
    finally:
        done.set()
        reporter.join()

def scan_size(size):
    value = max(0., float(size))
    for unit in ('B', 'KB', 'MB', 'GB', 'TB', 'PB'):
        if value < 1000 or unit == 'PB':
            return f'{value:.1f} {unit}'
        value /= 1000


def scan_path_rate(rate):
    for multiplier, unit in ((1, 's'), (60, 'min'), (3600, 'h')):
        value = max(0., rate) * multiplier
        if value >= 1 or unit == 'h' or rate == 0:
            return f'{value:.1f} paths/{unit}'


def scan_mode_progress(rows, mode):
    rows = rows or [[0, 0, 0.]]
    files, size, seconds = rows[min(max((mode or 1) - 1, 0), len(rows) - 1)]
    maximum = max(row[1] for row in rows)
    estimate = format_elapsed(seconds * maximum / size) if size > 0 else '—'
    return f'{files:,} files · {scan_size(size)}/{scan_size(maximum)} · {format_elapsed(seconds)}/{estimate}'


def format_elapsed(seconds):
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f'{hours}:{minutes:02}:{seconds:02}'
    return f'{minutes}:{seconds:02}'
# FORMAT ELAPSED FOR THE DRIVE-TUI WORKFLOW ]
# KEEP PATHS ON ONE TERMINAL LINE WITHOUT INTERPRETING CONTROL CHARACTERS [
def safe_text(value):
    """Keep paths on one terminal line without interpreting control characters."""
    return ''.join(c if c.isprintable() else '?' for c in str(value))
# KEEP PATHS ON ONE TERMINAL LINE WITHOUT INTERPRETING CONTROL CHARACTERS ]
# PROBE BEFORE PROMPT_TOOLKIT STARTS READING INPUT, THEN CACHE CAPABILITIES [
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
# PROBE BEFORE PROMPT_TOOLKIT STARTS READING INPUT, THEN CACHE CAPABILITIES ]
# RENDER A BOUNDED TERM-IMAGE FRAME; ANSI IS CONSUMED ONLY BY INFOLEXER [
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
# RENDER A BOUNDED TERM-IMAGE FRAME; ANSI IS CONSUMED ONLY BY INFOLEXER ]
# RETAIN A BOUNDED CACHE OF FULLY PREPARED TERMINAL THUMBNAILS [
from collections import OrderedDict
GRID_RENDER_CACHE = OrderedDict()
GRID_RENDER_CACHE_LIMIT = 128
GRID_RENDER_CACHE_LOCK = Lock()


def retain_grid_render(key, item):
    with GRID_RENDER_CACHE_LOCK:
        GRID_RENDER_CACHE[key] = item
        GRID_RENDER_CACHE.move_to_end(key)
        while len(GRID_RENDER_CACHE) > GRID_RENDER_CACHE_LIMIT:
            GRID_RENDER_CACHE.popitem(last=False)
    return item


def clear_grid_cache_files(cache_root, scope, records):
    from vfs.thumbnails import clear_thumbnail_cache
    result = clear_thumbnail_cache(cache_root, scope, records)
    with GRID_RENDER_CACHE_LOCK:
        GRID_RENDER_CACHE.clear()
    return result
# RETAIN A BOUNDED CACHE OF FULLY PREPARED TERMINAL THUMBNAILS ]
# DECODE, CACHE, FIT AND SERIALIZE ON A WORKER WITHOUT REDIRECTING STDOUT [
def prepare_grid_thumbnail(path, file_id, size, bounds, cell_ratio, cache_only=False, cached_record=None):
    """Decode, cache, fit and serialize on a worker without redirecting stdout."""
    from PIL import Image
    from term_image.image import AutoImage, BlockImage, KittyImage
    from prompt_toolkit.formatted_text import ANSI, to_formatted_text
    record = thumbnail(path, file_id, size, cache_only=cache_only, cached_record=cached_record)
    if record is None:
        return None
    key = (record['id'], record['path'], tuple(bounds), cell_ratio, AutoImage)
    with GRID_RENDER_CACHE_LOCK:
        if key in GRID_RENDER_CACHE:
            GRID_RENDER_CACHE.move_to_end(key)
            return GRID_RENDER_CACHE[key]
    with Image.open(record['path']) as source:
        image = source.convert('RGB')
    color = '#%02x%02x%02x' % image.resize((1, 1)).getpixel((0, 0))
    width, height = bounds
    scale = min(width / image.width, height / (image.height * cell_ratio))
    target = (max(1, min(width, round(image.width * scale))),
              max(1, min(height, round(image.height * scale * cell_ratio))))
    with AutoImage(image, width=target[0], height=target[1]) as preview:
        if isinstance(preview, KittyImage):
            # Public string formatting performs the same protocol serialization
            # without draw()'s process-global stdout writes from a worker thread.
            art = format(preview, '1.1+Wz732m1')
            return retain_grid_render(key, {'color': color, 'record': record, 'native': (art, target), 'lines': [], 'dimensions': target})
        if isinstance(preview, BlockImage):
            art = str(preview)
        else:
            with BlockImage(image.copy(), width=target[0], height=target[1]) as fallback:
                art = str(fallback)
    return retain_grid_render(key, {'color': color, 'record': record, 'native': None,
            'lines': [to_formatted_text(ANSI(line)) for line in art.splitlines()],
            'dimensions': target})
# DECODE, CACHE, FIT AND SERIALIZE ON A WORKER WITHOUT REDIRECTING STDOUT ]
# CONSUME GRAPHICS APC RESPONSES BEFORE PT CAN TURN THEM INTO APP KEYS [
class KittyReplyFilter:
    """Consume graphics APC responses before PT can turn them into app keys."""
    # INITIALIZE KITTY REPLY FILTER [
    def __init__(self, parser):
        self.parser = parser
        self.pending = ''
    # INITIALIZE KITTY REPLY FILTER ]
    # FILTER TERMINAL REPLIES FROM KEYBOARD INPUT [
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
    # FILTER TERMINAL REPLIES FROM KEYBOARD INPUT ]
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES [
    def flush(self):
        if self.pending and not self.pending.startswith('\x1b_G'):
            self.parser.feed(self.pending)
            self.pending = ''
        self.parser.flush()
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES ]
    # DELEGATE ATTRIBUTE ACCESS FOR KITTY REPLY FILTER [
    def __getattr__(self, name):
        return getattr(self.parser, name)
    # DELEGATE ATTRIBUTE ACCESS FOR KITTY REPLY FILTER ]
# CONSUME GRAPHICS APC RESPONSES BEFORE PT CAN TURN THEM INTO APP KEYS ]
# KEEP ONLY KITTY APC PACKETS; TEXT-LAYOUT CURSOR MOVES MUST NOT REACH THE TUI [
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
# KEEP ONLY KITTY APC PACKETS; TEXT-LAYOUT CURSOR MOVES MUST NOT REACH THE TUI ]
# SERIALIZE ONE SOFTWARE-DECODED FRAME ON THE PLAYBACK WORKER [
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
# SERIALIZE ONE SOFTWARE-DECODED FRAME ON THE PLAYBACK WORKER ]
# KEEP THE FILENAME ENDING WHEN A TILE CANNOT DISPLAY ITS FULL NAME [
def filename_end(text, width):
    """Character offset of the final viewport, without splitting wide glyphs."""
    start, used = len(text), 0
    for char in reversed(text):
        cells = get_cwidth(char)
        if used + cells > max(0, width):
            break
        start -= 1
        used += cells
    return start

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
# KEEP THE FILENAME ENDING WHEN A TILE CANNOT DISPLAY ITS FULL NAME ]
# FIT DISPLAY TEXT TO THE AVAILABLE WIDTH [
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
# FIT DISPLAY TEXT TO THE AVAILABLE WIDTH ]
# HIGHLIGHT ONLY THE BOOKMARK MARKER, RETAINING ROW BACKGROUND AND WIDTHS [
def bookmark_label(style, text, marked, offset=1):
    """Highlight only the bookmark marker, retaining row background and widths."""
    if not marked or len(text) <= offset or text[offset] != 'B':
        return [(style + ' class:literal', text)]
    style += ' class:literal'
    return [(style, text[:offset]), (style + ' class:bookmark', 'B'),
            (style, text[offset + 1:])]
# HIGHLIGHT ONLY THE BOOKMARK MARKER, RETAINING ROW BACKGROUND AND WIDTHS ]
# MANAGE TITLE CONTROL [
class TitleControl(UIControl):
    # CREATE CONTENT FOR TITLE CONTROL [
    def create_content(self, width, height):
        title = 'drive.py — file manager'
        text = ' ' * max(0, (width - get_cwidth(title)) // 2) + title
        return UIContent(get_line=lambda _: [('', text)], line_count=1,
                         show_cursor=False)
    # CREATE CONTENT FOR TITLE CONTROL ]
# MANAGE TITLE CONTROL ]
# MANAGE FILES CONTROL [
class FilesControl(UIControl):
    # INITIALIZE FILES CONTROL [
    def __init__(self, browser, header=False):
        self.browser = browser
        self.header = header
    # INITIALIZE FILES CONTROL ]
    # CHECK FOCUSABLE FOR FILES CONTROL [
    def is_focusable(self):
        return not self.header
    # CHECK FOCUSABLE FOR FILES CONTROL ]
    # CREATE CONTENT FOR FILES CONTROL [
    def create_content(self, width, height):
        browser = self.browser
        if browser.graphics_mode:
            return browser.grid_content(width, height, header=self.header)
        # Reserve metadata first; degrade gracefully in very small terminals.
        size_width, dups_width = browser.metadata_widths
        files_width = browser.file_count_width
        if width < size_width + files_width + dups_width + 6:
            available = max(0, width - 3)
            size_width = min(size_width, available // 3)
            files_width = min(files_width, (available - size_width) // 2)
            dups_width = min(dups_width, available - size_width - files_width)
        name_width = max(0, width - size_width - files_width - dups_width - 3)
        browser.columns = (name_width, size_width, files_width, dups_width)
        if self.header:
            return UIContent(get_line=lambda _: browser.column_header(),
                             line_count=1, show_cursor=False)

        # FORMAT ONE VISIBLE DISPLAY ROW [
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
            name_style = base + ' class:literal' + (' class:expanded-dir-name' if expanded else '') + browser.scan_row_style(row)
            prefix = browser.scan_row_marker(row) + ' ' + browser.file_icon(row) + ' '
            excluded = row['name'] != '..' and row['node'].is_dir and row['node'].id in browser.blacklist
            available = max(0, name_width - get_cwidth(prefix) - (2 if browser.bookmark_path(row) in browser.bookmarks else 0) - (2 if excluded else 0))
            path_label = browser.file_list_path(row)
            if path_label.startswith(('♫ ', '▶ ')):
                path_label = path_label[2:]
            label = prefix + browser.fit_name(path_label, available, selected=selected)
            marked = browser.bookmark_path(row) in browser.bookmarks
            if marked:
                label = label[:2] + 'B ' + label[2:]
            label = (fit(label[:-2], max(0, name_width - 2)) + ' ↗') if label.endswith(' ↗') and name_width >= 2 else fit(label, name_width)
            fragments = []
            if label and (browser.display_mode != 3 or 'scan_symbol' in row or label[0] != row['label'][0]):
                marker_style = (' fg:' + row.get('scan_activity_color', '#ffd700') if row.get('scan_active', False) else
                                ' class:' + ('green' if label[0] == '·' else row.get('scan_color', row['indicator'])))
                fragments.append((base + marker_style, label[0]))
                fragments.extend(browser.exclusion_label(name_style, label[1:], marked, row))
            else:
                fragments.extend(browser.exclusion_label(name_style, label, marked, row, 2))
            files = row['dups'].strip('()') if row['node'].is_dir else '1'
            dups = '—' if row['node'].is_dir else row['dups'].strip('()')
            if row['name'] == '..':
                files = dups = '—'
            fragments.append((base, ' ' + fit(' ' + row['size'], size_width) +
                              ' ' + fit(' ' + files, files_width) +
                              ' ' + fit(' ' + dups, dups_width)))
            return fragments
        # FORMAT ONE VISIBLE DISPLAY ROW ]

        return UIContent(get_line=line, line_count=max(1, len(browser.rows)),
                         cursor_position=Point(x=0, y=browser.selected), show_cursor=False)
    # CREATE CONTENT FOR FILES CONTROL ]
    # MOUSE HANDLER FOR FILES CONTROL [
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
            if event.button == MouseButton.LEFT and 0 <= index < len(browser.rows):
                browser.click_file(index)
        else:
            return NotImplemented
    # MOUSE HANDLER FOR FILES CONTROL ]
# MANAGE FILES CONTROL ]
# RESERVE MAP COLUMNS FROM THE CURRENT PANE GEOMETRY BEFORE RENDERING [
class FilesWindow(Window):
    def __init__(self, browser, *args, **kwargs):
        self.browser = browser
        super().__init__(*args, **kwargs)

    def write_to_screen(self, screen, mouse_handlers, write_position,
                        parent_style, erase_bg, z_index):
        b = self.browser
        tile = max(1, b.icon_dimensions()[0])
        b.preview_map_columns = max(1, write_position.width // (tile + 2))
        super().write_to_screen(screen, mouse_handlers, write_position,
                                parent_style, erase_bg, z_index)
# RESERVE MAP COLUMNS FROM THE CURRENT PANE GEOMETRY BEFORE RENDERING ]
# SHOW FULL LISTING THUMBNAIL COVERAGE IN A FIXED HEIGHT RIGHT MARGIN [
class PreviewMapMargin(Margin):
    def __init__(self, browser):
        self.browser = browser

    def get_width(self, get_ui_content):
        b = self.browser
        if not b.graphics_mode:
            return 0
        return getattr(b, 'preview_map_columns', max(1, b.grid_columns))

    def create_margin(self, window_render_info, width, height):
        b = self.browser
        groups, locations = DriveBrowser.grid_media_layout(b)
        location = locations.get(getattr(b, 'selected', -1))
        cursor = ((min(height - 1, (location[0] * height + len(groups) - 1) // max(1, len(groups))),
                   location[1]) if location is not None else None)
        result = []
        for y in range(height):
            start = y * len(groups) // max(1, height)
            entries = groups[min(start, len(groups) - 1)] if groups else []
            for x in range(width):
                if x >= b.grid_columns:
                    result.append(('', ' '))
                    continue
                if cursor == (y, x):
                    result.append(('fg:#ffffff bg:#000000 bold', '◆'))
                    continue
                if x >= len(entries):
                    result.append(('', ' '))
                    continue
                item = b.thumbnails.get(b.rows[entries[x]]['node'].id, {})
                color = item.get('color')
                result.append((f'bg:{color}' if color else '', ' ' if color else '·'))
            if y < height - 1:
                result.append(('', '\n'))
        return result
# SHOW FULL LISTING THUMBNAIL COVERAGE IN A FIXED HEIGHT RIGHT MARGIN ]
# MANAGE VIDEO SEEK CONTROL [
class VideoSeekControl(UIControl):
    # INITIALIZE VIDEO SEEK CONTROL [
    def __init__(self, browser):
        self.browser = browser
        self.keys = KeyBindings()
        for key, seconds in [('left', -5), ('right', 5)]:
            self.keys.add(key)(lambda event, seconds=seconds: browser.seek_video(seconds, relative=True))
        self.keys.add('home')(lambda event: browser.seek_video(0))
        self.keys.add('end')(lambda event: browser.seek_video(browser.video_duration))
        self.width = 1
    # INITIALIZE VIDEO SEEK CONTROL ]
    # CHECK FOCUSABLE FOR VIDEO SEEK CONTROL [
    def is_focusable(self):
        return True
    # CHECK FOCUSABLE FOR VIDEO SEEK CONTROL ]
    # RESOLVE KEY BINDINGS [
    def get_key_bindings(self):
        return self.keys
    # RESOLVE KEY BINDINGS ]
    # CREATE CONTENT FOR VIDEO SEEK CONTROL [
    def create_content(self, width, height):
        self.width = max(1, width - 20)
        duration = self.browser.video_duration
        fraction = min(1., self.browser.video_position / duration) if duration else 0
        filled = round(fraction * self.width)
        text = '[' + '=' * filled + '-' * (self.width - filled) + '] '
        text += format_elapsed(self.browser.video_position) + ' / ' + format_elapsed(duration)
        return UIContent(get_line=lambda _: [('class:header', fit(text, width))], line_count=1,
                         show_cursor=False)
    # CREATE CONTENT FOR VIDEO SEEK CONTROL ]
    # MOUSE HANDLER FOR VIDEO SEEK CONTROL [
    def mouse_handler(self, event):
        browser = self.browser
        if event.event_type in (MouseEventType.SCROLL_UP, MouseEventType.SCROLL_DOWN):
            browser.seek_video(5 if event.event_type == MouseEventType.SCROLL_UP else -5, relative=True)
        elif event.event_type == MouseEventType.MOUSE_UP:
            browser.app.layout.focus(self)
            browser.seek_video(max(0., min(1., (event.position.x - 1) / self.width)) * browser.video_duration)
        else:
            return NotImplemented
    # MOUSE HANDLER FOR VIDEO SEEK CONTROL ]
# MANAGE VIDEO SEEK CONTROL ]
# COLOR ONLY EXPLICIT STATUS MARKERS; FILENAMES REMAIN LITERAL TEXT [
class InfoLexer(Lexer):
    """Color only explicit status markers; filenames remain literal text."""
    # INITIALIZE INFO LEXER [
    def __init__(self):
        self.colors = {}
        self.image_lines = {}
        self.hash_lines = set()
    # INITIALIZE INFO LEXER ]
    # LEX DOCUMENT FOR INFO LEXER [
    def lex_document(self, document):
        colors = self.colors.copy()
        image_lines = self.image_lines.copy()
        hash_lines = self.hash_lines.copy()

        # FORMAT ONE VISIBLE DISPLAY ROW [
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
            generated = text.startswith(('Size:', 'Disk free:', 'Dirs:', 'Files:', 'Created:', 'Modified:',
                                         'Image:', 'Other Duplicates', 'Current disk size:'))
            return [('' if generated else 'class:literal', text)]
        # FORMAT ONE VISIBLE DISPLAY ROW ]

        return line
    # LEX DOCUMENT FOR INFO LEXER ]
# COLOR ONLY EXPLICIT STATUS MARKERS; FILENAMES REMAIN LITERAL TEXT ]
# CONFIGURE TERMINAL THEMES AND BOOKMARK STORAGE [
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
    {'': 'bg:#ffffff #202020', 'border': '#606060',
     'header': 'bg:#eeeeee #202020 bold', 'table-header': 'bg:#eeeeee #202020 bold',
     'info-header': 'bg:#eeeeee #202020 bold',
     'files-pane': 'bg:#ffffff #202020', 'info-pane': 'bg:#ffffff #202020',
     'selected': 'bg:#cce8ff #202020 nobold noreverse',
     'white': '#202020', 'yellow': '#806000', 'green': '#287500',
     'red': '#bb2020', 'orange': '#a64c00', 'muted': '#666666',
     'bookmark': '#008b8b bold', 'audio-play': '#7030a0 bold',
     'expanded-dir': 'bg:#e6ddf2', 'expanded-dir-name': '#703090 bold',
     'scan-input': 'bg:#eeeeee #202020 nobold noreverse',
     'scrollbar.background': 'bg:#eeeeee', 'scrollbar.button': 'bg:#909090'},
]


BOOKMARKS_PATH = Path(".bookmarks.json")
BLACKLIST_PATH = Path(".blacklist.json")
HISTORY_PATH = Path("history.llog")


def terminal_color_depth():
    """Respect overrides and use RGB only when the terminal advertises it."""
    override = ColorDepth.from_env()
    if override is not None:
        return override
    if os.environ.get('TERM_PROGRAM') == 'Apple_Terminal':
        return ColorDepth.DEPTH_8_BIT
    if os.environ.get('COLORTERM', '').lower() in ('truecolor', '24bit'):
        return ColorDepth.DEPTH_24_BIT
    return None

# CONFIGURE TERMINAL THEMES AND BOOKMARK STORAGE ]
# USE CONFIGURED VFS IDENTITY FOR ALIASES, MOUNT PATHS AND REPORT PREFIXES [
def normalize_bookmark_path(path):
    """Use configured VFS identity for aliases, mount paths and report prefixes."""
    if path == '~' or path.startswith('~/'):
        return '/~0:/' + path[2:] if path != '~' else '/~0:'
    if path.startswith('~0:/'):
        return '/' + path
    if path.startswith('/~0:'):
        return path
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
    home = os.path.expanduser('~').rstrip('/')
    if path == home or path.startswith(home + '/'):
        return '/~0:' + path[len(home):]
    return path
# USE CONFIGURED VFS IDENTITY FOR ALIASES, MOUNT PATHS AND REPORT PREFIXES ]
# BROWSE FILES AND COORDINATE QUICK VIEW AND POPUPS [
class DriveBrowser:
    # INITIALIZE DRIVE BROWSER [
    def __init__(self, vfs, *, path=None, input=None, output=None):
        import sys
        configure_image_terminal(probe=output is None and sys.stdout.isatty())
        self.show_path_prefixes = False
        self.startup_path = os.getcwd()  # Namespace anchor, independent of initial cursor directory.
        self.displayed_paths = {}
        self.native_preview = None
        self.native_visible = False
        self.native_drawn = None
        self.auto_quick_view = False
        self.image_previews = True
        self.info_directory = True
        self.graphics_mode = False
        self.thumbnail_cache_clearing = False
        self.grid_scroll_to_tile = None
        self.thumbnail_order = 'sequence'
        self.thumbnail_seconds = 0.05
        self.thumbnail_step = 1
        self.preview_map_dragging = False
        self.files_scrollbar_dragging = False
        self.expanded_dirs = set()
        self.expansion_cwd = None
        self.expansion_task = None
        self.expansion_files = set()
        self.expansion_listing_cache = {}
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
        self.quickview_jobs = set()
        self.quickview_animation_task = None
        self.video_status = ''
        self.video_first_row = 0
        self.video_dimensions = (1, 1)
        self.video_render_dimensions = (1, 1)
        self.video_metadata = TextArea(read_only=True, wrap_lines=True, lexer=InfoLexer(),
                                       height=Dimension(min=1, preferred=7, max=7))
        self.video_task = None
        self.video_workers = []
        self.preview_bookmark_path = None
        self.preview_bookmark_control = FormattedTextControl(self.preview_bookmark_fragments)
        self.video_muted = False
        self.mute_button = Button('🔊', width=3, handler=self.toggle_mute)
        self.previous_button = Button('Prev', width=5, handler=lambda: self.step_media(-1))
        self.next_button = Button('Next', width=5, handler=lambda: self.step_media(1))
        self.play_button = Button('Play', width=5, handler=self.play_video)
        self.stop_button = Button('Stop', width=5, handler=self.stop_video)
        self.grid_layout_key = None
        self.grid_lines = []
        self.grid_positions = {}
        self.icon_size = 128
        self.icon_lines = 8
        self.grid_columns = 1
        self.grid_tile_width = 1
        self.grid_tile_height = 3
        self.thumbnail_epoch = 0
        self.thumbnail_task = None
        self.thumbnail_executor = None
        self.thumbnail_executors = []
        self.thumbnails = {}
        self.grid_native_drawn = None
        self.thumbnail_errors = 0
        self.vfs = vfs
        self.navigation_store = ScanStore(vfs.db)
        self.media_type_cache = {}
        self.media_type_legacy_keys = set()
        saved_depth = ScanStore(vfs.db).get('ui', 'expand_all_levels', False)
        self.expand_all_levels = saved_depth if isinstance(saved_depth, bool) else False
        self.selected = 0
        self.scan_selection = set()
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
            **theme,
        }) for theme in THEMES]
        self.rows = []
        self.history = []
        from vfs.action_history import ActionHistory
        self.action_history = ActionHistory(HISTORY_PATH)
        self.play_history_entry = None
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
        self.blacklist_enabled = True
        self.show_blacklisted = True
        self.show_problem_files = True
        try:
            saved = json.loads(BLACKLIST_PATH.read_text(encoding='utf-8'))
            self.blacklist = set(normalize_bookmark_path(path) for path in saved
                                 if isinstance(path, str) and path.startswith('/')) if isinstance(saved, list) else set()
        except (OSError, ValueError):
            self.blacklist = set()
        self.pending_bookmark = None
        self.info_paths = {}
        self.quickview_filter_duplicates = True
        self.quickview_duplicate_rows = None
        self.cursor_idle_until = 0.
        self.cursor_idle_task = None
        self.cursor_refresh_pending = False
        self.dups_pending = set()
        self.dups_task = None
        self.scanners = []
        self.scanner_restart_task = None
        self.scan_statistics = ScanStatistics(self.vfs.db)
        self.directory_counts = DirectoryCounts(self.vfs.db)
        self.directory_count_pending = {}
        self.directory_count_task = None
        self.scan_statistics_scope = 'current'
        self.conversions = ConversionQueue(self.vfs.db)
        self.db_trash = DBTrash(self.vfs.db)
        self.trashed_roots = self.db_trash.roots()
        self.conversion_task = None
        self.filename_pan = None
        self.filename_width = 20
        self.columns = (20, 8, 6, 4)
        self.file_count_width = 6
        self.metadata_widths = (5, 7)
        self.control = FilesControl(self)
        self.files = FilesWindow(self, self.control, right_margins=[PreviewMapMargin(self), ScrollbarMargin()],
                            wrap_lines=False, always_hide_cursor=True)
        self.filename_slider = HorizontalBar(FilenameViewport(self))
        self.filename_search = None
        self.filename_slider_window = Window(self.filename_slider, height=1)
        self.info_lexer = InfoLexer()
        self.info = TextArea(read_only=True, scrollbar=True,
                             wrap_lines=Condition(lambda: not bool(self.info_paths)),
                             lexer=self.info_lexer, focus_on_click=True)
        info_mouse_handler = self.info.control.mouse_handler
        info_click = {'last': None, 'time': 0., 'down': None}
        def focus_info_row(event):
            left = event.button == MouseButton.LEFT
            if event.event_type == MouseEventType.MOUSE_DOWN and left:
                self.app.layout.focus(self.info)
                info_click['down'] = event.position
            result = info_mouse_handler(event)
            if event.event_type == MouseEventType.MOUSE_UP and left:
                path = self.info_paths.get(self.info.buffer.document.cursor_position_row)
                now = time.monotonic()
                down = info_click['down']
                click = down is not None and down.y == event.position.y and abs(down.x - event.position.x) <= 1
                if (click and path and not self.screen_stack and path == info_click['last']
                        and 0 <= now - info_click['time'] < .3):
                    info_click['last'] = None
                    self.info.buffer.exit_selection()
                    self.open_duplicate()
                else:
                    info_click['last'] = path if click else None
                    info_click['time'] = now
                info_click['down'] = None
            return result
        self.info.control.mouse_handler = focus_info_row
        self.info.window.height = lambda: Dimension(min=self.video_info_height() if self.video_path and
            hasattr(self, 'app') and self.app.output.get_size().rows >= 18 else 1)
        self.info.window.right_margins = [ScrollbarMargin()]
        self.info.window.cursorline = has_focus(self.info)
        try:
            saved_directory = self.navigation_store.get('ui', 'last_directory', {})
        except (ValueError, TypeError):
            self.navigation_store.delete('ui', 'last_directory')
            saved_directory = {}
        if path is None or not os.fspath(path).strip():
            if not isinstance(saved_directory, dict):
                saved_directory = {}
            directory = saved_directory.get('directory')
            if saved_directory.get('catalog_root') is True:
                self.vfs.cwd = self.vfs.db.get_root()
            else:
                try:
                    valid = (isinstance(directory, str) and os.path.isabs(directory)
                             and os.path.isdir(directory))
                    # Restore the logical spelling before physical mount matching can
                    # replace a symlink route with its target.
                    route = saved_directory.get('vfs_path', directory)
                    restored = None
                    if valid and isinstance(route, str) and self.original_path(route) == os.path.normpath(directory):
                        restored = self.vfs.get_from_path(route)
                    if restored is not None and restored.is_dir:
                        self.vfs.cwd = restored
                    else:
                        self.vfs.start_in_current_directory(directory if valid else None)
                except (ValueError, OSError):
                    self.vfs.start_in_current_directory()
            if self.is_trashed(self.vfs.pwd()):
                self.vfs.start_in_current_directory()
        else:
            self.vfs.start_in_current_directory(path)
        self.action_history.add('chdir', self.vfs.pwd())
        self.refresh()
        bindings = KeyBindings()
        @bindings.add('<any>', filter=Condition(lambda: not (
            getattr(self.app.layout.current_control, 'buffer', None) is not None
            and not self.app.layout.current_control.buffer.read_only())))
        def unknown_key(event):
            key = event.key_sequence[-1].key
            self.show_notification(f'Unknown key {getattr(key, "value", key)}', error=True)

        # Replace toolkit no-op defaults while keeping concrete UI bindings later
        # in the registry (and focused widget bindings) in charge.
        from prompt_toolkit.key_binding.bindings.basic import load_basic_bindings
        fallback_filter = bindings.bindings[-1].filter
        for binding in load_basic_bindings().bindings:
            if binding.handler.__name__ == '_ignore' and str(binding.keys[-1]) != 'Keys.Ignore':
                bindings.add(*binding.keys, filter=fallback_filter)(unknown_key)

        main_focused = Condition(lambda: not self.screen_stack)
        files_focused = has_focus(self.control)

        # REGISTER KEYBOARD ACTIONS FOR DRIVE BROWSER [
        def bind(keys, handler, **kwargs):
            kwargs_filter = kwargs.pop('filter', None)
            for key in keys:
                bindings.add(key, filter=main_focused & (kwargs_filter if kwargs_filter is not None else Condition(lambda: True)), **kwargs)(handler)
        # REGISTER KEYBOARD ACTIONS FOR DRIVE BROWSER ]

        for key, action in [('s-left', -1), ('s-right', 1), ('s-home', 'start'), ('s-end', 'end'),
                            ('s-pageup', 'start'), ('s-pagedown', 'end')]:
            bindings.add(key, eager=True, filter=Condition(self.can_pan_filename))(lambda event, action=action: self.pan_filename(action))

        bindings.add('x', eager=True, filter=Condition(lambda: not self.screen_stack))(lambda event: self.toggle_path_prefixes())
        command_closed = Condition(lambda: not self.screen_stack or (not isinstance(self.screen_stack[-1][0], (PathCommandView, ConversionView, FilenameSearchView)) and not self.help_search_focused()))
        bindings.add('b', eager=True, filter=command_closed)(lambda event: self.toggle_bookmark())
        bindings.add('j', eager=True, filter=command_closed)(lambda event: self.push(BookmarksView(self)))
        bindings.add('q', eager=True, filter=command_closed)(lambda event: self.request_quit())
        bindings.add('c-c')(lambda event: self.request_quit())
        bindings.add('f10', eager=True)(lambda event: self.request_quit())
        bindings.add('f1', eager=True)(lambda event: self.show_context_help())
        bindings.add('c-p', eager=True)(lambda event: self.pause_scanner())
        bindings.add('c-k', eager=True)(lambda event: self.stop_scanner())
        bindings.add('f6', eager=True)(lambda event: self.show_scan_statistics())
        bindings.add('f4', eager=True)(lambda event: self.show_status())
        bindings.add('p', filter=Condition(lambda: (not self.screen_stack or
            isinstance(self.screen_stack[-1][0], BookmarksView)) and bool(self.video_path) and
            not (self.screen_stack and (self.app.layout.has_focus(self.screen_stack[-1][0].path) or
                                       self.app.layout.has_focus(self.screen_stack[-1][0].number)))))(lambda event: self.toggle_playback())
        bind(['~'], lambda event: self.go_path(os.path.expanduser('~')), eager=True)
        bind(['/'], lambda event: self.push(PathCommandView(self)), eager=True)
        bind(['c-s'], lambda event: self.push(FilenameSearchView(self)), filter=files_focused, eager=True)
        bind(['l'], lambda event: self.push(HistoryView(self)))
        bind(['a'], lambda event: self.push(ActionsView(self)))
        bind(['f7'], lambda event: self.push(DriveMappingsView(self)))
        bind(['s', 'f3'], lambda event: self.toggle_scanner())
        bind(['c-e'], lambda event: self.edit_conversion())
        bind(['Q'], lambda event: self.push(ConversionQueueView(self)))
        bind([' '], lambda event: self.toggle_scan_selection(), filter=files_focused)
        bind(['insert'], lambda event: self.toggle_scan_selection(True), filter=files_focused)
        bind(['*'], lambda event: self.invert_scan_selection(), filter=files_focused)
        bind(['-'], lambda event: self.resize_icons(-1) if self.graphics_mode else self.clear_scan_selection(), filter=files_focused)
        bind(['R'], lambda event: self.reset_current_map())
        bind(['h'], lambda event: self.push(HelpView(self, 'File manager help', main_help(self.display_mode))))
        bind(['delete'], lambda event: self.queue_remove())
        bind(['s-delete'], lambda event: self.queue_remove(all_duplicates=True))
        bind(['c-y'], lambda event: self.copy_info(), eager=True)
        bind(['c-o'], lambda event: self.open_default(), eager=True)
        bind(['c-x'], lambda event: self.copy_path(), eager=True)
        bind(['c-t'], lambda event: self.open_location(True), eager=True)
        bind(['c-f'], lambda event: self.open_location(), eager=True)
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
        bind(['G'], lambda event: self.cycle_thumbnail_order(), filter=files_focused)
        bind(['k'], lambda event: self.clear_preview_cache(False), filter=files_focused)
        bind(['K'], lambda event: self.clear_preview_cache(True), filter=files_focused)
        bind(['!'], lambda event: self.toggle_exclusion(), filter=files_focused)
        bind(['X'], lambda event: self.toggle_blacklist())
        bind(['L'], lambda event: self.show_blacklist())
        bind(['c-b'], lambda event: self.toggle_blacklist_visibility())
        bind(['c-u'], lambda event: self.toggle_problem_files(), eager=True)
        bind(['c-d'], lambda event: self.trash_selected())
        bind(['d'], lambda event: self.push(DBTrashView(self)))
        bind(['u'], lambda event: self.expand_subdirs(), eager=True)
        bind(['o'], lambda event: self.toggle_expansion_depth(), eager=True)
        bind(['enter'], lambda event: self.open_duplicate(), filter=has_focus(self.info), eager=True)
        bind(['f'], lambda event: self.toggle_duplicate_filter(from_files=files_focused()),
             filter=has_focus(self.info) | files_focused, eager=True)
        duplicate_focused = has_focus(self.info) & Condition(lambda: bool(self.info_paths))
        for key, step in [('up', -1), ('down', 1), ('pageup', -10), ('pagedown', 10),
                          ('home', 'first'), ('end', 'last')]:
            bind([key], lambda event, step=step: self.move_info_duplicate(step),
                 filter=has_focus(self.info), eager=True)
        bind(['right'], lambda event: self.open_duplicate(), filter=duplicate_focused, eager=True)
        bind(['left'], lambda event: self.app.layout.focus(self.control),
             filter=has_focus(self.info), eager=True)
        bind(['v'], lambda event: self.toggle_media_filter())
        bind(['.'], lambda event: self.toggle_dotfiles(), filter=files_focused)
        bind(['+', '='], lambda event: self.resize_icons(1), filter=files_focused)
        bind(['_'], lambda event: self.resize_icons(-1), filter=files_focused)
        bind(['y'], lambda event: self.toggle_auto_quick_view())
        bind(['i'], lambda event: self.toggle_image_previews())
        bind(['n'], lambda event: self.cycle_mode())
        bind(['t'], lambda event: self.cycle_theme())
        bind(['f5', 'c-r'], lambda event: self.refresh(self.current_name()))
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
                        DynamicContainer(lambda: self.filename_search.field if self.filename_search
                                         else self.filename_slider_window),
                    ]),
                ]), style='class:files-pane',
                      width=lambda: Dimension.exact(get_app().output.get_size().columns // 2)),
                Frame(HSplit([
                    Window(height=1),
                    VSplit([
                        Window(width=1),
                        HSplit([
                            Window(FormattedTextControl(self.quickview_heading), height=1,
                                   style='class:info-header'),
                            Window(self.preview_bookmark_control, height=1),
                            ConditionalContainer(self.video_metadata,
                                                 filter=Condition(lambda: self.video_path is not None)),
                            ConditionalContainer(HSplit([
                                ConditionalContainer(self.video_area, filter=Condition(lambda: not self.audio_selected())),
                                VSplit([self.previous_button, self.play_button, self.stop_button, self.next_button, self.mute_button,
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
        layout.children.append(ConditionalContainer(VSplit([
            Button('Convert', width=9, handler=self.edit_conversion),
            Button('Queue +/-', width=11, handler=self.toggle_conversion),
            Button('Queue', width=7, handler=lambda: self.push(ConversionQueueView(self))),
            Window(FormattedTextControl(lambda: self.conversion_status()), height=1),
        ], height=1), filter=Condition(lambda: self.app.output.get_size().rows >= 12 and
                                      self.app.output.get_size().columns >= 40)))
        self.clipboard_notice = ''
        self.clipboard_notice_error = False
        self.clipboard_notice_epoch = 0
        self.main_layout = Layout(self.popup_layout(layout), focused_element=self.control)
        self.app = Application(layout=self.main_layout,
                               key_bindings=bindings, full_screen=True, mouse_support=True,
                               style=DynamicStyle(self.style), color_depth=terminal_color_depth(),
                               input=input, output=output,
                               after_render=self.draw_native_preview)
        if hasattr(self.app.input, 'vt100_parser'):
            self.app.input.vt100_parser = KittyReplyFilter(self.app.input.vt100_parser)
        self.app.pre_run_callables.append(self.start_conversions)
        self.app.pre_run_callables.append(self.start_history_writer)
        self.app.pre_run_callables.append(self.start_directory_counts)
    # INITIALIZE DRIVE BROWSER ]
    # OVERLAY TRANSIENT NOTIFICATIONS WITHOUT RESERVING A SCREEN ROW [
    def popup_layout(self, content):
        notice = ConditionalContainer(HSplit([Frame(Window(
            FormattedTextControl(lambda: safe_text(self.clipboard_notice)), height=1,
            style=lambda: 'fg:#ffffff bg:#cc0000' if self.clipboard_notice_error else 'class:header'),
            title='Notification')],
            style=lambda: 'fg:#ffffff bg:#cc0000' if self.clipboard_notice_error else ''),
            filter=Condition(lambda: bool(self.clipboard_notice)))
        content = HSplit([content, ConditionalContainer(
            Window(FormattedTextControl(self.scan_progress), height=1, style='class:header'),
            filter=Condition(lambda: bool(self.scanners))), ConditionalContainer(
            Window(FormattedTextControl(self.function_keys), height=1, wrap_lines=False,
                   style='class:header'),
            filter=Condition(lambda: not self.scanners))])
        return NumberHighlight(FloatContainer(content, floats=[
            Float(content=notice, right=1, bottom=1,
                  width=lambda: min(len(self.clipboard_notice) + 4,
                                    max(4, get_app().output.get_size().columns - 2)),
                  height=3)]))
    # OVERLAY TRANSIENT NOTIFICATIONS WITHOUT RESERVING A SCREEN ROW ]
    # RESOLVE VFS IDENTITIES TO ORIGINAL LOCAL FILESYSTEM PATHS [
    def original_path(self, path):
        return os.path.abspath(os.path.expanduser(get_real_path(path or '/')))
    # RESOLVE VFS IDENTITIES TO ORIGINAL LOCAL FILESYSTEM PATHS ]
    # FORMAT STARTUP DRIVE AND GLOBAL PATH PREFIXES [
    def display_path(self, path):
        local = self.original_path(path)
        result = local
        if self.show_path_prefixes:
            mappings = [(key, os.path.abspath(os.path.expanduser(value)))
                        for key, value in aliases.items() if value != '0']
            mappings.insert(0, ('~0', os.path.expanduser('~')))

            result = ':' + local
            for key, root in sorted(mappings, key=lambda item: len(item[1]), reverse=True):
                root = root.rstrip('/') or '/'
                if local == root or local.startswith(root.rstrip('/') + '/'):
                    result = key + ':/' + local[len(root):].lstrip('/')
                    break
            # Relativity comes from the source namespace, never directory containment.
            source = os.fspath(path)
            if source.startswith(('/~:', '/@:', '~:', '@:')):
                relative = source.lstrip('/')[2:].lstrip('/')
                result = '@:' + relative
            elif (not os.path.isabs(source) and not source.startswith('~')
                  and ':/' not in source and source.split('/', 1)[0] not in aliases):
                relative = os.path.normpath(source)
                result = '@:' + ('' if relative == '.' else relative)
        self.displayed_paths[path] = result
        return result
    # FORMAT STARTUP DRIVE AND GLOBAL PATH PREFIXES ]
    # CONVERT DISPLAYED PREFIXES BACK TO STORED VFS IDENTITIES [
    def parse_display_path(self, path):
        if path.startswith(('@:', '~:')):
            return '/~:/' + path[2:].lstrip('/')
        key, separator, rest = path.partition(':/')
        if separator and (key in aliases or key in ('', '~', '~0')):
            if key == '~':
                return '/~:/' + rest
            if key == '~0':
                return '/~0:/' + rest
            root = aliases.get(key, '/')
            path = os.path.join(root, rest)
        return normalize_bookmark_path(path)
    # CONVERT DISPLAYED PREFIXES BACK TO STORED VFS IDENTITIES ]
    # TOGGLE PATH PREFIXES [
    def toggle_path_prefixes(self):
        previous = dict(self.displayed_paths)
        self.show_path_prefixes = not self.show_path_prefixes
        changes = {shown: self.display_path(path) for path, shown in previous.items()}
        areas = [self.info, self.video_metadata]
        for screen, _ in self.screen_stack:
            if isinstance(screen, BookmarksView):
                areas.extend([screen.list, screen.path, screen.details])
            elif isinstance(screen, ActionsView):
                screen.refresh_rows()
        if changes:
            pattern = re.compile(r'(?m)(?<!\S)(?:' + '|'.join(re.escape(value) for value in sorted(changes, key=len, reverse=True)) + r')$')
            for area in dict.fromkeys(areas):
                cursor = area.buffer.cursor_position
                area.text = pattern.sub(lambda match: changes[match[0]], area.text)
                area.buffer.cursor_position = min(cursor, len(area.text))
                if isinstance(area.lexer, MarkupLexer):
                    area.lexer.fragments = [[(style, pattern.sub(lambda match: changes[match[0]], text))
                                             for style, text in line]
                                            for line in area.lexer.fragments]
        self.app.invalidate()
    # TOGGLE PATH PREFIXES ]
    # SHOW CURRENT QUICK VIEW AND FILE DISPLAY TOGGLES [
    def info_title(self):
        return (f' Info · y:{"auto" if self.auto_quick_view else "off"}'
                f' · o:{"all" if self.expand_all_levels else "one"}'
                f' · .:{"hide" if self.hide_dotfiles else "show"}'
                f' · i:{"on" if self.image_previews else "off"}')
    # SHOW CURRENT QUICK VIEW AND FILE DISPLAY TOGGLES ]
    def quickview_busy(self):
        return (bool(self.quickview_jobs) or self.video_status == 'Starting…' or
                (getattr(self, 'cursor_refresh_pending', False) and self.auto_quick_view
                 and self.video_player is None and not self.screen_stack))

    def quickview_heading(self):
        result = [('', self.info_title())]
        if self.quickview_busy():
            result.append(('fg:#ffd700', ' ' + ('\\', '|', '/', '-')[int(time.monotonic() * 8) % 4]))
        return result

    def animate_quickview(self):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        if self.quickview_animation_task is not None and not self.quickview_animation_task.done():
            return
        async def animate():
            try:
                while self.quickview_busy() and not self.app.is_done:
                    self.app.invalidate()
                    await asyncio.sleep(.125)
                self.app.invalidate()
            finally:
                self.quickview_animation_task = None
        self.quickview_animation_task = self.app.create_background_task(animate())

    def begin_quickview(self):
        token = object()
        self.quickview_jobs.add(token)
        if hasattr(self, 'app'):
            self.animate_quickview()
            self.app.invalidate()
        return token

    def end_quickview(self, token):
        self.quickview_jobs.discard(token)
        if hasattr(self, 'app'):
            self.app.invalidate()

    # VIDEO FRAME HEIGHT [
    def video_frame_height(self):
        rows = self.app.output.get_size().rows if hasattr(self, 'app') else 27
        return max(1, min(30, rows - 14 - self.video_info_height()))

    def video_info_height(self):
        # Hash, spacer, heading, then up to three visible duplicate rows.
        return 3 + min(3, len(self.info_paths))

    def video_poster_bounds(self):
        render = self.video_area.window.render_info
        if render is not None:
            return (max(1, min(80, render.window_width - 1)),
                    max(1, min(30, render.window_height)))
        return self.video_dimensions[0], self.video_frame_height()
    # VIDEO FRAME HEIGHT ]
    # AUDIO SELECTED FOR DRIVE BROWSER [
    def audio_selected(self):
        return bool(self.video_path and (getattr(self, 'video_audio_only', False) or
                    os.path.splitext(self.video_path)[1].lower() in AUDIO_SUFFIXES))
    # AUDIO SELECTED FOR DRIVE BROWSER ]
    # VIDEO PANEL VISIBLE [
    def video_panel_visible(self):
        if not self.video_path or not hasattr(self, 'app'):
            return False
        size = self.app.output.get_size()
        return size.rows >= 12 and size.columns >= 60
    # VIDEO PANEL VISIBLE ]
    # FOCUS MAIN FOR DRIVE BROWSER [
    def focus_main(self, direction):
        controls = [self.control, self.info]
        if self.video_panel_visible():
            controls.extend([self.previous_button, self.play_button, self.stop_button, self.next_button, self.mute_button, self.seek_control])
        index = next((i for i, control in enumerate(controls)
                      if self.app.layout.has_focus(control)), 0)
        self.app.layout.focus(controls[(index + direction) % len(controls)])
    # FOCUS MAIN FOR DRIVE BROWSER ]
    # SEEK VIDEO FOR DRIVE BROWSER [
    def seek_video(self, seconds, relative=False):
        target = self.video_position + seconds if relative else seconds
        target = max(0., min(self.video_duration, target)) if self.video_duration else max(0., target)
        self.video_position = target
        if self.video_player is not None:
            self.video_player.seek(target)
        self.app.invalidate()
    # SEEK VIDEO FOR DRIVE BROWSER ]
    def load_media_type(self, node, stat):
        if node.is_dir or os.path.splitext(node.name)[1].lower() not in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
            return
        logical = self.original_path(node.id)
        key = os.path.realpath(logical)
        if key not in self.media_type_cache:
            try:
                record = self.navigation_store.get('media_type', key, {})
                if not record and logical != key:
                    record = self.navigation_store.get('media_type', logical, {})
                    if record:
                        self.media_type_legacy_keys.add(key)
                self.media_type_cache[key] = record
            except (TypeError, ValueError):
                self.media_type_cache[key] = {}
        record = self.media_type_cache[key]
        if (stat.get('exists') and isinstance(record, dict) and record.get('type') in ('audio', 'video')
                and record.get('size') == stat.get('size')
                and record.get('modified') == stat.get('modified')):
            node.info['media_type'] = record['type']
            if key in self.media_type_legacy_keys:
                self.navigation_store.put('media_type', key, record)
                self.media_type_legacy_keys.discard(key)
        else:
            node.info.pop('media_type', None)

    def record_media_type(self, file_id, media_type):
        if media_type not in ('audio', 'video'):
            return
        token = (self.video_epoch, file_id, media_type)
        if getattr(self, '_recorded_stream_type', None) == token:
            return
        self._recorded_stream_type = token
        key = os.path.realpath(self.original_path(file_id))
        stat = get_stat_info(file_id)
        if not stat.get('exists'):
            return
        record = {'type': media_type, 'size': stat.get('size'), 'modified': stat.get('modified')}
        if self.media_type_cache.get(key) != record:
            self.navigation_store.put('media_type', key, record)
            self.media_type_cache[key] = record
        for row in self.rows:
            if os.path.realpath(self.original_path(row['node'].id)) == key:
                row['node'].info['media_type'] = media_type
                row['label'] = row['label'][0] + ' ' + self.file_icon(row) + ' ' + row['name']
                row.pop('_display_label', None)
                if media_type == 'audio':
                    self.thumbnails.pop(row['node'].id, None)
        self.grid_layout_key = None
        self.app.invalidate()

    # LOAD VIDEO POSTER [
    async def load_video_poster(self, path, epoch):
        token = self.begin_quickview()
        try:
            await self._load_video_poster(path, epoch)
        finally:
            self.end_quickview(token)

    async def _load_video_poster(self, path, epoch):
        file_id = self.video_file_id
        try:
            media_type = await background_call(probe_media_type, path)
            if self.video_epoch != epoch or self.video_player is not None:
                return
            if media_type is not None:
                self.record_media_type(file_id, media_type)
            if media_type == 'audio':
                self.video_audio_only = True
                self.native_preview = None
                self.video_status = 'Audio only · Press Play'
                self.app.invalidate()
                return
            from term_image.utils import get_cell_size
            cell_width, cell_height = get_cell_size() or (8, 16)
            bounds = self.video_poster_bounds()
            self.video_poster_request = (epoch, bounds)
            item = await background_call(prepare_grid_thumbnail, path, file_id, 256,
                                         bounds, cell_width / cell_height)
            if (self.video_epoch != epoch or self.video_player is not None
                    or self.video_poster_request != (epoch, bounds)):
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
    # LOAD VIDEO POSTER ]
    # APPLY VIDEO FRAME [
    def apply_video_frame(self, value):
        if value['native']:
            art, dimensions = value['native']
            # Grid serialization uses its own layer; posters belong to quick view.
            self.native_preview = (art.replace('z=732', 'z=731'), dimensions,
                                   max(0, (self.video_frame_height() - dimensions[1]) // 2))
        else:
            self.native_preview = None
            width, height = self.video_poster_bounds()
            lines = value['lines']
            frame_width = max((sum(get_cwidth(text) for _, text in row)
                               for row in lines), default=0)
            left = max(0, (width - frame_width) // 2)
            top = max(0, (height - len(lines)) // 2)
            centered = [[('', '')] for _ in range(top)]
            centered.extend([[('', ' ' * left), *row] for row in lines])
            centered.extend([[('', '')] for _ in range(max(0, height - len(centered)))])
            self.video_area.lexer.image_lines = dict(enumerate(centered))
            self.video_area.text = '\n'.join(''.join(text for _, text in row) for row in centered)
    # APPLY VIDEO FRAME ]
    # PERSIST THE LAST KNOWN PLAYBACK POSITION [
    def update_play_history(self):
        entry = getattr(self, 'play_history_entry', None)
        if entry is not None:
            self.action_history.update(entry, position=self.video_position,
                                       duration=self.video_duration)
    # PERSIST THE LAST KNOWN PLAYBACK POSITION ]
    # STOP VIDEO FOR DRIVE BROWSER [
    def stop_video(self):
        self.update_play_history()
        self.play_history_entry = None
        if self.video_player is not None:
            self.video_player.close()
            self.video_player = None
        self.video_status = 'Stopped'
        if hasattr(self, 'app'):
            self.app.invalidate()
    # STOP VIDEO FOR DRIVE BROWSER ]
    # TOGGLE PLAYBACK FOR DRIVE BROWSER [
    def toggle_mute(self):
        self.video_muted = not self.video_muted
        self.mute_button.text = '🔇' if self.video_muted else '🔊'
        if self.video_player is not None:
            self.video_player.set_muted(self.video_muted)
        self.app.invalidate()

    def toggle_playback(self):
        if self.video_player is None:
            self.play_video()
        else:
            self.stop_video()
    # TOGGLE PLAYBACK FOR DRIVE BROWSER ]
    def click_file(self, index):
        row = self.rows[index]
        identity = row['node'].id
        now = time.monotonic()
        previous = getattr(self, '_file_click', None)
        double = previous is not None and previous[0] == identity and now - previous[1] <= .4
        playing = self.video_player is not None or (double and previous[2])
        self.select(index)
        if double:
            self._file_click = None
            if not row['node'].is_dir:
                self.show_info()
                if playing and os.path.splitext(row['node'].name)[1].lower() in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
                    self.play_video()
        else:
            self._file_click = (identity, now, playing)

    def step_media(self, direction):
        playing = self.video_player is not None
        view = self.screen_stack[-1][0] if self.screen_stack else None
        if isinstance(view, BookmarksView):
            nodes = [(index, self.vfs.get_from_path(path)) for index, path in enumerate(self.bookmarks)]
            current = view.table.index
        else:
            nodes = [(index, row['node']) for index, row in enumerate(self.rows)]
            current = next((index for index, node in nodes if node.id == self.preview_bookmark_path), self.selected)
        eligible = [index for index, node in nodes if node is not None and not node.is_dir
                    and os.path.splitext(node.name)[1].lower() in VIDEO_SUFFIXES | AUDIO_SUFFIXES
                    and (index > current if direction > 0 else index < current)]
        if not eligible:
            return
        target = min(eligible) if direction > 0 else max(eligible)
        if isinstance(view, BookmarksView):
            view.table.index = target
            view.preview()
        else:
            self.selected = target
            self.show_info()
        if playing:
            self.play_video()
        self.app.invalidate()

    # PLAY VIDEO FOR DRIVE BROWSER [
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
        player.muted = self.video_muted
        self.video_player = player
        self.video_workers = [worker for worker in self.video_workers if worker.thread.is_alive()]
        self.video_workers.append(player)
        self.video_status = 'Starting…'
        self.animate_quickview()
        self.play_history_entry = self.action_history.add('play', getattr(self, 'video_virtual_path', self.video_path),
            start_position=self.video_position, position=self.video_position, duration=self.video_duration)
        player.start()
        if self.video_position:
            player.seek(self.video_position)
        self.video_task = self.app.create_background_task(self.receive_video(player))
        self.app.invalidate()
    # PLAY VIDEO FOR DRIVE BROWSER ]
    # RECEIVE VIDEO FOR DRIVE BROWSER [
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
                    self.record_media_type(getattr(self, 'video_file_id', self.video_path), 'audio')
                    self.video_audio_only = True
                    self.native_preview = None
                    self.video_status = 'Playing'
                    self.video_position, self.video_duration = value
                elif kind == 'frame':
                    self.record_media_type(getattr(self, 'video_file_id', self.video_path), 'video')
                    self.video_status = 'Playing'
                    self.video_position = value.get('_position', self.video_position)
                    self.video_duration = value.get('_duration', self.video_duration)
                    self.apply_video_frame(value)
                self.update_play_history()
                self.app.invalidate()
        except Exception as exc:
            if self.video_player is player:
                self.video_status = 'Video preview error: ' + safe_text(str(exc))[:100]
                self.video_player = None
        finally:
            player.close()
            self.app.invalidate()
    # RECEIVE VIDEO FOR DRIVE BROWSER ]
    # ICON DIMENSIONS FOR DRIVE BROWSER [
    def icon_dimensions(self):
        from term_image.utils import get_cell_size
        cell_width, cell_height = get_cell_size() or (8, 16)
        return (max(1, math.ceil(self.icon_lines * cell_height / cell_width)),
                self.icon_lines)
    # ICON DIMENSIONS FOR DRIVE BROWSER ]
    # CHECK MEDIA FOR DRIVE BROWSER [
    @staticmethod
    def is_media(row):
        return not row['node'].is_dir and os.path.splitext(row['name'])[1].lower() in MEDIA_SUFFIXES
    # CHECK MEDIA FOR DRIVE BROWSER ]
    # TOGGLE DOTFILES FOR DRIVE BROWSER [
    def toggle_dotfiles(self):
        self.hide_dotfiles = not self.hide_dotfiles
        self.refresh(self.current_name(), update_info=self.video_player is None)
    # TOGGLE DOTFILES FOR DRIVE BROWSER ]
    # TOGGLE MEDIA FILTER [
    @property
    def media_only(self):
        return self.media_filter != 'all'

    @media_only.setter
    def media_only(self, enabled):
        self.media_filter = 'media' if enabled else 'all'

    def toggle_media_filter(self):
        modes = ('all', 'media', 'image', 'videos')
        self.media_filter = modes[(modes.index(self.media_filter) + 1) % len(modes)]
        self.show_notification(f'File filter: {self.media_filter}')
        self.refresh(self.current_name())
    # TOGGLE MEDIA FILTER ]
    # MOVE GRID ROW [
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
    # MOVE GRID ROW ]
    # MOVE GRID PAGE [
    def move_grid_page(self, direction):
        if self.selected not in self.grid_positions:
            return
        x, y, _, _ = self.grid_positions[self.selected]
        height = self.files.render_info.window_height if self.files.render_info else 10
        target = max(0, min(len(self.grid_lines) - 1, y + direction * height))
        entries = self.grid_lines[target][0]
        self.select(min(entries, key=lambda index: abs(self.grid_positions[index][0] - x)))
    # MOVE GRID PAGE ]
    # TOGGLE GRAPHICS FOR DRIVE BROWSER [
    def toggle_graphics(self):
        self.graphics_mode = not self.graphics_mode
        self.refresh(self.current_name(), update_info=False)
        self.app.invalidate()
    # TOGGLE GRAPHICS FOR DRIVE BROWSER ]
    # TOGGLE EXPANSION DEPTH [
    def toggle_expansion_depth(self):
        self.app.layout.focus(self.control)
        self.expand_all_levels = not self.expand_all_levels
        ScanStore(self.vfs.db).put('ui', 'expand_all_levels', self.expand_all_levels)
        self.app.invalidate()
    # TOGGLE EXPANSION DEPTH ]
    def excluded_directory(self, node):
        identity = getattr(node, 'id', node)
        return self.blacklist_enabled and any(
            identity == path or identity.startswith(path.rstrip('/') + '/') for path in self.blacklist)

    def toggle_exclusion(self):
        if not self.rows:
            return
        row = self.rows[self.selected]
        if row['name'] == '..' or not row['node'].is_dir:
            return
        path = normalize_bookmark_path(row['node'].id)
        self.blacklist.symmetric_difference_update({path})
        self.save_blacklist()
        self.apply_blacklist()

    def save_blacklist(self):
        temporary = BLACKLIST_PATH.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(sorted(self.blacklist), ensure_ascii=False) + '\n', encoding='utf-8')
        temporary.replace(BLACKLIST_PATH)

    def apply_blacklist(self):
        for scanner in self.scanners:
            scanner.controls.excluded_paths = tuple(self.blacklist) if self.blacklist_enabled else ()
            for entry in list(scanner.model.entries.values()):
                excluded = self.excluded_directory(entry.id)
                if entry.blacklisted != excluded:
                    scanner.model.update(replace(entry, blacklisted=excluded), rebuild=False)
            scanner.refresh_colors()
            scanner.catalog_signature = None
            scanner.request_projection()
        if self.expansion_task is not None:
            self.expansion_task.cancel()
            self.expansion_task = None
        self.expanded_dirs = {path for path in self.expanded_dirs if not self.excluded_directory(path)}
        self.refresh(self.current_name(), update_info=False)

    def toggle_blacklist(self):
        self.blacklist_enabled = not self.blacklist_enabled
        self.apply_blacklist()
        if self.app.is_running:
            self.show_notification('Blacklist: ' + ('on' if self.blacklist_enabled else 'off'))

    def show_blacklist(self):
        self.push(BlacklistView(self))

    def toggle_blacklist_visibility(self):
        self.show_blacklisted = not self.show_blacklisted
        self.refresh(self.current_name(), update_info=False)
        if self.app.is_running:
            self.show_notification('Blacklisted files: ' + ('shown' if self.show_blacklisted else 'hidden'))

    def toggle_problem_files(self):
        self.show_problem_files = not self.show_problem_files
        self.refresh(self.current_name(), update_info=False)
        if self.app.is_running:
            self.show_notification('Not-found files: ' + ('shown' if self.show_problem_files else 'hidden'))

    def problem_file_style(self, row):
        return ' fg:#ff5555' if row.get('problem_file') else ''

    def is_trashed(self, path):
        return any(path == root or path.startswith(root.rstrip('/') + '/') for root in self.trashed_roots)

    def trash_selected(self):
        if self.screen_stack:
            return
        paths = tuple(sorted({row['node'].id for row in self.rows
                              if row['name'] != '..' and row['node'].id in self.scan_selection}))
        if not paths:
            if not self.rows or self.rows[self.selected]['name'] == '..':
                return
            paths = (self.rows[self.selected]['node'].id,)
        self.push(RemoveDBConfirmView(self, paths))

    def trash_paths(self, paths):
        # An explicitly selected ancestor already includes its descendants.
        roots = tuple(path for path in paths if not any(
            path.startswith(parent.rstrip('/') + '/') for parent in paths if parent != path))
        async def move():
            try:
                # Finish worker writes before removing their baseline records.
                for scanner in tuple(self.scanners):
                    scanner.stop_scanning()
                while self.scanners:
                    await asyncio.sleep(.02)
                count = 0
                for path in roots:
                    present = os.path.exists(get_real_path(path))
                    count += self.db_trash.move(path, archive=not present)
                    self.action_history.add('reset scan info' if present else 'database trash', path)
                self.trashed_roots = self.db_trash.roots()
                self.vfs._local_nodes = {key: value for key, value in self.vfs._local_nodes.items()
                                         if not any(key == root or key.startswith(root.rstrip('/') + '/') for root in roots)}
                self.scan_selection.difference_update(paths)
                self.refresh(update_info=False)
                self.show_notification(f'Removed {count} database records; disk files kept, ready to rescan')
            except (ValueError, OSError, sqlite3.Error) as exc:
                self.trashed_roots = self.db_trash.roots()
                self.refresh(update_info=False)
                self.show_notification(str(exc), error=True)
        self.app.create_background_task(move())

    def exclusion_label(self, style, text, marked, row, offset=1):
        excluded = row['name'] != '..' and row['node'].is_dir and normalize_bookmark_path(row['node'].id) in self.blacklist
        if not excluded:
            return bookmark_label(style, text, marked, offset)
        position = offset + (2 if marked else 0)
        text = (text[:position] + '! ' + text[position:])[:len(text)]
        fragments = bookmark_label(style, text, marked, offset)
        result, cursor = [], 0
        for color, value in fragments:
            index = position - cursor
            if 0 <= index < len(value):
                result.extend([(color, value[:index]),
                               (color + (' fg:#ff5555' if self.blacklist_enabled else ' fg:#00bb55'), '!'),
                               (color, value[index + 1:])])
            else:
                result.append((color, value))
            cursor += len(value)
        return result

    # EXPAND SUBDIRS FOR DRIVE BROWSER [
    def expand_subdirs(self):
        if self.expansion_task is not None and not self.expansion_task.done():
            self.expansion_task.cancel()
            self.expansion_task = None
            self.app.invalidate()
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self.expand_subdirs_sync()
            return
        if not self.rows or not self.rows[self.selected]['node'].is_dir:
            return
        self.expansion_files = set()
        self.expansion_listing_cache = {}
        self.expansion_task = self.app.create_background_task(self.run_expansion())
        self.app.invalidate()

    # REPORT EXPANSION PROGRESS AND CLEAR IT ON EVERY EXIT [
    def expansion_status(self):
        task = self.expansion_task
        if task is None or task.done():
            return ''
        return f'u: scanning {len(self.expansion_files) // 1000 * 1000} files (u:cancel) · '

    async def run_expansion(self):
        notice = self.begin_working('Working… expanding folders (u: cancel)')
        try:
            await self.expand_subdirs_async()
        finally:
            self.end_working(notice)
            if self.expansion_task is asyncio.current_task():
                self.expansion_task = None
            self.app.invalidate()
    # REPORT EXPANSION PROGRESS AND CLEAR IT ON EVERY EXIT ]

    async def expansion_nodes(self, node):
        if node.id in self.expansion_listing_cache:
            return self.expansion_listing_cache[node.id]
        # Snapshot database children on its owning thread; disk I/O runs separately.
        from copy import copy
        from types import SimpleNamespace
        snapshot = copy(self.vfs)
        children = list(self.vfs.db.get_children(node))
        root = self.vfs.db.get_root()
        child_index = {child.name: child for child in children}
        snapshot.db = SimpleNamespace(
            get_children=lambda _: children,
            get_root=lambda: root,
            get_child=lambda parent, name: child_index.get(name) if parent.id == node.id else None)
        nodes = await background_call(snapshot.list_nodes, node)
        self.expansion_listing_cache[node.id] = nodes
        previous = len(self.expansion_files) // 1000
        self.expansion_files.update(child.id for child in nodes if not child.is_dir)
        if len(self.expansion_files) // 1000 > previous:
            self.app.invalidate()
        return nodes

    async def expand_subdirs_async(self):
        if not self.rows:
            return
        row = self.rows[self.selected]
        if not row['node'].is_dir:
            return
        cwd = self.vfs.pwd()
        expanded = set(self.expanded_dirs)
        self.app.layout.focus(self.control)
        roots = await self.expansion_nodes(self.vfs.cwd) if row['name'] == '..' else [row['node']]
        roots = [node for node in roots if node.is_dir and not self.excluded_directory(node)]
        if roots and all(node.id in expanded for node in roots):
            prefixes = [node.id.rstrip('/') + '/' for node in roots]
            expanded = {path for path in expanded if path not in {node.id for node in roots}
                        and not any(path.startswith(prefix) for prefix in prefixes)}
        else:
            pending, visited = roots.copy(), set()
            while pending:
                node = pending.pop()
                if self.excluded_directory(node):
                    continue
                physical = await background_call(os.path.realpath, get_real_path(node.id))
                if physical in visited:
                    continue
                visited.add(physical)
                expanded.add(node.id)
                if self.expand_all_levels:
                    pending.extend(child for child in await self.expansion_nodes(node) if child.is_dir)
                await asyncio.sleep(0)
        entries, seen = [], set()
        pending = [(node.name, node) for node in reversed(await self.expansion_nodes(self.vfs.cwd))]
        while pending:
            name, node = pending.pop()
            if (self.hide_dotfiles and node.name.startswith('.')) or node.id in seen:
                continue
            seen.add(node.id)
            entries.append((name, node))
            if node.is_dir and node.id in expanded and not self.excluded_directory(node):
                pending.extend((name + '/' + child.name, child)
                               for child in reversed(await self.expansion_nodes(node)))
            if len(seen) % 1000 == 0:
                await asyncio.sleep(0)
        parent = self.vfs.get('..')
        if parent is not None:
            entries.insert(0, ('..', parent))
        # Enumeration already established presence; do not stat every file again.
        infos = {node.id: {'exists': node.info.get('status') != 'deleted'}
                 for _, node in entries}
        if cwd == self.vfs.pwd():
            self.expanded_dirs = expanded
            self.refresh(row['name'], update_info=False, _entries=entries, _infos=infos)

    def expand_subdirs_sync(self):
        if not self.rows:
            return
        row = self.rows[self.selected]
        if not row['node'].is_dir:
            return
        self.app.layout.focus(self.control)
        roots = (self.vfs.list_nodes() if row['name'] == '..' else [row['node']])
        roots = [node for node in roots if node.is_dir and not self.excluded_directory(node)]
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
            if self.excluded_directory(node):
                continue
            # Follow directory links once per physical target to stop cycles.
            physical = os.path.realpath(get_real_path(node.id))
            if physical in visited:
                continue
            visited.add(physical)
            self.expanded_dirs.add(node.id)
            if self.expand_all_levels:
                pending.extend(child for child in self.vfs.list_nodes(node) if child.is_dir)
        self.refresh(row['name'], update_info=False)
    # EXPAND SUBDIRS FOR DRIVE BROWSER ]
    # RESIZE ICONS FOR DRIVE BROWSER [
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
    # RESIZE ICONS FOR DRIVE BROWSER ]
    # START THUMBNAILS FOR DRIVE BROWSER [
    def start_thumbnails(self):
        self.thumbnail_epoch += 1
        self.thumbnails = {}
        self.thumbnail_errors = 0
        if self.thumbnail_task is not None and not self.thumbnail_task.done():
            return  # Existing worker finishes its current conversion, then restarts.
        if self.thumbnail_cache_clearing or not self.graphics_mode or not self.image_previews or self.app.is_done:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        if self.thumbnail_executor is None:
            from concurrent.futures import ThreadPoolExecutor
            self.thumbnail_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='drive-thumbnails')
            self.thumbnail_executors.append(self.thumbnail_executor)
        self.thumbnail_task = self.app.create_background_task(self.generate_thumbnails())
    # START THUMBNAILS FOR DRIVE BROWSER ]
    # CLEAR THUMBNAIL FILES AND LINKS WITHOUT RACING IN-FLIGHT DECODING [
    def clear_preview_cache(self, all_directories=False):
        if not self.graphics_mode or self.thumbnail_cache_clearing:
            return
        self.thumbnail_cache_clearing = True
        self.thumbnail_epoch += 1
        self.thumbnails = {}
        self.clear_grid_native()
        scope = None if all_directories else get_real_path(self.vfs.cwd.id)
        self.app.create_background_task(self.clear_preview_cache_async(all_directories, scope))
        self.app.invalidate()

    async def clear_preview_cache_async(self, all_directories, scope=None):
        from vfs.thumbnails import cache_record_in_scope
        store = ScanStore(self.vfs.db)
        records = store.items('thumbnail')
        scope = None if all_directories else (scope if scope is not None else get_real_path(self.vfs.cwd.id))
        try:
            # The same executor waits for any current conversion before deleting.
            if self.thumbnail_executor is None:
                from concurrent.futures import ThreadPoolExecutor
                self.thumbnail_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='drive-thumbnails')
                self.thumbnail_executors.append(self.thumbnail_executor)
            await thumbnail_worker_call(
                self.thumbnail_executor, clear_grid_cache_files, '.cache', scope, list(records.values()))
            for key, record in records.items():
                if scope is None or cache_record_in_scope(record, scope):
                    store.delete('thumbnail', key)
        finally:
            self.thumbnail_cache_clearing = False
            self.start_thumbnails()
            self.app.invalidate()
    # CLEAR THUMBNAIL FILES AND LINKS WITHOUT RACING IN-FLIGHT DECODING ]
    # SELECT THUMBNAIL GENERATION ORDER WITHOUT DISCARDING COMPLETED IMAGES [
    def cycle_thumbnail_order(self):
        if not self.graphics_mode:
            return
        modes = ('sequence', 'random', 'page-stride', 'range-stride')
        self.thumbnail_order = modes[(modes.index(self.thumbnail_order) + 1) % len(modes)]
        self.show_notification(f'Preview order: {self.thumbnail_order}')

    def next_thumbnail(self, pending):
        render = self.files.render_info
        height = max(1, render.window_height if render else 20)
        columns = max(1, self.grid_columns)
        def location(index):
            x, y, _, _ = self.grid_positions.get(index, (index % columns, index // columns, 0, True))
            return y // height, y // max(1, self.grid_tile_height), x // (self.grid_tile_width + 1)
        top = getattr(self.files, 'vertical_scroll', getattr(render, 'vertical_scroll', None))
        pool = list(pending)
        if top is not None:
            visible = [i for i in pool if i in self.grid_positions
                       and top <= self.grid_positions[i][1] < top + height]
            if visible:
                pool = visible
                view = (top, height)
                if getattr(self, '_thumbnail_view', None) != view:
                    self._thumbnail_view = view
                    return min(pool)
        if self.thumbnail_order == 'random':
            import random
            return random.choice(pool)
        if self.thumbnail_order == 'sequence':
            return min(pool)
        if self.thumbnail_order == 'page-stride' and top is None:
            # Before viewport information exists, finish the first page locally.
            # Once it is complete, stride across all remaining pages together.
            first_page = [i for i in pool if location(i)[0] == 0]
            if first_page:
                pool = first_page
        # Advance one column and row at a time across the full remaining range.
        self.thumbnail_step = 1
        return min(pool, key=lambda i: ((location(i)[2] - location(i)[1]) % columns,
                                        location(i)[1], i))
    # SELECT THUMBNAIL GENERATION ORDER WITHOUT DISCARDING COMPLETED IMAGES ]
    def visible_thumbnail_rows(self, pending, top, height):
        visible = {}
        for entries, offset, media in self.grid_lines[max(0, top):max(0, top + height)]:
            if media and offset == 0:
                visible.update((index, pending[index]) for index in entries if index in pending)
        return visible

    # GENERATE THUMBNAILS FOR DRIVE BROWSER [
    async def generate_thumbnails(self):
        from term_image.exceptions import TermImageError
        epoch = self.thumbnail_epoch
        size = self.icon_size
        icon_width, icon_height = self.icon_dimensions()
        dimensions = (icon_width, icon_height)
        from term_image.utils import get_cell_size
        cell_width, cell_height = get_cell_size() or (8, 16)
        cell_ratio = cell_width / cell_height
        store = ScanStore(self.vfs.db)
        try:
            pending = {i: row for i, row in enumerate(self.rows)
                       if not row['node'].is_dir and os.path.splitext(row['node'].name)[1].lower() in THUMBNAIL_SUFFIXES}
            cache_pending = dict(pending)
            self._thumbnail_view = None
            generation_view = None
            # Probe visible JPEGs first, then fill visible misses before offscreen work.
            while pending:
                await self.wait_cursor_idle()
                render = self.files.render_info
                top = getattr(self.files, 'vertical_scroll', getattr(render, 'vertical_scroll', 0))
                height = render.window_height if render else 20
                visible = self.visible_thumbnail_rows(pending, top, height)
                visible_cache = {i: row for i, row in visible.items() if i in cache_pending}
                cache_only = bool(visible_cache) if visible else bool(cache_pending)
                queue = (visible_cache if cache_only else visible) if visible else (cache_pending if cache_only else pending)
                index = self.next_thumbnail(queue)
                if not cache_only and generation_view != (top, height):
                    generation_view = (top, height)
                    index = min(queue)
                row = pending[index]
                if cache_only:
                    cache_pending.pop(index, None)
                else:
                    pending.pop(index, None)
                if epoch != self.thumbnail_epoch or not self.graphics_mode or not self.image_previews:
                    break
                node = row['node']
                if node.is_dir or getattr(node, 'info', {}).get('media_type') == 'audio' or os.path.splitext(node.name)[1].lower() not in THUMBNAIL_SUFFIXES:
                    continue
                started = time.monotonic()
                try:
                    item = await thumbnail_worker_call(
                        self.thumbnail_executor, prepare_grid_thumbnail, get_real_path(node.id),
                        node.id, size, dimensions, cell_ratio, cache_only,
                        store.get('thumbnail', f'{size}:{node.id}'))
                    if epoch != self.thumbnail_epoch:
                        break
                    if item is None:
                        continue
                    pending.pop(index, None)
                    await self.wait_cursor_idle()
                    if epoch != self.thumbnail_epoch:
                        break
                    # Attach only complete worker results; keep DB writes on UI thread.
                    store.put('thumbnail', f'{size}:{node.id}', item['record'])
                    self.thumbnails[node.id] = item
                except (OSError, ValueError, Warning, TermImageError):
                    pending.pop(index, None)
                    self.thumbnail_errors += 1
                    self.thumbnails[node.id] = {'native': None, 'lines': [],
                                                'dimensions': (0, 0), 'failed': True}
                self.thumbnail_seconds = max(.001, time.monotonic() - started)
                self.app.invalidate()  # Append the finished icon without reordering files.
                await asyncio.sleep(0)
        finally:
            self.thumbnail_task = None
            if not self.thumbnail_cache_clearing and (self.app.is_done or not self.graphics_mode or not self.image_previews):
                if self.thumbnail_executor is not None:
                    self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
                    self.thumbnail_executor = None
            if epoch != self.thumbnail_epoch and not self.thumbnail_cache_clearing and self.graphics_mode and self.image_previews and not self.app.is_done:
                self.start_thumbnails()
    # GENERATE THUMBNAILS FOR DRIVE BROWSER ]
    def grid_media_layout(self):
        if getattr(self, '_media_layout_lines', None) is not self.grid_lines:
            groups = [entries for entries, offset, media in self.grid_lines if media and offset == 0]
            locations = {index: (group, column) for group, entries in enumerate(groups)
                         for column, index in enumerate(entries)}
            self._media_layout_lines = self.grid_lines
            self._media_layout = groups, locations
        return self._media_layout

    # GRID CONTENT FOR DRIVE BROWSER [
    def grid_content(self, width, height, header=False):
        icon_width, icon_height = self.icon_dimensions()
        self.grid_tile_width = max(1, icon_width)
        self.grid_tile_height = icon_height + 2
        self.grid_columns = min(getattr(self, 'preview_map_columns', 1000000),
                                max(1, (width + 1) // (self.grid_tile_width + 1)))
        columns, tile_width, tile_height = self.grid_columns, self.grid_tile_width, self.grid_tile_height
        key = (id(self.rows), len(self.rows), width, columns, tile_width, tile_height)
        if self.grid_layout_key != key:
            self.grid_lines, self.grid_positions = [], {}
            pending = []
            # FLUSH BUFFERED OUTPUT AND PENDING UPDATES [
            def flush():
                if not pending:
                    return
                first = len(self.grid_lines)
                entries = pending.copy()
                for column, index in enumerate(entries):
                    self.grid_positions[index] = (column * (tile_width + 1), first, tile_width, True)
                self.grid_lines.extend((entries, offset, True) for offset in range(tile_height))
                pending.clear()
            # FLUSH BUFFERED OUTPUT AND PENDING UPDATES ]
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
            title = self.expansion_status() + f' Graphics u:show/hide o:{"all" if self.expand_all_levels else "one"} · {self.media_filter} · {self.icon_lines} lines · cache {self.icon_size}x{self.icon_size} · {len(self.thumbnails)} previews · G:{self.thumbnail_order} · k/K:clear cache'
            if self.thumbnail_errors:
                title += f' · {self.thumbnail_errors} unavailable'
            return UIContent(get_line=lambda _: [('class:table-header', fit(title, width))], line_count=1)

        # FORMAT ONE VISIBLE DISPLAY ROW [
        def line(index):
            if not self.grid_lines:
                return [('', '(empty)')]
            entries, subrow, media = self.grid_lines[index]
            if not media:
                row = self.rows[entries[0]]
                style = 'class:selected' if entries[0] == self.selected else 'class:' + row['color']
                if not row['node'].is_dir:
                    style += ' class:muted'
                style += self.problem_file_style(row)
                prefix = ' B ' if self.bookmark_path(row) in self.bookmarks else ' '
                path_label = self.file_list_path(row)
                if row['node'].is_dir and row['name'] != '..':
                    path_label = path_label.rstrip('/') + '/'
                excluded = row['name'] != '..' and row['node'].is_dir and row['node'].id in self.blacklist
                label = prefix + self.fit_name(path_label, max(0, width - len(prefix) - (2 if excluded else 0)), graphics=True, selected=entries[0] == self.selected) + ('  ' if excluded else '')
                if row['node'].is_dir and row['node'].id in self.expanded_dirs:
                    if entries[0] != self.selected:
                        style += ' class:expanded-dir'
                    return self.exclusion_label(style + ' class:expanded-dir-name' + self.scan_row_style(row), label, prefix == ' B ', row)
                return self.exclusion_label(style + self.scan_row_style(row), label, prefix == ' B ', row)
            fragments = []
            for column, entry in enumerate(entries):
                if column:
                    fragments.append(('', ' '))
                row = self.rows[entry]
                style = 'class:selected' if entry == self.selected else 'class:' + row['color']
                style += self.problem_file_style(row)
                item = self.thumbnails.get(row['node'].id) if self.image_previews and getattr(row['node'], 'info', {}).get('media_type') != 'audio' else None
                if subrow == icon_height:
                    image_width = item['dimensions'][0] if item else 0
                    marked = self.bookmark_path(row) in self.bookmarks
                    if image_width > 0:
                        label_width = min(tile_width, image_width)
                        left = (tile_width - label_width) // 2
                        prefix = ('B ' if label_width > 1 else 'B') if marked else ''
                        label = prefix + self.fit_name(self.file_list_path(row), label_width - len(prefix), graphics=True, selected=entry == self.selected)
                        fragments.append((style, ' ' * left))
                        fragments.extend(bookmark_label(style, label, marked, offset=0))
                        fragments.append((style, ' ' * (tile_width - left - label_width)))
                    else:
                        prefix = ('B ' if tile_width > 1 else 'B') if marked else ''
                        fragments.extend(bookmark_label(style, prefix + self.fit_name(self.file_list_path(row), tile_width - len(prefix), graphics=True, selected=entry == self.selected), marked, offset=0))
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
                        # The media icon belongs before the filename, once per file.
                        label = '.' if pending and subrow == icon_height // 2 else ''
                        fragments.append((style, fit(label.center(tile_width), tile_width)))
                else:
                    fragments.append((style, ' ' * tile_width))
            return fragments or [('', '(empty)')]
        # FORMAT ONE VISIBLE DISPLAY ROW ]

        x, y, _, media = self.grid_positions.get(self.selected, (0, 0, 0, False))
        # Keep the filename visible when scrolling to the final tile row.
        if media and self.grid_scroll_to_tile != self.selected:
            y += icon_height
        return UIContent(get_line=line, line_count=max(1, len(self.grid_lines)),
                         cursor_position=Point(x=x, y=y), show_cursor=False)
    # GRID CONTENT FOR DRIVE BROWSER ]
    # CLEAR GRID NATIVE [
    def clear_grid_native(self):
        if getattr(self, 'grid_native_drawn', None):
            self.app.output.write_raw('\x1b_Ga=d,d=Z,z=732,q=2;\x1b\\')
            self.app.output.flush()
        self.grid_native_drawn = None
    # CLEAR GRID NATIVE ]
    # DRAW GRID NATIVE [
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
            if not item or not item['native'] or getattr(row['node'], 'info', {}).get('media_type') == 'audio':
                continue
            art, (width, height) = item['native']
            icon_height = self.grid_tile_height - 2
            top = (icon_height - height) // 2
            tile_x, tile_y, _, _ = self.grid_positions[index]
            first = tile_y + top
            visible = [render.input_line_to_visible_line.get(first + offset) for offset in range(height)]
            x = tile_x + (self.grid_tile_width - width) // 2
            if (any(y is None for y in visible) or visible[-1] >= render.window_height
                    or x + width > render.window_width):
                continue
            overlays.append((art, position.xpos + x, position.ypos + visible[0]))
        signature = tuple((id(art), x, y) for art, x, y in overlays)
        if signature == self.grid_native_drawn:
            return
        previous = set(self.grid_native_drawn or ())
        if not previous.issubset(set(signature)):
            self.clear_grid_native()
            previous = set()
        overlays = [(art, x, y) for art, x, y in overlays if (id(art), x, y) not in previous]
        if overlays:
            app.output.write_raw('\x1b7' + ''.join(f'\x1b[{y+1};{x+1}H' + native_graphics_payload(art) for art, x, y in overlays) + '\x1b8')
            app.output.flush()
            self.grid_native_drawn = signature
    # DRAW GRID NATIVE ]
    # CLEAR NATIVE PREVIEW [
    def clear_native_preview(self):
        if self.native_visible:
            # Delete only this pane's Kitty z-index, retaining other graphics.
            self.app.output.write_raw('\x1b_Ga=d,d=Z,z=731,q=2;\x1b\\')
            self.app.output.flush()
            self.native_visible = False
        self.native_drawn = None
        self.video_image_id = None
    # CLEAR NATIVE PREVIEW ]
    # MARGINS HAVE NO DEFAULT PT MOUSE HANDLER; BIND THE PAINTED COLUMN [
    def fit_name(self, text, width, graphics=False, selected=False):
        prefix = text[:2] if text.startswith(('♫ ', '▶ ')) else ''
        if prefix:
            text = text[2:]
        available = max(0, width - len(prefix))
        if selected:
            self.filename_width = max(1, available)
        if self.filename_pan is None:
            name = fit_filename(text, available) if graphics else fit(text, available)
        else:
            text = safe_text(text)
            name = fit(text[self.filename_pan:], available)
        return fit(prefix, min(width, len(prefix))) + name

    def filename_maximum(self):
        key = (id(self.rows), self.filename_width, self.show_path_prefixes)
        if getattr(self, '_filename_maximum_key', None) != key:
            labels = [self.file_list_path(row) for row in self.rows]
            self._filename_maximum_value = max(
                (filename_end(safe_text(label[2:] if label.startswith(('♫ ', '▶ ')) else label) + ' ',
                              self.filename_width) for label in labels), default=0)
            self._filename_maximum_key = key
        return self._filename_maximum_value

    def help_search_focused(self):
        return bool(self.screen_stack and isinstance(self.screen_stack[-1][0], HelpView)
                    and self.app.layout.has_focus(self.screen_stack[-1][0].search))

    def can_pan_filename(self):
        control = self.app.layout.current_control
        return (control is self.control or isinstance(control, (RowsControl, HorizontalBar)) or
                (hasattr(control, 'buffer') and control.buffer.read_only()))

    def pan_filename(self, action):
        control = self.app.layout.current_control
        if isinstance(control, HorizontalBar):
            control = control.table
        if isinstance(control, FilenameViewport):
            control = self.control
        if isinstance(control, RowsControl):
            maximum = control.maximum_pan()
            if action == 'start':
                control.pan = 0
            elif action == 'end':
                control.pan = maximum
            elif action < 0:
                control.pan = max(0, control.pan - 1)
            else:
                control.pan = min(maximum, control.pan + 1)
        elif control is self.control and self.rows:
            text = self.file_list_path(self.rows[self.selected])
            maximum = self.filename_maximum()
            current = self.filename_pan
            if current is None:
                current = maximum if self.graphics_mode else 0
            self.filename_pan = (0 if action == 'start' else maximum if action == 'end'
                                 else max(0, min(maximum, current + action)))
        elif hasattr(control, 'buffer') and control.buffer.read_only():
            buffer = control.buffer
            document = buffer.document
            if action == 'start':
                buffer.cursor_position += document.get_start_of_line_position()
            elif action == 'end':
                buffer.cursor_position += document.get_end_of_line_position()
            else:
                buffer.cursor_position += (document.get_cursor_left_position() if action < 0
                                           else document.get_cursor_right_position())
        self.app.invalidate()

    def install_files_scrollbar(self, app):
        """Margins have no default PT mouse handler; bind the painted column."""
        screen = app.renderer._last_screen
        position = screen.visible_windows_to_write_positions.get(self.files) if screen else None
        if not position or self.screen_stack or not self.files.render_info or app.is_done:
            self.files_scrollbar_dragging = False
            self.preview_map_dragging = False
            return
        if not self.graphics_mode:
            self.preview_map_dragging = False
        if self.graphics_mode and not self.files_scrollbar_dragging:
            margin = self.files.right_margins[0]
            width = margin.get_width(None)
            groups = self.grid_media_layout()[0]
            def map_click(event):
                if event.event_type == MouseEventType.MOUSE_DOWN and event.button == MouseButton.LEFT:
                    self.preview_map_dragging = True
                    self.install_files_scrollbar(app)
                elif event.event_type == MouseEventType.MOUSE_MOVE:
                    if not self.preview_map_dragging:
                        return NotImplemented
                    if event.button != MouseButton.LEFT:
                        self.preview_map_dragging = False
                        app.invalidate()
                        return
                elif event.event_type == MouseEventType.MOUSE_UP and event.button == MouseButton.LEFT:
                    self.preview_map_dragging = False
                else:
                    return NotImplemented
                if groups:
                    y = max(0, min(position.height - 1, event.position.y - position.ypos))
                    entries = groups[min(len(groups) - 1, y * len(groups) // max(1, position.height))]
                    x = event.position.x - (position.xpos + position.width - 1 - width)
                    app.layout.focus(self.control)
                    self.select_grid_tile(entries[max(0, min(len(entries) - 1, x))])
            if self.preview_map_dragging:
                size = app.output.get_size()
                app.renderer.mouse_handlers.set_mouse_handler_for_range(
                    x_min=0, x_max=size.columns, y_min=0, y_max=size.rows, handler=map_click)
                return
            app.renderer.mouse_handlers.set_mouse_handler_for_range(
                x_min=position.xpos + position.width - 1 - width,
                x_max=position.xpos + position.width - 1,
                y_min=position.ypos, y_max=position.ypos + position.height, handler=map_click)
        # HANDLE A DISPLAY CONTROL MOUSE CLICK [
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
        # HANDLE A DISPLAY CONTROL MOUSE CLICK ]
        if self.files_scrollbar_dragging:
            size = app.output.get_size()
            # Keep the drag captured when the pointer leaves the narrow track.
            bounds = dict(x_min=0, x_max=size.columns, y_min=0, y_max=size.rows)
        else:
            bounds = dict(x_min=position.xpos + position.width - 1,
                          x_max=position.xpos + position.width,
                          y_min=position.ypos, y_max=position.ypos + position.height)
        app.renderer.mouse_handlers.set_mouse_handler_for_range(**bounds, handler=click)
    # MARGINS HAVE NO DEFAULT PT MOUSE HANDLER; BIND THE PAINTED COLUMN ]
    # REFIT IMAGE ON RESIZE [
    def refit_image_on_resize(self, app):
        if self.cursor_busy():
            return False
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
    # REFIT IMAGE ON RESIZE ]
    # DRAW NATIVE PREVIEW [
    def draw_native_preview(self, app):
        if self.screen_stack and isinstance(self.screen_stack[-1][0], (ConversionView, HistoryView)):
            self.screen_stack[-1][0].install_drag(app)
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
            if (getattr(self, 'image_previews', False) and self.video_player is None
                    and not self.audio_selected()):
                bounds = self.video_poster_bounds()
                request = (self.video_epoch, bounds)
                if getattr(self, 'video_poster_request', None) != request:
                    self.video_poster_request = request
                    app.create_background_task(self.load_video_poster(self.video_path, self.video_epoch))

        if (getattr(self, 'video_path', None) and not self.video_panel_visible()
                and any(app.layout.has_focus(control)
                        for control in (self.previous_button, self.play_button, self.stop_button, self.next_button, self.mute_button, self.seek_control))):
            app.layout.focus(self.screen_stack[-1][0].table if self.screen_stack and isinstance(self.screen_stack[-1][0], BookmarksView) else self.control)
        if app.is_done:
            self.stop_video()
        if (self.screen_stack and not isinstance(self.screen_stack[-1][0], (BookmarksView, ConversionView))) or not self.native_preview or app.is_done:
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
    # DRAW NATIVE PREVIEW ]
    # BUILD THE CURRENT TERMINAL COLOR THEME [
    def style(self):
        # A new Style on each render changes its invalidation hash and forces
        # prompt_toolkit to repaint the entire screen instead of changed cells.
        return self.styles[self.theme]
    # BUILD THE CURRENT TERMINAL COLOR THEME ]
    # RENDER FILE TABLE HEADERS FOR THE CURRENT PATH DISPLAY [
    def column_header(self):
        name, size, files, dups = self.columns
        title = (self.media_filter.title() + (' path' if self.show_path_prefixes else '')) if self.media_only else ('Path' if self.show_path_prefixes else 'Name')
        return [('class:table-header', self.expansion_status() + fit(title, name) + ' ' + fit(' Size', size) + ' ' + fit(' Files', files) + ' ' + fit(' Dups', dups))]
    # RENDER FILE TABLE HEADERS FOR THE CURRENT PATH DISPLAY ]
    # FORMAT RELATIVE OR PREFIXED FILE LABELS WITHOUT CHANGING ROW IDENTITIES [
    def file_icon(self, row):
        if row['node'].is_dir:
            return '📁'
        kind = getattr(row['node'], 'info', {}).get('media_type')
        if kind is None:
            suffix = os.path.splitext(row['name'])[1].lower()
            kind = 'audio' if suffix in AUDIO_SUFFIXES else 'video' if suffix in VIDEO_SUFFIXES else None
        return {'audio': '♫', 'video': '▶'}.get(kind, '📄')

    def file_list_path(self, row):
        cached = row.get('_display_label')
        if cached is not None and cached[0] == self.show_path_prefixes:
            return cached[1]
        label = row['name'] if row['name'] == '..' or not self.show_path_prefixes else self.display_path(row['node'].id)
        kind = getattr(row['node'], 'info', {}).get('media_type')
        if not row['node'].is_dir and kind is None:
            suffix = os.path.splitext(row['name'])[1].lower()
            kind = 'audio' if suffix in AUDIO_SUFFIXES else 'video' if suffix in VIDEO_SUFFIXES else None
        if row['name'] != '..' and kind in ('audio', 'video'):
            label = ('♫ ' if kind == 'audio' else '▶ ') + label
        if row['name'] != '..' and os.path.islink(get_real_path(row['node'].id)):
            label += ' ↗'
        row['_display_label'] = (self.show_path_prefixes, label)
        return label
    # FORMAT RELATIVE OR PREFIXED FILE LABELS WITHOUT CHANGING ROW IDENTITIES ]
    # CURRENT NAME FOR DRIVE BROWSER [
    def current_name(self):
        return self.rows[self.selected]['name'] if self.rows else None
    # CURRENT NAME FOR DRIVE BROWSER ]
    # KEEP MEDIA ANCESTORS AND HIDE DIRECTORIES WITHOUT MEDIA DESCENDANTS [
    def directory_has_media(self, root, cache, suffixes=MEDIA_SUFFIXES):
        if root.id in cache:
            return cache[root.id]
        pending, seen = [root], set()
        while pending:
            node = pending.pop()
            if self.excluded_directory(node):
                continue
            physical = os.path.realpath(get_real_path(node.id))
            if physical in seen:
                continue
            seen.add(physical)
            if node.id in cache:
                if cache[node.id]:
                    cache[root.id] = True
                    return True
                continue
            for child in self.vfs.list_nodes(node):
                if self.hide_dotfiles and child.name.startswith('.'):
                    continue
                if child.is_dir:
                    pending.append(child)
                elif os.path.splitext(child.name)[1].lower() in suffixes:
                    cache[root.id] = True
                    return True
        cache[root.id] = False
        return False
    # KEEP MEDIA ANCESTORS AND HIDE DIRECTORIES WITHOUT MEDIA DESCENDANTS ]
    # REFRESH FILE ROWS AND PRESERVE THE CURRENT SELECTION [

    def refresh(self, target=None, *, update_info=True, _entries=None, _infos=None):
        changing_directory = self.expansion_cwd != self.vfs.pwd()
        notice = self.begin_working('Working… loading folder') if changing_directory else None
        try:
            result = self.refresh_rows(target, update_info=update_info, _entries=_entries, _infos=_infos)
            if changing_directory:
                self.navigation_store.put('ui', 'last_directory',
                    dict(directory=self.original_path(self.vfs.pwd()),
                         vfs_path=self.vfs.cwd.info.get('_navigation_path', self.vfs.pwd()),
                         catalog_root=self.vfs.pwd() == '/'))
            return result
        finally:
            self.end_working(notice)

    def refresh_rows(self, target=None, *, update_info=True, _entries=None, _infos=None):
        if _entries is None and self.expansion_task is not None:
            self.expansion_task.cancel()
            self.expansion_task = None
        if self.expansion_cwd != self.vfs.pwd():
            self.scan_selection.clear()
            self.expanded_dirs.clear()
            self.expansion_cwd = self.vfs.pwd()
        if _entries is None:
            entries = []
            pending = [(node.name, node) for node in reversed(self.vfs.list_nodes())]
            seen = set()
            while pending:
                name, node = pending.pop()
                if not self.show_blacklisted and any(node.id == root or node.id.startswith(root.rstrip('/') + '/')
                                                      for root in self.blacklist):
                    continue
                if self.hide_dotfiles and node.name.startswith('.'):
                    continue
                if node.id in seen:
                    continue
                seen.add(node.id)
                entries.append((name, node))
                if node.is_dir and node.id in self.expanded_dirs and not self.excluded_directory(node):
                    pending.extend((name + '/' + child.name, child)
                                   for child in reversed(self.vfs.list_nodes(node)))
            parent = self.vfs.get('..')
            if parent is not None:
                entries.insert(0, ('..', parent))
        else:
            entries = _entries
        filter_suffixes = {'all': MEDIA_SUFFIXES, 'media': MEDIA_SUFFIXES,
                          'image': IMAGE_SUFFIXES, 'videos': VIDEO_SUFFIXES}[self.media_filter]
        media_directories = {}
        image_directories = {}
        previous_dups = {row['node'].id: row.get('dups', '(0)') for row in self.rows}
        self.rows = []
        for name, node in entries:
            if name != '..' and (not self.show_blacklisted and any(
                    node.id == root or node.id.startswith(root.rstrip('/') + '/') for root in self.blacklist)):
                continue
            local_info = _infos[node.id] if _infos is not None else self.vfs.get_full_info(node, True)
            self.load_media_type(node, local_info)
            detected = node.info.get('media_type')
            media = not node.is_dir and (self.media_filter in ('all', 'media') if detected == 'audio'
                    else self.media_filter in ('all', 'media', 'videos') if detected == 'video'
                    else os.path.splitext(name)[1].lower() in filter_suffixes)
            blacklisted = node.is_dir and normalize_bookmark_path(node.id) in self.blacklist
            if self.graphics_mode and node.is_dir and name != '..' and not blacklisted:
                if not self.directory_has_media(node, image_directories, THUMBNAIL_SUFFIXES):
                    continue
            if self.media_only:
                if node.is_dir and name != '..' and not blacklisted:
                    if not self.directory_has_media(node, media_directories, filter_suffixes):
                        continue
                elif not node.is_dir and not media:
                    continue
            status = node.info.get('status', 'tracked') if name != '..' else 'tracked'
            exists = local_info.get('exists', False)
            problem_file = not node.is_dir and not exists
            if problem_file and not self.show_problem_files:
                continue
            indicator = 'green' if exists else 'red'
            if self.display_mode == 1 and status == 'new' and not local_info.get('is_symlink'):
                indicator = 'orange'
            color = {'new': 'yellow', 'deleted': 'red'}.get(status, 'white') if self.display_mode == 2 else 'white'
            marker = {'new': '*', 'deleted': '!'}.get(status, ' ') if self.display_mode == 3 else '●'
            listing_empty = False
            if node.is_dir and name != '..' and exists:
                try:
                    with os.scandir(get_real_path(node.id)) as children:
                        listing_empty = next(children, None) is None
                except OSError:
                    pass
            count = (node.total_files if node.is_dir else
                     (len(self.vfs.get_hash_dups(node.info.get('hashinfo'))) if _entries is None else 0))
            icon = self.file_icon({'name': name, 'node': node})
            self.rows.append(dict(name=name, node=node, color=color, indicator=indicator, problem_file=problem_file,
                                  listing_empty=listing_empty,
                                  label=f'{marker} {icon} {name}',
                                  size=('-' if node.is_dir else format_size(node.size, 1).strip()),
                                  dups=(previous_dups.get(node.id, '(?)') if _entries is not None and not node.is_dir
                                        else (f'({count})' if node.is_dir or node.info.get('hashinfo') else '(?)'))))
        self.file_rows_by_path = {row['node'].id: row for row in self.rows if not row['node'].is_dir}
        self.dups_hash_rows = {}
        for row in self.file_rows_by_path.values():
            hashinfo = row['node'].info.get('hashinfo')
            if hashinfo:
                self.dups_hash_rows.setdefault(hashinfo, []).append(row)
        if _entries is not None:
            self.queue_dups_refresh(self.file_rows_by_path)
        self.directory_size_rows = {normalize_bookmark_path(row['node'].id).rstrip('/'): row
                                    for row in self.rows if row['node'].is_dir and row['name'] != '..'}
        for path, row in self.directory_size_rows.items():
            row['size'] = self.directory_size_label(row, path)
            count = max([row['node'].total_files, self.directory_counts.get(path)] + [scanner.directory_counts.get(path, 0)
                                                   for scanner in self.scanners])
            row['dups'] = f'({count})'
            if (isinstance(self.vfs.db, SQLiteDBAdapter) and not row['node'].total_files
                    and path not in self.directory_counts.saved and path not in self.directory_counts.observed):
                self.directory_count_pending[path] = row['node'].id
        if hasattr(self, 'app'):
            self.start_directory_counts()
        self.refresh_scan_symbols()
        self.grid_layout_key = None
        self.grid_positions = {}
        self._filename_maximum_key = None
        self.file_count_width = max([6] + [len(row['dups'].strip('()')) + 1 for row in self.directory_size_rows.values()])
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

    # REFRESH FILE ROWS AND PRESERVE THE CURRENT SELECTION ]
    # PAGE SIZE FOR DRIVE BROWSER [
    def page_size(self):
        if self.graphics_mode:
            height = self.files.render_info.window_height if self.files.render_info else 10
            return max(1, height // self.grid_tile_height) * self.grid_columns
        return max(1, self.files.render_info.window_height - 1) if self.files.render_info else 10
    # PAGE SIZE FOR DRIVE BROWSER ]
    # ALIGN MAP TARGETS TO THE TOP OF THEIR IMAGE TILE [
    def select_grid_tile(self, index):
        self.select(index)
        if index in self.grid_positions:
            self.grid_scroll_to_tile = index
            self.files.vertical_scroll = self.grid_positions[index][1]
            self.app.invalidate()
    # ALIGN MAP TARGETS TO THE TOP OF THEIR IMAGE TILE ]
    # SELECT DRIVE BROWSER [
    def select(self, index):
        selected = max(0, min(max(0, len(self.rows) - 1), index))
        if selected != self.selected:
            self.note_cursor_motion(refresh=True)
            self.grid_scroll_to_tile = None
            self.selected = selected
        if self.graphics_mode and selected in self.grid_positions:
            _, first, _, media = self.grid_positions[selected]
            if media:
                self.grid_scroll_to_tile = selected
                render = self.files.render_info
                if render and (first < self.files.vertical_scroll or
                               first + self.icon_lines >= self.files.vertical_scroll + render.window_height):
                    self.files.vertical_scroll = first
        self.app.invalidate()
    # SELECT DRIVE BROWSER ]
    # MOVE DRIVE BROWSER [
    def move(self, delta):
        self.select(self.selected + delta)
    # MOVE DRIVE BROWSER ]
    def cursor_busy(self):
        return time.monotonic() < getattr(self, 'cursor_idle_until', 0.)

    async def wait_cursor_idle(self):
        while self.cursor_busy():
            await asyncio.sleep(min(.05, self.cursor_idle_until - time.monotonic()))

    def note_cursor_motion(self, refresh=False):
        self.cursor_idle_until = time.monotonic() + 1.
        self.cursor_refresh_pending = getattr(self, 'cursor_refresh_pending', False) or refresh
        if refresh and getattr(self.app, 'is_running', False):
            self.animate_quickview()
        for scanner in self.scanners:
            scanner.controls.interaction_until = self.cursor_idle_until
        task = getattr(self, 'cursor_idle_task', None)
        if task is not None and not task.done():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        async def settled():
            try:
                await self.wait_cursor_idle()
                pending = self.cursor_refresh_pending
                self.cursor_refresh_pending = False
                if pending and not self.screen_stack:
                    self.sync_scan_symbols()
                    if self.video_player is None and self.auto_quick_view:
                        self.show_info(directory=self.current_name() == '..')
                self.app.invalidate()
            finally:
                self.cursor_idle_task = None
        self.cursor_idle_task = self.app.create_background_task(settled())

    def queue_dups_refresh(self, paths):
        self.dups_pending.update(path for path in paths if path in self.file_rows_by_path)
        if not self.dups_pending or (self.dups_task is not None and not self.dups_task.done()):
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        async def refresh_counts():
            try:
                while self.dups_pending:
                    await self.wait_cursor_idle()
                    deadline = time.monotonic() + .002
                    for _ in range(16):
                        if not self.dups_pending or time.monotonic() >= deadline:
                            break
                        path = self.dups_pending.pop()
                        row = self.file_rows_by_path.get(path)
                        if row is None:
                            continue
                        # Catalog-only lookup: never stat disk to find a hash.
                        node = self.vfs.db.get_root()
                        for name in path.strip('/').split('/'):
                            node = self.vfs.db.get_child(node, name)
                            if node is None:
                                break
                        hashinfo = node.info.get('hashinfo') if node is not None else None
                        if hashinfo:
                            row['node'].info.update(node.info)
                            group = self.dups_hash_rows.setdefault(hashinfo, [])
                            if not any(item is row for item in group):
                                group.append(row)
                            count = len(self.vfs.get_hash_dups(hashinfo))
                            for item in group:
                                item['dups'] = f'({count})'
                            self.metadata_widths = (self.metadata_widths[0],
                                                    max(self.metadata_widths[1], len(f'({count})') + 3))
                        else:
                            row['dups'] = '(?)'
                    self.app.invalidate()
                    await asyncio.sleep(.05)
            finally:
                self.dups_task = None
        self.dups_task = self.app.create_background_task(refresh_counts())

    def directory_size_label(self, row, path):
        """Distinguish unknown totals from measured zero; ignore disk inode sizes."""
        node = row['node']
        live = [scan.directory_sizes[path] for scan in self.scanners
                if path in scan.directory_sizes]
        if row.get('listing_empty') and not any(live):
            return '0'
        catalog_size = (node.size if getattr(node, 'info', {}).get('status') != 'new' else 0)
        if live or catalog_size or getattr(node, 'total_files', 0):
            size = max([catalog_size] + live)
            return format_size(size, 0).strip() if size else '0'
        return '-'

    def update_scan_directory_sizes(self, scanner):
        """Apply a bounded set of cached totals, without disk or catalog reads."""
        if self.cursor_busy():
            return
        deadline = time.monotonic() + .002
        for _ in range(128):
            if not scanner.directory_size_dirty or time.monotonic() >= deadline:
                break
            path = scanner.directory_size_dirty.pop()
            row = getattr(self, 'directory_size_rows', {}).get(path)
            if row is None:
                continue
            row['size'] = self.directory_size_label(row, path)
            count = max([getattr(row['node'], 'total_files', 0),
                         self.directory_counts.get(path) if hasattr(self, 'directory_counts') else 0] +
                        [scan.directory_counts.get(path, 0) for scan in self.scanners])
            row['dups'] = f'({count})'
            self.file_count_width = max(getattr(self, 'file_count_width', 6), len(str(count)) + 1)
            self.metadata_widths = (max(self.metadata_widths[0], len(row['size']) + 1),
                                    max(self.metadata_widths[1], len(row['dups']) + 3))

    def start_directory_counts(self):
        if (not self.directory_count_pending or
                self.directory_count_task is not None and not self.directory_count_task.done()):
            return
        db = self.vfs.db
        if not isinstance(db, SQLiteDBAdapter) or db.db_path == ':memory:':
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        async def recover():
            try:
                while self.directory_count_pending:
                    await self.wait_cursor_idle()
                    paths = dict(list(self.directory_count_pending.items())[:16])
                    try:
                        counts = await background_call(catalog_directory_counts, db.db_path,
                                                       tuple(getattr(db, 'routes', {}).values()), paths)
                    except sqlite3.OperationalError as exc:
                        if 'locked' not in str(exc).lower():
                            raise
                        await asyncio.sleep(.1)
                        continue
                    await self.wait_cursor_idle()
                    self.directory_counts.remember(counts)
                    for path in paths:
                        self.directory_count_pending.pop(path, None)
                        row = self.directory_size_rows.get(path)
                        if row is not None:
                            count = max([row['node'].total_files, self.directory_counts.get(path)] +
                                        [scan.directory_counts.get(path, 0) for scan in self.scanners])
                            row['dups'] = f'({count})'
                            self.file_count_width = max(self.file_count_width, len(str(count)) + 1)
                    self.app.invalidate()
                    await asyncio.sleep(.01)
            finally:
                self.directory_count_task = None
        self.directory_count_task = self.app.create_background_task(recover())

    def sync_scan_symbols(self):
        """Apply pending scan events and snapshot markers on cursor movement."""
        for scanner in self.scanners:
            if not scanner.repacking:
                scanner.drain_all(budget=.015)
        self.refresh_scan_symbols()

    def scan_row_marker(self, row):
        # Exact file lookups are cheap; only directory aggregation is snapshotted.
        row['scan_active'] = False
        if row['name'] == '..':
            return row['label'][0]
        node = row['node']
        if self.is_trashed(node.id) and node.info.get('status') == 'new':
            row['indicator'] = 'orange'
            row.pop('scan_color', None)
            return row['label'][0]
        target = normalize_bookmark_path(node.id).rstrip('/')
        symbol = row.get('scan_symbol', row['label'][0])
        for scanner in self.scanners:
            if not node.is_dir:
                entry = scanner.model.entries.get(node.id)
                if entry is None:
                    entry = scanner.model.entries.get(target)
                if entry is not None:
                    symbol = '!' if entry.blacklisted else SCAN_STATES.get(
                        entry.state, SCAN_STATES['unknown'])[0]
                    # Match the settled marker color to the live scan result,
                    # rather than the listing's pre-scan 'new' status.
                    row['indicator'] = {
                        'verified': 'green', 'modified': 'orange',
                        'missing': 'red', 'unknown': 'white', 'new': 'white',
                    }.get(entry.state, row.get('indicator', 'white'))
            if (scanner.closing or scanner.paused_modes is not None
                    or not any(scanner.controls.modes) or not scanner.stats.active):
                continue
            path = normalize_bookmark_path(scanner.stats.path).rstrip('/')
            if path == target or (node.is_dir and path.startswith(target + '/')):
                row['scan_active'] = True
                row['scan_activity_color'] = '#af5fff' if scan_activity_mode(scanner) == 2 else '#ffd700'
                return scan_activity_frame(scanner, time.monotonic())
        return row['label'][0] if symbol == '?' else symbol

    def refresh_scan_symbols(self):
        """Snapshot map states once per reload, never in the redraw loop."""
        targets = {}
        for row in self.rows:
            row.pop('scan_symbol', None)
            row.pop('scan_color', None)
            if row.get('listing_empty', False):
                row['scan_symbol'] = '·'
            if row['name'] != '..':
                targets[normalize_bookmark_path(row['node'].id).rstrip('/')] = row
        masks = dict.fromkeys(targets, 0)
        states = list(SCAN_STATES)
        bits = {state: 1 << index for index, state in enumerate(states)}
        for scanner in self.scanners:
            for entry in scanner.model.entries.values():
                bit = bits.get(entry.state, bits['unknown'])
                if entry.blacklisted:
                    bit |= 1 << len(states)
                path = normalize_bookmark_path(entry.path).rstrip('/')
                while True:
                    if path in masks:
                        masks[path] |= bit
                    if not path:
                        break
                    path = path.rpartition('/')[0]
        for path, mask in masks.items():
            if not mask:
                continue
            state = next(state for state in states if mask & bits[state])
            symbol = SCAN_STATES[state][0]
            if mask & (1 << len(states)):
                symbol = '!'
            if symbol == '·':
                exact = [scanner.model.entries.get(targets[path]['node'].id) for scanner in self.scanners]
                if not any(entry is not None and entry.state == 'empty' for entry in exact):
                    symbol = 'D'
            targets[path]['scan_symbol'] = symbol
            if targets[path]['node'].is_dir and state in ('verified', 'empty', 'modified', 'missing'):
                targets[path]['scan_color'] = {
                    'verified': 'green', 'empty': 'green',
                    'modified': 'orange', 'missing': 'red',
                }[state]

    # SCAN ROW STYLE [
    def scan_row_style(self, row):
        return ' fg:#ffd700' if row['node'].id in self.scan_selection and row['name'] != '..' else ''
    # SCAN ROW STYLE ]
    # TOGGLE SCAN SELECTION [
    def toggle_scan_selection(self, advance=False):
        if self.rows:
            row = self.rows[self.selected]
            if row['name'] != '..':
                self.scan_selection.symmetric_difference_update([row['node'].id])
        if advance:
            self.move(1)
        self.app.invalidate()
    # TOGGLE SCAN SELECTION ]
    # INVERT SCAN SELECTION [
    def invert_scan_selection(self):
        self.scan_selection.symmetric_difference_update(
            row['node'].id for row in self.rows if row['name'] != '..')
        self.app.invalidate()
    # INVERT SCAN SELECTION ]
    # CLEAR SCAN SELECTION [
    def clear_scan_selection(self):
        self.scan_selection.clear()
        self.app.invalidate()
    # CLEAR SCAN SELECTION ]
    # TOGGLE AUTO QUICK VIEW [
    def toggle_auto_quick_view(self):
        self.auto_quick_view = not self.auto_quick_view
        if self.auto_quick_view and self.video_player is None:
            self.show_info(directory=self.current_name() == '..')
        self.app.invalidate()
    # TOGGLE AUTO QUICK VIEW ]
    # TOGGLE IMAGE PREVIEWS [
    def toggle_image_previews(self):
        self.image_previews = not self.image_previews
        self.show_info(directory=self.info_directory)
        self.start_thumbnails()
        self.app.invalidate()
    # TOGGLE IMAGE PREVIEWS ]
    # OPEN DRIVE BROWSER [
    def open(self):
        name = self.current_name()
        if name == '..':
            self.parent()
        elif name is not None and self.rows[self.selected]['node'].is_dir:
            self.history.append((self.vfs.pwd(), name))
            self.vfs.cwd = self.rows[self.selected]['node']
            self.action_history.add('chdir', self.vfs.pwd())
            self.refresh()
        else:
            self.show_info()
    # OPEN DRIVE BROWSER ]
    # OPEN THE SELECTION USING THE DESKTOPS CONFIGURED FILE ASSOCIATION [
    def open_default(self):
        """Open the selection using the desktop's configured file association."""
        path = self.selected_action_path()
        if path is None:
            return
        self.action_history.add('open default', path)
        local = os.path.abspath(get_real_path(path))

        # LAUNCH THE DESKTOP DEFAULT APPLICATION [
        async def launch():
            import sys
            try:
                if not os.path.exists(local):
                    raise FileNotFoundError(f'File or directory unavailable: {local}')
                if sys.platform == 'win32':
                    await background_call(os.startfile, local)
                else:
                    command = ['open' if sys.platform == 'darwin' else 'xdg-open', local]
                    await background_call(subprocess.run, command, stdin=subprocess.DEVNULL,
                                          capture_output=True, text=True, check=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                self.push(HelpView(self, 'Open error', [safe_text(str(exc))]))
        # LAUNCH THE DESKTOP DEFAULT APPLICATION ]
        self.app.create_background_task(launch())
    # OPEN THE SELECTION USING THE DESKTOPS CONFIGURED FILE ASSOCIATION ]
    def selected_action_path(self):
        """Prefer an Info duplicate, falling back to the main selection."""
        path = self.selected_path()
        if path is None and self.rows and self.current_name() != '..':
            path = self.rows[self.selected]['node'].id
        return path

    def copy_path(self):
        path = self.selected_action_path()
        if path is not None:
            self.copy_text(os.path.abspath(get_real_path(path)))

    def open_location(self, terminal=False):
        import sys
        path = self.selected_action_path()
        if path is None:
            return
        local = os.path.abspath(get_real_path(path))

        async def launch():
            try:
                if not os.path.exists(local):
                    raise FileNotFoundError(f'File or directory unavailable: {local}')
                directory = local if os.path.isdir(local) else os.path.dirname(local)
                if terminal:
                    if sys.platform == 'win32':
                        command = ['cmd.exe', '/c', 'start', '', 'cmd.exe']
                    elif sys.platform == 'darwin':
                        command = ['open', '-a', 'Terminal', directory]
                    else:
                        executable = next((name for name in ('x-terminal-emulator',
                            'gnome-terminal', 'konsole', 'xfce4-terminal', 'xterm')
                            if shutil.which(name)), None)
                        if executable is None:
                            raise FileNotFoundError('No supported terminal emulator found')
                        command = [executable]
                    await background_call(subprocess.Popen, command, cwd=directory,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif not os.path.isdir(local):
                    from vfs.desktop import reveal_file
                    await background_call(reveal_file, local)
                elif sys.platform == 'win32':
                    await background_call(os.startfile, directory)
                else:
                    await background_call(subprocess.run,
                        ['open' if sys.platform == 'darwin' else 'xdg-open', directory],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
                    from vfs.desktop import activate_file_manager
                    await background_call(activate_file_manager, directory)
            except (OSError, subprocess.CalledProcessError) as exc:
                self.push(HelpView(self, 'Open error', [safe_text(str(exc))]))
        self.app.create_background_task(launch())

    # NAVIGATE TO THE PARENT AND RESTORE CHILD SELECTION [
    def parent(self):
        if self.vfs.get('..') is None:
            return
        name = self.vfs.get_cwd().name
        self.vfs.enter('..')
        self.action_history.add('chdir', self.vfs.pwd())
        if self.history and self.history[-1][0] == self.vfs.pwd():
            _, name = self.history.pop()
        self.refresh(name)
        self.app.layout.focus(self.control)
    # NAVIGATE TO THE PARENT AND RESTORE CHILD SELECTION ]
    # CYCLE MODE FOR DRIVE BROWSER [
    def cycle_mode(self):
        self.display_mode = self.display_mode % 3 + 1
        self.refresh(self.current_name())
    # CYCLE MODE FOR DRIVE BROWSER ]
    # CYCLE THEME FOR DRIVE BROWSER [
    def cycle_theme(self):
        self.theme = (self.theme + 1) % len(THEMES)
        self.app.invalidate()
    # CYCLE THEME FOR DRIVE BROWSER ]
    # LISTING STATS FOR DRIVE BROWSER [
    def listing_stats(self):
        visible = [row for row in self.rows if row['name'] != '..']
        directories = sum(row['node'].is_dir for row in visible)
        files = len(visible) - directories
        return f'Dirs: {directories} · Files: {files}'
    # LISTING STATS FOR DRIVE BROWSER ]
    # UPDATE LISTING STATS [
    def update_listing_stats(self):
        # Update a fixed logical row without replacing the opened preview/player.
        for area in (self.info, self.video_metadata):
            lines = area.text.split('\n')
            for index, line in enumerate(lines):
                if line.startswith(('Dirs: ', 'Files: ')):
                    counts = self.listing_stats().split(' · ')
                    text = counts[0] if line.startswith('Dirs: ') else counts[1]
                    if line != text:
                        cursor = area.buffer.cursor_position
                        lines[index] = text
                        area.text = '\n'.join(lines)
                        area.buffer.cursor_position = min(cursor, len(area.text))
    # UPDATE LISTING STATS ]
    # SHOW INFO FOR DRIVE BROWSER [
    def show_info(self, directory=False, preview_node=None):
        self.cursor_refresh_pending = False
        token = self.begin_quickview()
        try:
            return self._show_info(directory=directory, preview_node=preview_node)
        finally:
            self.end_quickview(token)

    def _show_info(self, directory=False, preview_node=None):
        self.quickview_duplicate_rows = None
        self.preview_bookmark_path = None
        self.stop_video()
        self.video_epoch += 1
        self.play_history_entry = None
        self.video_position = self.video_duration = 0.
        self.video_audio_only = False
        self.video_path = None
        if hasattr(self, 'app') and any(self.app.layout.has_focus(control)
                                       for control in (self.previous_button, self.play_button, self.stop_button, self.next_button, self.mute_button, self.seek_control)):
            self.app.layout.focus(self.screen_stack[-1][0].table if self.screen_stack and isinstance(self.screen_stack[-1][0], BookmarksView) else self.control)
        self.info_directory = directory
        self.image_preview_node = None
        self.native_preview = None
        self.info_lexer.hash_lines = set()
        self.info_lexer.colors = {}
        self.info_lexer.image_lines = {}
        self.info_paths = {}
        if directory and self.vfs.pwd() == "/":
            lines = [self.display_path('/'), "╭────────╮  drive.py v0.997", "│ ━━━━ ● │  File Manager",
                     "╰────────╯  Explore • Compare • Keep", "", "h: Open help view", "",
                     *main_help(self.display_mode)]
            from term_image.image import KittyImage, auto_image_class
            if self.image_previews and issubclass(auto_image_class(), KittyImage):
                render = self.info.window.render_info
                width = max(1, (render.window_width - 1) // 2) if render else 18
                height = max(1, (render.window_height - 10) // 2) if render else 7

                # NATIVE LOGO FOR SHOW INFO [
                def native_logo(art, dimensions):
                    self.native_preview = (art, dimensions, 1)
                # NATIVE LOGO FOR SHOW INFO ]

                logo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'assets', 'info-logo.png')
                preview_lines = ascii_image_preview(logo, width, height,
                                                   color=True, native=native_logo)
                if self.native_preview:
                    # Keep the title/help below the real logo; no block fallback.
                    lines = [self.display_path('/'), *preview_lines[1:], '', 'drive.py — File Manager',
                             'Explore • Compare • Keep', '', 'h: Open help view', '',
                             *main_help(self.display_mode)]
            self.info.lexer = MarkupLexer()
            self.info.text = plain_markup("\n".join(lines))
            self.info.lexer.fragments = markup_lines(lines)
            self.info.buffer.cursor_position = 0
            return
        self.info.lexer = self.info_lexer
        if not self.rows and not directory and preview_node is None:
            self.info.text = self.display_path(self.vfs.pwd()) + '\n\nNo files.'
            return
        row = self.rows[self.selected] if self.rows else None
        node = preview_node if preview_node is not None else (self.vfs.get_cwd() if directory else row['node'])
        self.preview_bookmark_path = normalize_bookmark_path(node.id)
        info = self.vfs.get_full_info(node)
        self.load_media_type(node, info)
        self.video_audio_only = node.info.get('media_type') == 'audio'
        if not node.is_dir and os.path.splitext(node.name)[1].lower() not in IMAGE_SUFFIXES:
            self.action_history.add('view file', node.id, coalesce=True)

        # FORMAT FILE METADATA TIMESTAMPS [
        def timestamp(key):
            value = info.get(key)
            try:
                return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S') if value is not None else ''
            except (ValueError, OverflowError, OSError):
                return ''
        # FORMAT FILE METADATA TIMESTAMPS ]

        self.preview_status_color = (
            'green' if info.get('exists') else 'red') if directory or preview_node is not None else row['indicator']
        size = format_size(node.size, 0).strip()
        disk_space = ''
        if info.get('exists'):
            try:
                usage = shutil.disk_usage(get_real_path(node.id))
                disk_space = f'Disk free: {scan_size(usage.free)} / {scan_size(usage.total)}'
            except OSError:
                pass
        lines = [self.display_path(node.id or '/'), 'Size:   ' + size, *self.listing_stats().split(' · '),
                 'Created:  ' + timestamp('created'),
                 'Modified: ' + timestamp('modified')]
        if disk_space:
            lines.insert(2, disk_space)
        if not node.is_dir:
            if os.path.splitext(node.name)[1].lower() in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
                self.video_file_id = node.id
                self.video_virtual_path = node.id
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
                self.action_history.add('view image', node.id, coalesce=True)
                self.image_preview_node = node
                size = self.app.output.get_size()
                render = self.info.window.render_info
                self.image_preview_geometry = (size.columns, size.rows, render.window_width if render else 37)
                width = max(1, render.window_width - 1) if render else 36
                # Reserve bottom metadata and three duplicate rows as well as chrome.
                height = max(1, self.app.output.get_size().rows - 22) if hasattr(self, 'app') else 12
                from prompt_toolkit.formatted_text import ANSI, to_formatted_text
                lines.append('')
                # INSTALL A NATIVE TERMINAL IMAGE PREVIEW [
                def native(art, dimensions):
                    self.native_preview = (art, dimensions, len(lines) + 1 + max(0, (height - dimensions[1]) // 2))
                # INSTALL A NATIVE TERMINAL IMAGE PREVIEW ]
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
            self.quickview_duplicate_node = node.id
            selected_real = os.path.normcase(os.path.realpath(get_real_path(node.id)))
            all_paths = []
            known, filtered = set(), []
            for path, state in zip(info.get('dups', []), info.get('dups_states', [])):
                if path == node.id:
                    continue
                all_paths.append((path, state))
                real = os.path.normcase(os.path.realpath(get_real_path(path)))
                if real == selected_real:
                    continue
                if real not in known:
                    known.add(real)
                    filtered.append((path, state))
            self.quickview_duplicate_rows = (filtered, all_paths)
            lines.extend([', '.join(sorted(hashes)) if isinstance(hashes, set) else str(hashes), '',
                          self.duplicate_heading()])
            for path, state in (filtered if self.quickview_filter_duplicates else all_paths):
                self.info_lexer.colors[len(lines)] = 'green' if state.get('exists') else 'red'
                self.info_paths[len(lines)] = path
                lines.append('● ' + self.display_path(path))
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
    # SHOW INFO FOR DRIVE BROWSER ]
    def duplicate_heading(self):
        filtered, all_paths = self.quickview_duplicate_rows
        mode = 'filtered' if self.quickview_filter_duplicates else 'all'
        shown = len(filtered) if self.quickview_filter_duplicates else len(all_paths)
        return f'Duplicates ({shown}/{len(all_paths)}) · {mode} · f: filter/all:'

    def toggle_duplicate_filter(self, *, from_files=False):
        if (from_files and not self.screen_stack
                and (self.quickview_duplicate_rows is None
                     or getattr(self, 'quickview_duplicate_node', None) != self.selected_path())):
            self.show_info()
        if self.quickview_duplicate_rows is None:
            return
        lines = self.info.text.split('\n')
        start = next((index for index, line in enumerate(lines) if line.startswith('Duplicates (')), None)
        if start is None:
            return
        end = max(self.info_paths) + 1 if self.info_paths else start + 1
        current = self.info_paths.get(self.info.buffer.document.cursor_position_row)
        self.quickview_filter_duplicates = not self.quickview_filter_duplicates
        filtered, all_paths = self.quickview_duplicate_rows
        rows = filtered if self.quickview_filter_duplicates else all_paths
        self.info_paths = {}
        self.info_lexer.colors = {index: color for index, color in self.info_lexer.colors.items()
                                  if index < start}
        replacement = [self.duplicate_heading()]
        for path, state in rows:
            index = start + len(replacement)
            self.info_paths[index] = path
            self.info_lexer.colors[index] = 'green' if state.get('exists') else 'red'
            replacement.append('● ' + self.display_path(path))
        self.info.text = '\n'.join(lines[:start] + replacement + lines[end:])
        index = next((index for index, path in self.info_paths.items() if path == current),
                     min(self.info_paths, default=start))
        self.info.buffer.cursor_position = self.info.buffer.document.translate_row_col_to_index(index, 0)
        self.app.invalidate()

    def preview_bookmark_fragments(self):
        marked = self.preview_bookmark_path in self.bookmarks
        path = self.preview_bookmark_path
        if path is None:
            return []
        return [('class:' + getattr(self, 'preview_status_color', 'red'), '● '),
                ('#00ffff bold' if marked else '#888888', 'B', self.click_preview_bookmark),
                ('class:literal', ' ' + safe_text(path.rstrip('/').rsplit('/', 1)[-1] or '/'))]

    def click_preview_bookmark(self, event):
        if event.event_type != MouseEventType.MOUSE_UP or event.button != MouseButton.LEFT:
            return NotImplemented
        path = self.preview_bookmark_path
        if path is None:
            return
        if path in self.bookmarks:
            self.bookmarks.remove(path)
        else:
            self.bookmarks.append(path)
        self.save_bookmarks()
        for screen, _ in self.screen_stack:
            if isinstance(screen, BookmarksView):
                screen.refresh()
        self.app.invalidate()

    # BOOKMARK PATH FOR DRIVE BROWSER [
    def bookmark_path(self, row):
        # The parent-navigation row represents the current directory for bookmarks.
        return normalize_bookmark_path(self.vfs.pwd() if row['name'] == '..' else row['node'].id)
    # BOOKMARK PATH FOR DRIVE BROWSER ]
    # SAVE BOOKMARKS FOR DRIVE BROWSER [
    def save_bookmarks(self):
        temporary = BOOKMARKS_PATH.with_suffix('.json.tmp')
        self.bookmark_index = max(0, min(self.bookmark_index, len(self.bookmarks) - 1))
        state = {'bookmarks': self.bookmarks, 'selected_index': self.bookmark_index}
        temporary.write_text(json.dumps(state, ensure_ascii=False) + '\n', encoding='utf-8')
        temporary.replace(BOOKMARKS_PATH)
    # SAVE BOOKMARKS FOR DRIVE BROWSER ]
    # TOGGLE BOOKMARK FOR DRIVE BROWSER [
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
    # TOGGLE BOOKMARK FOR DRIVE BROWSER ]
    # NAVIGATE FROM HOME AND PATH COMMAND SHORTCUTS [
    def go_path(self, text):
        text = text.strip()
        if text.startswith('cd '):
            text = text[3:].strip()
        if text.startswith('~') and not text.startswith(('~:', '~0:', '~/')) and text != '~':
            text = os.path.expanduser(text)
        path = (text if text.startswith('/') else self.parse_display_path(text)) if text else '/'
        if not path.startswith('/'):
            path = os.path.normpath(self.vfs.pwd().rstrip('/') + '/' + path)
        node = self.vfs.get_from_path(path)
        if node is None:
            return False
        if self.screen_stack and isinstance(self.screen_stack[-1][0], PathCommandView):
            self.action_history.add('path command', node.id)
            self.screen_stack[-1][0].close()
        self.pending_bookmark = path
        self.finish_bookmark()
        return True
    # NAVIGATE FROM HOME AND PATH COMMAND SHORTCUTS ]
    # GO BOOKMARK FOR DRIVE BROWSER [
    def go_bookmark(self, index):
        if 0 <= index < len(self.bookmarks):
            path = normalize_bookmark_path(self.bookmarks[index])
            if self.vfs.get_from_path(path) is None:
                if self.screen_stack and isinstance(self.screen_stack[-1][0], BookmarksView):
                    self.screen_stack[-1][0].details.text = (safe_text(self.display_path(path)) +
                        '\nBookmark unavailable. Check the drive mapping in config.sh or edit its path.')
                return
            self.bookmarks[index] = path
            self.bookmark_index = index
            self.save_bookmarks()
            self.pending_bookmark = self.bookmarks[index]
            self.finish_bookmark()
    # GO BOOKMARK FOR DRIVE BROWSER ]
    # FINISH BOOKMARK FOR DRIVE BROWSER [
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
            self.action_history.add('chdir', self.vfs.pwd())
            self.history.clear()
            self.media_only = False
            self.refresh(None if node.is_dir else node.name)
            if not node.is_dir:
                self.show_info()
            self.app.layout.focus(self.control)
    # FINISH BOOKMARK FOR DRIVE BROWSER ]
    # OPEN DUPLICATE FOR DRIVE BROWSER [
    def move_info_duplicate(self, step):
        """Navigate cached duplicate rows, skipping Quick View metadata."""
        lines = sorted(self.info_paths)
        if not lines:
            if step in ('first', 'last'):
                self.info.buffer.cursor_position = 0 if step == 'first' else len(self.info.text)
            elif step < 0:
                self.info.buffer.cursor_up(count=-step)
            else:
                self.info.buffer.cursor_down(count=step)
            return
        current = self.info.buffer.document.cursor_position_row
        if step == 'first':
            target = lines[0]
        elif step == 'last':
            target = lines[-1]
        elif current in self.info_paths:
            index = lines.index(current)
            target = lines[max(0, min(len(lines) - 1, index + step))]
        else:
            candidates = [line for line in lines if line > current] if step > 0 else [line for line in lines if line < current]
            target = (candidates[0] if step > 0 else candidates[-1]) if candidates else (lines[-1] if step > 0 else lines[0])
        self.info.buffer.cursor_position = self.info.buffer.document.translate_row_col_to_index(target, 0)
        self.app.invalidate()

    def open_duplicate(self):
        path = self.selected_path()
        if not path:
            return
        parent, _, name = path.rpartition('/')
        node = self.vfs.get_from_path(parent or '/')
        if node is not None and node.is_dir:
            self.vfs.cwd = node
            self.action_history.add('chdir', self.vfs.pwd())
            self.history.clear()
            self.refresh(name)
            self.show_info()
            self.app.layout.focus(self.control)
    # OPEN DUPLICATE FOR DRIVE BROWSER ]
    # OPEN A POPUP AND RETAIN THE CURRENT LAYOUT [
    def show_context_help(self):
        screen = self.screen_stack[-1][0] if self.screen_stack else None
        if isinstance(screen, (HelpView, TrashHelpView)):
            screen.close()
        elif isinstance(screen, DBTrashView):
            self.push(TrashHelpView(self))
        elif isinstance(screen, ScannerView):
            self.push(HelpView(self, 'Drive map help', SCANNER_HELP))
        else:
            self.push(HelpView(self, 'File manager help', main_help(self.display_mode)))

    def function_keys(self):
        labels = {1: 'Help', 3: 'Scan', 4: 'Status', 5: 'Refresh', 6: 'Stats', 7: 'Paths', 10: 'Quit'}
        width = self.app.output.get_size().columns
        result = []
        for index, (number, label) in enumerate(labels.items()):
            cells = width // len(labels) + (index < width % len(labels))
            key = f'F{number}'
            text = fit(key, min(len(key), cells))
            result.append(('fg:#ffffff bg:#000000 bold', text))
            if cells > len(text):
                result.append(('class:header', fit(' ' + label, cells - len(text))))
        return result

    def push(self, screen):
        self.files_scrollbar_dragging = False
        if not isinstance(screen, (ScanStatisticsView, StatusView)):
            self.stop_video()
        self.screen_stack.append((screen, self.app.layout))
        self.app.layout = Layout(self.popup_layout(screen.container), focused_element=screen.focus)
        self.app.layout.update_parents_relations()
        screen.start()
        self.app.invalidate()
    # OPEN A POPUP AND RETAIN THE CURRENT LAYOUT ]
    # RESTORE THE PREVIOUS SCREEN LAYOUT [
    def pop(self, screen):
        if not self.screen_stack or self.screen_stack[-1][0] is not screen:
            return
        _, layout = self.screen_stack.pop()
        self.app.layout = layout
        self.app.invalidate()
        self.finish_bookmark()
    # RESTORE THE PREVIOUS SCREEN LAYOUT ]
    def toggle_scanner(self):
        if self.scanner_restart_task is not None and not self.scanner_restart_task.done():
            return
        scanner = next((scan for scan in self.scanners if not scan.closing), None)
        if (scanner is not None and not any(scanner.controls.modes)
                and scanner.paused_modes is None and not scanner.requested_modes
                and not (scanner.mode_thread and scanner.mode_thread.is_alive())):
            finished = scanner.stop_scanning()

            async def restart():
                # Save/join the old session before reopening even the same path.
                await finished
                self.push(ScannerView(self))
            self.scanner_restart_task = self.app.create_background_task(restart())
            return
        self.push(scanner if scanner is not None else ScannerView(self))

    def start_history_writer(self):
        self.action_history.start_writer()
        async def lifetime():
            previous_error = self.action_history.error
            try:
                while True:
                    await asyncio.sleep(1)
                    if self.action_history.error != previous_error:
                        previous_error = self.action_history.error
                        self.app.invalidate()
            finally:
                self.action_history.close_writer()
        self.app.create_background_task(lifetime())

    def start_conversions(self):
        async def tick():
            try:
                while True:
                    self.conversions.tick()
                    if self.conversions.jobs:
                        self.app.invalidate()
                    await asyncio.sleep(.1)
            finally:
                self.conversions.close()
        self.conversion_task = self.app.create_background_task(tick())

    def conversion_source(self):
        if not self.rows:
            return None
        row = self.rows[self.selected]
        return os.path.abspath(get_real_path(self.vfs.pwd() if row['name'] == '..' else row['node'].id))

    def edit_conversion(self):
        source = self.conversion_source()
        if source:
            self.push(ConversionView(self, source))

    def toggle_conversion(self):
        source = self.conversion_source()
        if not source:
            return
        async def toggle():
            try:
                if any(job['source'] == source or job['source'].startswith(source + os.sep)
                       for job in self.conversions.jobs):
                    self.conversions.remove(source)
                    self.show_notification('Removed from conversion queue')
                else:
                    sources = await background_call(lambda: conversion_files(source))
                    self.conversions.submit(sources, ConversionOptions())
                    self.show_notification(f'Queued {len(sources)} video(s)')
            except (OSError, ValueError) as exc:
                self.show_notification(str(exc))
        self.app.create_background_task(toggle())

    def show_status(self):
        if self.screen_stack and isinstance(self.screen_stack[-1][0], StatusView):
            self.screen_stack[-1][0].close()
        else:
            self.push(StatusView(self))

    def status_lines(self):
        """Read cached activity only: no disk probes or map traversal."""
        def running(task):
            return task is not None and not task.done()
        lines = ['Files', f'  Directory: {self.display_path(self.vfs.pwd())}',
                 f'  Rows: {len(self.rows)} · marked items: {len(self.scan_selection)}',
                 f'  Cursor: {"moving / work deferred" if self.cursor_busy() else "idle"}',
                 f'  Expansion: {"working" if running(self.expansion_task) else "idle"}',
                 f'  Duplicate updates: {len(self.dups_pending)} pending', '', 'Quick View',
                 f'  Preview: {"working" if self.quickview_busy() else "idle"} · {len(self.quickview_jobs)} jobs',
                 f'  Pending selection: {"yes" if self.cursor_refresh_pending else "no"}',
                 f'  Media: {self.video_status or "idle"}',
                 f'  Path: {self.video_path or self.preview_bookmark_path or "—"}', '', 'Thumbnails',
                 f'  Worker: {"working" if running(self.thumbnail_task) else "idle"}',
                 f'  Ready: {len(self.thumbnails)} · errors: {self.thumbnail_errors}',
                 f'  Cache clearing: {"yes" if self.thumbnail_cache_clearing else "no"}', '', 'Scanning']
        if not self.scanners:
            lines.append('  No scan session')
        for scanner in self.scanners:
            state = ('stopping' if scanner.closing else 'paused' if scanner.paused_modes is not None
                     else 'running' if any(scanner.controls.modes) else 'complete / idle')
            stats = scanner.stats
            lines += [f'  {self.display_path(scanner.path)} · {state}',
                      f'  {scanner.phase} · Loop {"ON" if scanner.controls.loop else "OFF"}',
                      '  Modes: ' + ' / '.join(f'{i} {"RUN" if enabled else "STOP"}'
                                               for i, enabled in enumerate(scanner.controls.modes, 1)),
                      f'  {stats.paths:,} paths · {stats.paths_per_second:.1f} paths/s · {stats.mb_per_second:.2f} MB/s',
                      f'  Current: {self.display_path(stats.path) if stats.path else "—"}',
                      f'  Map: {len(scanner.model.entries):,} paths / {len(scanner.model.buckets):,} buckets',
                      f'  Queued events: {scanner.events.qsize()} · repacking: {scanner.repacking}',
                      f'  Directory size/count updates: {len(scanner.directory_size_dirty)} pending']
            current, total = scanner.timing.display_snapshot()
            lines.append(f'  Processing time: {format_elapsed(current)} / {format_elapsed(total)}')
            if scanner.projection_error:
                lines.append(f'  Error: {scanner.projection_error}')
        lines += ['', 'Conversions', f'  {self.conversion_status()}']
        active = next((job for job in self.conversions.jobs if job['id'] == self.conversions.current), None)
        if active:
            lines.append(f'  Active: {active["source"]}')
        for job in self.conversions.jobs[:20]:
            lines.append(f'  {job["status"]} {job.get("progress", 0) * 100:.0f}% · {job["source"]}')
            if job.get('error'):
                lines.append('    Error: ' + job['error'])
        if len(self.conversions.jobs) > 20:
            lines.append(f'  … {len(self.conversions.jobs) - 20} more jobs in Q')
        lines += ['', 'Activity and errors', f'  Queued file actions: {len(self.actions)}',
                  f'  History writer: {self.action_history.error or "OK"}',
                  f'  Notification: {self.clipboard_notice or "—"}']
        lines += ['', *getattr(self, 'storage_status_lines', ['Storage', '  Loading database sizes and disk space…'])]
        return [safe_text(line) for line in lines]

    def conversion_status(self):
        jobs = self.conversions.jobs
        active = next((job for job in jobs if job['id'] == self.conversions.current), None)
        state = 'Paused' if self.conversions.paused else 'Running' if self.conversions.enabled else 'Stopped'
        return f'Convert {state} · {len(jobs)} jobs' + (f' · {active["progress"] * 100:.0f}%' if active else '')

    def show_scan_statistics(self):
        if self.screen_stack and isinstance(self.screen_stack[-1][0], ScanStatisticsView):
            self.screen_stack[-1][0].close()
            return
        scanner = next((screen for screen, _ in reversed(self.screen_stack)
                        if isinstance(screen, ScannerView)), None)
        if scanner is not None and scanner.closing:
            scanner = None
        if scanner is None:
            scanner = next((item for item in reversed(self.scanners) if not item.closing), None)
        if scanner is not None:
            scanner.update_statistics()
            path = scanner.storage_path
        else:
            path = self.vfs.pwd().rstrip('/') or '/'
            roots = tuple(sorted(self.scan_selection))
            if roots:
                path += '::selection:' + json.dumps(roots)
        self.push(ScanStatisticsView(self, path))

    def pause_scanner(self):
        for scanner in self.scanners:
            if not scanner.closing:
                scanner.pause_resume()

    def stop_scanner(self):
        for scanner in tuple(self.scanners):
            scanner.stop_scanning()

    def scan_progress(self):
        if not self.scanners:
            return ''
        scanner = next((item for item in reversed(self.scanners)
                        if not item.closing and item.paused_modes is None
                        and any(item.controls.modes) and item.stats.active), self.scanners[-1])
        active = (not scanner.closing and scanner.paused_modes is None
                  and any(scanner.controls.modes) and scanner.stats.active)
        result = []
        if active:
            color = '#af5fff' if scan_activity_mode(scanner) == 2 else '#ffd700'
            result.append(('fg:' + color, scan_activity_frame(scanner, time.monotonic()) + ' · '))
        scope = self.scan_statistics_scope
        rows = self.scan_statistics.record(scanner.storage_path)[scope]
        progress = scan_mode_progress(rows, scan_activity_mode(scanner))
        result.append(('', f'{scope}: {progress} · {scan_path_rate(scanner.stats.paths_per_second)} · '
                           f'{scan_size(scanner.stats.mb_per_second * 1_000_000)}/s'))
        width = self.app.output.get_size().columns if hasattr(self, 'app') else 80
        available = width - sum(get_cwidth(text) for _, text in result) - 3
        path = safe_text(getattr(scanner.stats, 'path', '') or '')
        if path and available > 0:
            if get_cwidth(path) > available:
                if available < 5:
                    path = '.' * min(3, available)
                else:
                    left = (available - 2) // 2
                    right = available - 3 - left
                    path = fit(path, left).rstrip() + '...' + path[filename_end(path, right):]
            result.append(('', ' · ' + path))
        clipped = []
        remaining = max(0, width)
        for style, text in result:
            clipped.append((style, fit(text, remaining).rstrip() if get_cwidth(text) > remaining else text))
            remaining -= get_cwidth(clipped[-1][1])
        return clipped

    # RESET CURRENT MAP [
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
        self.info.text = safe_text(self.display_path(path)) + '\n\nSaved map and scan resume positions cleared.'
        self.info.buffer.cursor_position = 0
        self.app.invalidate()
    # RESET CURRENT MAP ]
    # SELECTED PATH FOR DRIVE BROWSER [
    def selected_path(self):
        if self.app.layout.has_focus(self.info):
            return self.info_paths.get(self.info.buffer.document.cursor_position_row)
        if self.rows and self.current_name() != '..':
            return self.rows[self.selected]['node'].id
        return None
    # SELECTED PATH FOR DRIVE BROWSER ]
    # QUEUE REMOVE FOR DRIVE BROWSER [
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
                self.action_history.add('queue remove', item)
                self.actions.append(action)
                existing.add(action)
        self.app.invalidate()
    # QUEUE REMOVE FOR DRIVE BROWSER ]
    # COPY INFO FOR DRIVE BROWSER [
    def copy_info(self):
        self.copy_text(self.info.text)

    def begin_working(self, message):
        if not hasattr(self, 'app') or not self.app.is_running:
            return None
        self.clipboard_notice = message
        self.clipboard_notice_error = False
        self.clipboard_notice_epoch += 1
        epoch = self.clipboard_notice_epoch
        # Paint before synchronous filesystem checks can block the event loop.
        self.app._redraw()
        return epoch

    def end_working(self, epoch):
        if epoch is not None and self.clipboard_notice_epoch == epoch:
            self.clipboard_notice = ''
            self.app.invalidate()

    # SHOW TEMPORARY ACTION FEEDBACK WITHOUT STEALING FOCUS [
    def show_notification(self, message, *, error=False):
        self.clipboard_notice = message
        self.clipboard_notice_error = error
        self.clipboard_notice_epoch += 1
        epoch = self.clipboard_notice_epoch
        self.app.invalidate()
        async def dismiss():
            await asyncio.sleep(3)
            if self.clipboard_notice_epoch == epoch:
                self.clipboard_notice = ''
                self.app.invalidate()
        self.app.create_background_task(dismiss())
    # SHOW TEMPORARY ACTION FEEDBACK WITHOUT STEALING FOCUS ]
    def copy_text(self, text):
        # COPY THE CURRENT PROJECTION OR OUTPUT STATE [
        async def copy():
            try:
                from vfs.clipboard import copy_native, clipboard_escape
                if not await background_call(copy_native, text):
                    # OSC packets do not move the cursor; avoid leaving/redrawing
                    # the alternate screen just to emit this control sequence.
                    self.app.output.write_raw(clipboard_escape(text))
                    self.app.output.flush()
                    self.show_notification('Clipboard request sent')
                else:
                    self.show_notification('Copied to clipboard')
            except (OSError, subprocess.SubprocessError) as exc:
                self.push(HelpView(self, 'Clipboard error', [str(exc)]))
        # COPY THE CURRENT PROJECTION OR OUTPUT STATE ]
        self.app.create_background_task(copy())
    # COPY INFO FOR DRIVE BROWSER ]
    def request_quit(self):
        self.clipboard_notice = 'Quitting… closing interface and background tasks'
        self.app.invalidate()
        if self.app.is_running:
            self.app._redraw()
        self.app.exit()

    # RUN DRIVE BROWSER [
    def run(self):
        try:
            self.app.run()
        finally:
            print('Quitting: stopping background work', file=sys.stderr, flush=True)
            for scanner in self.scanners:
                scanner.stop.set()
                scanner.controls.wake.set()
                scanner.projection_wake.set()
            shutdown_step('Stopping media playback', self.stop_video)
            shutdown_step('Stopping and saving conversions', self.conversions.close)
            for index, player in enumerate(self.video_workers, 1):
                shutdown_step(f'Waiting for media worker {index}', lambda player=player: player.thread.join(timeout=2))
            shutdown_step('Clearing terminal images', lambda: (self.clear_native_preview(), self.clear_grid_native()))
            self.thumbnail_epoch += 1
            executors = list(self.thumbnail_executors)
            if self.thumbnail_executor is not None and self.thumbnail_executor not in executors:
                executors.append(self.thumbnail_executor)
            for index, executor in enumerate(executors, 1):
                shutdown_step(f'Waiting for thumbnail worker {index}',
                              lambda executor=executor: executor.shutdown(wait=True, cancel_futures=True))
            self.thumbnail_executor = None
            self.thumbnail_executors.clear()
            for scanner in self.scanners:
                root = safe_text(scanner.path)
                for label, thread in (('map projection', scanner.projection_thread),
                                      ('scan worker', scanner.worker),
                                      ('mode switch', scanner.mode_thread),
                                      ('order switch', scanner.order_thread)):
                    if thread is not None:
                        shutdown_step(f'Waiting for {label}: {root}', thread.join)
                shutdown_step(f'Applying remaining scan events: {root}', scanner.drain_all)
                shutdown_step(f'Saving scan map ({len(scanner.model.entries):,} paths): {root}', scanner.save)
            shutdown_step('Saving scan statistics', self.scan_statistics.save)
            shutdown_step('Saving directory file counts', self.directory_counts.save)
            shutdown_step('Flushing action history', self.action_history.close_writer)
            print('Quitting: cleanup complete', file=sys.stderr, flush=True)
    # RUN DRIVE BROWSER ]
# BROWSE FILES AND COORDINATE QUICK VIEW AND POPUPS ]
# DESCRIBE FILE MANAGER SHORTCUTS AND CURRENT MODE LEGEND [
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
        '[#ff8800]x[/#ff8800]: Toggle prefixed / original filesystem paths (all screens)',
        '[#ff8800]Ctrl+S[/#ff8800] (Files): Quick filename prefix search; type to select, Ctrl+S/Down next, Up previous, Enter open best match · Esc finish',
        '[#ff8800]F7[/#ff8800]: View loaded config drive mappings (aliases, source prefixes, local paths, disabled roots)',
        '[#ff8800]b / j[/#ff8800]: Toggle selected file/directory bookmark / editable bookmarks (all screens)',
        '[#ff8800]Ctrl+O[/#ff8800]: Open selected file/directory with the system default app',
        '[#ff8800]f[/#ff8800] (Files or Quick View focus): Toggle real-path filtered/all duplicates; shown/total excludes selected path, all mode retains its aliases',
        'Quick View duplicates: click a row or Tab to info; Up/Down select duplicate rows, PageUp/PageDown move ten, Home/End select first/last; Right/Enter or double-click jumps to the duplicate, Left returns to Files. Without duplicates, text scrolls normally.',
        '[#ff8800]F1 / h[/#ff8800]: Open help from Files; close when help is focused',
        '[#ff8800]Esc[/#ff8800] (in help): Leave search, then close help',
        '[#ff8800]Enter[/#ff8800]: Open directory or view file info / ASCII image preview',
        'Media quick view: p toggles Play / Stop; seek bar click/wheel or focused Left/Right (5s)',
        '[#ff8800]![/#ff8800]: Toggle directory blacklist for u and scanner',
        '[#ff8800]X[/#ff8800]: Toggle blacklist bypass',
        '[#ff8800]L[/#ff8800]: Open directory blacklist',
        '[#ff8800]Ctrl+B[/#ff8800]: Show/hide blacklisted entries in Files (independent of X)',
        '[#ff8800]Ctrl+U[/#ff8800]: Show/hide not-found files; red names in graphics mode',
        '[#ff8800]v[/#ff8800]: Cycle all / media (images, videos, audio) / image / videos',
        '[#ff8800].[/#ff8800]: Toggle dotfiles and hidden directories (shown by default)',
        '[#ff8800]g[/#ff8800]: Toggle thumbnail grid; G page-priority generation order; k/K clear directory/all thumbnail caches; +/- display height (minimum 1 line), cache 128/256 pixels',
        '[#ff8800]u / o[/#ff8800]: Table/graphics: show/hide selected subtree (..: all current subdirs) / toggle one or all levels',
        '[#ff8800]y[/#ff8800]: Toggle automatic quick view on file selection (default off)',
        '[#ff8800]i[/#ff8800]: Toggle image previews, including the logo (default on)',
        '[#ff8800]Esc / Backspace[/#ff8800] (main view): Go to parent directory',
        '[#ff8800]Tab / Shift+Tab[/#ff8800]: Focus next/previous pane or media control',
        '[#ff8800]Ctrl+Y[/#ff8800]: Copy info panel text to clipboard',
        '[#ff8800]Ctrl+X[/#ff8800]: Copy selected absolute local path',
        '[#ff8800]Ctrl+T[/#ff8800]: New terminal at selection (file: parent folder)',
        '[#ff8800]Ctrl+F[/#ff8800]: Reveal selected file in Finder/file manager; open selected folder',
        '[#ff8800]~ / /[/#ff8800]: Home folder / path command (empty Enter: /; Esc: cancel)',
        '[#ff8800]l[/#ff8800]: History · Delete: remove entry · Shift+Delete: clear · t: online/offline filter · v: preview · drag: select · F5: refresh presence',
        '[#ff8800]t[/#ff8800]: Cycle MC Default, MC Blue, Textual Dark and White themes',
        '[#ff8800]n[/#ff8800]: Cycle circles, colored names and monochrome display',
        '[#ff8800]Space / Insert / * / -[/#ff8800]: Toggle file/folder / toggle and down / invert items / clear marks',
        '[#ff8800]F3 / s[/#ff8800]: Open/hide scan view; finished scans restart at current directory/marked items',
        '[#ff8800]Ctrl+P / Ctrl+K[/#ff8800]: Pause/resume background scan / stop and save scan',
        '[#ff8800]F6[/#ff8800]: Scan statistics table; v switches current/total display',
        '[#ff8800]Ctrl+E / Q[/#ff8800]: Video conversion editor / persistent conversion queue',
        'Convert / Queue +/- / Queue buttons: edit, toggle selected video/folder, manage queue',
        '[#ff8800]Shift+R[/#ff8800]: Clear saved map and resume positions for the current directory',
        '[#ff8800]F4[/#ff8800]: Live status window for scans, previews, thumbnails, duplicates, conversions and errors',
        '[#ff8800]F5 / Ctrl+R[/#ff8800]: Reload Files metadata and scan symbols',
        '[#ff8800]=[/#ff8800]: Grow thumbnails (same as +)',
        '[#ff8800]_[/#ff8800]: Shrink thumbnails; graphics - also shrinks, table - clears folder marks',
        '[#ff8800]F10 / q / Ctrl+C[/#ff8800]: Quit',
        '', '[bold]Trash[/bold]',
        '[#ff8800]Ctrl+D[/#ff8800]: Confirm removal of marked items (or cursor item) from db to Trash; disk files kept',
        'Stops active scans first; trashed paths remain excluded from scanning. Restore is not available; D supports Delete for marked/cursor archive entries and Ctrl+Delete to clear all.',
        '[#ff8800]d[/#ff8800]: Open database Trash',
        'Deleted (UTC) is first: yyyy-mm-dd hh:mm:ss. Right column: size and last six hash characters; full hashes remain saved.',
        'In Trash, / focuses live case-insensitive filename search; matches are bold black on yellow, like Help.',
        'Enter on an archive row expands/collapses active duplicates underneath. Arrows/PageUp/PageDown select rows; Enter on a duplicate jumps to its file in Files.',
        'Duplicate status: green circle means present on disk; red circle means missing/inaccessible. Status refreshes when expanding, with no disk checks during cursor movement.',
        'Expanded duplicate names also match search; archive parents remain visible as context. Clear search text to show all entries.',
        'Esc in search clears the filter and focuses the list; Enter focuses the list keeping the filter. Esc from the list closes Trash. d closes outside search; horizontal keys/slider pan narrow views.',
        'In Trash, h opens quick help with highlighted keys. Insert marks/unmarks archive rows and moves down; - deselects all.',
        'Delete permanently removes marked archive entries (or the cursor entry); Ctrl+Delete clears all D entries including hidden results. Disk files and active duplicates remain untouched.',
        '', '[bold]Removal queue[/bold]',
        '[#ff8800]Delete[/#ff8800]: Queue selected file for removal',
        '[#ff8800]Shift+Delete[/#ff8800]: Queue file and all duplicates for removal',
        '[#ff8800]a[/#ff8800]: Open Actions to review operations',
        'In Actions: [#ff8800]x[/#ff8800] clears the queue; [#ff8800]e[/#ff8800] exports actions/action*.sh',
        'Use the Apply button to apply queued operations',
        '', '[bold]File table[/bold]',
        'Size, Files and Dups remain visible beside clipped long names',
        '[#ff8800]Shift+Left / Right[/#ff8800]: Pan long names one symbol in all views',
        '[#ff8800]Shift+Home / End (or Shift+PageUp / PageDown)[/#ff8800]: Beginning / end of longest filename',
        'Horizontal sliders: click or drag to pan long filenames',
        'Files shows directory descendant counts or 1 for a file; Dups shows file hash matches, — for directories',
        'The vertical scrollbar is always visible',
    ]
# DESCRIBE FILE MANAGER SHORTCUTS AND CURRENT MODE LEGEND ]
# DOCUMENT LIVE SCANNER CONTROLS AND STATUS SYMBOLS [
SCANNER_HELP = [
    '[#ff8800]F3[/#ff8800]: Hide scan view; background scanning continues (same as s)',
    '[#ff8800]F1[/#ff8800]: Open or close context help',
    '[#ff8800]F10[/#ff8800]: Quit the app from any view',
    'Shift+Left / Right: pan one symbol; Shift+Home / End or Shift+PageUp / PageDown: filename beginning / end',
    '[#ff8800]x[/#ff8800]: Toggle prefixed / original filesystem paths',
    '[#ff8800]b / j[/#ff8800]: Toggle selected file/directory bookmark / editable bookmarks',
    '[#ff8800]q[/#ff8800]: Quit the app from any view',
    '[#ff8800]F4[/#ff8800]: Live status window for all background activity',
    '[bold]Scanning[/bold]',
    'On open: lite → medium → heavy once, then all modes stop',
    'A started mode finishes, then advances 1 → 2 → 3; L toggles loop (off by default)',
    '[#ff8800]1 / 2 / 3[/#ff8800]: Start/stop selected stage; completion advances to the next stage',
    '[#ff8800]L[/#ff8800]: Toggle repeat Lite → Medium → Heavy (Loop ON/OFF)',
    '[green]RUN[/green] / [red]STOP[/red]: enabled/paused mode',
    'Lite: discover paths and build buckets; directories have D state',
    'Medium: discover new paths and verify file presence/type/size without checksums',
    'Heavy: compare checksums; verified new files enter VFS and show green in main',
    'Heavy scanning keeps your map cursor and file page in place',
    'Directories are skipped by medium/heavy verification',
    'Blacklist prunes discovery and verification; red ! chunks contain excluded entries; X bypasses from Files',
    'Start/stop resumes each mode at its saved pending path',
    '[#ff8800]Shift+1 / Shift+2 / Shift+3[/#ff8800] (also [#ff8800]! / @ / #[/#ff8800]): start from cursor bucket',
    '[#ff8800]r[/#ff8800]: Toggle known-file disk metadata reads in lite',
    '[#ff8800]t[/#ff8800]: Toggle heavy new-first/all priority within buckets',
    '[#ff8800]J[/#ff8800]: Heavy normal/expert order; keeps stage sequencing',
    'Finite expert uses a pending-file pass; the continuous blue selector is not used for sequenced runs',
    'Default: finite expert pass, new then unknown, then stop; no verified-file checksum rereads',
    'Manual mode starts include old files; Heavy finishes and stops unless L Loop is ON',
    '[#ff8800]F6[/#ff8800]: live per-path statistics table; v switches current/total display',
    '', '[bold]Symbols[/bold]',
    '[white]D[/white] Directory',
    '[green]·[/green] Empty directory (confirmed by discovery)',
    '[white]?[/white] Unverified/new file',
    '[green]?[/green] Bucket has both unverified and verified files',
    '[white]U[/white] Legacy new state',
    '[red]U[/red] Missing file',
    '[green]●[/green] Verified by the latest metadata/checksum check',
    '[#ff8800]M[/#ff8800] Modified file',
    '[white on red]\\ | / -[/white on red] Recent map activity in Lite/Medium; red overrides blue until animation ends; S n% is file progress',
    '[white on red]◐ ◓ ◑ ◒[/white on red] Heavy (stage 3) activity uses a rotating circular indicator',
    '', '[bold]Map and settings[/bold]',
    '[#ff8800]m[/#ff8800]: Count/size bucket packing',
    '[#ff8800]v[/#ff8800]: Fixed/scroll packing',
    '[#ff8800]Tab / Shift+Tab[/#ff8800]: Focus next/previous scanner control',
    '[#ff8800]Enter[/#ff8800]: Apply Paths/bucket or MiB/bucket input',
    '[#ff8800]Shift+Home / End (or Shift+PageUp / PageDown)[/#ff8800]: Beginning / end of longest filename',
    '[#ff8800]Ctrl+C[/#ff8800]: Quit',
    'Paths/bucket and MiB/bucket: edit limits; Enter applies',
    '', '[bold]File list and pages[/bold]',
    'Click a status count to filter; click it again or All to remove filter',
    '[#ff8800]][/#ff8800] in map or file list: select /a, then /a/b for selected file /a/b/c',
    '[#ff8800][[/#ff8800]: Move back through parent directories',
    'Both directory scope keys wrap at the ends of the ancestor chain',
    'The matching directory prefix in file paths is gold; the remaining name keeps its normal color',
    'Matching buckets get a random background; symbol foregrounds stay unchanged',
    '[#ff8800]f[/#ff8800]: Fix matching bucket colors',
    '[#ff8800]d[/#ff8800]: Clear all bucket colors',
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
    '[#ff8800]h[/#ff8800]: Open scanner help',
    '[#ff8800]s / Esc[/#ff8800] (scanner): Hide scanner (keeps running); Ctrl+P pause/resume; Ctrl+K stop; [#ff8800]h[/#ff8800]: Help',
    '[#ff8800]h / Esc[/#ff8800] (help) or Close button: Return to scanner',
]


# Prompt-toolkit screens share backend contracts; none import Textual widgets.
MARKUP_TAG = re.compile(r'\[(/?)(#[0-9a-fA-F]{6}|bold|white on red|white|green|red|yellow|dark_orange)\]')
# DOCUMENT LIVE SCANNER CONTROLS AND STATUS SYMBOLS ]
# MARKUP LINES FOR THE DRIVE-TUI WORKFLOW [
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
# MARKUP LINES FOR THE DRIVE-TUI WORKFLOW ]
# PLAIN MARKUP FOR THE DRIVE-TUI WORKFLOW [
def plain_markup(text):
    return MARKUP_TAG.sub('', text)
# PLAIN MARKUP FOR THE DRIVE-TUI WORKFLOW ]
# MANAGE MARKUP LEXER [
class MarkupLexer(Lexer):
    # INITIALIZE MARKUP LEXER [
    def __init__(self, lines=()):
        self.fragments = markup_lines(lines)
    # INITIALIZE MARKUP LEXER ]
    # LEX DOCUMENT FOR MARKUP LEXER [
    def lex_document(self, document):
        fragments = self.fragments
        return lambda line: fragments[line] if line < len(fragments) else []
    # LEX DOCUMENT FOR MARKUP LEXER ]
# MANAGE MARKUP LEXER ]
# MANAGE PTSCREEN FOR THE DRIVE-TUI WORKFLOW [
class PTScreen:
    # INITIALIZE PTSCREEN FOR PTSCREEN [
    def __init__(self, browser):
        self.browser = browser
        self.keys = KeyBindings()
        self.bind(['x'], browser.toggle_path_prefixes, eager=True,
                  filter=Condition(lambda: not browser.help_search_focused() and not isinstance(self, (PathCommandView, ConversionView)) and (not isinstance(self, BookmarksView) or
                      not (browser.app.layout.has_focus(self.path) or browser.app.layout.has_focus(self.number)))))
    # INITIALIZE PTSCREEN FOR PTSCREEN ]
    # START PTSCREEN FOR PTSCREEN [
    def start(self):
        pass
    # START PTSCREEN FOR PTSCREEN ]
    # CLOSE PTSCREEN FOR PTSCREEN [
    def close(self):
        self.browser.pop(self)
    # CLOSE PTSCREEN FOR PTSCREEN ]
    # REGISTER KEYBOARD ACTIONS FOR PTSCREEN [
    def bind(self, keys, callback, **kwargs):
        for key in keys:
            self.keys.add(key, **kwargs)(lambda event, callback=callback: callback())
    # REGISTER KEYBOARD ACTIONS FOR PTSCREEN ]
    # REQUEST A REDRAW FOR PTSCREEN [
    def invalidate(self):
        self.browser.app.invalidate()
    # REQUEST A REDRAW FOR PTSCREEN ]
# MANAGE PTSCREEN FOR THE DRIVE-TUI WORKFLOW ]
# EDIT BOOKMARK TARGETS AND PREVIEW SELECTED FILES [
class ConversionSeekControl(VideoSeekControl):
    def __init__(self, editor):
        super().__init__(editor.browser)
        self.editor = editor

    def create_content(self, width, height):
        self.width = max(1, width - 20)
        duration = self.editor.duration or 1
        start = round(self.editor.value('start') / duration * (self.width - 1))
        end = round(self.editor.value('end') / duration * (self.width - 1))
        current = round(self.browser.video_position / duration * (self.width - 1))
        track = ''.join('|' if i == current else '[' if i == start else ']' if i == end
                        else '=' if start <= i <= end else '-' for i in range(self.width))
        text = track + f' {self.browser.video_position:.1f}/{self.editor.duration:.1f}s'
        return UIContent(get_line=lambda _: [('class:header', fit(text, width))],
                         line_count=1, show_cursor=False)

    def mouse_handler(self, event):
        if event.event_type == MouseEventType.MOUSE_UP:
            editor = self.editor
            target = next((name for name, field in editor.times.items()
                           if editor.browser.app.layout.has_focus(field)), editor.time_target)
            position = max(0., min(1., event.position.x / max(1, self.width - 1))) * editor.duration
            editor.set_time(target, position - editor.value('start') if target == 'length' else position)
            return None
        return super().mouse_handler(event)


class ConversionView(PTScreen):
    def __init__(self, browser, source, job=None):
        super().__init__(browser)
        from prompt_toolkit.layout import ScrollablePane
        self.source = source
        self.job_id = job['id'] if job else None
        self.options = ConversionOptions(**job['options']) if job else ConversionOptions()
        self.duration = 0.
        self.sources = []
        self.closed = False
        self.updating = False
        self.time_target = 'start'
        self.frame_epoch = 0
        self.task = None
        self.frame_task = None
        self.drag = None
        self.message = 'Reading media…'
        self.option_error = False
        self.times = {name: TextArea(height=1, multiline=False) for name in ('start', 'end', 'length')}
        self.times['start'].text = str(self.options.start)
        self.times['end'].text = str(self.options.end or 0)
        self.times['length'].text = '0'
        self.crf = TextArea(text=str(self.options.crf), height=1, multiline=False)
        self.bitrate = TextArea(text=str(self.options.bitrate), height=1, multiline=False)
        self.cap = TextArea(text=str(self.options.max_mb), height=1, multiline=False)
        self.extra = TextArea(text=self.options.extra, height=2, multiline=False, wrap_lines=True)
        self.cli = TextArea(read_only=True, height=3, wrap_lines=False, scrollbar=True)
        self.network = Button('', width=28, handler=self.cycle_network)
        self.codec = Button('', width=28, handler=self.cycle_codec)
        self.quality = Button('', width=28, handler=self.cycle_quality)
        self.resolution = Button('', width=28, handler=self.cycle_resolution)
        self.seek = ConversionSeekControl(self)
        self.focus = self.times['start']
        self.bind(['escape'], self.close, eager=True)
        self.bind(['tab'], lambda: browser.app.layout.focus_next())
        self.bind(['s-tab'], lambda: browser.app.layout.focus_previous())
        self.bind(['c-y'], lambda: browser.copy_text(self.cli.text), eager=True)
        for name, field in self.times.items():
            original = field.control.mouse_handler
            state = {}
            def mouse(event, name=name, field=field, original=original, state=state):
                if event.event_type == MouseEventType.MOUSE_DOWN:
                    self.time_target = name
                    state.update(x=event.position.x, value=self.value(name))
                    positions = browser.app.renderer._last_screen.visible_windows_to_write_positions if browser.app.renderer._last_screen else {}
                    position = positions.get(field.window)
                    self.drag = (name, (position.xpos if position else 0) + event.position.x, self.value(name))
                    self.invalidate()
                elif event.event_type == MouseEventType.MOUSE_MOVE and 'x' in state and self.drag:
                    self.set_time(name, state['value'] + (event.position.x - state['x']) * .1)
                    return None
                elif event.event_type == MouseEventType.MOUSE_UP:
                    self.drag = None
                    state.clear()
                return original(event)
            field.control.mouse_handler = mouse
            def changed(buffer, name=name):
                if not self.updating and self.duration:
                    try:
                        self.set_time(name, parse_time(buffer.text), rewrite=False)
                    except ValueError:
                        pass
            field.buffer.on_text_changed += changed
        def row(label, widget):
            return VSplit([Window(FormattedTextControl(label), width=13), widget], height=1)
        form = HSplit([
            self.network, self.codec, self.quality, self.resolution,
            row('CRF 0..51', self.crf), row('kbps (0=CRF)', self.bitrate), row('Max MB (0=off)', self.cap),
            Window(FormattedTextControl(lambda: f'Source length: {self.duration:.3f}s'), height=1),
            row('Start seconds', self.times['start']), row('End seconds', self.times['end']),
            row('Length seconds', self.times['length']),
            Button('Reset full length', width=20, handler=self.reset),
            Window(FormattedTextControl('Extra FFmpeg encoding options'), height=1), self.extra,
        ])
        preview = HSplit([
            browser.video_area,
            VSplit([Button('Play', width=6, handler=self.play), Button('Stop', width=6, handler=browser.stop_video), browser.mute_button,
                    Window(FormattedTextControl(lambda: safe_text(browser.video_status)), height=1)], height=1),
            Window(self.seek, height=1),
            Window(FormattedTextControl('Choose Start/End/Length, click seek bar. Drag time field: 0.1s/column.'),
                   height=2, wrap_lines=True),
        ])
        self.container = HSplit([
            Window(FormattedTextControl(lambda: safe_text(self.source)), height=1, style='class:header'),
            VSplit([Frame(preview, title='Preview'), Frame(ScrollablePane(form), title='Conversion settings')]),
            Window(FormattedTextControl(lambda: safe_text(self.message)), height=2, wrap_lines=True),
            self.cli,
            VSplit([Button('Submit', width=8, handler=self.submit),
                    Button('Convert now', width=13, handler=self.convert_now),
                    Button('Pause/resume', width=14, handler=browser.conversions.pause),
                    Button('Copy CLI', width=10, handler=lambda: browser.copy_text(self.cli.text)),
                    Button('Queue', width=7, handler=lambda: browser.push(ConversionQueueView(browser))),
                    Button('Close', width=7, handler=self.close)], height=1),
        ], key_bindings=self.keys)
        self.labels()

    def value(self, name):
        try:
            return parse_time(self.times[name].text)
        except ValueError:
            return 0.

    def install_drag(self, app):
        if self.drag is None:
            return
        def drag(event):
            if self.drag is None:
                return NotImplemented
            name, origin, initial = self.drag
            if event.event_type in (MouseEventType.MOUSE_MOVE, MouseEventType.MOUSE_UP):
                self.set_time(name, initial + (event.position.x - origin) * .1)
                if event.event_type == MouseEventType.MOUSE_UP:
                    self.drag = None
                self.invalidate()
        size = app.output.get_size()
        app.renderer.mouse_handlers.set_mouse_handler_for_range(
            x_min=0, x_max=size.columns, y_min=0, y_max=size.rows, handler=drag)

    def labels(self):
        self.network.text = 'Export: ' + self.options.network
        self.codec.text = 'Codec: ' + self.options.codec
        self.quality.text = 'Quality: ' + self.options.quality
        self.resolution.text = 'Resolution: ' + self.options.resolution

    def cycle_network(self):
        network = NETWORKS[(NETWORKS.index(self.options.network) + 1) % len(NETWORKS)]
        start, end = self.value('start'), self.value('end')
        self.options = ConversionOptions.preset(network)
        self.options.start, self.options.end = start, end
        self.crf.text, self.bitrate.text, self.cap.text = str(self.options.crf), '0', str(self.options.max_mb)
        self.labels()

    def cycle_codec(self):
        self.options.codec = 'h265' if self.options.codec == 'h264' else 'h264'
        self.labels()

    def cycle_quality(self):
        self.options.quality = 'low' if self.options.quality == 'high' else 'high'
        self.crf.text = '30' if self.options.quality == 'low' else '20'
        self.labels()

    def cycle_resolution(self):
        self.options.resolution = RESOLUTIONS[(RESOLUTIONS.index(self.options.resolution) + 1) % len(RESOLUTIONS)]
        self.labels()

    def reset(self):
        self.updating = True
        self.times['start'].text = '0.000'
        self.times['end'].text = f'{self.duration:.3f}'
        self.times['length'].text = f'{self.duration:.3f}'
        self.updating = False
        self.seek_frame(0)

    def set_time(self, name, value, rewrite=True):
        if not math.isfinite(value) or not self.duration:
            return
        start = max(0, min(self.value('start'), max(0, self.duration - .001)))
        end = max(start + .001, min(self.duration, self.value('end')))
        if name == 'start':
            start = max(0, min(value, max(0, end - .001)))
            position = start
        else:
            end = max(start + .001, min(self.duration, start + value if name == 'length' else value))
            position = end
        self.updating = True
        for key, number in [('start', start), ('end', end), ('length', end - start)]:
            if rewrite or key != name:
                self.times[key].text = f'{number:.3f}'
        self.updating = False
        self.time_target = name
        self.seek_frame(position)

    def seek_frame(self, seconds):
        self.browser.seek_video(seconds)
        self.frame_epoch += 1
        epoch = self.frame_epoch
        if self.browser.video_player is not None:
            return
        self.browser.video_epoch += 1  # Invalidate a still poster at the old time.
        if self.frame_task:
            self.frame_task.cancel()
        async def preview():
            await asyncio.sleep(.15)
            def load():
                import io
                from PIL import Image
                result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss',
                                         str(min(seconds, max(0, self.duration - .04))), '-i', self.sources[0],
                                         '-vf', "scale='min(640,iw)':-2", '-frames:v', '1',
                                         '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'],
                                        capture_output=True, timeout=20, check=True)
                image = Image.open(io.BytesIO(result.stdout)).convert('RGB')
                return serialize_video_frame(image, self.browser.video_render_dimensions)
            try:
                frame = await background_call(load)
                if (epoch == self.frame_epoch and not self.closed and self.browser.screen_stack
                        and self.browser.screen_stack[-1][0] is self):
                    self.browser.apply_video_frame(frame)
                    self.invalidate()
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                self.message = 'Frame preview: ' + str(exc)
        self.frame_task = self.browser.app.create_background_task(preview())

    def read_options(self):
        self.options.start = parse_time(self.times['start'].text)
        self.options.end = parse_time(self.times['end'].text)
        self.options.crf = int(self.crf.text)
        self.options.bitrate = int(self.bitrate.text)
        self.options.max_mb = float(self.cap.text)
        self.options.extra = self.extra.text
        output = str(Path(self.sources[0]).parent / 'youtube-conv' / f'{Path(self.sources[0]).stem}-{self.options.network}-export.mp4')
        args = conversion_command(self.sources[0], output, self.options, self.duration)
        return args

    def play(self):
        self.browser.play_video()

    def submit(self):
        try:
            self.read_options()
            options = replace(self.options)
            if Path(self.source).is_dir() and self.value('end') == round(self.duration, 3) and not options.start:
                options.end = None
            self.browser.conversions.submit(self.sources, options, self.job_id)
            if self.job_id is None and len(self.sources) == 1:
                self.job_id = next(job['id'] for job in reversed(self.browser.conversions.jobs)
                                   if job['source'] == self.sources[0] and job['status'] == 'queued')
            self.message = f'Saved {len(self.sources)} conversion(s) to queue'
            return True
        except (ValueError, OSError, IndexError) as exc:
            self.message = str(exc)
            return False

    def convert_now(self):
        if self.submit():
            try:
                if self.job_id:
                    self.browser.conversions.convert_now(self.job_id)
                else:
                    self.browser.conversions.start()
            except ValueError as exc:
                self.message = str(exc)

    def start(self):
        async def run():
            try:
                self.sources = await background_call(lambda: conversion_files(self.source))
                if not self.sources:
                    raise ValueError('No video files found')
                self.duration = await background_call(lambda: probe_media(self.sources[0]))
                if self.closed:
                    return
                from vfs.nodes import VFSNode
                path = self.sources[0]
                self.browser.show_info(preview_node=VFSNode(path, Path(path).name, False, size=Path(path).stat().st_size))
                self.browser.video_duration = self.duration
                self.updating = True
                self.times['end'].text = f'{min(self.duration, self.options.end or self.duration):.3f}'
                self.times['length'].text = f'{self.value("end") - self.value("start"):.3f}'
                self.updating = False
                self.message = f'{len(self.sources)} file(s) · output: source directory/youtube-conv/'
                self.seek_frame(self.value('start'))
                while not self.closed:
                    try:
                        text = shlex.join(self.read_options())
                        if self.cli.text != text:
                            self.cli.text = text
                        if self.option_error:
                            self.message = f'{len(self.sources)} file(s) · output: source directory/youtube-conv/'
                            self.option_error = False
                    except (ValueError, OSError) as exc:
                        self.option_error = True
                        self.message = str(exc)
                    self.invalidate()
                    await asyncio.sleep(.2)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                self.message = str(exc)
                self.invalidate()
        self.task = self.browser.app.create_background_task(run())

    def close(self):
        self.closed = True
        if self.task:
            self.task.cancel()
        if self.frame_task:
            self.frame_task.cancel()
        self.browser.stop_video()
        self.browser.video_epoch += 1
        self.browser.pop(self)


class ConversionQueueView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        self.table = RowsControl(self.rows)
        self.focus = self.table
        table_bindings(self, self.table)
        self.bind(['escape'], self.close, eager=True)
        self.bind(['enter'], self.edit, eager=True)
        self.bind(['delete'], self.remove, eager=True)
        self.container = HSplit([
            Window(FormattedTextControl('Video conversion queue · Enter edit/go · Delete remove'), height=1, style='class:header'),
            Window(self.table, right_margins=[ScrollbarMargin()], always_hide_cursor=True),
            Window(FormattedTextControl(self.preset_text), height=3, wrap_lines=True),
            Window(FormattedTextControl(lambda: f'{len(browser.conversions.jobs)} jobs · '
                   f'{"Paused" if browser.conversions.paused else "Running" if browser.conversions.enabled else "Stopped"}'), height=1),
            VSplit([Button('Start', width=7, handler=browser.conversions.start),
                    Button('Pause/resume', width=14, handler=browser.conversions.pause),
                    Button('Stop', width=6, handler=browser.conversions.stop),
                    Button('Clear', width=7, handler=browser.conversions.clear),
                    Button('Convert now', width=13, handler=self.now),
                    Button('Edit', width=6, handler=self.edit)], height=1),
        ], key_bindings=self.keys)

    def rows(self):
        return [[('', f'{job["status"]:7} {job["progress"] * 100:5.1f}% '),
                 ('class:literal', job['source']),
                 ('', ' · ' + job['options']['network'] + ' · ' + (job['error'] or job['output']))]
                for job in self.browser.conversions.jobs]

    def preset_text(self):
        job = self.selected()
        if not job:
            return 'Queue is empty'
        options = job['options']
        return (f"{options['network']} · {options['codec']} · {options['quality']} · "
                f"CRF {options['crf']} · {options['resolution']} · {options['bitrate']} kbps · "
                f"cap {options['max_mb']} MB\n"
                f"Start {options['start']:.3f}s → {options['end'] if options['end'] is not None else 'EOF'} · "
                'Enter/Edit: go to source and edit this preset')

    def selected(self):
        jobs = self.browser.conversions.jobs
        return jobs[min(self.table.index, len(jobs) - 1)] if jobs else None

    def remove(self):
        job = self.selected()
        if job:
            # Remove only this preset/job; directory toggles remove whole trees.
            if self.browser.conversions.current == job['id']:
                self.browser.conversions.stop()
            self.browser.conversions.jobs.remove(job)
            self.browser.conversions.dirty = True
            self.browser.conversions.save()
            self.table.move(0)

    def now(self):
        job = self.selected()
        if job:
            try:
                self.browser.conversions.convert_now(job['id'])
            except ValueError as exc:
                self.browser.show_notification(str(exc))

    def edit(self):
        job = self.selected()
        if job:
            self.close()
            while self.browser.screen_stack and isinstance(self.browser.screen_stack[-1][0], ConversionView):
                self.browser.screen_stack[-1][0].close()
            self.browser.go_path(str(Path(job['source']).parent))
            self.browser.refresh(Path(job['source']).name)
            self.browser.push(ConversionView(self.browser, job['source'], job))


class StatusView(PTScreen):
    """Live cached activity, with stable scroll position and no playback stop."""
    def __init__(self, browser):
        super().__init__(browser)
        self.table = TextArea(read_only=True, scrollbar=True, wrap_lines=True)
        self.focus = self.table
        self.task = None
        self.storage_task = None
        self.closed = False
        self.storage_wake = asyncio.Event()
        self.bind(['escape'], self.close, eager=True)
        self.bind(['f5'], self.refresh_storage, eager=True)
        self.container = HSplit([
            Frame(self.table, title='Status · F4 / Esc close · F5 refresh'),
            Button('Close', handler=self.close),
        ], key_bindings=self.keys)
        self.bind(['tab'], lambda: browser.app.layout.focus_next())
        self.bind(['s-tab'], lambda: browser.app.layout.focus_previous())
        self.refresh()

    def refresh(self):
        text = '\n'.join(self.browser.status_lines())
        if text != self.table.text:
            cursor = self.table.buffer.cursor_position
            self.table.text = text
            self.table.buffer.cursor_position = min(cursor, len(text))
        self.invalidate()

    def refresh_storage(self):
        self.storage_wake.set()
        self.refresh()

    async def probe_storage(self):
        from vfs.storage_status import storage_status
        while not self.closed:
            self.storage_wake.clear()
            db = self.browser.vfs.db
            paths = ([str(db.db_path), *map(str, getattr(db, 'routes', {}).values())]
                     if isinstance(db, SQLiteDBAdapter) else [])
            directory = get_real_path(self.browser.vfs.pwd())
            try:
                self.browser.storage_status_lines = await background_call(storage_status, paths, directory)
            except Exception as exc:
                self.browser.storage_status_lines = ['Storage', f'  Unable to read storage: {safe_text(exc)}']
            if self.closed:
                return
            self.refresh()
            try:
                await asyncio.wait_for(self.storage_wake.wait(), timeout=5.)
            except asyncio.TimeoutError:
                pass

    def start(self):
        async def tick():
            while True:
                await asyncio.sleep(.3)
                self.refresh()
        self.task = self.browser.app.create_background_task(tick())
        self.storage_task = self.browser.app.create_background_task(self.probe_storage())

    def close(self):
        self.closed = True
        self.storage_wake.set()
        if self.task:
            self.task.cancel()
        if self.storage_task:
            self.storage_task.cancel()
        super().close()


class ScanStatisticsView(PTScreen):
    def __init__(self, browser, path):
        super().__init__(browser)
        self.path = path
        self.table = TextArea(read_only=True, scrollbar=True, wrap_lines=False)
        self.focus = self.table
        self.task = None
        self.bind(['escape'], self.close, eager=True)
        self.bind(['v'], self.switch, eager=True)
        self.container = Frame(self.table, title='Scan statistics · v current/total · Esc close',
                               key_bindings=self.keys)
        self.refresh()

    def switch(self):
        self.browser.scan_statistics_scope = ('total' if self.browser.scan_statistics_scope == 'current' else 'current')
        self.refresh()
        self.invalidate()

    def refresh(self):
        record = self.browser.scan_statistics.record(self.path)
        primary = self.browser.scan_statistics_scope
        scopes = [primary] + [scope for scope in ('current', 'session', 'last', 'total') if scope != primary]
        root, separator, selection = self.path.partition('::selection:')
        label = safe_text(self.browser.display_path(root))
        if separator:
            label += ' · folders: ' + ', '.join(safe_text(self.browser.display_path(path))
                                               for path in json.loads(selection))
        lines = [label, f'View: {primary} · adaptive size units · processing time (pauses excluded)',
                 '', f'{"Scope / mode":<24} {"Files":>12} {"Size":>14} {"Time":>12}']
        labels = {'current': 'Current scan', 'session': 'Current session',
                  'last': 'Last session', 'total': 'Total scans'}
        for scope in scopes:
            rows = record[scope]
            for mode, (files, size, seconds) in enumerate(rows, 1):
                label = f'{labels[scope]} / {mode}'
                lines.append(f'{label:<24} {files:>12,d} {scan_size(size):>14} {format_elapsed(seconds):>12}')
            files, size, seconds = (sum(row[column] for row in rows) for column in range(3))
            lines.append(f'{"All modes":<24} {files:>12,d} {scan_size(size):>14} {format_elapsed(seconds):>12}')
            lines.append('')
        text = '\n'.join(lines)
        if text != self.table.text:
            cursor = self.table.buffer.cursor_position
            self.table.text = text
            self.table.buffer.cursor_position = min(cursor, len(text))

    def start(self):
        async def tick():
            while True:
                self.refresh()
                self.invalidate()
                await asyncio.sleep(.3)
        self.task = self.browser.app.create_background_task(tick())

    def close(self):
        if self.task:
            self.task.cancel()
        super().close()


class BookmarksView(PTScreen):
    # INITIALIZE BOOKMARKS VIEW [
    def __init__(self, browser):
        super().__init__(browser)
        self.table = RowsControl(self.rows, changed=self.preview)
        self.horizontal = HorizontalBar(self.table)
        horizontal_keys(self, self.horizontal)
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
                Frame(HSplit([Window(self.table, right_margins=[ScrollbarMargin()]),
                              Window(self.horizontal, height=1)]), title='Bookmarks',
                      width=Dimension(min=4, preferred=0, weight=1)),
                Frame(HSplit([
                    Window(browser.preview_bookmark_control, height=1),
                    ConditionalContainer(browser.video_metadata, filter=Condition(lambda: browser.video_path is not None)),
                    ConditionalContainer(HSplit([
                        ConditionalContainer(browser.video_area, filter=Condition(lambda: not browser.audio_selected())),
                        VSplit([browser.previous_button, browser.play_button, browser.stop_button, browser.next_button, browser.mute_button,
                                Window(FormattedTextControl(lambda: safe_text(browser.video_status)), height=1)], height=1),
                        Window(browser.seek_control, height=1),
                    ]), filter=Condition(browser.video_panel_visible)),
                    self.details,
                ]), title='Quick view · e edit path · Delete remove',
                      width=Dimension(min=4, preferred=0, weight=1)),
            ]),
            self.number, self.path,
            VSplit([Button('Go', handler=self.choose), Button('Save path', handler=self.save),
                    Button('Remove', handler=self.remove), Button('Close', handler=self.close)], height=1),
            Window(FormattedTextControl('Arrows/click: preview · Enter: go · e: edit path · b/Delete: remove · Tab: fields'), height=1),
        ], key_bindings=self.keys)
        self.refresh()
    # INITIALIZE BOOKMARKS VIEW ]
    # START BOOKMARKS VIEW [
    def start(self):
        self.refresh()
    # START BOOKMARKS VIEW ]
    # CLOSE BOOKMARKS VIEW [
    def close(self):
        jumping = self.browser.pending_bookmark is not None
        self.browser.stop_video()
        self.browser.video_epoch += 1
        self.browser.pop(self)
        if not jumping:
            self.browser.show_info(directory=self.original_info_directory)
    # CLOSE BOOKMARKS VIEW ]
    # BUILD DISPLAY ROWS FOR BOOKMARKS VIEW [
    def rows(self):
        result = []
        for i, path in enumerate(self.browser.bookmarks, 1):
            online = os.path.exists(get_real_path(path))
            result.append([('', f'{i}. '), ('class:green' if online else 'class:red', '●'),
                           ('class:literal', ' ' + safe_text(self.browser.display_path(path)))])
        return result
    # BUILD DISPLAY ROWS FOR BOOKMARKS VIEW ]
    # REFRESH BOOKMARKS VIEW [
    def refresh(self):
        self.table.index = max(0, min(self.table.index, len(self.browser.bookmarks) - 1))
        self.list.text = '\n'.join(f'{i}. {safe_text(self.browser.display_path(path))}' for i, path in enumerate(self.browser.bookmarks, 1)) or 'No bookmarks.'
        self.preview()
    # REFRESH BOOKMARKS VIEW ]
    # SHOW THE SELECTED BOOKMARK QUICK VIEW [
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
            self.browser.preview_bookmark_path = None
            self.details.text = 'No bookmarks. Select a file and press b.'
            return
        path = self.browser.bookmarks[self.table.index]
        self.path.text = self.browser.display_path(path)
        self.number.text = ''
        self.browser.preview_bookmark_path = normalize_bookmark_path(path)
        self.browser.preview_status_color = 'red'
        node = self.browser.vfs.get_from_path(path)
        if node is None:
            self.browser.stop_video()
            self.browser.video_epoch += 1
            self.browser.video_path = None
            self.browser.native_preview = None
            self.browser.image_preview_node = None
            self.details.text = safe_text(self.browser.display_path(path)) + '\nUnavailable in VFS. Edit the path or remove this bookmark.'
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
    # SHOW THE SELECTED BOOKMARK QUICK VIEW ]
    # REMOVE THE SELECTED BOOKMARK [
    def remove(self):
        if self.browser.bookmarks:
            self.browser.bookmarks.pop(self.table.index)
            self.browser.save_bookmarks()
            self.refresh()
            self.invalidate()
    # REMOVE THE SELECTED BOOKMARK ]
    # SAVE BOOKMARKS VIEW [
    def save(self):
        path = self.browser.parse_display_path(self.path.text.strip())
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
    # SAVE BOOKMARKS VIEW ]
    # CHOOSE BOOKMARKS VIEW [
    def choose(self):
        index = int(self.number.text) - 1 if self.number.text.isdecimal() else self.table.index
        self.browser.go_bookmark(index)
    # CHOOSE BOOKMARKS VIEW ]
# EDIT BOOKMARK TARGETS AND PREVIEW SELECTED FILES ]
class RemoveDBConfirmView(PTScreen):
    def __init__(self, browser, paths):
        from prompt_toolkit.layout.containers import HorizontalAlign, WindowAlign
        super().__init__(browser)
        self.paths = tuple(paths)
        self.question = f'Remove {len(self.paths)} items from db?'
        cancel = Button('Cancel', handler=self.close)
        remove = Button('Remove', handler=self.confirm)
        self.focus = remove
        self.bind(['escape', 'n'], self.close)
        self.bind(['y'], self.confirm)
        self.bind(['left', 'right', 'tab', 's-tab'], lambda: browser.app.layout.focus(
            cancel if browser.app.layout.has_focus(remove) else remove), eager=True)
        dialog = Frame(Box(HSplit([
            Window(FormattedTextControl(self.question), height=1, width=30, align=WindowAlign.CENTER),
            Window(height=1),
            VSplit([remove, cancel], align=HorizontalAlign.CENTER, height=1, width=30),
        ], width=30), padding=1, width=32), style='fg:#ffffff bg:#cc0000', key_bindings=self.keys,
            modal=True, width=34, height=7)
        self.container = FloatContainer(browser.app.layout.container, floats=[
            Float(content=dialog, width=34, height=7)])

    def confirm(self):
        if not self.browser.screen_stack or self.browser.screen_stack[-1][0] is not self:
            return
        self.close()
        self.browser.trash_paths(self.paths)


class FilenameSearchView(PTScreen):
    """Incremental name search over the visible Files rows."""
    def __init__(self, browser):
        super().__init__(browser)
        # All printable characters belong to the query, including normal shortcuts.
        self.keys = KeyBindings()
        self.search = TextArea(height=1, multiline=False,
                               prompt=lambda: 'No match: ' if self.status else 'Search: ',
                               style='class:literal')
        self.status = ''
        self.search.buffer.on_text_changed += lambda _: self.find()
        self.bind(['escape'], self.close, eager=True)
        self.bind(['enter'], self.apply, eager=True)
        self.bind(['c-s', 'down'], lambda: self.find(1), eager=True)
        self.bind(['up'], lambda: self.find(-1), eager=True)
        self.focus = self.search
        self.field = HSplit([self.search], key_bindings=self.keys, modal=True)
        browser.filename_search = self
        self.container = browser.app.layout.container

    def close(self):
        self.browser.filename_search = None
        super().close()
        self.browser.app.layout.focus(self.browser.control)

    def apply(self):
        query = self.search.text.casefold()
        browser = self.browser
        previous = browser.current_name()
        browser.refresh(previous, update_info=False)
        candidates = []
        for index, row in enumerate(browser.rows):
            name = row['node'].name.casefold()
            if row['name'] == '..' or not query or query not in name:
                continue
            rank = 0 if name == query else 1 if name.startswith(query) else 2
            candidates.append((rank, index))
        if candidates:
            browser.select(min(candidates)[1])
            self.status = ''
        elif query:
            self.status = 'No matching name'
            browser.app.invalidate()
            return
        self.close()
        browser.open()
        browser.app.invalidate()

    def find(self, step=0):
        query = self.search.text.casefold()
        if not query:
            self.status = ''
            self.browser.app.invalidate()
            return
        rows = self.browser.rows
        count = len(rows)
        direction = -1 if step < 0 else 1
        start = self.browser.selected + direction if step else 0
        for offset in range(count):
            index = (start + direction * offset) % count
            row = rows[index]
            if row['name'] != '..' and row['node'].name.casefold().startswith(query):
                self.browser.select(index)
                self.status = ''
                break
        else:
            self.status = 'No matching name'
        self.browser.app.invalidate()


class DriveMappingsView(PTScreen):
    """Inspect effective loaded drive mappings without reloading configuration."""
    def __init__(self, browser):
        super().__init__(browser)
        self.lines = [[('class:header', 'Alias · source prefix → local path · state')]]
        def path_fragment(path):
            return ('class:green class:literal' if path != '0' and os.path.exists(path)
                    else 'class:red class:literal', path)
        def mapping_row(alias, source, local):
            return [('ansicyan bold class:literal', alias),
                    ('', ' · '), path_fragment(source) if source != '—' else ('', source), ('', ' → '),
                    path_fragment(local),
                    ('', ' · disabled' if local == '0' else ' · enabled')]
        represented = set()
        for source, mapping in sorted(prefixes.items()):
            alias, local = mapping['alias'], mapping['local']
            represented.add(alias)
            self.lines.append(mapping_row(alias, source, local))
        for alias, local in sorted(aliases.items()):
            if alias not in represented:
                self.lines.append(mapping_row(alias, '—', local))
        for source in sorted(disabled_prefixes):
            self.lines.append([('class:red class:literal', f'Disabled source prefix: {source}')])
        if len(self.lines) == 1:
            self.lines.append([('', 'No drive mappings loaded from config.sh.')])
        self.lines += [[('', '')],
                       [('ansicyan bold class:literal', '@:'), ('', ' relative paths / current directory → '), path_fragment(browser.startup_path)],
                       [('ansicyan bold class:literal', '~0:/'), ('', ' → '),
                        path_fragment(os.path.expanduser("~")), ('', ' · home directory')],
                       [('ansicyan bold class:literal', ':/'), ('', ' → '), path_fragment('/'), ('', ' · global filesystem root')],
                       [('', 'Read-only loaded configuration. Edit config.sh and restart to change mappings.')]]
        self.table = RowsControl(lambda: self.lines, cache=True)
        self.horizontal = HorizontalBar(self.table)
        self.focus = self.table
        table_bindings(self, self.table)
        horizontal_keys(self, self.horizontal)
        self.bind(['escape', 'f7'], self.close, eager=True)
        self.container = Frame(HSplit([
            Window(self.table, right_margins=[ScrollbarMargin()], wrap_lines=False),
            Window(self.horizontal, height=1),
            Window(FormattedTextControl('F7 / Esc: close · read-only drive mappings'), height=1),
        ]), title='Config · MAP DRIVES', key_bindings=self.keys)


class TrashHelpView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        self.bind(['escape', 'h', 'enter'], self.close, eager=True)
        lines = [
            '[#ff8800]Enter[/#ff8800]: expand/collapse duplicates or jump to file',
            '[#ff8800]Insert[/#ff8800]: select/deselect archive row and move down',
            '[#ff8800]-[/#ff8800]: deselect all',
            '[#ff8800]Delete[/#ff8800]: remove marked archive entries, or cursor entry',
            '[#ff8800]Ctrl+Delete[/#ff8800]: clear ALL archive entries, including hidden',
            '[#ff8800]/[/#ff8800]: search filenames (clear text to show all)',
            'Search: [#ff8800]Enter[/#ff8800] keeps filter, focuses list; [#ff8800]Esc[/#ff8800] clears filter, focuses list',
            'List: [#ff8800]Esc / d[/#ff8800] closes D',
            '[#ff8800]Shift+Left/Right[/#ff8800]: pan names; [#ff8800]Shift+PageUp/Down[/#ff8800]: ends',
            '',
            'Removal is permanent archive metadata only. Disk files stay intact.',
            'Restore is not available. Duplicate rows cannot be marked/deleted.',
            '[#ff8800]Ctrl+D[/#ff8800] in Files resets present files; missing paths enter D.',
            '',
            '[#ff8800]Esc / Enter / h[/#ff8800]: close this help',
        ]
        self.text = '\n'.join(plain_markup(line) for line in lines)
        fragments = []
        for index, line in enumerate(markup_lines(lines)):
            if index:
                fragments.append(('', '\n'))
            fragments.extend(line)
        self.focus = FormattedTextControl(fragments, focusable=True)
        dialog = Frame(Box(Window(self.focus, wrap_lines=True), padding=1),
            title='D · quick help', key_bindings=self.keys, modal=True,
            width=72, height=19)
        self.container = FloatContainer(browser.app.layout.container, floats=[
            Float(content=dialog, width=72, height=19)])


class DBTrashView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        self.records = dict(sorted(browser.db_trash.records().items(),
            key=lambda item: (item[1]['trashed_at'], item[0]), reverse=True))
        self.marked = set()
        self.expanded = {}
        self.duplicate_status = {}
        self.rows_revision = 0
        self.rows_key = None
        self.cached_rows = None
        self.items = []
        self.search = TextArea(height=1, multiline=False, prompt='/ Search: ')
        self.search.buffer.on_text_changed += lambda _: self.filter_entries()
        self.table = RowsControl(self.rows, cache=True)
        self.horizontal = HorizontalBar(self.table)
        self.focus = self.table
        horizontal_keys(self, self.horizontal)
        self.bind(['escape'], self.escape, eager=True)
        self.bind(['d'], self.close, eager=True, filter=~has_focus(self.search))
        self.bind(['h'], lambda: browser.push(TrashHelpView(browser)), eager=True,
                  filter=~has_focus(self.search))
        self.bind(['/'], self.search_focus, eager=True, filter=~has_focus(self.search))
        self.bind(['insert'], self.toggle_mark, eager=True, filter=has_focus(self.table))
        self.bind(['-'], self.clear_marks, eager=True, filter=has_focus(self.table))
        self.bind(['delete'], self.remove_marked, eager=True, filter=has_focus(self.table))
        self.bind(['c-delete'], lambda: self.remove_marked(all_entries=True), eager=True,
                  filter=has_focus(self.table))
        for key, delta in [('up', -1), ('down', 1), ('pageup', -10), ('pagedown', 10)]:
            self.bind([key], lambda delta=delta: self.table.move(delta), filter=has_focus(self.search))
        self.bind(['enter'], lambda: self.browser.app.layout.focus(self.table),
                  eager=True, filter=has_focus(self.search))
        self.bind(['enter'], self.choose, eager=True, filter=has_focus(self.table))
        table_bindings(self, self.table)
        self.container = Frame(HSplit([
            Window(FormattedTextControl(self.header), height=1),
            Window(self.table, right_margins=[ScrollbarMargin()], wrap_lines=False),
            Window(self.horizontal, height=1),
            self.search,
            Window(FormattedTextControl('h: help · Enter: expand/collapse or jump · / search · Esc: browse/close'), height=1),
        ]), title='D · database trash · disk files kept', key_bindings=self.keys)

    def toggle_mark(self):
        self.rows()
        if self.items:
            kind, path = self.items[min(self.table.index, len(self.items) - 1)]
            if kind == 'trash':
                self.marked.symmetric_difference_update((path,))
                self.rows_revision += 1
                self.table.move(1)
                self.invalidate()

    def clear_marks(self):
        self.marked.clear()
        self.rows_revision += 1
        self.invalidate()

    def remove_marked(self, *, all_entries=False):
        self.rows()
        paths = set(self.marked)
        if not all_entries and not paths and self.items:
            kind, path = self.items[min(self.table.index, len(self.items) - 1)]
            if kind == 'trash':
                paths.add(path)
        if not all_entries and not paths:
            return
        try:
            count = self.browser.db_trash.remove(None if all_entries else paths)
        except (ValueError, OSError, sqlite3.Error) as exc:
            self.browser.show_notification(str(exc), error=True)
            return
        remaining = self.browser.db_trash.records()
        self.records = dict(sorted(remaining.items(),
            key=lambda item: (item[1]['trashed_at'], item[0]), reverse=True))
        self.marked.intersection_update(self.records)
        self.expanded = {key: value for key, value in self.expanded.items() if key in self.records}
        self.browser.trashed_roots = self.browser.db_trash.roots()
        for scanner in self.browser.scanners:
            scanner.controls.trashed_paths = self.browser.trashed_roots
        self.rows_revision += 1
        self.rows()
        self.table.index = max(0, min(self.table.index, len(self.items) - 1))
        self.invalidate()
        self.browser.show_notification(f'Removed {count} entries from D; disk files kept')

    def header(self):
        self.rows()
        return fit('Deleted (UTC)', 19) + '  ' + fit('Path', self.path_width) + '  ' + 'Size Hash'.rjust(self.hash_width)

    def search_focus(self):
        self.browser.app.layout.focus(self.search)
        self.search.buffer.cursor_position = len(self.search.text)

    def escape(self):
        if self.browser.app.layout.has_focus(self.search):
            self.search.text = ''
            self.browser.app.layout.focus(self.table)
        else:
            self.close()

    def filter_entries(self):
        self.table.index = 0
        self.table.pan = 0
        self.invalidate()

    @staticmethod
    def summary(node):
        digest = (node.get('info') or {}).get('hashinfo') or ''
        # Catalog identities are algorithm:digest:size; never take the size suffix.
        parts = digest.split(':')
        tail = (parts[-2] if len(parts) >= 3 else parts[-1])[-6:]
        size = format_size(node.get('size', 0), 0).strip()
        return size + (' ' + tail if tail else '')

    @staticmethod
    def timestamp(value):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return safe_text(value)

    def rows(self):
        key = (self.table.width, self.search.text, self.rows_revision,
               self.browser.show_path_prefixes)
        if key == self.rows_key:
            return self.cached_rows
        entries = []
        self.items = []
        query = self.search.text.casefold()
        for path, value in self.records.items():
            own_match = query in path.rstrip('/').rsplit('/', 1)[-1].casefold()
            duplicates = [candidate for candidate in self.expanded.get(path, [])
                          if own_match or query in candidate.rstrip('/').rsplit('/', 1)[-1].casefold()]
            if not own_match and not duplicates:
                continue
            digest = self.summary(value['node'])
            entries.append((self.timestamp(value['trashed_at']), 'D ' + safe_text(self.browser.display_path(path)), digest, False))
            self.items.append(('trash', path))
            if path in self.expanded:
                for duplicate in duplicates:
                    entries.append(('', '    ↳ ' + safe_text(self.browser.display_path(duplicate)), digest, True))
                    self.items.append(('duplicate', duplicate))
                if not self.expanded[path]:
                    entries.append(('', '    No active duplicates.', '', True))
                    self.items.append(('message', path))
        hash_width = max([9] + [get_cwidth(str(entry[2])) for entry in entries])
        path_width = max(4, self.table.width - 23 - hash_width)
        self.path_width, self.hash_width = path_width, hash_width
        self.cached_rows = []
        for index, (stamp, path, digest, duplicate) in enumerate(entries):
            row = [('', fit(stamp, 19) + '  ')]
            kind, target = self.items[index]
            if kind == 'duplicate':
                prefix = [('class:literal', '    ↳ '),
                          (self.duplicate_status.get(target, 'class:red'), '● ')]
                available = path_width
                for style, text in prefix:
                    clipped = fit(text, max(0, min(get_cwidth(text), available)))
                    row.append((style, clipped))
                    available -= get_cwidth(clipped)
                row += highlighted(fit(path[6:], max(0, available)), self.search.text, 'class:literal')
            else:
                row += highlighted(fit(path, path_width), self.search.text,
                                   'class:literal' if duplicate else ('class:literal fg:#ffd700' if target in self.marked else 'class:literal fg:#ff5555'))
            row.append(('', '  ' + str(digest).rjust(hash_width)))
            self.cached_rows.append(row)
        self.rows_key = key
        return self.cached_rows

    def choose(self):
        self.rows()
        if not self.items:
            return
        kind, path = self.items[min(self.table.index, len(self.items) - 1)]
        if kind == 'duplicate':
            if self.browser.vfs.get_from_path(path) is None:
                self.browser.show_notification('Duplicate is no longer in the catalog', error=True)
                return
            self.browser.pending_bookmark = path
            self.browser.finish_bookmark()
        elif kind == 'trash':
            if path in self.expanded:
                del self.expanded[path]
            else:
                digest = (self.records[path]['node'].get('info') or {}).get('hashinfo')
                self.expanded[path] = sorted({self.browser.vfs.decode_source_path(candidate)
                    for candidate in self.browser.vfs.get_hash_dups(digest)
                    if not self.browser.is_trashed(self.browser.vfs.decode_source_path(candidate))})
                for duplicate in self.expanded[path]:
                    self.duplicate_status[duplicate] = ('class:green' if get_stat_info(duplicate).get('exists')
                                                        else 'class:red')
            self.rows_revision += 1
            self.invalidate()


class BlacklistView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        self.table = RowsControl(self.rows)
        self.horizontal = HorizontalBar(self.table)
        self.focus = self.table
        horizontal_keys(self, self.horizontal)
        table_bindings(self, self.table)
        self.bind(['escape', 'L'], self.close, eager=True)
        self.bind(['enter'], self.choose, eager=True)
        self.bind(['delete'], self.remove, eager=True)
        self.container = HSplit([
            Frame(HSplit([Window(self.table, right_margins=[ScrollbarMargin()]),
                          Window(self.horizontal, height=1)]), title='u blacklist'),
            Window(FormattedTextControl('Enter: open directory · Delete: remove exclusion · Esc: close'), height=1),
        ], key_bindings=self.keys)

    def rows(self):
        color = 'fg:#ff5555' if self.browser.blacklist_enabled else 'fg:#00bb55'
        return [[(color, '! '), ('class:literal', safe_text(self.browser.display_path(path)))]
                for path in sorted(self.browser.blacklist)]

    def selected_path(self):
        paths = sorted(self.browser.blacklist)
        return paths[min(self.table.index, len(paths) - 1)] if paths else None

    def remove(self):
        path = self.selected_path()
        if path is None:
            return
        self.browser.blacklist.remove(path)
        self.browser.save_blacklist()
        self.browser.apply_blacklist()
        self.table.index = max(0, min(self.table.index, len(self.browser.blacklist) - 1))
        self.invalidate()

    def choose(self):
        path = self.selected_path()
        if path is None:
            return
        node = self.browser.vfs.get_from_path(path)
        if node is None or not node.is_dir:
            return
        self.close()
        self.browser.pending_bookmark = path
        self.browser.finish_bookmark()

# BROWSE PERSISTENT ACTION HISTORY [
class HistoryView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        self.online = None
        self.signature = None
        self.presence = {}
        self.pending = deque()
        self.requested = set()
        self.indexed = None
        self.async_presence = False
        self.presence_task = None
        self.presence_epoch = 0
        self.checking_paths = 0
        self.preview_visible = False
        self.preview_task = None
        self.preview_epoch = 0
        self.preview_lexer = InfoLexer()
        self.preview = TextArea(read_only=True, scrollbar=True, lexer=self.preview_lexer)
        self.table = HistoryRowsControl(self.rows, changed=self.update_preview)
        self.table_window = Window(self.table, right_margins=[ScrollbarMargin()])
        self.horizontal = HorizontalBar(self.table)
        horizontal_keys(self, self.horizontal)
        self.focus = self.table
        self.bind(['escape', 'l'], self.close, eager=True)
        self.bind(['delete'], self.remove, eager=True)
        self.bind(['s-delete'], self.clear, eager=True)
        self.bind(['enter'], self.choose, eager=True)
        self.bind(['t'], self.toggle, eager=True)
        self.bind(['f5'], self.refresh_presence, eager=True)
        self.bind(['v'], self.toggle_preview, eager=True)
        table_bindings(self, self.table)
        self.container = HSplit([
            VSplit([Frame(HSplit([Window(FormattedTextControl('#  State  Started                 Action / Path'), height=1, style='class:table-header'),
                          self.table_window,
                          Window(self.horizontal, height=1)]), title=lambda: 'Action history' + (' · Save error: ' + safe_text(browser.action_history.error) if browser.action_history.error else '')),
                    ConditionalContainer(Frame(self.preview, title='Preview · v:hide'),
                                         filter=Condition(lambda: self.preview_visible))]),
            Window(FormattedTextControl(lambda: ('All' if self.online is None else 'Online' if self.online else 'Offline')
                + f' · {len(self.rows()):,} actions · {len(self.pending) + self.checking_paths:,} paths pending · #: newest first'), height=1),
            Window(FormattedTextControl('Enter:go · Del:remove · Shift+Del:clear · t:filter · v:preview · F5:refresh · Esc:close'), height=1),
        ], key_bindings=self.keys)

    def toggle_preview(self):
        self.preview_visible = not self.preview_visible
        self.update_preview()
        self.invalidate()

    def update_preview(self):
        self.preview_epoch += 1
        if self.preview_task:
            self.preview_task.cancel()
        if not self.preview_visible or not self.browser.app.is_running:
            return
        entry = self.selected_entry()
        self.preview_lexer.image_lines = {}
        self.preview.text = 'Loading…' if entry else '(empty)'
        if entry is None:
            return
        entry = dict(entry)
        epoch = self.preview_epoch
        async def load():
            # Debounce cursor drags; never read source files in the render path.
            await asyncio.sleep(.12)
            text, images = await background_call(self.read_preview, entry)
            if epoch == self.preview_epoch and self.preview_visible:
                self.preview_lexer.image_lines = images
                self.preview.text = text
                self.invalidate()
        self.preview_task = self.browser.app.create_background_task(load())

    @staticmethod
    def read_preview(entry):
        path = Path(get_real_path(entry['path']))
        lines = [safe_text(entry['path']), safe_text(entry['action']),
                 'Started: ' + safe_text(entry['started']),
                 'Last known: ' + safe_text(entry['last_known'])]
        for key in ('position', 'duration'):
            if key in entry:
                lines.append(f'{key.title()}: {entry[key]} s')
        images = {}
        try:
            info = path.stat()
            lines.extend(['Size: ' + format_size(info.st_size, 0).strip(), ''])
            import stat
            if stat.S_ISDIR(info.st_mode):
                lines.append('Directory')
                with os.scandir(path) as children:
                    for index, child in enumerate(children):
                        if index >= 100:
                            lines.append('… (first 100 entries)')
                            break
                        lines.append(safe_text(child.name))
            elif not stat.S_ISREG(info.st_mode):
                lines.append('Special file (contents not read)')
            elif path.suffix.lower() in THUMBNAIL_SUFFIXES:
                from PIL import Image
                from term_image.image import BlockImage
                from prompt_toolkit.formatted_text import ANSI, to_formatted_text
                record = thumbnail(path, entry['path'], 128)
                with Image.open(record['path']) as image:
                    image = image.convert('RGB')
                    with BlockImage(image, width=32, height=12) as preview:
                        art = str(preview)
                for line in art.splitlines():
                    images[len(lines)] = to_formatted_text(ANSI(line))
                    lines.append(' ')
            else:
                with path.open('rb') as source:
                    data = source.read(16385)
                if b'\x00' in data:
                    lines.append('Binary file')
                else:
                    lines.extend(safe_text(line) for line in data[:16384].decode('utf-8', errors='replace').splitlines())
                    if len(data) > 16384:
                        lines.append('… (first 16 KiB)')
        except (OSError, ValueError) as error:
            lines.append('Preview unavailable: ' + safe_text(str(error)))
        return '\n'.join(lines), images

    def install_drag(self, app):
        if not self.table.dragging:
            return
        screen = app.renderer._last_screen
        position = screen.visible_windows_to_write_positions.get(self.table_window) if screen else None
        if not position or not self.table_window.render_info:
            return
        def drag(event):
            if event.event_type not in (MouseEventType.MOUSE_MOVE, MouseEventType.MOUSE_UP):
                return NotImplemented
            if event.button != MouseButton.LEFT:
                self.table.dragging = False
                return
            y = event.position.y - position.ypos
            scroll = self.table_window.vertical_scroll
            self.table.select_row(scroll + y)
            if event.event_type == MouseEventType.MOUSE_UP:
                self.table.dragging = False
            app.invalidate()
        size = app.output.get_size()
        app.renderer.mouse_handlers.set_mouse_handler_for_range(
            x_min=0, x_max=size.columns, y_min=0, y_max=size.rows, handler=drag)

    def prepare(self):
        history = self.browser.action_history
        signature = history.revision, len(history.entries)
        if signature != self.signature:
            self.indexed = HistoryIndex(history.entries, self.presence, self.online, safe_text)
            self.lazy_rows = HistoryRows(self.indexed, self.request_presence, safe_text)
            self.signature = signature
            if self.online is not None:
                for path in self.indexed.by_path:
                    self.request_presence(path)

    def entries(self):
        self.prepare()
        if not self.async_presence:
            self.resolve_sync()
        return [self.indexed.entries[i] for i in self.indexed.visible]

    def present(self, entry):
        return os.path.exists(get_real_path(entry['path']))

    def request_presence(self, path):
        if path not in self.presence and path not in self.requested:
            self.pending.append(path)
            self.requested.add(path)

    def resolve_sync(self):
        values = {path: os.path.exists(get_real_path(path)) for path in self.indexed.by_path
                  if path not in self.presence}
        if values:
            self.indexed.availability(values)

    def rows(self):
        self.prepare()
        if not self.async_presence:
            self.resolve_sync()
        return self.lazy_rows

    def start(self):
        if not self.browser.app.is_running:
            return
        self.async_presence = True
        async def check():
            while True:
                self.prepare()
                if self.pending:
                    paths = [self.pending.popleft() for _ in range(min(64, len(self.pending)))]
                    epoch = self.presence_epoch
                    self.checking_paths = len(paths)
                    self.invalidate()
                    values = await background_call(lambda: {path: os.path.exists(get_real_path(path)) for path in paths})
                    self.checking_paths = 0
                    if epoch != self.presence_epoch:
                        continue
                    visible = self.indexed.visible
                    selected = visible[min(self.table.index, len(visible) - 1)] if visible else None
                    self.indexed.availability(values)
                    if selected is not None and selected in self.indexed.included:
                        self.table.index = bisect_left(self.indexed.visible, selected)
                    else:
                        self.table.index = min(self.table.index, max(0, len(self.lazy_rows) - 1))
                        self.update_preview()
                    self.invalidate()
                await asyncio.sleep(.05)
        self.presence_task = self.browser.app.create_background_task(check())

    def close(self):
        if self.presence_task:
            self.presence_task.cancel()
        self.preview_epoch += 1
        if self.preview_task:
            self.preview_task.cancel()
        self.table.dragging = False
        super().close()

    def remove(self):
        entry = self.selected_entry()
        if entry:
            self.browser.action_history.remove(entry)
        self.table.index = max(0, min(self.table.index, len(self.rows())-1))
        self.update_preview()
        self.invalidate()

    def selected_entry(self):
        rows = self.rows()
        if rows:
            index = self.indexed.visible[min(self.table.index, len(rows) - 1)]
            return self.indexed.entries[index]
        return None

    def refresh_presence(self):
        self.presence_epoch += 1
        self.presence.clear()
        self.pending.clear()
        self.requested.clear()
        self.signature = None
        self.prepare()
        self.table.index = 0
        self.update_preview()
        self.invalidate()

    def clear(self):
        self.browser.action_history.clear()
        self.table.index = 0
        self.update_preview()
        self.invalidate()

    def toggle(self):
        self.online = not self.online if self.online is not None else True
        self.prepare()
        self.indexed.set_filter(self.online)
        for path in self.indexed.by_path:
            self.request_presence(path)
        self.table.index = 0
        self.update_preview()
        self.invalidate()

    def choose(self):
        entry = self.selected_entry()
        if entry is None:
            return
        path = entry['path']
        self.browser.preview_bookmark_path = normalize_bookmark_path(path)
        self.browser.preview_status_color = 'red'
        node = self.browser.vfs.get_from_path(path)
        if node is None:
            return
        directory = node if node.is_dir else self.browser.vfs.get_from_path(path.rpartition('/')[0] or '/')
        if directory is None:
            return
        self.close()
        self.browser.vfs.cwd = directory
        self.browser.action_history.add('chdir', directory.id)
        self.browser.refresh(None if node.is_dir else node.name)
        self.browser.app.layout.focus(self.browser.control)
# BROWSE PERSISTENT ACTION HISTORY ]
# ENTER A DIRECTORY PATH WITHOUT GLOBAL SHORTCUT INTERCEPTION [
class CommandPathCompleter(Completer):
    """Complete immediate catalog and disk children without recursively scanning."""
    def __init__(self, browser):
        self.browser = browser

    def get_completions(self, document, complete_event):
        return iter(())

    async def get_completions_async(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if text.startswith('cd '):
            text = text[3:].lstrip()
        directory, _, partial = text.rpartition('/')
        parent = directory + '/' if '/' in text else ''
        if not parent and text.startswith(('@:', '~:')):
            parent, partial = '@:/', text[2:]
        if parent.startswith('~') and not parent.startswith('~:'):
            parent = os.path.expanduser(parent)
        path = self.browser.parse_display_path(parent) if parent else self.browser.vfs.pwd()
        if not path.startswith('/'):
            path = os.path.normpath(self.browser.vfs.pwd().rstrip('/') + '/' + path)
        node = self.browser.vfs.get_from_path(path)
        names = {}
        if node is not None and node.is_dir:
            names.update((child.name, child.is_dir)
                         for child in self.browser.vfs.db.get_children(node))

        def disk_children():
            try:
                with os.scandir(get_real_path(path)) as entries:
                    return {entry.name: entry.is_dir() for entry in entries
                            if entry.name.startswith(partial)}
            except OSError:
                return {}
        names.update(await background_call(disk_children))
        for name, is_dir in sorted(names.items(), key=lambda item: (not item[1], item[0])):
            if name.startswith(partial):
                value = name + ('/' if is_dir else '')
                yield Completion(value, start_position=-len(partial), display=safe_text(value))


class PathCommandView(PTScreen):
    def __init__(self, browser):
        super().__init__(browser)
        current = '/'
        self.path = TextArea(text=current, height=1, multiline=False, prompt='/ ', style='class:literal')
        self.path.buffer.cursor_position = len(current)
        self.completer = CommandPathCompleter(browser)
        self.matches = []
        self.suggestion_epoch = 0
        self.suggestions = RowsControl(lambda: [[('class:literal', safe_text(c.text))]
                                               for c in self.matches], selected=self.accept_suggestion)
        self.history_paths = list(dict.fromkeys(e['path'] for e in reversed(browser.action_history.entries)
                                                if e['action'] == 'path command'))
        self.history = RowsControl(lambda: [[('class:literal', safe_text(p))] for p in self.history_paths],
                                   selected=self.accept_history)
        self.message = TextArea(text='↑↓: suggestions · Tab: complete · Ctrl+R: history · Enter: go · Esc: cancel', read_only=True, height=2)
        self.focus = self.path
        self.bind(['escape'], self.close, eager=True)
        self.bind(['enter'], self.submit, eager=True)
        self.bind(['~'], self.home_input, filter=has_focus(self.path), eager=True)
        self.bind(['tab'], self.accept_suggestion, eager=True)
        self.bind(['c-r'], lambda: browser.app.layout.focus(self.history), eager=True)
        self.bind(['up'], lambda: self.suggestions.move(-1), filter=has_focus(self.path))
        self.bind(['down'], lambda: self.suggestions.move(1), filter=has_focus(self.path))
        table_bindings(self, self.suggestions)
        table_bindings(self, self.history)
        self.suggestion_slider = HorizontalBar(self.suggestions)
        self.history_slider = HorizontalBar(self.history)
        horizontal_keys(self, self.suggestion_slider)
        horizontal_keys(self, self.history_slider)
        self.path.buffer.on_text_changed += lambda _: self.update_suggestions()
        self.container = HSplit([Frame(self.path, title='Path command'), VSplit([
            Frame(HSplit([Window(self.suggestions, right_margins=[ScrollbarMargin()]),
                          Window(self.suggestion_slider, height=1)]), title='Paths'),
            Frame(HSplit([Window(self.history, right_margins=[ScrollbarMargin()]),
                          Window(self.history_slider, height=1)]), title='Path history'),
        ]), self.message], key_bindings=self.keys)

    def start(self):
        self.update_suggestions()

    def home_input(self):
        if self.path.text == '/':
            self.path.text = os.path.expanduser('~').rstrip('/') + '/'
            self.path.buffer.cursor_position = len(self.path.text)
            self.update_suggestions()
        else:
            self.path.buffer.insert_text('~')

    def close(self):
        self.suggestion_epoch += 1
        super().close()

    def update_suggestions(self):
        from prompt_toolkit.completion import CompleteEvent
        self.suggestion_epoch += 1
        epoch = self.suggestion_epoch
        self.matches = []
        self.suggestions.index = 0
        async def load():
            # Buffer text events can precede the matching cursor update.
            document = self.path.buffer.document
            matches = [c async for c in self.completer.get_completions_async(document, CompleteEvent())]
            if epoch == self.suggestion_epoch:
                self.matches = matches
                self.invalidate()
        self.suggestion_task = self.browser.app.create_background_task(load())
        self.invalidate()

    def accept_suggestion(self):
        if not self.matches:
            task = getattr(self, 'suggestion_task', None)
            epoch = self.suggestion_epoch
            if task is not None and not task.done():
                async def accept_when_ready():
                    await asyncio.shield(task)
                    if epoch == self.suggestion_epoch and self.matches:
                        self.accept_suggestion()
                self.browser.app.create_background_task(accept_when_ready())
            return
        if self.matches:
            completion = self.matches[min(self.suggestions.index, len(self.matches) - 1)]
            buffer = self.path.buffer
            buffer.delete_before_cursor(-completion.start_position)
            buffer.insert_text(completion.text)
            self.browser.app.layout.focus(self.path)

    def accept_history(self):
        if self.history_paths:
            self.path.text = self.history_paths[min(self.history.index, len(self.history_paths) - 1)]
            self.path.buffer.cursor_position = len(self.path.text)
            self.browser.app.layout.focus(self.path)
            self.update_suggestions()

    def submit(self):
        if self.browser.app.layout.has_focus(self.history):
            self.accept_history()
        elif self.browser.app.layout.has_focus(self.suggestions):
            self.accept_suggestion()
            return
        if not self.browser.go_path(self.path.text):
            self.message.text = 'Path unavailable: ' + safe_text(self.path.text)
            self.invalidate()
# ENTER A DIRECTORY PATH WITHOUT GLOBAL SHORTCUT INTERCEPTION ]
# DISPLAY SCROLLABLE CONTEXT HELP [
class HelpView(PTScreen):
    def __init__(self, browser, title, lines):
        super().__init__(browser)
        self.origin_control = browser.app.layout.current_control
        self.entries = help_entries(lines, plain_markup)
        self.query = ''
        self.index = 0
        self.filtered = list(self.entries)
        self.search = TextArea(height=1, multiline=False, prompt='/ Search: ')
        self.text = TextArea(text=plain_markup('\n'.join(lines)), read_only=True,
                             scrollbar=True, wrap_lines=True)
        self.bind(['tab'], lambda: browser.app.layout.focus_next())
        self.bind(['s-tab'], lambda: browser.app.layout.focus_previous())
        if not self.entries:
            self.focus = self.text
            self.bind(['h', 'escape'], self.close, eager=True)
            self.container = HSplit([Frame(self.text, title=title, style='class:info-pane'),
                                      Button('Close', handler=self.close)], key_bindings=self.keys)
            return
        self.grid = HelpIndexControl(self)
        self.window = Window(self.grid, right_margins=[ScrollbarMargin()], always_hide_cursor=True,
                             height=Dimension(min=3, weight=3))
        self.text.lexer = HelpSearchLexer(self)
        self.text.window.height = Dimension(min=2, preferred=5, max=7)
        self.focus = self.grid
        self.bind(['/'], self.search_focus, eager=True, filter=~has_focus(self.search))
        self.bind(['h'], self.close, eager=True, filter=~has_focus(self.search))
        self.bind(['escape'], self.escape, eager=True)
        for key, delta in [('up', -3), ('down', 3)]:
            self.bind([key], lambda delta=delta: self.move(delta),
                      filter=has_focus(self.grid) | has_focus(self.search))
        self.bind(['left'], lambda: self.move_column(-1), filter=has_focus(self.grid))
        self.bind(['right'], lambda: self.move_column(1), filter=has_focus(self.grid))
        self.bind(['home'], lambda: self.select(0), filter=has_focus(self.grid))
        self.bind(['end'], lambda: self.select(len(self.filtered) - 1), filter=has_focus(self.grid))
        browsing = has_focus(self.grid) | has_focus(self.search) | has_focus(self.text)
        self.bind(['pageup'], lambda: self.column_endpoint(False), filter=browsing)
        self.bind(['pagedown'], lambda: self.column_endpoint(True), filter=browsing)
        self.bind(['enter'], self.apply_selected, filter=browsing, eager=True)
        self.search.buffer.on_text_changed += lambda _: self.filter_entries()
        self.container = HSplit([
            Window(FormattedTextControl(title + ' · / search · Esc close'), height=1, style='class:header'),
            self.window,
            Frame(self.text, title='Description', style='class:info-pane'),
            self.search,
            VSplit([Window(FormattedTextControl(lambda: f'{len(self.filtered)}/{len(self.entries)} entries · Enter: run · Esc: close'), height=1),
                    Button('Close', width=7, handler=self.close)], height=1),
        ], key_bindings=self.keys)
        self.preview()

    def apply_selected(self):
        if not self.filtered:
            return
        entry = self.filtered[self.index]
        key = shortcut_key(entry.key)

        def applied():
            if not self.browser.app.is_done:
                self.browser.show_notification(f'Applied key {entry.key}: {entry.short}')

        if entry.local:
            if entry.key == 'Enter':
                self.browser.app.layout.focus(self.grid)
                applied()
                return
            if entry.key == '/':
                self.search_focus()
                applied()
                return
            self.browser.app.layout.focus(self.grid)
        elif key is not None or entry.key == '🔊/🔇':
            self.close()
            if self.browser.screen_stack:
                context = self.browser.screen_stack[-1][0]
                if isinstance(context, ScannerView):
                    if entry.key == 'Enter':
                        focus = (context.byte_limit if self.origin_control is context.byte_limit.control
                                 else context.limit)
                    elif entry.key in ('Shift+Left', 'Shift+Right', 'Shift+Home', 'Shift+End',
                                       'Shift+PageUp', 'Shift+PageDown'):
                        focus = context.details
                    else:
                        focus = context.grid
                    self.browser.app.layout.focus(focus)
            else:
                self.browser.app.layout.focus(self.browser.control)
            if entry.key == '🔊/🔇':
                self.browser.toggle_mute()
                applied()
                return
        else:
            return
        # Use the original binding/filter dispatch rather than duplicating actions.
        self.browser.app.key_processor.feed(KeyPress(key), first=True)
        asyncio.get_running_loop().call_soon(applied)

    def search_focus(self):
        self.browser.app.layout.focus(self.search)
        self.search.buffer.cursor_position = len(self.search.text)

    def escape(self):
        if self.browser.app.layout.has_focus(self.search):
            self.browser.app.layout.focus(self.grid)
        else:
            self.close()

    def filter_entries(self):
        self.query = self.search.text
        query = self.query.casefold()
        self.filtered = [entry for entry in self.entries if query in
                         (entry.section + ' ' + entry.key + ' ' + entry.short + ' ' + entry.description).casefold()]
        self.index = 0
        self.window.vertical_scroll = 0
        self.preview()
        self.invalidate()

    def select(self, index):
        self.browser.note_cursor_motion()
        _, positions = self.grid.layout_rows()
        previous_column = positions.get(self.index, (1, 0))[1]
        self.index = max(0, min(index, len(self.filtered) - 1))
        y, column = positions.get(self.index, (1, 0))
        if self.index == 0 or (column > previous_column and y <= self.grid.column_height):
            self.window.vertical_scroll = 0
        self.preview()
        self.invalidate()

    def move(self, delta):
        if not self.filtered:
            return
        # Vertical movement follows reading order across column ends.
        step = delta // 3 if abs(delta) >= 3 else delta
        target = self.index + step
        self.select(0 if target >= len(self.filtered) else
                    len(self.filtered) - 1 if target < 0 else target)

    def move_column(self, delta):
        _, positions = self.grid.layout_rows()
        if not positions:
            return
        row, column = positions.get(self.index, next(iter(positions.values())))
        columns = sorted({col for _, col in positions.values()})
        target = columns[(columns.index(column) + delta) % len(columns)]
        candidates = (index for index, (_, col) in positions.items() if col == target)
        closest = min(candidates, key=lambda index: (abs(positions[index][0] - row), positions[index][0]))
        self.select(closest)

    def column_endpoint(self, last):
        _, positions = self.grid.layout_rows()
        if not positions:
            return
        column = positions.get(self.index, next(iter(positions.values())))[1]
        candidates = [index for index, (_, col) in positions.items() if col == column]
        self.select(candidates[-1] if last else candidates[0])

    def preview(self):
        self.text.text = self.filtered[self.index].description if self.filtered else 'No shortcuts match this search.'
        match = re.search(re.escape(self.query), self.text.text, re.I) if self.query else None
        self.text.buffer.cursor_position = match.start() if match else 0

# DISPLAY SCROLLABLE CONTEXT HELP ]
# VIRTUAL TABLE WITH COLORED FRAGMENTS AND PERSISTENT HORIZONTAL PAN [
class RowsControl(UIControl):
    """Virtual table with colored fragments and persistent horizontal pan."""
    # INITIALIZE ROWS CONTROL [
    def __init__(self, rows, changed=None, selected=None, resized=None, cache=False):
        self.get_rows = rows
        self.cache = cache
        self._width_rows = None
        self._row_width = 0
        self.changed = changed or (lambda: None)
        self.on_selected = selected
        self.on_resize = resized
        self.index = 0
        self.pan = 0
        self.width = 1
        self.height = 1
    # INITIALIZE ROWS CONTROL ]
    # CHECK FOCUSABLE FOR ROWS CONTROL [
    def is_focusable(self):
        return True
    # CHECK FOCUSABLE FOR ROWS CONTROL ]
    # CREATE CONTENT FOR ROWS CONTROL [
    def create_content(self, width, height):
        if (width, height) != (self.width, self.height):
            self.width, self.height = width, height
            if self.on_resize:
                self.on_resize()
        rows = self.get_rows()
        self.index = max(0, min(self.index, len(rows) - 1))
        self.pan = max(0, min(self.pan, self.maximum_pan()))

        # FORMAT ONE VISIBLE DISPLAY ROW [
        def line(index):
            fragments = rows[index] if rows else [('', '(empty)')]
            result, offset = [], 0
            for style, text in [*fragments, ('', ' ')]:
                if self.cache and offset >= self.pan + self.width:
                    break
                for char in (text if self.cache else safe_text(text)):
                    if self.cache and offset >= self.pan + self.width:
                        break
                    cells = get_cwidth(char)
                    if offset >= self.pan:
                        result.append((('class:selected ' if index == self.index else '') + style, char))
                    elif offset + cells > self.pan:
                        result.append(('', ' '))
                    offset += cells
            return result
        # FORMAT ONE VISIBLE DISPLAY ROW ]
        return UIContent(get_line=line, line_count=max(1, len(rows)),
                         cursor_position=Point(x=0, y=self.index), show_cursor=False)
    # CREATE CONTENT FOR ROWS CONTROL ]
    # MOVE ROWS CONTROL [
    def maximum_pan(self):
        rows = self.get_rows()
        if not self.cache or rows is not self._width_rows:
            self._row_width = max((sum(get_cwidth(part[1]) for part in row)
                                   for row in rows), default=0)
            self._width_rows = rows
        return max(0, self._row_width + 1 - self.width)

    def move(self, delta):
        rows = self.get_rows()
        self.index = max(0, min(max(0, len(rows) - 1), self.index + delta))
        self.changed()
    # MOVE ROWS CONTROL ]
    # MOUSE HANDLER FOR ROWS CONTROL [
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
    # MOUSE HANDLER FOR ROWS CONTROL ]
# VIRTUAL TABLE WITH COLORED FRAGMENTS AND PERSISTENT HORIZONTAL PAN ]
class HistoryRowsControl(RowsControl):
    dragging = False

    def select_row(self, index):
        index = max(0, min(max(0, len(self.get_rows()) - 1), index))
        if index != self.index:
            self.index = index
            self.changed()

    def mouse_handler(self, event):
        if event.event_type == MouseEventType.MOUSE_DOWN and event.button == MouseButton.LEFT:
            self.dragging = True
            get_app().layout.focus(self)
        elif event.event_type == MouseEventType.MOUSE_MOVE:
            if not self.dragging:
                return NotImplemented
            if event.button != MouseButton.LEFT:
                self.dragging = False
                return NotImplemented
        elif event.event_type == MouseEventType.MOUSE_UP and event.button == MouseButton.LEFT:
            self.dragging = False
        else:
            return super().mouse_handler(event)
        self.select_row(event.position.y)
        get_app().invalidate()

    def maximum_pan(self):
        rows = self.get_rows()
        if isinstance(rows, HistoryRows):
            return max(0, rows.maximum_width + 1 - self.width)
        return super().maximum_pan()


# TABLE BINDINGS FOR THE DRIVE-TUI WORKFLOW [
def table_bindings(screen, control):
    focused = has_focus(control)
    for key, delta in [('up', -1), ('down', 1), ('pageup', -10), ('pagedown', 10)]:
        screen.bind([key], lambda delta=delta: control.move(delta), filter=focused)
    screen.bind(['home'], lambda: control.move(-len(control.get_rows())), filter=focused)
    screen.bind(['end'], lambda: control.move(len(control.get_rows())), filter=focused)
    screen.bind(['left'], lambda: setattr(control, 'pan', max(0, control.pan - 4)), filter=focused)
    screen.bind(['right'], lambda: setattr(control, 'pan', min(control.maximum_pan(), control.pan + 4)), filter=focused)
# TABLE BINDINGS FOR THE DRIVE-TUI WORKFLOW ]
# KEEP LONG STATUS-FILTER ROWS REACHABLE AT NARROW TERMINAL WIDTHS [
class FilterControl(UIControl):
    """Keep long status-filter rows reachable at narrow terminal widths."""
    # INITIALIZE FILTER CONTROL [
    def __init__(self, screen):
        self.screen = screen
        self.pan = 0
        self.width = 1
        self.fragments = []
    # INITIALIZE FILTER CONTROL ]
    # CHECK FOCUSABLE FOR FILTER CONTROL [
    def is_focusable(self):
        return True
    # CHECK FOCUSABLE FOR FILTER CONTROL ]
    # CREATE CONTENT FOR FILTER CONTROL [
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
    # CREATE CONTENT FOR FILTER CONTROL ]
    # MOUSE HANDLER FOR FILTER CONTROL [
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
    # MOUSE HANDLER FOR FILTER CONTROL ]
# KEEP LONG STATUS-FILTER ROWS REACHABLE AT NARROW TERMINAL WIDTHS ]
# MANAGE HORIZONTAL BAR [
class FilenameViewport:
    """Connect the main filename offset to the shared draggable slider."""
    def __init__(self, browser):
        self.browser = browser

    @property
    def pan(self):
        if self.browser.filename_pan is None:
            return self.maximum_pan() if self.browser.graphics_mode else 0
        return self.browser.filename_pan

    @pan.setter
    def pan(self, value):
        if self.browser.filename_pan is not None or value != self.pan:
            self.browser.filename_pan = value

    def maximum_pan(self):
        return self.browser.filename_maximum()

class HorizontalBar(UIControl):
    # INITIALIZE HORIZONTAL BAR [
    def __init__(self, table):
        self.table = table
        self.width = 1
        self.maximum = 0
        self.dragging = False
    # INITIALIZE HORIZONTAL BAR ]
    # CHECK FOCUSABLE FOR HORIZONTAL BAR [
    def is_focusable(self):
        return True
    # CHECK FOCUSABLE FOR HORIZONTAL BAR ]
    # CREATE CONTENT FOR HORIZONTAL BAR [
    def create_content(self, width, height):
        self.width = max(1, width)
        self.maximum = self.table.maximum_pan()
        self.table.pan = max(0, min(self.table.pan, self.maximum))
        viewport = (self.table.browser.filename_width if isinstance(self.table, FilenameViewport)
                    else self.table.width)
        thumb = (max(1, min(width, round(width * viewport / (viewport + self.maximum))))
                 if self.maximum else width)
        position = round(self.table.pan * (width - thumb) / self.maximum) if self.maximum else 0
        fragments = [('class:scrollbar.background', ' ' * position),
                     ('class:scrollbar.button', ' ' * thumb),
                     ('class:scrollbar.background', ' ' * (width - position - thumb))]
        return UIContent(get_line=lambda _: fragments, line_count=1, show_cursor=False)
    # CREATE CONTENT FOR HORIZONTAL BAR ]
    # MOUSE HANDLER FOR HORIZONTAL BAR [
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
    # MOUSE HANDLER FOR HORIZONTAL BAR ]
# MANAGE HORIZONTAL BAR ]
# HORIZONTAL KEYS FOR THE DRIVE-TUI WORKFLOW [
def horizontal_keys(screen, bar):
    focused = has_focus(bar)
    screen.bind(['left'], lambda: setattr(bar.table, 'pan', max(0, bar.table.pan - 4)), filter=focused)
    screen.bind(['right'], lambda: setattr(bar.table, 'pan', min(bar.maximum, bar.table.pan + 4)), filter=focused)
    screen.bind(['home'], lambda: setattr(bar.table, 'pan', 0), filter=focused)
    screen.bind(['end'], lambda: setattr(bar.table, 'pan', bar.maximum), filter=focused)
# HORIZONTAL KEYS FOR THE DRIVE-TUI WORKFLOW ]
# REVIEW EXPORT AND APPLY QUEUED FILE OPERATIONS [
class ActionsView(PTScreen):
    # INITIALIZE ACTIONS VIEW [
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
        self.bind(['c-delete'], self.clear)
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
    # INITIALIZE ACTIONS VIEW ]
    # BUILD DISPLAY ROWS FOR ACTIONS VIEW [
    def rows(self):
        return self.cached_rows
    # BUILD DISPLAY ROWS FOR ACTIONS VIEW ]
    # REFRESH ROWS FOR ACTIONS VIEW [
    def refresh_rows(self):
        result = []
        for op, path in self.browser.actions:
            exists = get_stat_info(path).get('exists')
            result.append([('', f'{op:<10} '), ('class:green' if exists else 'class:red', '●'),
                           ('class:literal', ' ' + safe_text(self.browser.display_path(path)))])
        self.cached_rows = result
    # REFRESH ROWS FOR ACTIONS VIEW ]
    # CLEAR ACTIONS VIEW [
    def clear(self):
        self.browser.actions.clear()
        self.refresh_rows()
        self.table.index = 0
        self.invalidate()
    # CLEAR ACTIONS VIEW ]
    # EXPORT ACTIONS VIEW [
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
    # EXPORT ACTIONS VIEW ]
    # APPLY ACTIONS VIEW [
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
        self.browser.refresh(self.browser.current_name(), update_info=False)
        if not pending:
            self.close()
        else:
            self.message += f' · Removed {removed}; {len(pending)} remain'
        self.invalidate()
    # APPLY ACTIONS VIEW ]
# REVIEW EXPORT AND APPLY QUEUED FILE OPERATIONS ]
# DEFINE SCAN STATE SYMBOLS COLORS AND LABELS [
def scan_activity_mode(scanner):
    """Prefer the running worker stage over enabled-mode fallback."""
    mode = getattr(getattr(scanner, 'engine', None), 'current_mode', 0)
    if not mode:
        modes = getattr(getattr(scanner, 'controls', None), 'modes', ())
        mode = next((index for index, enabled in enumerate(modes, 1) if enabled), 0)
    return mode


def scan_activity_frame(scanner, now):
    """Use circular rotation for Heavy and line rotation for other stages."""
    mode = scan_activity_mode(scanner)
    frames = ('◐', '◓', '◑', '◒') if mode == 3 else ('\\', '|', '/', '-')
    return frames[int(now * 8) % len(frames)]


SCAN_STATES = {
    'modified': ('M', '#ff8800', 'modified'),
    'missing': ('U', '#ff0000', 'not found'),
    'new': ('U', '#ffffff', 'undefined / new'),
    'unknown': ('?', '#ffffff', 'unverified'),
    'verified': ('●', '#98e024', 'verified'),
    'directory': ('D', '#ffffff', 'directories'),
    'empty': ('·', '#98e024', 'empty directories'),
}
# DEFINE SCAN STATE SYMBOLS COLORS AND LABELS ]
# CUSTOM MAP RENDERER: CACHED CELLS BECOME COMPACT RUNS OF EQUAL STYLE [
class BucketRowRenderer:
    """Custom map renderer: cached cells become compact runs of equal style.

    Generic FormattedTextControl reparses/hashes its entire supplied text. This
    renderer keeps virtual rows lazy and only compacts rows whose cells change.
    """
    # INITIALIZE BUCKET ROW RENDERER [
    def __init__(self, control):
        self.control = control
        self.rows = OrderedDict()
        self.frame = 0
    # INITIALIZE BUCKET ROW RENDERER ]
    # BUILD COMPACT FILE ROWS WITHOUT THUMBNAILS [
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
    # BUILD COMPACT FILE ROWS WITHOUT THUMBNAILS ]
    # FORMAT ONE VISIBLE DISPLAY ROW [
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
    # FORMAT ONE VISIBLE DISPLAY ROW ]
# CUSTOM MAP RENDERER: CACHED CELLS BECOME COMPACT RUNS OF EQUAL STYLE ]
# BOUNDED VISIBLE-ROW CACHE; BLUE DELTAS INVALIDATE INDIVIDUAL CELLS [
class MapControl(UIControl):
    """Bounded visible-row cache; blue deltas invalidate individual cells."""
    # INITIALIZE MAP CONTROL [
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
    # INITIALIZE MAP CONTROL ]
    # CHECK FOCUSABLE FOR MAP CONTROL [
    def is_focusable(self):
        return True
    # CHECK FOCUSABLE FOR MAP CONTROL ]
    # MARK BUCKETS FOR MAP CONTROL [
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
    # MARK BUCKETS FOR MAP CONTROL ]
    # RENDER CELL FOR MAP CONTROL [
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
                symbol, color = scan_activity_frame(screen, now), '#ffffff'
                deadline = min((int(now * 8) + 1) / 8, bucket.updated + 1)
                background = '#ff0000'
        elif screen.follow_end and index == screen.selected:
            symbol, color = '>', '#ffffff'
        style = f'fg:{color} bg:{background}'
        if index == screen.selected:
            style += ' bg:#00ffff fg:#000000 underline'
        if index < len(screen.model.buckets) and screen.model.buckets[index].blacklisted:
            symbol = '!'
            style = ('bg:#00ffff underline' if index == screen.selected else 'bg:#000000') + ' fg:#ff5555'
            deadline = None
        return (style, symbol), deadline
    # RENDER CELL FOR MAP CONTROL ]
    # DIRTY CELL FOR MAP CONTROL [
    def dirty_cell(self, index):
        if index is not None:
            cached = self.row_cache.get(index // self.columns)
            if cached is not None:
                cached[2].add(index % self.columns)
    # DIRTY CELL FOR MAP CONTROL ]
    # CREATE CONTENT FOR MAP CONTROL [
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
        # FORMAT ONE VISIBLE DISPLAY ROW [
        def line(row):
            return self.renderer.line(row, now, expert_mode, frame)
        # FORMAT ONE VISIBLE DISPLAY ROW ]

        return UIContent(get_line=line,
                         line_count=max(1, math.ceil((count + int(screen.follow_end)) / self.columns)),
                         cursor_position=Point(x=screen.selected % self.columns,
                                               y=screen.selected // self.columns), show_cursor=False)
    # CREATE CONTENT FOR MAP CONTROL ]
    # MOUSE HANDLER FOR MAP CONTROL [
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
    # MOUSE HANDLER FOR MAP CONTROL ]
# BOUNDED VISIBLE-ROW CACHE; BLUE DELTAS INVALIDATE INDIVIDUAL CELLS ]
# MANAGE PAGE CONTROL [
class PageControl(UIControl):
    # INITIALIZE PAGE CONTROL [
    def __init__(self, screen, slider=False):
        self.screen = screen
        self.slider = slider
        self.targets = []
        self.width = 1
        self.dragging = False
    # INITIALIZE PAGE CONTROL ]
    # CHECK FOCUSABLE FOR PAGE CONTROL [
    def is_focusable(self):
        return True
    # CHECK FOCUSABLE FOR PAGE CONTROL ]
    # CREATE CONTENT FOR PAGE CONTROL [
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
    # CREATE CONTENT FOR PAGE CONTROL ]
    # SEEK TO A REQUESTED MEDIA OR SCAN POSITION [
    def seek(self, x):
        fraction = max(0, min(x, self.width - 1)) / max(1, self.width - 1)
        self.screen.set_page(1 + round(fraction * (self.screen.pages - 1)))
    # SEEK TO A REQUESTED MEDIA OR SCAN POSITION ]
    # MOUSE HANDLER FOR PAGE CONTROL [
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
    # MOUSE HANDLER FOR PAGE CONTROL ]
# MANAGE PAGE CONTROL ]
# DISPLAY LIVE SCAN BUCKETS AND FILE DETAILS [
class ScannerView(PTScreen):
    # INITIALIZE SCANNER VIEW [
    def __init__(self, browser, startup=True):
        super().__init__(browser)
        self.vfs = browser.vfs
        self.path = self.vfs.pwd().rstrip('/') or '/'
        self.scan_roots = tuple(sorted(browser.scan_selection))
        self.storage_path = self.path + '::selection:' + json.dumps(self.scan_roots) if self.scan_roots else self.path
        self.return_name = browser.current_name()
        self.store = ScanStore(self.vfs.db)
        saved = self.store.get('map', self.storage_path, {})
        self.timing = ScanTiming(saved.get('mode_elapsed', (0., 0., 0.)))
        self.controls = ScanControls(saved.get('modes', (True, False, False)),
            saved.get('read_known', False), saved.get('new_first', True), startup=startup,
            heavy_order=saved.get('heavy_order', 'normal'))
        self.controls.excluded_paths = tuple(browser.blacklist) if browser.blacklist_enabled else ()
        self.controls.trashed_paths = browser.trashed_roots
        self.directory_sizes = {}
        self.directory_counts = {}
        self.directory_size_files = {}
        self.directory_size_dirty = set()
        self.model = FileMap()
        self.model.fixed = False
        for name in ('mode', 'fixed', 'limit', 'byte_limit'):
            if name in saved:
                setattr(self.model, name, saved[name])
        self.model.entries = {value['id']: ScanEntry(**dict(value, progress=None,
                              blacklisted=browser.excluded_directory(value['id'])))
                              for value in saved.get('entries', []) if not browser.is_trashed(value['id'])}
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
        self.catalog_filtered_cache = ()
        self.catalog_filter_signature = None
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
        self.activity_log = deque(maxlen=2)
        self.phase = 'Starting scanner'
        self.paused_modes = None
        self.stats = ScanStats(path=self.path)
        self.detail_ids = []
        self.filtered_count = 0
        self.pages = 1
        self.page_size = 10
        self.detail_signature = None
        self.detail_revision = 0
        self.filter_fragments = []
        self.grid = MapControl(self)
        self.map_window = Window(self.grid, height=Dimension(min=3, weight=2),
                                 right_margins=[ScrollbarMargin()], style='bg:#000000',
                                 wrap_lines=False, always_hide_cursor=True)
        self.map_window.vertical_scroll = saved.get('scroll_y', 0)
        self.details = RowsControl(self.detail_rows, resized=self.details_resized, cache=True)
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
        self.bind(['escape', 's', 'f3'], self.close, eager=True)
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
        self.bind(['L'], self.toggle_loop, filter=not_input)
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
                Window(FormattedTextControl(lambda: [('', 'Drive map — '), ('class:literal', safe_text(self.browser.display_path(self.path)))]), height=1, style='class:header'),
                Window(FormattedTextControl(self.controls_text), height=1),
                Window(FormattedTextControl(self.summary), height=1),
                Window(FormattedTextControl(lambda: self.path_fragments(self.stats_text())), height=2),
                Window(FormattedTextControl(self.activity_text), height=3, wrap_lines=False),
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
    # INITIALIZE SCANNER VIEW ]
    # NAVIGATION ROW FOR SCANNER VIEW [
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
    # NAVIGATION ROW FOR SCANNER VIEW ]
    # START PROJECTION FOR SCANNER VIEW [
    def start_projection(self):
        if self.projection_thread is not None:
            return
        # BUILD A MAP PROJECTION OUTSIDE THE UI THREAD [
        def project():
            while not self.stop.is_set():
                self.projection_wake.wait(.1)
                self.projection_wake.clear()
                if self.stop.is_set():
                    break
                if self.browser.cursor_busy():
                    continue
                try:
                    self.update_catalog()
                    self.update_expert()
                except Exception as exc:
                    self.projection_error = exc
                    self.phase = f'Map projection failed: {exc}'
        # BUILD A MAP PROJECTION OUTSIDE THE UI THREAD ]
        self.projection_thread = Thread(target=project, name='drive-pt-map-projection', daemon=True)
        self.projection_thread.start()
        self.projection_wake.set()
    # START PROJECTION FOR SCANNER VIEW ]
    # REQUEST PROJECTION FOR SCANNER VIEW [
    def request_projection(self):
        self.projection_wake.set()
    # REQUEST PROJECTION FOR SCANNER VIEW ]
    # START SCANNER VIEW [
    def start(self):
        if self.worker is not None:
            return
        self.browser.scanners.append(self)
        self.statistics_token = object()
        self.browser.scan_statistics.begin(self.storage_path, self.statistics_token,
                                          self.timing.statistics_snapshot()[0])
        self.start_projection()
        scanner = DriveScanner(self.vfs.db, self.path, self.events, self.stop, controls=self.controls,
            timing=self.timing, scan_roots=self.scan_roots, storage_path=self.storage_path,
            entries=self.model.entries.values(),
            root_names=tuple(node.name for node in self.vfs.list_nodes(self.vfs.db.get_root())) if self.path == '/' else ())
        self.engine = scanner
        self.worker = Thread(target=scanner.run, name='drive-pt-scanner', daemon=True)
        self.worker.start()
        self.tick_task = self.browser.app.create_background_task(self.tick())
    # START SCANNER VIEW ]
    # REFRESH LIVE SCAN STATE AND ANIMATION [
    async def tick(self):
        presented = 0.
        while not self.stop.is_set():
            if self.browser.cursor_busy():
                await asyncio.sleep(.05)
                continue
            if not self.repacking:
                self.drain_all(budget=.008)
            now = time.monotonic()
            if now - presented >= .1:
                if not self.repacking:
                    self.browser.update_scan_directory_sizes(self)
                    self.request_projection()
                    if self.browser.screen_stack and self.browser.screen_stack[-1][0] is self:
                        self.update_details()
                self.invalidate()
                self.update_statistics()
                presented = now
            # Catch up with discovery independently of the display refresh rate.
            # Short slices still let keyboard input and rendering run between batches.
            await asyncio.sleep(.005 if not self.events.empty() and not self.repacking
                                else max(.005, .1 - (time.monotonic() - presented)))
    # REFRESH LIVE SCAN STATE AND ANIMATION ]
    def account_directory_size(self, entry=None, removed=None):
        key = entry.id if entry is not None else removed
        previous = self.directory_size_files.pop(key, None)
        current = ((normalize_bookmark_path(entry.path).rstrip('/'), max(0, entry.size))
                   if entry is not None and not entry.is_dir and not entry.blacklisted else None)
        if current is not None:
            self.directory_size_files[key] = current
        if previous == current:
            return
        for value, sign in ((previous, -1), (current, 1)):
            if value is None:
                continue
            path, size = value
            while path:
                path = path.rpartition('/')[0]
                self.directory_sizes[path] = max(0, self.directory_sizes.get(path, 0) + sign * size)
                self.directory_counts[path] = max(0, self.directory_counts.get(path, 0) + sign)
                self.directory_size_dirty.add(path)

    # DRAIN ALL FOR SCANNER VIEW [
    def drain_all(self, budget=None):
        deadline = time.monotonic() + budget if budget is not None else float('inf')
        dirty_buckets = set()
        while time.monotonic() < deadline:
            try:
                kind, payload = self.events.get_nowait()
            except Empty:
                break
            if kind == 'entry':
                if self.browser.is_trashed(payload.id):
                    continue
                blacklisted = self.browser.excluded_directory(payload.id)
                if payload.blacklisted != blacklisted:
                    payload = replace(payload, blacklisted=blacklisted)
                self.detail_revision = getattr(self, 'detail_revision', 0) + 1
                self.account_directory_size(payload)
                if not payload.is_dir and payload.state == 'verified':
                    self.browser.queue_dups_refresh((payload.id,))
                repack = self.model.update(payload, rebuild=False)
                self.detail_signature = None
                if repack and not self.closing and budget is not None:
                    self.repack(minimum=self.model.capacity * 2 if self.model.fixed else 1)
                    break
                if repack:
                    self.model.rebuild()
                    self.refresh_colors()
                    dirty_buckets.clear()
                else:
                    dirty_buckets.add(self.model.locations[payload.id])
            elif kind == 'removed':
                self.detail_revision = getattr(self, 'detail_revision', 0) + 1
                for key in payload:
                    self.account_directory_size(removed=key)
                if not self.closing and budget is not None:
                    self.repack(removed=set(payload))
                    break
                for key in payload:
                    self.model.entries.pop(key, None)
                self.model.rebuild()
                self.refresh_colors()
                dirty_buckets.clear()
            elif kind == 'stats':
                finished = self.stats.active and not payload.active
                self.stats = payload
                if finished:
                    self.browser.refresh_scan_symbols()
            elif kind == 'expert':
                self.phase = 'Heavy expert — processing selected bucket'
            elif kind == 'activity':
                self.activity_log.append(safe_text(payload))
            elif kind == 'phase':
                self.phase = safe_text(payload)
        if dirty_buckets:
            self.refresh_colors(dirty_buckets)
    # DRAIN ALL FOR SCANNER VIEW ]
    # UPDATE CATALOG FOR SCANNER VIEW [
    def update_catalog(self):
        # Only the projection worker publishes catalog snapshots. Discovery is
        # append-only between repacks, so old immutable buckets can be reused.
        model = self.model
        filter_signature = (self.browser.blacklist_enabled, tuple(self.browser.blacklist),
                            self.browser.trashed_roots)
        signature = (id(model), len(model.entries), filter_signature)
        if signature == self.catalog_signature:
            return
        if (model is self.catalog_model and self.catalog_cache and
                filter_signature == self.catalog_filter_signature):
            start = len(self.catalog_cache) - 1
            catalog = self.catalog_cache[:start] + tuple(
                tuple(bucket.ids) for bucket in model.buckets[start:])
            filtered_prefix = self.catalog_filtered_cache[:start]
        else:
            start = 0
            filtered_prefix = ()
            catalog = tuple(tuple(bucket.ids) for bucket in model.buckets)
        filtered = filtered_prefix + tuple(tuple(path for path in bucket
            if not self.browser.excluded_directory(path) and not self.browser.is_trashed(path))
            for bucket in catalog[start:])
        self.controls.buckets = filtered
        self.catalog_cache = catalog
        self.catalog_filtered_cache = filtered
        self.catalog_filter_signature = filter_signature
        self.catalog_model = model
        self.catalog_signature = signature
    # UPDATE CATALOG FOR SCANNER VIEW ]
    # UPDATE EXPERT FOR SCANNER VIEW [
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
        # RETAIN THE CURRENT MAP SELECTION [
        def anchor(ids):
            return next((model.locations[key] for key in ids if key in model.locations), None)
        # RETAIN THE CURRENT MAP SELECTION ]
        # ACCOUNT FOR COMPLETED SCAN WORK [
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
        # ACCOUNT FOR COMPLETED SCAN WORK ]
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
    # UPDATE EXPERT FOR SCANNER VIEW ]
    # FIT DISPLAY TEXT TO THE AVAILABLE WIDTH [
    def fit(self, cells):
        if self.model.cells != cells and not self.repacking:
            self.model.cells = cells
            if self.model.fixed and hasattr(self.browser, 'app') and self.browser.app.is_running:
                self.repack()
    # FIT DISPLAY TEXT TO THE AVAILABLE WIDTH ]
    # REPACK FILE ENTRIES INTO DISPLAY BUCKETS [
    def repack(self, minimum=1, removed=()):
        if self.repacking or self.closing:
            return
        self.repacking = True
        replacement = FileMap()
        for name in ('mode', 'fixed', 'cells', 'limit', 'byte_limit'):
            setattr(replacement, name, getattr(self.model, name))
        source = self.model
        # BUILD CATALOG OR MAP CONTENTS [
        def build():
            replacement.entries = {key: entry for key, entry in source.entries.items() if key not in removed}
            replacement.rebuild(minimum=minimum)
            return replacement
        # BUILD CATALOG OR MAP CONTENTS ]
        # INSTALL A COMPLETED MAP PROJECTION [
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
        # INSTALL A COMPLETED MAP PROJECTION ]
        self.repack_task = self.browser.app.create_background_task(install())
    # REPACK FILE ENTRIES INTO DISPLAY BUCKETS ]
    # CLOSE SCANNER VIEW [
    def close(self):
        self.browser.refresh_scan_symbols()
        self.browser.pop(self)

    def pause_resume(self):
        if self.paused_modes is None:
            self.paused_modes = tuple(self.requested_modes.get(i + 1, enabled)
                                      for i, enabled in enumerate(self.controls.modes))
            targets = (False, False, False)
        else:
            targets = self.paused_modes
            self.paused_modes = None
        self.requested_modes = dict(enumerate(targets, 1))
        self.apply_requested_modes()
        self.invalidate()

    def stop_scanning(self):
        if self.closing:
            return self.stop_task
        self.closing = True
        self.stop.set()
        self.controls.wake.set()
        self.projection_wake.set()
        # INSTALL COMPLETED BACKGROUND RESULTS [
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
            self.browser.refresh(self.browser.current_name(), update_info=False)
            self.browser.pop(self)
            # A global stop can arrive while help or bookmarks covers the map.
            # Unlink the hidden map so closing that popup returns to browsing.
            for index, (screen, previous_layout) in enumerate(self.browser.screen_stack):
                if screen is self:
                    next_screen, _ = self.browser.screen_stack[index + 1]
                    self.browser.screen_stack[index + 1] = (next_screen, previous_layout)
                    del self.browser.screen_stack[index]
                    break
            if self in self.browser.scanners:
                self.browser.scanners.remove(self)
            self.invalidate()
        # INSTALL COMPLETED BACKGROUND RESULTS ]
        self.stop_task = self.browser.app.create_background_task(finish())
        return self.stop_task
    # CLOSE SCANNER VIEW ]
    # SAVE SCANNER VIEW [
    def save(self):
        self.update_statistics(final=self.worker is not None and not self.worker.is_alive())
        self.browser.directory_counts.remember(self.directory_counts)
        snapshot = {name: getattr(self.model, name) for name in ('mode', 'fixed', 'limit', 'byte_limit')}
        snapshot.update(entries=[asdict(replace(entry, progress=None)) for entry in self.model.entries.values()],
            modes=self.controls.modes, read_known=self.controls.read_known, new_first=self.controls.new_first,
            selected=self.selected, scroll_y=self.map_window.vertical_scroll, page=self.pagination.page,
            follow_end=self.follow_end, file_filter=self.filter, heavy_order=self.controls.heavy_order,
            scope_path=self.scope_path, scope_color=self.scope_color, fixed_colors=self.fixed_colors)
        snapshot['mode_elapsed'] = self.timing.snapshot()[1]
        self.store.put('map', self.storage_path, snapshot)

    def update_statistics(self, final=False):
        if not hasattr(self, 'statistics_token'):
            return
        counts = self.engine.mode_counts if final else self.stats.mode_counts
        current = self.engine.mode_current if final else self.stats.mode_current
        elapsed, current_elapsed = self.timing.statistics_snapshot()
        self.browser.scan_statistics.update(self.storage_path, self.statistics_token,
                                            counts, current, elapsed, current_elapsed)
    # SAVE SCANNER VIEW ]
    # SELECTED BUCKET FOR SCANNER VIEW [
    def selected_bucket(self):
        return self.model.buckets[self.selected] if not self.follow_end and 0 <= self.selected < len(self.model.buckets) else None
    # SELECTED BUCKET FOR SCANNER VIEW ]
    # SELECTION CHANGED FOR SCANNER VIEW [
    def selection_changed(self):
        self.pagination.page = 1
        self.details.index = 0
        self.detail_signature = None
        self.update_details(immediate=True)
        self.invalidate()
    # SELECTION CHANGED FOR SCANNER VIEW ]
    # MOVE MAP FOR SCANNER VIEW [
    def move_map(self, delta, arrow=False):
        self.browser.note_cursor_motion()
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
    # MOVE MAP FOR SCANNER VIEW ]
    # CLOSE A LIVELOG BLOCK OR FOLLOW THE MAP END [
    def end(self):
        self.follow_end = True
        self.selected = len(self.model.buckets)
        self.selection_changed()
    # CLOSE A LIVELOG BLOCK OR FOLLOW THE MAP END ]
    # DETAILS RESIZED FOR SCANNER VIEW [
    def details_resized(self):
        self.page_size = max(1, min(100, self.details.height))
        self.detail_signature = None
        self.update_details(immediate=True)
    # DETAILS RESIZED FOR SCANNER VIEW ]
    # UPDATE DETAILS FOR SCANNER VIEW [
    def update_details(self, *, immediate=False):
        if not immediate and self.browser.cursor_busy():
            return
        bucket = self.selected_bucket()
        signature = (id(bucket), self.filter, self.pagination.page, self.page_size, len(self.model.entries))
        if signature == self.detail_signature:
            return
        filter_key = (id(bucket), self.filter, getattr(self, 'detail_revision', 0),
                      len(bucket.ids) if bucket else 0)
        if bucket is None:
            ids = []
        elif self.filter is None:
            ids = bucket.ids
        elif filter_key == getattr(self, '_filtered_ids_key', None):
            ids = self._filtered_ids_value
        else:
            ids = [key for key in bucket.ids if self.model.entries[key].state == self.filter]
            self._filtered_ids_key, self._filtered_ids_value = filter_key, ids
        self.pages = max(1, math.ceil(len(ids) / self.page_size))
        self.pagination.select(self.pagination.page, self.pages)
        first = (self.pagination.page - 1) * self.page_size
        self.detail_ids = ids[first:first + self.page_size]
        self.filtered_count = len(ids)
        self.details.index = max(0, min(self.details.index, len(self.detail_ids) - 1))
        self.detail_signature = (id(bucket), self.filter, self.pagination.page, self.page_size, len(self.model.entries))
    # UPDATE DETAILS FOR SCANNER VIEW ]
    # FORMAT SCANNER FILE ROWS WITH STATUS AND DIRECTORY SCOPE [
    def detail_rows(self):
        cache_key = (id(self.model), tuple(self.detail_ids),
                     tuple(self.model.entries.get(key) for key in self.detail_ids),
                     self.scope_path, getattr(getattr(self, 'browser', None), 'show_path_prefixes', None))
        if cache_key == getattr(self, '_detail_rows_key', None):
            return self._detail_rows_value
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
            if hasattr(self, 'browser'):
                shown = self.browser.display_path(entry.path)
                if entry.is_dir:
                    shown = shown.rstrip('/') + '/'
                prefix = self.browser.display_path(self.scope_path).rstrip('/') + '/' if prefix else ''
                path = shown
                if not path.startswith(prefix):
                    prefix = ''
            result.append([('', progress), ('fg:' + color, symbol), ('', ' '),
                ('fg:#ffd700', safe_text(prefix)),
                ('class:literal', safe_text(path[len(prefix):])),
                ('', '' if entry.is_dir else '  ' + format_size(entry.size, 0).strip())])
        self._detail_rows_key, self._detail_rows_value = cache_key, result
        return result
    # FORMAT SCANNER FILE ROWS WITH STATUS AND DIRECTORY SCOPE ]
    # UPDATE PAGE FOR SCANNER VIEW [
    def set_page(self, page):
        self.pagination.select(page, self.pages)
        self.details.index = 0
        self.detail_signature = None
        self.update_details(immediate=True)
        self.invalidate()
    # UPDATE PAGE FOR SCANNER VIEW ]
    # MOVE DETAILS FOR SCANNER VIEW [
    def move_details(self, delta):
        self.browser.note_cursor_motion()
        if delta < 0 and self.details.index == 0 and self.pagination.page > 1:
            self.set_page(self.pagination.page - 1)
            self.details.index = max(0, len(self.detail_ids) - 1)
        elif delta > 0 and self.details.index >= len(self.detail_ids) - 1 and self.pagination.page < self.pages:
            self.set_page(self.pagination.page + 1)
        else:
            self.details.move(delta)
        self.invalidate()
    # MOVE DETAILS FOR SCANNER VIEW ]
    # TOGGLE MODE FOR SCANNER VIEW [
    def toggle_mode(self, mode):
        if self.closing:
            return
        self.paused_modes = None
        current = self.requested_modes.get(mode, self.controls.modes[mode - 1])
        self.requested_modes = {**self.requested_modes, mode: not current}
        self.invalidate()
        self.apply_requested_modes()
    # TOGGLE MODE FOR SCANNER VIEW ]
    # APPLY REQUESTED MODES [
    def apply_requested_modes(self):
        if self.mode_thread is not None and self.mode_thread.is_alive():
            return

        # SWITCH ACTIVE SCAN MODE AND ACCOUNT FOR TIME [
        def switch():
            while True:
                targets = self.requested_modes
                if not targets:
                    return
                with self.controls.lock:
                    # Starting a mode also starts its remaining stage sequence.
                    for mode, enabled in targets.items():
                        if self.controls.modes[mode - 1] != enabled:
                            self.controls.toggle(mode)
                    self.controls.wake.set()
                if self.requested_modes == targets:
                    return
        # SWITCH ACTIVE SCAN MODE AND ACCOUNT FOR TIME ]

        thread = Thread(target=switch, name='drive-pt-modes', daemon=True)
        self.mode_thread = thread
        thread.start()

        # INSTALL COMPLETED BACKGROUND RESULTS [
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
        # INSTALL COMPLETED BACKGROUND RESULTS ]
        self.browser.app.create_background_task(finish())
    # APPLY REQUESTED MODES ]
        # Like j, mode keys persist on the next normal snapshot or close.


    # START FROM FOR SCANNER VIEW [
    def start_from(self, mode):
        self.paused_modes = None
        bucket = self.selected_bucket()
        if bucket and bucket.ids:
            self.controls.start_from(mode, bucket.ids[0])
            self.save()
            self.invalidate()
    # START FROM FOR SCANNER VIEW ]
    def toggle_loop(self):
        if not self.closing:
            self.controls.toggle_loop()
            self.invalidate()

    # TOGGLE FLAG FOR SCANNER VIEW [
    def toggle_flag(self, name):
        setattr(self.controls, name, not getattr(self.controls, name))
        self.controls.wake.set()
        self.invalidate()
    # TOGGLE FLAG FOR SCANNER VIEW ]
    # ORDER FILES FOR THE NEXT SCAN PASS [
    def order(self):
        if self.closing:
            return
        current = self.requested_order or self.controls.heavy_order
        self.requested_order = 'expert' if current == 'normal' else 'normal'
        self.invalidate()
        self.apply_requested_order()
    # ORDER FILES FOR THE NEXT SCAN PASS ]
    # APPLY REQUESTED ORDER [
    def apply_requested_order(self):
        if self.order_thread is not None and self.order_thread.is_alive():
            return

        # SWITCH ACTIVE SCAN MODE AND ACCOUNT FOR TIME [
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
        # SWITCH ACTIVE SCAN MODE AND ACCOUNT FOR TIME ]

        thread = Thread(target=switch, name='drive-pt-order', daemon=True)
        self.order_thread = thread
        thread.start()

        # INSTALL COMPLETED BACKGROUND RESULTS [
        async def finish():
            while thread.is_alive():
                await asyncio.sleep(.01)
            if self.order_thread is thread:
                if self.requested_order != self.controls.heavy_order:
                    self.apply_requested_order()
                else:
                    self.requested_order = None
                self.invalidate()
        # INSTALL COMPLETED BACKGROUND RESULTS ]
        self.browser.app.create_background_task(finish())
    # APPLY REQUESTED ORDER ]
        # Persist with the next ordinary snapshot or close, rather than
        # serializing every map entry for a single order-setting change.

    # CHANGE THE ACTIVE MAP GROUPING MODE [
    def mode(self):
        self.model.mode = 'size' if self.model.mode == 'count' else 'count'
        self.repack()
    # CHANGE THE ACTIVE MAP GROUPING MODE ]
    # CHANGE THE MAP DISPLAY LAYOUT [
    def view(self):
        self.model.fixed = not self.model.fixed
        self.repack()
    # CHANGE THE MAP DISPLAY LAYOUT ]
    # READ CURRENT MAP DISPLAY SETTINGS [
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
    # READ CURRENT MAP DISPLAY SETTINGS ]
    # FILTER CLICK FOR SCANNER VIEW [
    def filter_click(self, state):
        self.filter = None if self.filter == state else state
        self.selection_changed()
    # FILTER CLICK FOR SCANNER VIEW ]
    # FILTERS TEXT FOR SCANNER VIEW [
    def filters_text(self):
        bucket = self.selected_bucket()
        result = []
        for state, label, color in [(None, 'All', '#ffffff')] + [
                (state, f'{symbol} {label}: {bucket.counts[state] if bucket else 0}', color)
                for state, (symbol, color, label) in SCAN_STATES.items()
                if (bucket and bucket.counts[state]) or state == self.filter]:
            # HANDLE A DISPLAY CONTROL MOUSE CLICK [
            def click(event, state=state):
                if event.event_type == MouseEventType.MOUSE_UP:
                    self.filter_click(state)
            # HANDLE A DISPLAY CONTROL MOUSE CLICK ]
            result.append(('bg:#ffffff #000000' if state == self.filter else 'fg:' + color,
                           ' ' + label + ' ', click))
        return result
    # FILTERS TEXT FOR SCANNER VIEW ]
    # SELECT THE DIRECTORY PREFIX FOR BUCKET HIGHLIGHTING [
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
    # SELECT THE DIRECTORY PREFIX FOR BUCKET HIGHLIGHTING ]
    # REFRESH COLORS FOR SCANNER VIEW [
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
            background = self.scope_color if scoped else None
            if not background and self.fixed_colors:
                background = next((self.fixed_colors[key] for key in reversed(bucket.ids)
                                   if key in self.fixed_colors), None)
            if background:
                self.backgrounds[index] = background
            else:
                self.backgrounds.pop(index, None)
    # REFRESH COLORS FOR SCANNER VIEW ]
    # FIX COLORS FOR SCANNER VIEW [
    def fix_colors(self):
        if self.scope_path and self.scope_color:
            for index in self.scope_indices:
                for key in self.model.buckets[index].ids:
                    self.fixed_colors[key] = self.scope_color
            self.refresh_colors()
            self.save()
            self.invalidate()
    # FIX COLORS FOR SCANNER VIEW ]
    # CLEAR FIXED COLORS [
    def clear_fixed_colors(self):
        self.fixed_colors.clear()
        self.refresh_colors()
        self.save()
        self.invalidate()
    # CLEAR FIXED COLORS ]
    # CLEAR COLORS FOR SCANNER VIEW [
    def clear_colors(self):
        self.scope_path = self.scope_color = None
        self.fixed_colors.clear()
        self.refresh_colors()
        self.save()
        self.invalidate()
    # CLEAR COLORS FOR SCANNER VIEW ]
    # CONTROLS TEXT FOR SCANNER VIEW [
    def controls_text(self):
        result = []
        for i, (label, running) in enumerate(zip(('Lite', 'Medium', 'Heavy'), self.controls.modes), 1):
            running = self.requested_modes.get(i, running)
            result.extend([('', f'{i} {label} '), ('class:green' if running else 'class:red', 'RUN' if running else 'STOP'), ('', ' · ')])
        result.append(('', f'r {"on" if self.controls.read_known else "off"} · t {"new" if self.controls.new_first else "all"} · J {self.requested_order or self.controls.heavy_order}'))
        result.append(('', f' · L Loop {"ON" if self.controls.loop else "OFF"}'))
        if (self.requested_order or self.controls.heavy_order) == 'expert':
            result.append(('', f' · Expert selected {self.expert_selected_count} buckets'))
        current, total = self.timing.display_snapshot()
        result.append(('', f' · {format_elapsed(current)} / {format_elapsed(total)}'))
        return result
    # CONTROLS TEXT FOR SCANNER VIEW ]
    # SUMMARIZE THE VISIBLE SCAN BUCKET [
    def summary(self):
        return (f'{self.phase} | {self.model.mode} | {"fixed" if self.model.fixed else "scroll"} | '
                f'{len(self.model.entries)} paths · {len(self.model.buckets)} buckets')
    # SUMMARIZE THE VISIBLE SCAN BUCKET ]
    # PRESERVE LITERAL PATH STYLES IN SCANNER STATUS TEXT [
    def path_fragments(self, text):
        for path in (safe_text(self.stats.path), safe_text(self.scope_path or '')):
            if path and path in text:
                before, after = text.split(path, 1)
                return [('', before), ('class:literal', safe_text(self.browser.display_path(self.stats.path if path == safe_text(self.stats.path) else self.scope_path))), ('', after)]
        return [('', text)]
    # PRESERVE LITERAL PATH STYLES IN SCANNER STATUS TEXT ]
    # STATS TEXT FOR SCANNER VIEW [
    def stats_text(self):
        rate = self.stats.mb_per_second
        for unit in ('MB/s', 'GB/s', 'TB/s', 'PB/s'):
            if rate < 1000 or unit == 'PB/s':
                break
            rate /= 1000
        first = min(self.map_window.vertical_scroll * self.grid.columns + 1, len(self.model.buckets)) if self.model.buckets else 0
        scope = self.browser.scan_statistics_scope
        rows = self.browser.scan_statistics.record(self.storage_path)[scope]
        files, size, seconds = (sum(row[column] for row in rows) for column in range(3))
        return (f'{scan_path_rate(self.stats.paths_per_second)} · {rate:.2f} {unit} · '
                f'{scope.title()} {files:,} files / {scan_size(size)} / {format_elapsed(seconds)} · '
                f'bucket {first}/{len(self.model.buckets)}\n'
                f'{"Scanning" if self.stats.active else "Last path"}: {safe_text(self.stats.path)}')
    # STATS TEXT FOR SCANNER VIEW ]
    # BUCKET SUMMARY FOR SCANNER VIEW [
    def activity_text(self):
        engine = getattr(self, 'engine', None)
        if engine is None:
            current = 'Worker: starting scanner'
        else:
            started, message = engine.activity
            current = f'Worker ({time.monotonic() - started:.1f}s): {safe_text(message)}'
        return '\n'.join([current, *self.activity_log])

    def bucket_summary(self):
        bucket = self.selected_bucket()
        if bucket is None:
            return 'End of buckets > — following new buckets' if self.follow_end else 'Waiting for paths…'
        errors = [entry.error for key in self.detail_ids
                  if (entry := self.model.entries.get(key)) is not None and entry.error]
        text = (f'Bucket {self.selected + 1} · {bucket.files} files · '
                f'{len(bucket.ids) - bucket.files} dirs · {format_size(bucket.size, 0).strip()} · '
                f'M {bucket.file_states["modified"]} / deleted {bucket.file_states["missing"]} / green {bucket.file_states["verified"]} · '
                f'page {self.pagination.page}/{self.pages} · shown {self.filtered_count}/{len(bucket.ids)}')
        if self.scope_path:
            text += f'\nScope {safe_text(self.scope_path)} · {len(self.scope_indices)} buckets'
        elif errors:
            text += ' · ' + safe_text(errors[0])
        return text
    # BUCKET SUMMARY FOR SCANNER VIEW ]
# DISPLAY LIVE SCAN BUCKETS AND FILE DETAILS ]
# LOAD CONFIG FOR THE DRIVE-TUI WORKFLOW [
def load_config():
    from vfs.config import load_config as load_shared_config
    return load_shared_config()
# LOAD CONFIG FOR THE DRIVE-TUI WORKFLOW ]
# LOAD VFS FOR THE DRIVE-TUI WORKFLOW [
def load_vfs(args):
    from vfs.paths import catalog_source_data
    files = []
    if args.cache == 'memory' or args.build or args.update:
        for root in args.db or ['.']:
            files.extend(sorted(Path(root).rglob('llog-llogfiles.sh')))
    if args.cache == 'sqlite':
        options = {}
        if getattr(args, 'fragments', None) or getattr(args, 'refragment', False):
            options = {'fragments': getattr(args, 'fragments', {}),
                       'refragment': getattr(args, 'refragment', False)}
        fs = VirtualFS(None, 'sqlite', **options)
        try:
            if args.build:
                fs.db.rebuild_db()
                fs.cwd = fs.db.get_root()
            for path in files:
                data = {'hashes': {}, 'files': {}, 'file_types': {}, 'modified': {}}
                print(f'Loading {path}')
                load_log(data, path)
                fs.update(catalog_source_data(data))
            return fs
        except BaseException:
            fs.db.conn.close()
            raise
    data = {'hashes': {}, 'files': {}, 'file_types': {}, 'modified': {}}
    for path in files:
        print(f'Loading {path}')
        load_log(data, path)
    return VirtualFS(catalog_source_data(data), args.cache, args.build)
# LOAD VFS FOR THE DRIVE-TUI WORKFLOW ]
# START THE APPLICATION WORKFLOW [
def main():
    parser = argparse.ArgumentParser(
        description='Browse disk catalogs and live drive maps with prompt_toolkit.',
        epilog='Example: ./drive-tui.py ~/mypath\nUses config.sh drive aliases when available.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('path', nargs='?', help='Startup directory (empty/omitted: last directory, initially cwd; supports ~)')
    parser.add_argument('-d', '--db', action='append', help='Directory containing LLOG files (repeatable)')
    parser.add_argument('-c', '--cache', choices=['memory', 'sqlite', 'redis'], default='memory')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('-b', '--build', '--rebuild', action='store_true', help='Rebuild cache from logs')
    modes.add_argument('-u', '--update', action='store_true', help='Update SQLite cache from logs')
    parser.add_argument('-refragment', '--refragment', action='store_true',
                        help='Activate configured path fragments and migrate stored data in batches')
    parser.add_argument('-export-livelog', '--export-livelog', metavar='DIR',
                        help='Export database paths and catalog data to a livelog directory, then exit')
    args = parser.parse_args()
    if args.update and args.cache != 'sqlite':
        parser.error('--update requires -c sqlite')
    if args.path is not None and args.path.strip() and not Path(args.path).expanduser().is_dir():
        parser.error(f'Startup path is not a directory: {args.path}')
    if (args.refragment or args.export_livelog) and args.cache != 'sqlite':
        parser.error('--refragment and --export-livelog require -c sqlite')
    settings = load_config()
    args.fragments = settings.get('db_fragments', {})
    fs = load_vfs(args)
    try:
        if args.export_livelog:
            from vfs.export import export_livelog
            export_livelog(fs.db, args.export_livelog)
            return
        try:
            browser = DriveBrowser(fs, path=args.path)
        except ValueError as error:
            parser.error(str(error))
        browser.run()
    finally:
        if args.cache == 'sqlite':
            shutdown_step('Closing SQLite database', fs.db.conn.close)
# START THE APPLICATION WORKFLOW ]
# RUN DRIVE-TUI ENTRY POINT [
if __name__ == '__main__':
    main()
# RUN DRIVE-TUI ENTRY POINT ]
