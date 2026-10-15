# drive.py

drive.py v0.99

v0.99 - prompt_toolkit as the main TUI, live drive scanning and file maps, context help, and saved scan state

Multithreaded disk file comparison tool for verification and MD5 checksum reporting.

- **drive.py** — CLI disk analyzer.
- **drive-tui.py** — prompt_toolkit TUI for browsing the disk database and live drive maps.

![drive.py main](https://raw.githubusercontent.com/web3cryptowallet/drive-py/master/assets/console-1.png)
![drive.py file compare](https://raw.githubusercontent.com/web3cryptowallet/drive-py/master/assets/console-2.png)


## Prerequisites
- Python 3.10 or newer
- uv (runs the prompt_toolkit TUI)
- Node.js (required for the web viewer)

## Usage
```bash
usage: drive.py [-h] [-s SRC] [-d DST] [-f FILE] [-e EXCLUDE] [-n NOTREE] [-t THREADS] logdir

Compare directories. Usage examples:
  drive.py -s <src>.. <logdir> # scan dirs only
  drive.py -s <src>.. -d <dst>.. <logdir> # compare dirs
  drive.py -f <log>.. -e <dir>.. <logdir> # compare logs

positional arguments:
  logdir                Log directory path

options:
  -h, --help            show this help message and exit
  -s SRC, --src SRC     Source directory path
  -d DST, --dst DST     Destination directory path
  -f FILE, --file FILE  Log file path
  -e EXCLUDE, --exclude EXCLUDE
                        Exclude dir for scanning (with -f)
  -n NOTREE, --notree NOTREE
                        No files tree
  -t THREADS, --threads THREADS
                        Number of threads for file hashing
```

## Run demo: Build demo report

Just try this demo:
```bash
./drive.py -s test0/t0 -d test0/t1 log-test0
```

## Megadisks demo

Browse synthetic disks, files, and backup duplicates in the TUI:

```bash
./run-megadisks.sh
```

Requires uv and generated `log-megadisks/` data.

## Main TUI (prompt_toolkit)

```bash
./run.sh -d /path/to/logs
./run.sh -c sqlite
```

Uses `uv` to run `drive-tui.py` from the project directory, forwarding arguments.
`run.sh` defaults to SQLite; use `-c memory` for an in-memory catalog.
Use `./run-megadisks.sh` for the generated megadisks dataset.

Pass an optional startup directory, including `~`, relative paths or paths with spaces:

```bash
./drive-tui.py ~
./drive-tui.py ~/mypath
./run.sh ~/mypath
./run.sh "/path/with spaces"
```

Direct execution requires prompt_toolkit in the Python environment (for example,
activate `.venv` first); `run.sh` manages dependencies through uv. Without a path,
the browser starts in the process's current directory. The positional path changes
only the browsing location; config, log discovery and SQLite cache resolution
remain in the launch working directory. `run.sh` first changes to the project
directory. Configured local drive mounts translate to VFS aliases. Invalid or
non-directory paths produce a command-line error. `-d` selects log input.

Press **q** from any view (including help, Actions and scanner inputs) to quit
the app. Scanner shutdown retains the existing cancellation and save behavior.

In the PT main view, **Shift+R** clears the saved map and resume positions for the
current directory. Other folders, file records and checksums are retained.

The prompt_toolkit implementation is now the main `drive-tui.py`. Shared VFS,
scanner and database code remains in `vfs/`. Run active tests with
`uv run python -m unittest discover -s tests -v`.

The former Textual application, views, theme, launchers and dependent tests are
preserved in [texual.removed](texual.removed/README.md). The following legacy
Textual UI notes describe that archive; use the launchers above for the main UI.
See [FEATURE-pt-main.md](FEATURE-pt-main.md) for the migration record.

## Archived Textual TUI notes

MC Default starts with the reference Midnight Commander palette: muted blue panels,
teal selections, and yellow headings. MC Blue preserves the previous saturated blue
palette. Press `t` to cycle through MC Default, MC Blue, and Textual Dark. The shortcut is also
listed in the scrollable help popup: press **h** from the main view.
Help includes the current display-mode legend and queue shortcuts; shortcut
keys are orange. Press **h**,
**Esc**, or **Close** to return. The root info pane also shows the full main
help, including the current legend and shortcuts; scroll the info table to read it. See [FEATURE-help-view.md](FEATURE-help-view.md).

The file and info panes each use 50% of the width. Status circles in both panes
keep their colors when selected.

The info pane displays Created and Modified dates for files and directories in
local time using `YYYY-MM-DD HH:MM:SS` (for example, `2026-09-22 14:30:05`).
Unavailable dates are left blank.

```
sudo apt install python3-venv

python3 -m venv .venv

pip install textual
pip install pyperclip

sudo apt install xclip

```

Run with in-memory db for small amount of files
```
PYTHONPATH=.:texual.removed .venv/bin/python texual.removed/drive-tui.py
```

Rebuild SQLite cache for big disks (`-b`)
```
PYTHONPATH=.:texual.removed .venv/bin/python texual.removed/drive-tui.py -c sqlite -b
```
SQLite builds load and commit one log at a time through `load_lite`, releasing
each parsed log before loading the next. Memory usage depends on the largest
individual log rather than all logs combined. Later logs overwrite matching
files. The `-b` option recreates the cache once before loading begins.

**Experimental:** Update an existing SQLite cache without recreating it (`-u` / `--update`):
```
PYTHONPATH=.:texual.removed .venv/bin/python texual.removed/drive-tui.py -c sqlite -u -d log-test0
```
Both modes load one log at a time. Use either `-u` or `-b`, not both.

Run with SQLite cache without importing logs:
```
PYTHONPATH=.:texual.removed .venv/bin/python texual.removed/drive-tui.py -c sqlite
```

To merge files into an existing SQLite cache without rebuilding it, use the
adapter's `update` method:

```python
from vfs import SQLiteDBAdapter

db = SQLiteDBAdapter("drivevfs")
try:
    db.update({"disk/folder/file.txt": {"MD5:checksum:123"}})
finally:
    db.conn.close()
```

Updates overwrite matching files, create missing parent directories, adjust
directory sizes, and refresh duplicate lookups. Files omitted from the update
remain unchanged. Each path must have one `hash:size` value. An incoming file
replaces an existing directory and its cached descendants, including their
duplicate entries. A file needed as a parent is replaced with a directory;
its old size and duplicate entries are removed. Invalid input rolls back the
update. These replacements affect only the cache. `build` still recreates it.

```
pip install textual-image pillow
```

## Run demo: View demo log files in your browser 

1. Install LiveComment
```bash
npm i -g livecomment
```
2. Start LiveComment web server
```bash
livecomment --path log-test0
```
3. Open http://localhost:3070/
```bash
open http://localhost:3070/
```

![log-test0](https://raw.githubusercontent.com/web3cryptowallet/drive-py/master/assets/llog-demo.jpg)

### Dump log files to shell
```bash
$ cd log-test0/

# Differences log llog-diff.sh

$ cat llog-diff.sh 

# test0/t0 [
src= fileA md5-diff file c6f057b86584942e415435ffb1fa93d4
dst= fileC missed file d41d8cd98f00b204e9800998ecf8427e
dst= fileA md5-diff file 202cb962ac59075b964b07152d234b70
# test0/t0 ]

# All files llog-llogfiles.sh

$ cat llog-llogfiles.sh 

# files [
MD5 d41d8cd98f00b204e9800998ecf8427e test0/t0 fileB 0
MD5 c6f057b86584942e415435ffb1fa93d4 test0/t0 fileA 3
MD5 d41d8cd98f00b204e9800998ecf8427e test0/t1 fileC 0
MD5 d41d8cd98f00b204e9800998ecf8427e test0/t1 fileB 0
MD5 202cb962ac59075b964b07152d234b70 test0/t1 fileA 3
# files ]

# Resume llog-proc.sh 

$ cat llog-proc.sh 

# process [
PROCESS test0/t0 -> test0/t1
# process ]
# total [
src_files:2
src_dirs:0
src_size:3
dst_files:3
dst_dirs:0
dst_size:3
# total ]
```

## Tests

Run the regression suite with:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Redis tests require the Python `redis` package and `redis-server` on `PATH`
(or an executable path in `REDIS_SERVER`). They start and stop a private server
using a temporary Unix socket with persistence disabled. If either dependency
is missing, Redis tests are skipped. To run only Redis tests:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_redis.py' -v
```

Redis coverage reuses SQLite navigation assertions and compares node metadata,
directory sizes, and duplicate indexes with SQLite. It also checks reopening
and empty trees. Incremental updates remain SQLite-only.

## TODO

- TODO: files: Page up/down keys navigation (DataTable)
- TODO: actionsview: Delete key - remove from actlions list
- TODO: actionsview: highlight dir
- TODO: Shift-Delete: Select files to remove (DataTable, space select, multiple options)
- TODO: Config: -c config.sh arg 
- TODO: Config: config.sh section DB=mysql and LLOGSEARCHPATH=../llogd/:../llogd1/

## FAQ

### Why is the config in Livecomment format instead of JSON?

> Why is the config in Livecomment format instead of JSON?

Livecomment is an extensible format that can store multiple types of data. It supports both traditional Linux-style configuration formats (such as `fstab`-style mappings and plain text) as well as structured data like JSON, allowing different configuration styles to coexist in a single format.

## License
MIT

## Author
Github [@web3cryptowallet](https://github.com/web3cryptowallet)

Twitter [@web3wallet](https://twitter.com/web3wallet)

## Contribute
Just add an issue and push pull request

## Contact

[web3future@protonmail.com](mailto:web3future@protonmail.com)

## Sponsorship

If you appreciate this project, please star it on GitHub and/or sponsor on GitHub or donate crypto below.

Looking for sponsors to help fund development.

BTC 💰
18Bth1u3pSJzPrCf21tx1F6iSzA2fgKdfU

SOL Solana 💰
9gLVQr97baX3KrG9DyaUDd5FwXaiLcDuU6CK5RCNMnWu

ETH Ethereum 💰
0x072c709a8Ad95Fc182e0E2EEF834C3d944122f0b

USDT Ethereum 💰
0x072c709a8Ad95Fc182e0E2EEF834C3d944122f0b

DOGE Dogecoin 💰
DJP8425i4sGT4tSEXwEDRPJb4vJBGroJs6

LTC Litecoin 💰
ltc1q69gg9udgqnky60n7mfzfaj0w7lu80ujx6fysly

TRX Tron 💰
TLjkoQfnu7aRRbVRkEYN1vZPzW7ntuM4tn


## License

[MIT](https://github.com/web3cryptowallet/drive-py/blob/main/LICENSE)

## Version History

v0.91
 - added actions generation
 
v0.92
 - added a file indicator to the file list

v0.93
 - info: show dir status - n files

v0.94
 - info: show dir status - n files

v0.95
- BUGFIX: Shift+Del: Remove directories recursively
- TODO: ActionsView: Show the file status in the list
- BUGFIX: ActionsView: Wrong file is removed

v0.96
 - BUGFIX: vfs: sqlite: fix cloned files changes 

v0.97
- FIX: action apply

v0.98
- SQLITE: Add experimental `-u` incremental updates; `-b` rebuilds the cache. Both load one log at a time to limit memory usage
- TUI: Use MC Default at startup; press `t` to cycle through MC Default, MC Blue, and Textual Dark, with the shortcut listed in help and the footer
- TUI: Replace the file list with a DataTable showing Name, Size, and Files / Dups columns
- TUI: Adapt file selection, directory navigation, and cursor restoration to table rows; handle empty selections and display filenames as literal text
- FIX: Set the TUI file pane height to 100%
- TUI: Give the file and info panes equal widths (50% each)
- FIX: Preserve status circle colors under the cursor in both the file and info panes
- FIX: Use a portable Python 3 shebang for the TUI launcher
- REFACTOR: Split vfs.py into a vfs package with separate filesystem, node, path mapping, action, utility, and demo modules
- REFACTOR: Move the base, memory, SQLite, and Redis adapters into vfs/adapter while preserving public vfs imports and shared drive mappings
- TEST: Add regression coverage for memory and SQLite navigation, SQLite cache reopening, duplicate lookup, drive mappings, local metadata, and public exports
- DEV: Add run-test-llog.sh and run-test-tui.sh helpers for generating and browsing demo reports

v0.99

- TUI: Make prompt_toolkit the main `drive-tui.py`, with `run.sh` and `run-megadisks.sh` launchers using uv
- REFACTOR: Preserve the former Textual application, views, theme, launchers, and dependent tests in `texual.removed/`
- SCANNER: Add live drive maps with lite, medium, and heavy verification, independent scan controls, and normal/expert scheduling
- SCANNER: Save maps and resume positions per directory; promote checksum-verified new files into the VFS catalog
- TUI: Add context help with `h`, keep Size and Dups visible, and preserve file-status colors under selection
- TUI: Use **Shift+R** in the main view to clear the current directory's saved map and resume positions while retaining file records and checksums
- STORAGE: Skip unchanged scanner record writes across memory, SQLite, and Redis adapters

## Recomended projects

- [livecomment](https://github.com/d08ble/livecomment) project
- [bitchatX21](https://github.com/goldenwebb/bitchatX21) a better version of Bitchat for iOS

*AI-Independet code. Created through human work*

### Main file table

The main file pane shows **Name**, **Size**, and **Dups**, with left-aligned
metadata. Size and Dups reserve space so long names do not push them off-screen;
Name uses the remaining width and is clipped when necessary. Columns refit on
resize. The main file pane always shows its vertical scrollbar, including
short or empty listings. Directory rows retain total-file counts under the Dups heading.
Implementation and Rust handoff: [FEATURE-main-file-table.md](FEATURE-main-file-table.md).

### Live drive map

Original prompt, implementation contracts, update history, and Rust conversion
notes: [FEATURE-realtime-drive-scanner.md](FEATURE-realtime-drive-scanner.md).

Press **s** to open the live scanner for the **current VFS directory**, regardless
of the selected file/subdirectory. At `/` with `a` selected, it scans `/`.
The map dialog uses the main file pane’s solid pseudographic border and theme color.
Press **s** or **Esc** to close. **h** opens scanner help with all shortcuts and
symbols; **h/Esc** or **Close** returns without stopping scanning. The bottom
suggestion block has moved into this scrollable popup.
Scanning uses one background disk worker; expert has a separate bucket-selector
thread. Manual normal passes repeat after five seconds.
Closing saves the map per selected path and cancels the worker. Reopening restores
entries, packing settings, view position and scanner controls.

- **1 / 2 / 3** independently toggle **lite / medium / heavy** RUN/STOP.
  **RUN** appears in bold green; **STOP** appears in bold red.
  On opening, **lite → medium → heavy** runs once, then all modes stop. Changing
  1/2/3 (including Shift-start) cancels this startup sequence. Pending positions
  resume when saved. Lite builds buckets from database names/states and disk
  discoveries; new files show **?**. **r** toggles reading known file metadata
  in lite (off by default; directories still enumerate disk children).
  Lite recurses through all subfolders under the scan path, merging DB and disk
  entries. At the virtual root, this includes disk-only roots visible in the main
  list when the scanner opens, alongside DB roots and configured aliases.
  Directories show white **D** and have their own filter; medium and heavy skip
  them for verification. Medium also discovers new files/directories, then
  checks file presence/type/size; matching metadata is green. Heavy reads
  checksums, compares existing hashes or saves a new baseline in scanner storage.
  Successfully verified new files are also inserted into the VFS database with
  parent directories and hash indexes. Closing the scanner refreshes the main
  list, where these files show a green circle. Interrupted/failed hashes stay new.
  **t** switches heavy priority between **new-first / all** within each bucket;
  both process all files. Enabled passes run sequentially in one worker. Stop all to pause.
  Each mode saves its pending path on stop and resumes it on start/reopen.
  Interrupted hashes restart the unfinished file.
- **j** switches heavy bucket order: **normal** visits sequentially; **expert**
  uses a separate selector thread with a candidate pool built once and rebuilt
  when exhausted: **each tick picks one random starting bucket**,
  draws a length from **1–20**, then marks that many following eligible buckets
  blue in map order, wrapping at the end. It continuously appends ranges while
  scanning, skipping occupied/ineligible buckets without duplicates. **1–20 is
  the number added per tick**, and total blue work can exceed 20. New ranges are
  appended while earlier ranges scan, without waiting for a sequence to finish.
  Fewer are added only when fewer eligible unoccupied buckets remain.
  Buckets containing **? unverified files** are selected first, then other
  non-green buckets. Fully green buckets are skipped until **all file buckets
  are green**. Mixed ?/green buckets remain eligible. Directory-only buckets
  are skipped. **t** controls new/all priority inside
  each bucket. The scan worker consumes the queue in FIFO
  order, finishing each bucket without a time limit. Expert-only scanning reuses
  its checksum catalog between buckets to avoid repeated whole-map setup.
  SQLite groups each file's checksum/catalog writes and discovery/status writes
  into two short transactions, and skips empty expert bucket-start checkpoints.
  A local profiled run of 1,000 new 3-byte files improved from 17.3s to 7.8s
  (about six commits per file reduced to two, plus a final checkpoint). This
  isolates warm local SQLite scanning with an unbounded event queue and no UI;
  real-drive and UI performance can differ. Hash reads and event delivery occur
  outside these write transactions. Actual interrupted-bucket checkpoints persist.
  The selector keeps adding
  random-start ranges while scanning
  (a fresh random delay of 0.2–1 seconds after adding buckets; paused/unavailable work polled every
  50 ms). When the work queue empties, the scan worker immediately adds another
  random sequence, so the timer does not throttle hashing. Queued/processing buckets
  show blue backgrounds while heavy is on. Highlight updates apply only added or
  completed buckets; a full remap is needed when map grouping changes. Candidate
  ranges are removed without shifting the remaining pool. Pool building runs
  outside the shared lock; highlight refreshes defer if its snapshot lock is busy.
  Exhausted selection waits for catalog/queue/priority changes before searching
  again. Completing a bucket restores its normal background. Heavy scanning leaves your map
  cursor, file page and end-follow mode in place. Pausing keeps pending work in this
  window; closing retains the unfinished path checkpoint, not the entire queue.
  Switching j cancels startup; the automatic startup heavy pass stays finite/normal.
- With map or file-list focus, **]** moves deeper through the selected file
  row's directory ancestors; **[** moves back. For file `/a/b/c`, ] chooses `/a`, then `/a/b`.
  Both keys loop at the limits: for `/a/b/c/file`, **[** cycles
  `/a/b/c → /a/b → /a → /a/b/c`; **]** cycles in the opposite direction.
  The matching prefix in file-list paths is gold, including its trailing `/`:
  scope `a/b` colors `a/b/` in `a/b/file1`, while scope `a` colors only `a/`.
  The remaining filename keeps its normal color. **d** clears this highlight with the scope colors.
  Matching buckets get a random background while symbols keep their foreground.
  **f** fixes those colors; **c** clears all colors pinned with **f**, keeping
  the active scope and gold path highlight; **d** clears all colors. Fixed colors survive scope
  changes/repacking and are saved with the map. The active **[ / ]** scope color
  overrides pinned colors for matching buckets; leaving that scope reveals their
  saved colors. Press **f** again to replace the saved color. Highlighting is visual; scan
  targets and file filters stay independent.
- **Shift+1 / Shift+2 / Shift+3** starts that mode at the first file/path in the
  selected bucket, including while running. **! / @ / #** work in terminals that
  report shifted digits as characters. The scan continues through later map
  entries; heavy applies new/all priority after the cursor's first path. Empty
  maps do nothing. Lite discovers descendants in that suffix and preserves
  earlier entries until a later full scan. Mode start/stop also saves the map.
- **Arrows** move the map cursor; clicking a bucket selects it. The lower panel
  shows paths with colored status symbols matching the map, sizes, file totals
  and status counts, with up to 100 paths per page. Symbols keep their color under
  row selection; scanning rows retain the leading **S n%** progress text.
  Click a colored status-count button (such as **? unverified: 1**) to filter
  paths by that state. Click it again or **All** to remove the filter. Counts
  show bucket totals; file pages and errors follow matching paths. The active
  filter has a white background with black text, is saved with the map, and
  updates as scan states change. Buttons align left at their label width;
  the row scrolls horizontally when needed instead of scaling the buttons.
  **Right** at the last bucket enters follow mode: **>** marks the next empty cell
  and advances as new buckets arrive, scrolling and wrapping automatically.
  **Right** keeps follow mode active. Other arrows or **Page Up/Down** exit;
  clicking a real bucket exits too.
  The marker has no file details or Shift-start target. This mode is saved with
  the map and can also wait for the first bucket of an empty map.
- **m** switches between file-count and byte-size packing. **v** switches between
  fixed and scrolling packing (scrolling is the default). Map symbols occupy
  adjacent single-character cells across the available width. Bucket rows have
  no viewport cap; use the vertical scrollbar, wheel, arrows or **Page Up/Down**.
  Rows grow automatically; there is no Rows input. Edit **Paths/bucket** or
  **MiB/bucket** in the single-line settings row, then press **Enter**.
  Columns fit automatically with no Cols display; optional fixed
  packing uses the viewport as its cell budget. Scrolling size mode applies both limits; an oversized file gets
  its own bucket. The details list uses half its previous share of flexible height.
- The live scan info shows **paths/s**, **MB/s–PB/s** (MB, GB, TB, PB in 1,000-unit steps), **total paths** and **total size**
  across all three modes. Each completed visit counts, including repeat cycles;
  MB/s uses visited file sizes, not actual read bytes. Rates use only the last
  **five seconds** of completed visits/sizes, divided by five, and decay to zero
  after five idle seconds. Totals stay cumulative for this window. Counters reset on
  reopen. The current/last path stays visible, with its full path in a tooltip.
- **bucket N/total** on the Total-paths statistics line shows the first visible
  bucket and follows scrolling independently of selection. Empty maps show 0/0.
- Detail pages are numbered **1..N**, with as many numbered buttons as fit the
  width and ellipses for omitted ranges. The navigation row is
  `|< <-1000 <-100 <-10 < > >+10 >+100 >+1000 >|`; jumps stop at the first/last page.
  Click or drag the horizontal slider to seek. With the slider focused,
  **Left/Right** move one page and **Home/End** select first/last. Page zooming has
  been removed. **>** advances one page. File pages contain only as many rows as
  fit in the details panel, up to 100; the file list has no vertical scrollbar.
  Long paths have a **horizontal scrollbar**. With the file list focused,
  **Left/Right** pan horizontally. Live updates change rows in place and keep
  that position without briefly resetting to the left edge. Changing pages
  also preserves the horizontal position. Page height excludes the horizontal scrollbar. **Up** on
  the first file opens the previous page at its last file; **Down** on the last
  file opens the next page at its first file. The overall list endpoints clamp,
  and navigation follows the active status filter.
- White **?** means new/unverified, red **U** means missing from disk, green **●**
  means the latest metadata/checksum check matched, orange **M** means modified
  (white **U** is retained for legacy stored new states). For unknown files the
  details panel explains read/checksum errors. Mixed buckets display the highest
  priority state in that order: modified, missing, new, unverified, verified.
  A bucket containing both unverified and verified files shows a green **?**
  when unverified is its highest-priority state; unverified-only buckets stay white.
  Resting symbols have a black background; selection adds an underline and keeps
  the colors. The filled green circle matches the main files view.
  Details list all states. A white-on-red spinner animates updates for one
  second, including under the cursor; files currently being checked show **S n%** in the details list.

Existing VFS path IDs identify files. SQLite saves discoveries in a separate
`scan_paths` table; Redis uses a `scan_paths` hash; memory storage keeps them for
that adapter's lifetime. Additional JSON `scan_state` records store latest states,
new checksums, maps and per-mode pending-path positions; memory records last only for the adapter's lifetime.
Unchanged scanner records and existing discovery IDs are not rewritten, including
after reopening. Changed records/checkpoints still persist; live scan events and
counters update even when no persistence is needed.
Imported baseline nodes/hashes stay unchanged. Heavy detects same-size content
changes; medium's green metadata result does not certify file contents.
Unsupported checksums remain unverified; absent hashes are created by heavy.
Saved checksum paths remain discoverable even after deletion, so they show missing.
Directories are discovered by lite and excluded from verification; directory
symlinks are not traversed.
The virtual root scans configured/known drives, not the host root.
Map snapshots save on mode start/stop, cursor-start and close/shutdown; abrupt termination can lose the latest
snapshot. Changes appear on scan events; this is repeated scanning rather
than an OS filesystem watcher. Quick-view integration and bookmarks are deferred.
