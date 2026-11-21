# Version History

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
- TUI: Accept a startup directory such as `./drive-tui.py ~` or `./run.sh ~/mypath`, including paths with spaces and configured drive aliases
- REFACTOR: Preserve the former Textual application, views, theme, launchers, and dependent tests in `texual.removed/`
- LIVE MAP: Press `s` to scan the current VFS directory and display file-status buckets with live progress, path counts and throughput
- LIVE MAP: Show hashing speed during large files from bytes read/hashed over the last second, updating about every 0.1s; scale MB/s through PB/s and retain five-second paths/s and cumulative totals
- LIVE MAP: Show expert selected bucket count (queued plus processing), active-mode elapsed time and total processing time spent on the map; retain per-mode times across reopening and append `mode / total` at the end of the `Lite / Medium / Heavy` controls line, without a separate timing row as `M:SS` or `H:MM:SS` (hours continue beyond 24)
- LIVE MAP: Add independent lite discovery, medium metadata checks and heavy checksum verification; run lite → medium → heavy once on opening, with per-mode pause/resume and cursor-start controls
- LIVE MAP: Support packing by file count or size, fixed/scroll layouts, bucket limits, an end-follow cursor, status filters, paginated file details and horizontal scrolling
- LIVE MAP: Add normal/expert heavy scheduling; expert selects random sequences of 1–20 eligible buckets, marks queued work blue and processes it in FIFO order with immediate refill when empty
- LIVE MAP: Use `[` / `]` to cycle directory scopes, highlight matching file-path prefixes in gold and preview matching buckets over pinned colors; `f` pins colors, `c` clears pins and `d` clears scope and pins
- LIVE MAP: Save maps, controls and resume positions per directory; promote checksum-verified new files into the VFS catalog while retaining imported baselines
- TUI: Add context help with `h`, keep left-aligned Size and Dups visible beside clipped names, retain the vertical scrollbar and preserve file-status colors under selection
- TUI: Let `q` quit from every view, including help, Actions and scanner inputs
- TUI: Use **Shift+R** in the main view to clear the current directory's saved map and resume positions while retaining file records and checksums
- STORAGE: Skip unchanged scanner record writes across memory, SQLite, and Redis adapters
- PERFORMANCE: Move expert map projection and mode/order transitions off the UI thread; reduce SQLite processing overhead by grouping metadata writes and skipping empty expert checkpoints


v0.991

- TUI: Show the drive.py PNG logo at half size in root quick view on Kitty-compatible graphics terminals
- TUI: Press `v` to cycle all / media (images, videos, audio) / image / videos, with a three-second popup showing the selected filter; non-media files use compact gray lines only in graphics mode; directories remain visible in media-only mode only when they contain media in their subtree; `..` remains available
- TUI: Select a video for a large still preview, then click **Play** (or Tab to Play and press Enter); **Stop** ends playback. Video sits after Modified and before Other Duplicates, with controls below it; seek by clicking/scrolling the bar or focused Left/Right. Uses `ffprobe` (from FFmpeg) for video rotation and requires `python-mpv` and native `libmpv` (`sudo apt-get install libmpv2` on Ubuntu)
- TUI: Thumbnail HEIC/HEIF (pillow-heif), WebP/.web, AVIF and additional Pillow image formats; MOV/MP4/MKV/WebM/AVI/MTS and other video thumbnails require `ffmpeg` on PATH
- TUI: Toggle thumbnail graphics mode with `g`; `+`/`-` adjust icon display height down to one line while cached previews use 128 or 256 pixel bounds, centered and fitted, with filenames below; background workers prepare medium-quality cached JPEGs linked in the database
- TUI: Press Enter on an image to show a real image in quick view via term-image AutoImage.draw() on Kitty-compatible terminals (color block fallback elsewhere), with metadata and duplicate links; Tab scrolls the pane
- VIDEO: Play/Stop controls and a clickable, scrollable seek bar appear after Modified and before Other Duplicates; opening a video loads a large still without autoplay (selection with `y` on, Enter with `y` off)
- FIX: Suppress and filter Kitty graphics replies so they cannot navigate to root or toggle previews off
- FIX: Fit native video frames to smaller terminal viewports and keep the file list usable when video controls cannot fit
- FIX: Reduce playback blinking by displaying each new native frame before releasing the previous frame
- FIX: Apply video rotation explicitly before scaling to fix the portrait MOV crop assertion; isolate decoding in a child process so native failures cannot terminate the browser
- STORAGE: Cache medium-quality JPEG thumbnails at 128/256 pixel bounds, link cache IDs to source files in the database, and include thumbnail dimensions, source bytes and first-1-MiB SHA-256 in filenames; invalidate previews when source metadata, prefix content or JPEG quality changes

v0.992

- BOOKMARKS: Press `b` from any screen to toggle the selected file or directory; on `..`, bookmark the current directory. Bookmarked entries show `B` in both the file table and graphics view.
- BOOKMARKS: Press `j` to open the editable numbered list with equal-width list/preview panes. A green circle means the target exists on local storage; red means offline/missing. Arrows or clicks select and preview; Enter opens the item. With up to nine entries, press its number directly; for larger lists, Tab to the number field, type the number and press Enter.
- BOOKMARKS: Preview images and videos with the same quick view as the main screen: native Kitty images with block fallback, video posters, explicit Play/Stop and seeking. Text files have bounded previews; selecting a video never starts playback automatically.
- BOOKMARKS: Press `e` to edit the selected bookmark's VFS path, then Enter or Save path to save. Press `b` in bookmarks, Delete while the list is focused, or Remove to delete the bookmark. Tab moves between the list, preview, fields and buttons; Esc closes.
- BOOKMARKS: Save changes and cursor selection immediately to `.bookmarks.json` in the app's working directory. Restore bookmarks and the selected row/preview after reopening or restarting; accept older bookmark path-array files. Bookmark paths resolve configured aliases, local mount paths and original report prefixes; unavailable targets stay open for correction. File bookmarks open their parent directory, select the file and show its Info.
- TUI: Keep `g` for thumbnail graphics mode; use `J` (Shift+j) for scanner heavy normal/expert order.
- FIX: Highlight the selected Info row. Tab to Info, select a duplicate with arrows or a click, then Enter to open its directory and select the file. Delete queues the selected duplicate.

v0.993

- TUI: Press `.` with Files focused to hide/show dotfiles and dot-prefixed directories, including expanded subtrees. `..` remains visible; files are shown by default.
- FIX: Media replay defers saved seeks until loading completes; replay after EOF starts at zero. Bookmark `B` markers are bright cyan and bold in table and graphics modes.
- TUI: MP3 and other supported audio files show a purple ▶ in graphics mode. Select one and press **Play** or `p` in quick view; **Stop** and seeking use the same player controls as video; `p` toggles playback in main and bookmark previews. Native libmpv is required.
- TUI: Graphics tiles have a one-cell gutter. Preview height reserves bottom controls, the duplicates heading and the first duplicate row.
- TUI: In table or graphics mode, `u` toggles the selected directory subtree open/closed from Files, Info or player focus; select `..` to target all current subdirectories. Select a child to expand deeper, or press `o` to toggle one/all levels. Expanded directory names are bold over a lighter full-row background. Nested rows show relative paths; Enter opens a directory. Directory symlinks are followed, with repeated physical targets skipped to stop expansion loops.
- TUI: Info shows directory/file counts after Size, based on current visible entries including expanded subdirectories and active filters; `..` is excluded.
- TUI: Info header shows `y:auto/off`, `o:one/all`, `.:show/hide` (dotfile visibility) and `i:on/off`.
- TUI: Toggle automatic quick view with `y` (default off): on previews every selected file type in table and graphics modes; off requires Enter. Toggle image previews with `i` (default on); keep opened images stable during cursor movement
- TUI: Click or drag the Files scrollbar to move through the listing in table or graphics mode; the top and bottom select the first and last entry.
- FIX: Image quick view automatically rescales when terminal height or width changes, keeping the whole image visible.
- FIX: Graphics scrolling includes the final filename row. Automatic image quick view recalculates from stable viewport bounds when moving between landscape and portrait; previews preserve aspect ratio, with small images centered at natural pixel size.
- FIX: Moving file selection while a video plays retains its Info, preview and controls, including automatic quick view and graphics mode. Enter still explicitly opens another entry.
- LIVE MAP: Highlight the bucket cursor, including end-follow `>`, with a cyan background and black text.

v0.994

- TUI: Mark folders with `Space` without moving the cursor, or `Insert` to toggle and move down. `*` inverts marks on listed folders; `-` clears all marks. Files and `..` cannot be marked.
- TUI: Marked folder names appear gold in table and graphics views, including under the cursor. Entering another directory clears marks.
- SCANNER: `s` scans marked folders and their subtrees, or the current directory when nothing is marked. Save maps and resume positions separately for each folder set; marks remain session-only.
- CONTROLS: Thumbnail height now uses `+` to grow and `_` (Shift+-) to shrink, freeing `-` to clear folder marks.

v0.995

- HISTORY: `l` opens persistent action history with directory/file/image views, playback start/latest times and positions, desktop-open requests and queued removals. Image records use LiveLog subnodes; timestamps display without ISO separators or offsets.
- HISTORY CONTROLS: `Delete` removes one record, `Shift+Delete` clears all, `Enter` navigates to the recorded directory, and `t` filters present/missing paths with green/red indicators.
- NAVIGATION: `~` opens home; `/` opens a path command accepting paths or `cd PATH`. Empty Enter goes to `/`; Esc cancels.
- PATHS: Start with ordinary filenames; `x` toggles path prefixes across views. Store raw relative `test0/...` versus absolute `/home/...` sources, resolve relative paths per launch directory, and preserve configured mappings. Legacy catalogs can be migrated explicitly with backups using `migrate-paths.py`.
- SYMLINKS: Follow targets for file information and directory navigation; render a display-only `↗` suffix and target-presence status. Directory expansion guards physical-path cycles.
- STORAGE: Configure path-based SQLite fragments with `-refragment`; `-export-livelog DIR` exports catalogs with raw source paths for reimport.
- SOURCE: Maintain LiveComment navigation tags and synchronized feature/transplit documentation.

v0.996

- PREVIEW ORDER: `Shift+G` cycles sequence, random, page stride and range stride. All modes prioritize the visible page and start at its first pending image after a page change. Page stride finishes that page, then strides across the whole remaining range.
- GRAPHICS: Compact tiles follow actual icon width without fixed side borders, retain one-column gutters, and fit more images at 1–3 lines. Filenames match displayed image width; `-` shrinks previews in G mode and clears marks in table mode.
- PREVIEW MAP: Show cached colors and the selected media cell; click or drag to select files. Empty cells stay blank. Map and arrow navigation keep image rows visible above filenames.
- FORMATS: Decode HEIC/HEIF/HIF with pillow-heif, accept `.web` image aliases and verify WebP/AVIF plus real MTS video thumbnails through FFmpeg.
- CACHE: Include thumbnail bounds, source bytes and first-MiB SHA-256 in JPEG names. Unchanged source signatures reuse stored hashes; retain up to 128 prepared terminal previews. `k` clears current-directory-subtree thumbnails and `Shift+K` clears all thumbnail caches, then previews regenerate.
- EXPANSION: Press `u` again to cancel pending discovery. Reuse directory enumeration, skip extra metadata/duplicate passes, process rows and progress in 1,000-entry/file batches, and show the scanned-file count while working.
- FILTERS: `v` cycles all / media / image / videos and hides directories without matching descendants; graphics mode additionally hides directories without image/video descendants. Retain `..` and honor hidden-file settings.
- CLIPBOARD: `Ctrl+X` copies the selected absolute path; `Ctrl+Y` copies Info even with Info focused. Add platform clipboard fallbacks and built-in X11/XWayland ownership for Ubuntu, avoid fallback screen blinking, and show temporary copy feedback.
- DESKTOP: `Ctrl+F` reveals the selected file in Finder, Explorer or supported Linux file managers. Request foreground activation for existing Finder/X11 windows; desktop focus policy can still refuse it. `Ctrl+T` opens a terminal at the selected folder or file's parent.
- STARTUP: Initialize a navigable root for missing/empty SQLite catalogs. Select terminal color depth from capabilities, including Apple Terminal's 256-color palette and explicit overrides.
- PATH WINDOW: `/` starts at root with an immediate child list. Trailing slashes list directory children automatically; arrows/Tab and mouse select suggestions. `~` fills home from the initial root input. Persist successful file/directory targets in visible Path history; Ctrl+R focuses it and Enter recalls the selection.
- NOTIFICATIONS: Show clipboard and preview-order feedback in floating popups for three seconds. Remove the permanent bottom action row; desktop actions remain available through keyboard shortcuts.
- BLACKLIST: `!` excludes a directory from `u`; `X` bypasses/enables exclusions with red/green markers after bookmark B. `L` lists exclusions; Enter navigates and Delete removes an exclusion. Persist paths in `.blacklist.json`.
- QUICK VIEW: Combine status circle, clickable gray/cyan bookmark B and filename on one line.
- THEMES: Add White with white pane backgrounds and dark text. Keep digits inside words such as mp3 unhighlighted.
- LARGE LISTINGS: Cache filename measurements and preview-map indexes; bound thumbnail visibility lookup to viewport rows. Add a real 10,000-file regression. Initial folder loading remains synchronous; folder changes and u show Working feedback.
- README: Add a linked Star History chart with dark/light variants at the bottom.

v0.997

- SCANNING: Keep scans running while browsing files and playing media; `s` toggles the scan view, `Ctrl+P` pauses/resumes and `Ctrl+K` stops. Show progress outside the scan view.
- SCAN MODES: Default to finite expert processing of new files, then unknown files, then stop. Manually start Heavy with `3` to include previously verified files.
- STATISTICS: `Ctrl+S` opens per-scope mode 1/2/3 files, decimal MB and time for current scan, current session, last non-empty session and lifetime totals. Persist totals in SQLite/Redis; `v` changes current/total ordering.
- CONVERSION: Add a persistent video conversion queue with submit/start/pause/stop/clear and convert-now controls. Export beside each source in `youtube-conv/`, with network presets, H.264/H.265, CRF, quality, resolution, bitrate and editable size targets. Preview trim points, click the slider or drag time fields by 0.1 seconds, and copy the FFmpeg command. Exports remain local.
- BLACKLIST / TRASH: Apply directory exclusions to scanning, mark excluded chunks with a red `!`, and use `Ctrl+B` to show/hide blacklisted files. `Ctrl+D` archives database records in D without deleting disk files; `D` opens the archive.
- PLAYER: Fit compact controls in small panes, support audio-only video containers, add a session mute toggle and remove angle-bracket button decorations.
- PREFERENCES / STARTUP: Save the `o` expansion-depth preference in the database. Restore the last path when no startup path is supplied, falling back to the launch directory on first start.
- MISSING FILES: Color files absent from disk red in graphics mode; `Ctrl+U` shows/hides them while retaining directories for navigation.
- HELP: Show a bordered three-column shortcut index with short labels, detailed selection preview and `/` search with highlighted matches.
- HISTORY: Add stable row numbers, lazy row formatting, shared background presence checks and coalesced background saves with exit flushing. `F5` refreshes presence; `v` toggles bounded text/directory/image/video-still previews. Hold the left mouse button and drag to move the history cursor.
- FILENAMES: `Shift+Left/Right` pans long names; `Shift+Home/End` and `Shift+PageUp/PageDown` both reveal the beginning/end. Click or drag rectangular horizontal scrollbars across file lists. Limits use the longest name/row plus a trailing space that retains selection highlighting; main Size/Files/Dups stay fixed.
- BOOKMARKS: Use equal-width list/preview panes. Green/red circles show mapped filesystem target presence, including configured aliases; missing bookmarks remain editable/removable.
