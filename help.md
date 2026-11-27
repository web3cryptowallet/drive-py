# Help

## Main TUI (prompt_toolkit)

Startup directories and configured mount roots may be symlinks; their resolved
targets are used to match catalog drive aliases.

All screens highlight program-generated numbers in gold (`40` in `40 MB`,
`1.25` in `1.25 GiB/s`); units keep their normal colors. Complete hashes are gold. Numbers in filenames and paths
keep their normal colors. See [number highlighting](FEATURE-number-highlighting.md).

```bash
./run.sh -d /path/to/logs
./run.sh -c sqlite
```

Activates the project `.venv` (creating it with `uv sync` if needed), then uses
`uv` to run `drive-tui.py` from the project directory, forwarding arguments.
`run.sh` defaults to SQLite; use `-c memory` for an in-memory catalog.
A missing or empty `drivevfs` initializes an empty catalog and opens the local
startup directory without requiring a log import (see [first-start fix](FEATURE-sqlite-first-start.md)).
Use `./run-megadisks.sh` for the generated megadisks dataset.
Terminal colors follow detected capabilities: Apple Terminal uses 256 colors;
terminals advertising RGB use true color. To force 256 colors, run
`PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_8_BIT ./run.sh`. See
[terminal color compatibility](FEATURE-terminal-colors.md).

Startup and updates do not run legacy source-path migration. To convert an old
catalog explicitly, run from the project directory:

```bash
uv run migrate-paths.py                  # existing drivevfs and registered fragments
uv run migrate-paths.py /path/to/catalog --config /path/to/config.sh --batch-size 100
```

The command uses drive mappings from `config.sh` (if present), preserves backups
as `<database>.source-paths-backup.sqlite`, and refuses ambiguous path collisions
or overwriting an existing backup. It reports the number of changed file records.
Migration stages its plans in temporary SQLite files and processes 500 rows per
batch by default. Use `--batch-size 100` for smaller batches at the cost of speed.
Temporary disk space scales with catalog size; staging caches are capped at about
1 MiB per database. Batches remain in one transaction for rollback safety, so the
writer lock lasts through migration. New catalogs need no migration.

Split SQLite storage by catalog path using `db_fragments` in the `SETTINGS JSON`
section of `config.sh`:

```json
{"db": "sqlite", "db_fragments": {"/1T": "fragments/1T.sqlite", "/1T/photos": "fragments/photos.sqlite"}}
```

```bash
./run.sh -refragment
./run.sh -export-livelog /tmp/catalog-export
```

`-refragment` explicitly activates new paths. Existing files move lazily when their
directory is browsed or written, in bounded transactions without rescanning or
rehashing. Nested paths use the most specific prefix; all databases remain visible
during migration. Active mappings persist even if removed from config. Relative
filenames resolve from the launch directory; prefixes use catalog drive aliases.
Keep the main database and all fragments together for backup. Migration does not
automatically shrink the original SQLite file.

`-export-livelog DIR` exports to a new/empty directory and exits. It writes a
`db-paths.json` manifest, one importable `llog-llogfiles.sh` per database, raw node/hash
JSONL files and a coordinator SQL dump. Import checksum logs with
`./run.sh -u -d /tmp/catalog-export`; this does not restore raw metadata automatically.
See [path fragments](FEATURE-path-fragments.md) for storage and recovery details.

Pass an optional startup directory, including `~`, relative paths or paths with spaces:

```bash
./drive-tui.py ~
./drive-tui.py ~/mypath
./run.sh ~/mypath
./run.sh "/path/with spaces"
```

Direct execution requires prompt_toolkit, term-image and Pillow in the Python environment (for example,
activate `.venv` first); `run.sh` manages dependencies through uv. With an empty
or omitted path, the browser restores the last saved directory for this database.
On first launch, or if that directory is unavailable, it uses the process's current
directory. An explicit startup path always wins. The positional path changes
only the browsing location; config, log discovery and SQLite cache resolution
remain in the launch working directory. `run.sh` first changes to the project
directory. Configured local drive mounts translate to VFS aliases. Invalid or
non-directory paths produce a command-line error. `-d` selects log input.

Filename scrolling works in the main table, graphics labels, Bookmarks, Actions,
scanner details, action history and path-command lists:

| Shortcut | Action |
| --- | --- |
| **Shift+Left / Shift+Right** | Move the filename viewport one symbol |
| **Shift+Home / Shift+End** | Reveal the beginning / end |
| **Shift+PageUp / Shift+PageDown** | Same beginning / end actions |

Click or drag the horizontal scrollbar's rectangular thumb to pan. It uses the
same track/thumb colors as the vertical scrollbar. The scroll limit follows the
longest displayed name/row, regardless of selection, with one trailing space.
That space keeps the selected row's background. Main status/bookmark markers and
Size/Files/Dups columns stay fixed. In read-only Info/help, these shortcuts move the
text cursor within the logical line. See [filename navigation](FEATURE-filename-pan.md).

Press **j** for Bookmarks: the list and shared quick-view preview each use half
the width. Each path has a **green ●** when its mapped local target exists or a
**red ●** when offline/missing; configured aliases are resolved before checking.
Arrows or clicks select and preview; **Enter** opens the target. **e** edits its
path; **Delete** removes it. Bookmarks and selection persist in `.bookmarks.json`.
See [bookmark controls and previews](FEATURE-bookmarks.md).

In file lists, **x** off shows filenames and relative expanded subdirectory paths;
**x** on shows prefixed full paths in the Path column and graphics labels.
Press **x** to switch path labels across views between prefixed paths and original
absolute filesystem paths. Prefixes are `~:` for the launch working directory,
`<drive-id>:/` for configured drives, and `:/` for global paths. The preference is
session-only; bookmarks and scan identities retain their stored format. In bookmark
path/number editors, x types normally. Actions: **Ctrl+Delete** or **Clear** clears
the queue. See [path prefix details](FEATURE-path-prefixes.md).

In the main view, **Backspace** or **Esc** goes to the parent directory and
restores the child selection, including when the info pane has focus.
Press **Ctrl+O** to open the selected file with its default desktop application,
or a directory in the default file manager (Finder / Ubuntu Files, etc.).
In Info, a selected duplicate opens instead; otherwise the file-list selection
is used. Linux requires `xdg-open` and a configured desktop session.
Use **Ctrl+X** to copy the selected absolute local path, **Ctrl+T** to open a
new terminal, and **Ctrl+F** to open the default file
manager and highlight the selected file (Finder on macOS, Files on Ubuntu).
Directories open normally; Terminal uses the selected folder or a file's parent.
Linux selection uses FileManager1 D-Bus or supported manager selection commands;
the generic fallback opens the parent without highlighting.
Linux needs an installed terminal emulator (x-terminal-emulator, gnome-terminal,
konsole, xfce4-terminal or xterm). Clipboard uses pbcopy on macOS, wl-copy/xclip/xsel on Linux, PowerShell on
Windows/WSL, or a built-in X11/XWayland owner (python-xlib) when Linux utilities
are missing. Terminal OSC 52 is the final fallback; Ubuntu Terminal may ignore it.


Mark files and folders for scanning or database removal with **Space** (toggle without moving) or **Insert**
(toggle and move down). **\*** inverts marks on all listed files/folders; **-** clears
all marks. Marked item names are gold, including under the cursor. **s** scans
marked files/folders, or the current directory when none are marked. Entering another
directory clears marks. `..` cannot be marked. Marks are session-only;
scoped maps/resume positions are saved separately for each selected path set.
Thumbnail height uses **+** / **_** (Shift+-).

Press **q** from any view (including help, Actions and scanner inputs) to quit
the app. Scanner shutdown retains the existing cancellation and save behavior.

In the PT main view, **Shift+R** clears the saved map and resume positions for the
current directory. Other folders, file records and checksums are retained.

The prompt_toolkit implementation is now the main `drive-tui.py`. Shared VFS,
scanner and database code remains in `vfs/`. Run active tests with
`uv run python -m unittest discover -s tests -v`.

## Keys

Action history: press `l` in the main file manager to view saved navigation,
file/image views, playback start/latest positions, desktop-open requests and
queued removals. Stored locally in `history.llog`, with image views in their own
LiveLog subnode. In history, `Delete` removes one record, `Shift+Delete` clears
all records, and `Enter` goes to the directory when available in the catalog.
Green ● / red ○ show mapped local presence; `t` alternates online/offline history
filters (initially both). Rows have a # index. Presence is cached and checked in
the background; gray ? means pending, and F5 refreshes it. Only visible rows are
formatted, and repeated paths share one presence check. History snapshots save
in the background while the app runs and flush on exit. Main-screen `t` continues
to change themes. In history, `v` toggles the selected file preview; hold the
left mouse button and drag to move the history cursor. Previews load in the
background and show text, directory entries, or image/video thumbnails.

File lists start with ordinary names (no colon prefixes); x enables prefixed
paths. Local path resolution accepts `:/absolute/path` and configured
`alias:/path` prefixes. Relative paths such as `test0/` resolve from the launch
working directory; absolute `/home/...` paths remain rooted at `/`. A file-list
`↗` suffix marks a symlink without changing its name or stored identity. Its
circle is green when the target exists and red for a broken link.

Catalog source paths are stored as `test0/a` for relative paths and `/home/...`
for absolute paths in file metadata, duplicate indexes and LiveLog exports.
VFS decodes relative paths against each run's launch working directory; `~:test0`
is a virtual/display namespace, not a stored source-path prefix. Absolute paths
stay rooted at `/`, with configured drive mappings applied. Internal tree IDs
remain separate indexing keys. Run `uv run migrate-paths.py [database]` explicitly
to upgrade earlier prefixed source fields; startup does not migrate them. Each
changed database gets a `.source-paths-backup.sqlite` snapshot; earlier
`.paths-backup.sqlite` snapshots remain intact. See
[path storage and VFS decoding](FEATURE-path-prefixes.md).

## Path navigation and history

Press **~** on the main screen to open your home directory. Press **/** to open
the path window with `/` already entered and its children listed immediately.
Typing a directory such as `/home/` automatically lists its children, directories
first. Press `~` while the input is `/` to fill your home directory and list it;
Enter opens it.

- **↑/↓** select a path suggestion; **Tab** fills it into the input. Selecting a
  directory lists its children automatically. Clicking a suggestion also fills it.
- **Enter** opens the entered directory or selects the entered file in its parent.
  **Esc** closes the window without navigating.
- **Ctrl+U** clears the input to enter a replacement path or `cd PATH`. An empty
  Enter goes to `/`. Relative paths resolve from the browsed directory; `~:`
  retains its launch-relative meaning. Shortcut letters type normally here.
- **Ctrl+R** focuses the visible **Path history** pane. Use arrows and Enter to
  reopen a target, or click one to load it into the input. Successful targets,
  including selected files, appear newest first without duplicate rows. Invalid
  and cancelled paths are excluded. History persists in `history.llog`.

See [path-command details](FEATURE-path-command.md) for behavior and limitations.

## Recent graphics and desktop controls


### Filters, appearance and Quick View

| Control | Action |
| --- | --- |
| `v` | Cycle all → media → image → videos; show the selected filter in a three-second popup |
| `t` | Cycle MC Default → MC Blue → Textual Dark → White (white background, dark text) |
| Quick View `B` | Click in `● B filename` to toggle the previewed item's bookmark; gray is off, cyan is on |

Media includes images, videos and audio. Filtered directories must contain matching
descendants, except explicitly blacklisted directories, which remain visible.
Gold highlighting applies to standalone numeric values; words such as `mp3` and
`h264` keep their normal color. Complete hash records retain gold styling.

### Directory blacklist for u expansion

| Control | Action |
| --- | --- |
| `!` in Files | Add/remove the selected directory's exclusion; files and `..` are ignored |
| `X` | Enable or bypass all saved exclusions |
| `L` | Open the selectable blacklist |
| Enter in blacklist | Open the selected directory |
| Delete in blacklist | Remove the selected exclusion and save immediately; files are untouched |
| Esc in blacklist | Close the view |

Directory rows show `!` after bookmark `B`, when present. Red means exclusions are
active; green means bypassed. `u` skips each excluded directory's entire subtree.
Enabling exclusions collapses excluded expansions and cancels pending discovery.
After bypassing, press `u` to expand again. Unavailable blacklist entries remain
removable; Enter leaves the view open if the directory cannot be resolved.

Saved paths live in `.blacklist.json` in the app's working directory. The bypass
switch is session-only and restarts enabled. Manual navigation and live scanner
`s` are unaffected. See [u blacklist](FEATURE-u-blacklist.md).

### Loading feedback and large listings

Folder changes and `u` expansion show a Working popup until processing finishes.
Folder disk checks currently remain synchronous, so the popup does not imply
that navigation is nonblocking.

Graphics redraws reuse filename measurements, display labels and preview-map
indexes; thumbnail visibility checks visit viewport grid rows. Initial disk
listing, cold filename measurements, recursive qualification and image decoding
still take time, especially on external disks. The regression in
[tests/test_grid_large_directory.py](tests/test_grid_large_directory.py) creates
10,000 files and checks warm redraws and viewport-bounded visibility lookup; it
does not establish fast initial loading or image decoding.

Player controls include **<Prev** and **Next>** to move between audio/video files
in list order (bookmark order inside Bookmarks). Playback continues when active;
otherwise the target is previewed. Double-click a file in the main table/grid to
select and preview it; audio/video starts when playback is already active.

### Graphics, expansion and desktop actions

Graphics mode (`g`): press `G` (Shift+g) with Files focused to cycle thumbnail
creation order: sequence, random, page-diagonal stride, whole-range stride.
Every mode completes the current visible page first, starting at its first
pending image after a page change, then processes the remaining listing. Stride
advances one column and row at a time. Page-stride finishes the priority page,
then strides across the entire remaining range instead of completing each
offscreen page in turn. Completed thumbnails remain visible when
changing order. A fixed-height color map on the
right shows thumbnail coverage across the listing, one cell per grid column.

Press `u` again while a directory expansion is pending to cancel it and retain
the previous listing. Slow OS reads may finish in the background; cancelled rows
are discarded. Click the graphics preview map to select the represented file
and scroll to its page. Map columns match the current image grid after resizing.

During `u` expansion, the file header shows `u: scanning N files (u:cancel)` in
both table and graphics mode. The count updates after directory reads and counts
each discovered file once; it clears when expansion finishes or is cancelled.

`u` reuses directory discovery within each expansion and skips a second metadata
or duplicate-query pass. Its progress updates in batches of 1,000 discovered files
(start and finish still update immediately). New file duplicate counts are filled
by an ordinary refresh.

Expansion scheduling uses a shorter worker-completion poll and processes rows in
1,000-entry batches. A local 100-file/101-directory fixture improved from 2.02s to
0.30s; actual storage and OS scheduling affect discovery speed.

In filtered modes (`v`: all / media / image / videos), directories without matching descendants are
hidden, respecting dotfile visibility; explicitly blacklisted directories remain visible. The graphics map leaves missing file cells
blank, marks selection with `◆`, and supports left-button dragging to select
files and scroll the file pane.

Graphics mode hides directories without image/video descendants, retaining explicitly blacklisted directories and `..`
for navigation. Map clicks/dragging align the image tile above its filename.
Existing JPEG thumbnails load from disk cache before missing previews on the
current page are generated. With Files focused in graphics mode, `k` clears
thumbnail caches for the current directory subtree; `K` (Shift+k) clears all
thumbnail caches. Previews regenerate automatically. These keys clear generated
JPEGs and thumbnail links, retaining original media files.

Thumbnail names: `128x128-<source-bytes>-<first-1-MiB-SHA256>-<identity>.jpg`
(or 256x256). Images and videos use the same bounded prefix hash. A matching saved
source fingerprint reuses that hash without rereading the original; changed or
unrecognized sources are hashed again. Up to 128 prepared terminal previews stay
in memory for repeat visits. `k`/`K` also clear this prepared cache. Existing
old-name JPEGs regenerate on demand. A warm local repeated-preparation benchmark
improved from 1.79 to 0.22 ms/image; UI/terminal rendering time is separate.

Clipboard shortcuts: `Ctrl+Y` copies Info text, including with Info focused;
`Ctrl+X` copies the selected absolute path. Desktop clipboard tools
have bounded timeouts and fall back to OSC 52. SSH uses the terminal clipboard;
OSC 52 requires terminal clipboard permission/support. Under tmux, normal OSC 52
and passthrough framing are sent; tmux clipboard/passthrough settings still apply.

In graphics mode, `-` (or `_`) shrinks preview height and `+`/`=` enlarges it.
Table-mode `-` retains scan-selection clearing. Arrow navigation keeps selected
image rows above their filename visible. HEIC/HEIF/HIF previews use pillow-heif
(installed by `uv sync`); `.web` is supported as an image alias. WebP/WebM and
MTS/M2TS remain supported; video frames require system FFmpeg.

Completed G-mode preview filenames match the displayed image width and horizontal
alignment. Long names clip from the left; bookmark markers fit inside that width.

Small G-mode previews use their actual icon width, with one column between tiles
and no fixed side borders. At 1–3 lines, reducing zoom fits more images per row;
the right-side preview map follows the new column count.

Ubuntu clipboard: `Ctrl+X` can copy through X11/XWayland without
installing xclip or wl-copy. Run `uv sync` after updating to install python-xlib.
A native clipboard owner serves paste requests while the app runs; clipboard
persistence after exit depends on a desktop clipboard manager. Pure Wayland
without XWayland still needs `wl-copy` (package `wl-clipboard`). OSC 52 fallback
now writes directly without a full-screen blink.

Copy actions show “Copied to clipboard” in a floating popup for three
seconds after native success. Terminal OSC 52 fallback shows “Clipboard request
sent” because delivery cannot be confirmed. Repeated copies renew the notice.

Reveal also requests foreground activation: explicitly activates existing Finder
on macOS and requests the matching existing file-manager window on X11. Linux
startup IDs are forwarded. Desktop focus policy and Wayland-native windows can
prevent raising; selection/reveal still works when foreground activation is refused.

`Shift+G` preview-order changes also show `Preview order: <mode>` in a floating
popup for three seconds. Notifications do not reserve a bottom row.


Quick View’s Info header shows a gold rotating `\ | / -` while a preview is
pending/loading or media is starting. It clears when work finishes or is cancelled.
Enter opens the selected file immediately, bypassing the automatic-preview idle
delay and replacing any queued preview request.

On **q** or **Ctrl+C**, the interface shows “Quitting”, then the terminal lists
each cleanup step (workers, maps, statistics, history and SQLite close). Slow
steps print “Still waiting” with elapsed seconds every second. Thumbnail jobs
are explicitly joined here instead of silently holding Python open afterward.

### Live status window

Press **F4** from any view to open live status for Files, Quick View, thumbnails,
scanning, duplicate updates, conversions, queued file actions, notifications and
current errors. It refreshes cached state every 0.3 seconds without extra disk
reads. Scroll with arrows, page keys or the wheel; **F5** refreshes immediately.
**F4**, **Esc** or Close returns to the previous view. Scanning and playback
continue while it is open.

### Background drive scanning

Files table files show their matching scan entry’s live symbol without reloading;
the active file shows a gold activity marker (Heavy: `◐ ◓ ◑ ◒`;
Lite/Medium: `\ | / -`). Directories show
aggregate scan-map symbols (`?`, `M`, `U`, `●`,
`D`, `·`, or `!`) for their scanned contents, keeping their original circle color
except that confirmed empty directories show a green middle dot **·**. Discovery must
successfully list a directory with no catalog or disk children to mark it empty.
Closing the scan view with **Esc** or **s** refreshes these symbols immediately.
Files cursor redraws immediately. Expensive symbol snapshots and automatic
quick-view work wait until one second after the last cursor move. Thumbnail
scheduling and scanner work also yield during this interval. Each move resets
the timer; existing playback continues. Scanner cursor redraws reuse cached page text and widths; map selection updates its file page synchronously,
including active filters. Scanner file-page changes remain immediate:
Up/Down across a page boundary and explicit page controls redraw the requested
page immediately, even during this idle window. Directory Size values also grow
from cached scan-event totals without reloading the listing or reading disk.
These updates wait for cursor idle and preserve any larger catalog size while
discovery is incomplete. Directory Files (descendant file count) updates from the
same cached events. Files rows show 1 in Files; directory Dups is —. File Dups refreshes after checksum verification and subtree
expansion while idle; `(?)` means no checksum/count is available yet. File counts
retain the existing meaning: catalog paths sharing that hash, including the file. Press **Ctrl+R** or **F5** for full reloads; scanner events do not
automatically update the directory summaries. Directories containing the current
active scan path temporarily show a rotating `\ | / -` marker in the same
circle color; pause/idle restores their saved symbol.

`s` starts scanning marked files/folders (or the current directory) and toggles the scan
view. Closing it with `s` or Esc keeps scanning in the background while you browse
and play videos. While running or paused, press `s` again to return to the
same scan, even after navigating to another folder. If the scan has finished,
reopening with `s` starts a fresh 1 → 2 → 3 scan of the current directory
(or its marked files/folders), including when reopening the same directory. The bottom row shows state, paths processed, throughput and the
current/last path. **Ctrl+P** pauses/resumes enabled scan modes; **Ctrl+K** stops and
saves the scan. Pause switches the startup sequence to manual mode control.
After stopping, `s` starts a session for the current folder/marks. Quitting saves
and shuts down hidden scans too. Python behavior; Rust parity is unverified.

### Compact media controls

Compact Prev/Play/Stop/Next buttons keep the preview usable in narrow panes,
including 60- and 80-column terminals. Press `p` to play/stop; the main Tab order
is Files → Info → Prev → Play → Stop → Next → Mute → Seek.

Audio-only MP4 and other video containers play through the audio decoder when
ffprobe finds audio without a video stream; the empty video area hides once
playback progress arrives. Known audio extensions retain their existing route.

### Default expert scanning and statistics

New scans automatically run Lite → Medium → finite Heavy expert: new files first,
then unknown files, then stop. Previously verified checksum work is skipped.
Starting a mode manually with `1`, `2` or `3` selects that stage exclusively,
then advances through the remaining stages and stops after Heavy. Manual runs
include old files. **Shift+L** in the scanner toggles **Loop ON/OFF** (off by
default); ON repeats Lite → Medium → Heavy, and OFF stops after the current
cycle. Enabling Loop while idle starts Lite. Loop is session-only.
Lite still enumerates directories to find additions.

**F6** opens the live statistics table from Files or Scanner. It shows files,
decimal MB and processing time for modes 1/2/3 across current scan, current session,
last non-empty session and lifetime totals. **v** inside the table switches
current/total ordering and scanner summary display; **Esc** closes it. In Files
the table follows the current directory/marks; in Scanner it follows the scan root.
Totals count processing visits across modes, exclude directories, and persist per
scope in SQLite/Redis. Current session resets on launch; its previous nonzero
value becomes Last session. Memory-only storage ends with the process.
Details: [scan statistics](FEATURE-scan-statistics.md).

### Video conversion

Use **Convert / Ctrl+E** to edit the selected video or folder, **Queue +/-** to
add/remove it, and **Queue / Q** to manage the persistent conversion queue.
Submit saves a job; Start runs pending jobs, Pause/resume suspends processing,
Stop returns active work to the queue, Clear removes entries, and Convert now
prioritizes the selected job. Enter/Edit in the queue goes to the source file
and restores its options. Queue restoration is stopped until Start is requested.

Exports go into **youtube-conv/** inside each source file's directory. Presets
include Instagram, YouTube, Threads, Facebook, LQ, Instagram-25MB and YouTube-25MB;
H.264/H.265, CRF, low/high quality, orig/1280/1980/1920/4k resolution, bitrate and
size targets are editable. These create local files; they do not publish online.
25 MB is an editable export cap, not a claimed network upload limit.

Choose Start/End/Length and click the player slider to set it; drag a time field
left/right for 0.1-second adjustments. End and selection length stay synchronized.
Reset restores the full duration. The current frame previews while stopped, and
Play starts from that position. Copy CLI (or Ctrl+Y inside the editor) copies the
FFmpeg command. Extra encoding options are supported; sources and earlier
exports are never overwritten. FFmpeg/ffprobe are required. SQLite/Redis persist
the queue; memory mode is ephemeral. See [conversion details](FEATURE-video-conversion.md).

### Scan blacklist and database trash

`!` marks a directory as blacklisted for both `u` expansion and the live scanner.
Scans skip its subtree; affected map chunks show a **red !**. `X` bypasses the
blacklist, and `L` lists it. **Ctrl+B** independently shows/hides blacklisted
entries in Files without changing scan exclusions.

**Ctrl+D** moves the selected file/folder's database records into the **D** trash
table, leaving disk contents untouched. **d** opens that archive. Active scans are
stopped first, and trashed paths stay excluded from later scans so they are not
immediately re-added. Restore/purge UI is deferred; metadata is retained.
`Delete` / `Shift+Delete` still add filesystem-removal actions to the Actions queue.
See [database trash](FEATURE-database-trash.md) for storage and validation details.

Player **🔊 / 🔇** toggles sound without stopping playback. It also works before
Play and retains the setting for this session in Files, bookmarks and conversion
preview. Conversion output audio is unaffected. Buttons now display plain labels
without `<` / `>` decorations.

The **o** one/all-level expansion preference is saved in the database and restored
on launch (SQLite/Redis). Expanded folders themselves remain session-only.

In **g graphics mode**, files **not found on disk** have red filenames, including
on selected and compact rows. Present unknown/untracked files keep normal colors.
**Ctrl+U** shows/hides not-found files in both graphics and table listings. Directories remain visible for
navigation; the filter starts shown, lasts for this session and does not change
scan exclusions or delete anything.

Help (**h**) now shows a bordered **three-column shortcut index**, grouped under
**yellow section cells** such as Files, Scan view, Cache and Media. Sections and
shortcuts fill three continuous columns under one shared scrollbar. Read and
scroll the full first column, then continue at the top of the second column,
then the third. Columns do not restart in viewport-sized pages. All three
columns retain their vertical borders, with short
one-line labels and the selected shortcut's full description below. Filename
endpoint shortcuts appear separately as `Shift+Home`, `Shift+End`,
`Shift+PageUp` and `Shift+PageDown`. Press **/**
to search sections, keys and descriptions in the bottom input; matches highlight and the index
follows the selected result. **Down/Right** advance in reading order down each
column and then to the next column’s top; **Up/Left** reverse that order, skipping
section headings. Moving beyond the last entry wraps to the first; moving before
the first wraps to the last, with the shared scrollbar following. **Home/End** jump to the first/last entry and scroll it into view;
**PageUp/PageDown** advance five entries. Mouse wheel also browses entries. **Enter** returns
to the index, and **Esc** leaves search then closes help. Mouse selection works;
the Close button remains available. Typing shortcut letters in search enters text.
Files, scanner and help shortcut entries are checked against their registered
bindings, including Ctrl+R/F5, blacklist, sizing and scanner Loop controls.

### Scan worker activity

The scan popup shows the current worker operation and path, elapsed time in that
step, and two recent activity messages. Before map paths appear, this identifies
saved-state loading, catalog lookups, directory enumeration or database writes.
Recent messages are sampled; a slow operation retains its current step and timer.

After file scanning, the marker uses the live result: green for verified, orange
for modified, red for missing and white for new/unverified. Active scan rotation
is purple in Mode 2 (Medium), and gold in Lite and Heavy.

Saved checksums load on demand per directory, with up to 32 directories cached
by the worker across passes. The popup identifies the directory being loaded.
SQLite filters by path in the database; missing checksum-only descendants remain
visible to discovery. Large directory subtrees may still require a key scan.

When rotation ends, unverified Files rows use the normal file-list marker instead
of the map's `?`. Modified/missing and other specific results keep their symbols.
Folder summaries refresh when a scan pass finishes, without directory navigation.

Mode 3 groups SQLite checksum and scan-state writes in batches of up to 128 files,
flushing after 0.25 seconds at file-completion boundaries and at bucket/pass end
or stop. File reads stay outside write transactions. Completed markers and
catalog/duplicate updates appear after the batch commits; hashing progress stays
live. This reduces database commit overhead for small files.

Completed directory summaries keep their result color: green for verified/empty,
orange for modified and red for missing. The settled symbol and color refresh
together after scanning; active rotation retains its stage color.

### Database size and disk space in F4

Open F4 and scroll to Storage for each SQLite database/fragment file size,
WAL/SHM/journal sidecar size and their combined total. Containing disks show total,
used and free capacity; the browsed directory's disk is included if different.
Storage refreshes in the background every five seconds; F5 requests an immediate
refresh. These are database file sizes and volume capacity, not total catalogued
file content sizes. Memory and remote backends have no local database file size.

The main scan status line shows the mode's rotating indicator (purple for Medium,
gold for Lite/Heavy), scope file count/size/time, paths/s, MB/s and the current/last
scanned path. Shortcut hints are hidden; long paths keep their beginning and end
as `start...end` within the terminal width. Phase text is omitted. Paused/idle scans keep statistics without
rotation. Open s, F4 or F6 for more detail.

### More

Empty folders in the file list show a small green middle dot (`·`) immediately,
before scanning. Listing refresh checks for any child, including hidden entries;
unreadable folders keep their usual status marker.
Unhandled shortcuts show a red `Unknown key <key>` popup for three seconds.
Editable text fields continue to accept normal input.

The main scan status row hides shortcut hints and shows the current/last scanned
path after the statistics. Long paths use `start...end` to fit the terminal;
`s` still opens/hides the scanner.

In the Files Size column, unscanned directories with no known content total show
`-`; confirmed empty directories show `0`. Known scan/catalog totals show content
sizes, excluding the filesystem directory-entry size.

### Trash

**Ctrl+D** moves the selected database entry/subtree to Trash, keeping disk files.
**d** opens Trash. Active scans stop before removal; trashed paths stay excluded
from scanning. Restore/purge is not available.

In D (database Trash), deletion time is the first column in UTC
`yyyy-mm-dd hh:mm:ss` format; the right-aligned column shows size and the last six hash characters. Enter expands
active duplicates beneath an entry. Select a duplicate with arrows and press
Enter to jump to it in Files; Enter on the archive row collapses it.

Trash filename search: press `/` and type to filter names live (case-insensitive).
Expanded duplicate names also match. Esc returns to the list with the filter
retained; clear the search text to show all entries. The right column uses
`size hash-last-6`, such as `4 bytes 678901`; full hashes remain stored.

Trash `/` search highlights matching path text in bold black on yellow, matching
Help, including expanded duplicates and the selected row.

In D (database Trash), deletion time is the first column in UTC
`yyyy-mm-dd hh:mm:ss` format; the right-aligned column shows size and the last six hash characters. Enter expands
active duplicates beneath an entry. Select a duplicate with arrows and press
Enter to jump to it in Files; Enter on the archive row collapses it.

Trash filename search: press `/` and type to filter names live (case-insensitive).
Expanded duplicate names also match. Esc returns to the list with the filter
retained; clear the search text to show all entries. The right column uses
`size hash-last-6`, such as `4 bytes 678901`; full hashes remain stored.

Trash `/` search highlights matching path text in bold black on yellow, matching
Help, including expanded duplicates and the selected row.

Press `h` for Help's dedicated **Trash** section, covering Ctrl+D/D, search,
highlighting and duplicate navigation.


Trash duplicate rows show a green `●` for files present on disk and red `●` for
missing/inaccessible files. Collapse and expand again to refresh status; cursor
movement uses cached status. Green indicates presence, not checksum verification.

Quick View duplicate navigation: Tab to Info, then Up/Down selects duplicates,
PageUp/PageDown moves ten, Home/End selects first/last, Right/Enter jumps to the
file, and Left returns focus to Files. Without duplicates, vertical keys move
through text.

Click a Quick View row to focus the pane and select that row immediately; then
use arrows to select duplicates and Enter/Right to jump. Tab also focuses Info.

Double-click a Quick View duplicate to jump to its location, just like Enter.
Single-click selects it.

Space/Insert marks also target **Ctrl+D**. It opens **Remove data from db?**
for the marked paths, or the cursor item if there are no marks. Cancel/Esc/n
keeps them; select Remove or press y to confirm. Folders include their subtree.
Disk files stay in place and metadata moves to D; scans exclude trashed paths.

Database removal uses a small centered red popup: “Remove data from db?” with
Remove first, Cancel second. Left/Right/Tab switches buttons; Enter activates
the focused button. Esc/n cancels; y confirms.

Database removal confirmation centers its question and buttons in a padded red
window. Removed database entries still present on disk remain visible in Files
as orange/unscanned. D shows newest deletions first; its retained roots still
exclude automatic scan reimport.

Ctrl+D on items still present on disk now **resets their scan information**,
removing catalog/hash/checksum/verification state without adding them to D.
Select the files or their folder and press s to rescan. Only missing paths move
to D. Legacy D entries no longer exclude paths that exist on disk; stale saved
verification is discarded when their active catalog records are absent. This
supersedes the earlier automatic exclusion guidance for present disk paths.

In D, press **h** outside search for quick help; **Esc**, **Enter** or **h**
closes it. Restore is not implemented. Archive removal controls are listed below. In search, h types normally.

In **D**, **Insert** toggles a gold mark and advances; **-** deselects all.
**Delete** permanently removes marked archive rows, or the cursor archive row
when unmarked. **Ctrl+Delete** immediately clears all D records, including those
hidden by search. These affect archive metadata only, keeping disk files and
active duplicates. Folder archive rows are independent of descendant rows.
**h** opens quick help with orange highlighted keys. Commands require table
focus; search keeps normal editing. Restore remains unavailable.

D search: **Esc** clears the search and focuses the full list. **Enter** keeps
the filter and focuses the filtered list. From the list, Esc closes D and Enter
expands/collapses duplicates or jumps. Archive marks are unchanged by search.

The Files removal question reads **Remove N items from db?**. It counts marked
items in the current list, each folder once, without counting descendants.
Without marks it counts the cursor item as one.

Quick View duplicate paths default to **real-path filtering**, collapsing file
and directory symlink aliases. The exact selected path is excluded from both modes. Aliases resolving to it
are hidden only in filtered mode and remain visible in all mode. **f** while Info has
focus switches **filtered/all**. The heading shows **shown/total** paths excluding the exact selected path.
For another file plus a symlink to the selected file, it shows **1/2 filtered**
and **2/2 all**. The toggle reuses
the current preview snapshot; reopen it to refresh filesystem changes.

**d** opens/closes the D archive list (outside search); **Ctrl+D** retains its
Files reset/removal behavior. **f** toggles Quick View filtered/all duplicates
from either Files or Info focus. Help omits ordinary arrow/PageUp/PageDown/
Home/End shortcut entries while retaining their working navigation bindings.
Shift filename-scrolling shortcuts remain listed.





Trash caches formatted rows during cursor movement; search, expansion, width
and path-display changes rebuild the view.

Trash duplicate rows show a green `●` for files present on disk and red `●` for
missing/inaccessible files. Collapse and expand again to refresh status; cursor
movement uses cached status. Green indicates presence, not checksum verification.

Quick View duplicate navigation: Tab to Info, then Up/Down selects duplicates,
PageUp/PageDown moves ten, Home/End selects first/last, Right/Enter jumps to the
file, and Left returns focus to Files. Without duplicates, vertical keys move
through text.

Click a Quick View row to focus the pane and select that row immediately; then
use arrows to select duplicates and Enter/Right to jump. Tab also focuses Info.

Double-click a Quick View duplicate to jump to its location, just like Enter.
Single-click selects it.

SQLite catalogs use WAL journaling so scanner readers can remain open while
navigation saves commit. SQLite manages accompanying `-wal`/`-shm` files; competing
writers still use the existing lock timeout. See
[the navigation locking fix](FEATURE-startup-directory.md#2026-11-24--navigation-commits-while-scanner-readers-remain-open).

Folder-loading and expansion feedback use the normal notification color, clearing
any preceding error's red background. Red notification styling is reserved for
error feedback.

Space/Insert marks files and folders (Insert also advances); * inverts marks.
`s` scans marked items, or the current directory when unmarked. Ctrl+D opens
“Remove data from db?” for marks, falling back to the cursor item. Remove is
first and focused by default; Esc/n cancels, y or Remove confirms. Metadata moves to D;
disk files stay intact. See [database removal](FEATURE-database-trash.md).

Database removal uses a small centered red popup: “Remove data from db?” with
Remove first, Cancel second. Left/Right/Tab switches buttons; Enter activates
the focused button. Esc/n cancels; y confirms.

Database removal confirmation centers its question and buttons in a padded red
window. Removed database entries still present on disk remain visible in Files
as orange/unscanned. D shows newest deletions first; its retained roots still
exclude automatic scan reimport.

Ctrl+D on items still present on disk now **resets their scan information**,
removing catalog/hash/checksum/verification state without adding them to D.
Select the files or their folder and press s to rescan. Only missing paths move
to D. Legacy D entries no longer exclude paths that exist on disk; stale saved
verification is discarded when their active catalog records are absent. This
supersedes the earlier automatic exclusion guidance for present disk paths.

In D, press **h** outside search for quick help; **Esc**, **Enter** or **h**
closes it. Restore is not implemented. Archive removal controls are listed below. In search, h types normally.

In **D**, **Insert** toggles a gold mark and advances; **-** deselects all.
**Delete** permanently removes marked archive rows, or the cursor archive row
when unmarked. **Ctrl+Delete** immediately clears all D records, including those
hidden by search. These affect archive metadata only, keeping disk files and
active duplicates. Folder archive rows are independent of descendant rows.
**h** opens quick help with orange highlighted keys. Commands require table
focus; search keeps normal editing. Restore remains unavailable.

D search: **Esc** clears the search and focuses the full list. **Enter** keeps
the filter and focuses the filtered list. From the list, Esc closes D and Enter
expands/collapses duplicates or jumps. Archive marks are unchanged by search.

The Files removal question reads **Remove N items from db?**. It counts marked
items in the current list, each folder once, without counting descendants.
Without marks it counts the cursor item as one.

Quick View duplicate paths default to **real-path filtering**, collapsing file
and directory symlink aliases. The exact selected path is excluded from both modes. Aliases resolving to it
are hidden only in filtered mode and remain visible in all mode. **f** while Info has
focus switches **filtered/all**. The heading shows **shown/total** paths excluding the exact selected path.
For another file plus a symlink to the selected file, it shows **1/2 filtered**
and **2/2 all**. The toggle reuses
the current preview snapshot; reopen it to refresh filesystem changes.

**d** opens/closes the D archive list (outside search); **Ctrl+D** retains its
Files reset/removal behavior. **f** toggles Quick View filtered/all duplicates
from either Files or Info focus. Help omits ordinary arrow/PageUp/PageDown/
Home/End shortcut entries while retaining their working navigation bindings.
Shift filename-scrolling shortcuts remain listed.

## Loaded drive mappings

Press **F7** in Files to view loaded config.sh MAP DRIVES aliases, source prefixes,
local paths and disabled roots. The view is read-only and scrollable; **Esc/F7**
closes it. ~: shows the startup directory. Edit config.sh and restart to apply
changes. No disk availability checks or configuration reload occur on open.

**F7** opens drive mappings; **o** toggles one/all expansion levels.

F6 opens all three modes' statistics from Files or the scanner, using the hidden
scanner scope when present. Sizes scale through GB/TB/PB. The status row shows
active-mode bytes / largest mode bytes and elapsed / estimated total processing
time (— until bytes are observed). Slow path rates use paths/min or paths/h.
Estimates use observed progress and exclude pauses; they are not disk inventories.

Info shows **Disk free: free/total** on the next line after Size for connected preview targets,
for example **12.0 GB / 512.0 GB**. Capacity refreshes when Info opens; unavailable
targets or failed disk probes omit it.

Info metadata uses separate lines for **Size**, **Disk free** (when available),
**Dirs**, and **Files**. Counts follow the visible Files list and update in place.

Press **F7** in Files to inspect loaded drive mappings; **Esc/F7** closes.
See [drive mapping controls](FEATURE-drive-mappings.md).

F6 opens scan statistics. See [help.md](help.md) for adaptive size/rate units
and mode progress/time estimates.

## Function keys

**F1** opens context Help (press again to close); **F10** quits through the usual
save/cleanup path, including while typing in a search field. Existing h/q/Ctrl+C
shortcuts remain. The bottom row lists assigned keys: Help (F1), Scan (F3), Status (F4), Refresh (F5),
Stats (F6), Paths (F7) and Quit (F10); unused keys are hidden. Key names are white on black. Existing per-view key
scopes remain. Labels shorten on narrow terminals. When the scan status line is
present, it replaces the function-key hints; removing scan sessions restores them.

**F3** works like **s**: open/resume Scan from Files, hide the map while scanning
continues, or restart a finished scan for the current directory/marked paths.

Home paths: `~/media` uses `~0:/media` (current user's home).
F7 lists home `~0:/`, startup `~:`, global `:/`, and configured mappings.

On Linux/macOS, the top-level drive list starts with `/`: Enter browses
the real OS filesystem root; `..` returns to the drive list.

Home reached via its configured alias, `~0:/`, or the OS root browser
shares one catalog identity. F7 colors existing paths green, missing paths
red, and highlights `~0:/` in bold cyan.

Startup paths now display as `@:` (legacy `~:` input remains accepted).
F7 highlights all aliases/prefixes uniformly; `~0:/` stays one color.
Going up from home (~0:/ or its configured alias) returns to the top-level / drive list. Lookup-only cached
OS directories are excluded from the top-level drive list.

`@:` applies only to relative paths: `test0/t0` → `@:test0/t0`.
Home, absolute and mapped paths keep their own prefixes even inside cwd.

Parent navigation follows the entry route: OS `/home/vboxuser` goes up
to `/home`; home alias `~0:/` or configured `root` goes up to the drive
list. OS paths retain this behavior with or without a home mapping.

Files: Ctrl+S starts incremental filename prefix search. Type to select;
Ctrl+S/Down finds next, Up previous; Enter refreshes and opens the best match; Esc finishes. Matching ignores case
and searches visible file/directory names without filtering the listing.

Quick View reserves room for three duplicate rows below media on normal-sized
terminals. Duplicate paths use single lines; focus/click Info and use arrows,
PageUp/PageDown, End or its scrollbar to reach further entries.

## AI documentation rule

Never add new feature details after
`*AI-Independet code. Created through human work*` in README.md. Keep that
attribution as the final nonempty line. Add feature details to the appropriate
existing README section above it, or to help.md and the relevant FEATURE-*.md.
Verify the boundary after every README edit.

Filename search (Ctrl+S) replaces the Files panel's bottom horizontal scrollbar
with one line. Enter refreshes the listing and selects the first best filename
match (exact, prefix, then substring), then opens it. No match keeps search
active. Esc restores the
scrollbar. Quick View remains visible; no-match feedback stays inline.

Interactive filename search always selects the first prefix match on each
edit: m → media, mn → mnt, Backspace to m → media. Clearing the query keeps
the current selection. Ctrl+S/Down/Up still cycle matches.

Restart preserves saved symlink routes such as `~0:/src` instead of switching
to their physical target. If an older run already saved /mnt/src, navigate to
`~0:/src` once to save the intended route again.
