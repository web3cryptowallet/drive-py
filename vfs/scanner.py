"""Single-worker disk verification and event-driven, sequential map buckets.

Discovery records remain separate; verified new files join the VFS baseline.
Existing comparison baselines are preserved.
Path IDs have the same meaning as nodes.id throughout the existing VFS.
"""
# IMPORT SCANNER DEPENDENCIES [
from collections import Counter, deque
from contextlib import nullcontext
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
import random
from queue import Full
from threading import Event, RLock, Thread
import sqlite3
import stat
import time

from .adapter.sqlite import SQLiteDBAdapter
from .scanner_pool import CandidatePool
from .paths import aliases, get_real_path
from .nodes import VFSNode
# IMPORT SCANNER DEPENDENCIES ]
# DESCRIBE A DISCOVERED FILE AND ITS VERIFICATION STATE [
@dataclass(frozen=True)
class ScanEntry:
    id: str
    path: str
    is_dir: bool
    size: int = 0
    state: str = 'unknown'
    progress: int | None = None
    error: str = ''

    # NORMALIZE SCAN ENTRY [
    def __post_init__(self):
        if self.is_dir:
            object.__setattr__(self, 'state', 'directory')
            object.__setattr__(self, 'size', 0)
            object.__setattr__(self, 'progress', None)
        elif self.state == 'directory':
            object.__setattr__(self, 'state', 'unknown')
    # NORMALIZE SCAN ENTRY ]
# DESCRIBE A DISCOVERED FILE AND ITS VERIFICATION STATE ]
# REPORT SCAN COUNTS AND RECENT PROCESSING RATES [
@dataclass(frozen=True)
class ScanStats:
    path: str = ''
    bytes_read: int = 0
    elapsed: float = 0.
    active: bool = False

    paths: int = 0
    size_scanned: int | None = None

    # None preserves compatibility for callers constructing legacy statistics.
    rate_samples: tuple | None = None
    hash_samples: tuple | None = None
    hash_started: float | None = None

    # CALCULATE RECENT SCAN THROUGHPUT [
    def recent_rate(self, column):
        now = time.monotonic()
        return sum(sample[column] for sample in self.rate_samples
                   if 0 <= now - sample[0] < 5) / 5
    # CALCULATE RECENT SCAN THROUGHPUT ]
    # PATHS PER SECOND [
    @property
    def paths_per_second(self):
        if self.rate_samples is not None:
            return self.recent_rate(1)
        return self.paths / self.elapsed if self.active and self.elapsed > 0 else 0.
    # PATHS PER SECOND ]
    # MB PER SECOND [
    @property
    def mb_per_second(self):
        if self.hash_samples is not None:
            now = time.monotonic()
            duration = min(1., max(0., now - self.hash_started)) if self.hash_started is not None else 0.
            size = sum(size for stamp, size in self.hash_samples if 0 <= now - stamp < 1)
            return size / duration / 1_000_000 if duration > 0 else 0.
        if self.rate_samples is not None:
            return self.recent_rate(2) / 1_000_000
        size = self.bytes_read if self.size_scanned is None else self.size_scanned
        return size / self.elapsed / 1_000_000 if self.active and self.elapsed > 0 else 0.
    # MB PER SECOND ]
# REPORT SCAN COUNTS AND RECENT PROCESSING RATES ]
# TRACK ACTIVE SCAN MODE AND ACCUMULATED MAP TIME [
class ScanTiming:
    """Per-map mode processing time; pauses/watch delays are excluded."""
    # INITIALIZE SCAN TIMING [
    def __init__(self, elapsed=(0., 0., 0.)):
        self.elapsed = list(elapsed)
        self.run_elapsed = [0., 0., 0.]
        self.run_tokens = [object(), object(), object()]
        self.mode = 0
        self.started = time.monotonic()
        self.lock = RLock()
    # INITIALIZE SCAN TIMING ]
    # SWITCH ACTIVE SCAN MODE AND ACCOUNT FOR TIME [
    def switch(self, mode, token=None):
        with self.lock:
            now = time.monotonic()
            if self.mode:
                spent = max(0., now - self.started)
                self.elapsed[self.mode - 1] += spent
                self.run_elapsed[self.mode - 1] += spent
            if mode and self.run_tokens[mode - 1] != token:
                self.run_elapsed[mode - 1] = 0.
                self.run_tokens[mode - 1] = token
            self.mode, self.started = mode, now
    # SWITCH ACTIVE SCAN MODE AND ACCOUNT FOR TIME ]
    # SNAPSHOT FOR SCAN TIMING [
    def snapshot(self):
        with self.lock:
            elapsed = self.elapsed.copy()
            if self.mode:
                elapsed[self.mode - 1] += max(0., time.monotonic() - self.started)
            return self.mode, tuple(elapsed)
    # SNAPSHOT FOR SCAN TIMING ]
    # DISPLAY SNAPSHOT FOR SCAN TIMING [
    def display_snapshot(self):
        with self.lock:
            spent = max(0., time.monotonic() - self.started) if self.mode else 0.
            current = self.run_elapsed[self.mode - 1] + spent if self.mode else 0.
            return current, sum(self.elapsed) + spent
    # DISPLAY SNAPSHOT FOR SCAN TIMING ]
# TRACK ACTIVE SCAN MODE AND ACCUMULATED MAP TIME ]
# PERSIST SCANNER METADATA AND RESUME POSITIONS [
class ScanStore:
    """Scanner-owned records, separate from the imported comparison baseline."""
    # INITIALIZE SCAN STORE [
    def __init__(self, db):
        self.db = db
        if isinstance(db, SQLiteDBAdapter):
            db.conn.execute("CREATE TABLE IF NOT EXISTS scan_state (kind TEXT, key TEXT, value TEXT, PRIMARY KEY(kind, key))")
            db.conn.commit()
        elif not hasattr(db, 'client') and not hasattr(db, 'scan_state'):
            db.scan_state = {}
    # INITIALIZE SCAN STORE ]
    # READ A STORED SCANNER RECORD [
    def get(self, kind, key, default=None):
        db = self.db
        if isinstance(db, SQLiteDBAdapter):
            row = db.conn.execute('SELECT value FROM scan_state WHERE kind=? AND key=?', (kind, key)).fetchone()
            value = row[0] if row else None
        elif hasattr(db, 'client'):
            value = db.client.hget('scan_state:' + kind, key)
        else:
            value = db.scan_state.get((kind, key))
        return json.loads(value) if value is not None else default
    # READ A STORED SCANNER RECORD ]
    # ITERATE STORED LIVELOG OR SCANNER RECORDS [
    def items(self, kind):
        db = self.db
        if isinstance(db, SQLiteDBAdapter):
            rows = db.conn.execute('SELECT key, value FROM scan_state WHERE kind=?', (kind,))
        elif hasattr(db, 'client'):
            rows = db.client.hgetall('scan_state:' + kind).items()
        else:
            rows = ((key, value) for (record_kind, key), value in db.scan_state.items()
                    if record_kind == kind)
        return {(key.decode() if isinstance(key, bytes) else key): json.loads(value)
                for key, value in rows}
    # ITERATE STORED LIVELOG OR SCANNER RECORDS ]
    # DELETE EXACTLY ONE SCANNER RECORD, LEAVING OTHER SCOPES UNTOUCHED [
    def delete(self, kind, key):
        """Delete exactly one scanner record, leaving other scopes untouched."""
        db = self.db
        if isinstance(db, SQLiteDBAdapter):
            if db.conn.execute('SELECT 1 FROM scan_state WHERE kind=? AND key=?', (kind, key)).fetchone() is None:
                return False
            with db.conn:
                result = db.conn.execute('DELETE FROM scan_state WHERE kind=? AND key=?', (kind, key))
            return bool(result.rowcount)
        if hasattr(db, 'client'):
            return bool(db.client.hdel('scan_state:' + kind, key))
        return db.scan_state.pop((kind, key), None) is not None
    # DELETE EXACTLY ONE SCANNER RECORD, LEAVING OTHER SCOPES UNTOUCHED ]
    # PERSIST ONLY CHANGED JSON DATA; RETURN WHETHER A WRITE WAS NEEDED [
    def put(self, kind, key, value):
        """Persist only changed JSON data; return whether a write was needed."""
        value = json.dumps(value, sort_keys=True)
        db = self.db
        if isinstance(db, SQLiteDBAdapter):
            row = db.conn.execute('SELECT value FROM scan_state WHERE kind=? AND key=?',
                                  (kind, key)).fetchone()
            previous = row[0] if row else None
        elif hasattr(db, 'client'):
            previous = db.client.hget('scan_state:' + kind, key)
            if isinstance(previous, bytes):
                previous = previous.decode()
        else:
            previous = db.scan_state.get((kind, key))
        # Accept older JSON with different key order/spacing without rewriting it.
        if previous == value or (previous is not None and json.loads(previous) == json.loads(value)):
            return False
        if isinstance(db, SQLiteDBAdapter):
            with db.write_transaction():
                db.conn.execute('INSERT OR REPLACE INTO scan_state VALUES (?, ?, ?)', (kind, key, value))
        elif hasattr(db, 'client'):
            db.client.hset('scan_state:' + kind, key, value)
        else:
            db.scan_state[kind, key] = value
        return True
    # PERSIST ONLY CHANGED JSON DATA; RETURN WHETHER A WRITE WAS NEEDED ]
# PERSIST SCANNER METADATA AND RESUME POSITIONS ]
# INTERNAL FIFO THAT RECORDS MEMBERSHIP DELTAS FOR THE MAP OVERLAY [
class SelectionQueue(deque):
    """Internal FIFO that records membership deltas for the map overlay."""
    # INITIALIZE SELECTION QUEUE [
    def __init__(self, changed):
        super().__init__()
        self.changed = changed
    # INITIALIZE SELECTION QUEUE ]
    # APPEND PENDING WORK OR FILE OPERATIONS [
    def append(self, ids):
        super().append(ids)
        self.changed(ids, 1)
    # APPEND PENDING WORK OR FILE OPERATIONS ]
    # PREPEND PENDING SCAN WORK [
    def appendleft(self, ids):
        super().appendleft(ids)
        self.changed(ids, 1)
    # PREPEND PENDING SCAN WORK ]
    # EXTEND FOR SELECTION QUEUE [
    def extend(self, values):
        for ids in values:
            self.append(ids)
    # EXTEND FOR SELECTION QUEUE ]
    # TAKE THE NEXT PENDING SCAN ITEM [
    def popleft(self):
        ids = super().popleft()
        self.changed(ids, -1)
        return ids
    # TAKE THE NEXT PENDING SCAN ITEM ]
    # CLEAR SELECTION QUEUE [
    def clear(self):
        while self:
            self.popleft()
    # CLEAR SELECTION QUEUE ]
# INTERNAL FIFO THAT RECORDS MEMBERSHIP DELTAS FOR THE MAP OVERLAY ]
# COORDINATE SCAN MODES AND PENDING WORK [
class ScanControls:
    """Independent mode flags and wake signal shared with the worker."""
    # INITIALIZE SCAN CONTROLS [
    def __init__(self, modes=(True, False, False), read_known=False, new_first=True,
                 startup=False, heavy_order='normal'):
        self.startup_mode = 1 if startup else None
        self.modes = (True, False, False) if startup else tuple(modes)
        self.heavy_order = heavy_order if heavy_order in ('normal', 'expert') else 'normal'
        self.buckets = ()
        self.read_known = read_known
        self.new_first = new_first
        self.wake = Event()
        self.lock = RLock()
        self.epochs = (0, 0, 0)
        self.run_revisions = (0, 0, 0)
        self.requests = ((0, None),) * 3
        self.entry_priorities = {}
        self.selection_changes = {}
        self.selection_revision = 0
        self.expert_queue = SelectionQueue(self._selection_changed)
        self._expert_current = None
        self.selector_batch = 0
        self.selector_next = 0
        self.priority_revision = 0
        self.selector_pool = CandidatePool()
        self.selector_catalog = None
        self.selector_builder = None
        self.selector_empty_signature = None
    # INITIALIZE SCAN CONTROLS ]
    # SELECTION CHANGED FOR SCAN CONTROLS [
    def _selection_changed(self, ids, delta):
        key = id(ids)
        change = self.selection_changes.get(key)
        total = delta + (change[1] if change else 0)
        if total:
            self.selection_changes[key] = (ids, total)
        else:
            self.selection_changes.pop(key, None)
        self.selection_revision += 1
    # SELECTION CHANGED FOR SCAN CONTROLS ]
    # EXPERT CURRENT FOR SCAN CONTROLS [
    @property
    def expert_current(self):
        return self._expert_current
    # EXPERT CURRENT FOR SCAN CONTROLS ]
    # EXPERT CURRENT FOR SCAN CONTROLS [
    @expert_current.setter
    def expert_current(self, ids):
        if self._expert_current is not None:
            self._selection_changed(self._expert_current, -1)
        self._expert_current = ids
        if ids is not None:
            self._selection_changed(ids, 1)
    # EXPERT CURRENT FOR SCAN CONTROLS ]
    # SELECTED BUCKETS FOR SCAN CONTROLS [
    @property
    def selected_buckets(self):
        with self.lock:
            return ((self.expert_current,) if self.expert_current else ()) + tuple(self.expert_queue)
    # SELECTED BUCKETS FOR SCAN CONTROLS ]
    # EXPERT ELIGIBLE INDICES [
    def expert_eligible_indices(self, buckets, priorities=None):
        priorities_by_path = self.entry_priorities if priorities is None else priorities
        tiers = {}
        for index, ids in enumerate(buckets):
            priorities = [priorities_by_path[path] for path in ids
                          if path in priorities_by_path]
            if priorities:
                tiers[index] = (0 if any(value < 2 for value in priorities) else
                                1 if any(value != 3 for value in priorities) else 2)
        tier = min(tiers.values(), default=None)
        return {index for index, value in tiers.items() if value == tier}
    # EXPERT ELIGIBLE INDICES ]
    # SELECTOR-ONLY: ENQUEUE THE NEXT ELIGIBLE FILE BUCKET IN MAP ORDER [
    def enqueue_expert(self, eligible=None, buckets=None):
        """Selector-only: enqueue the next eligible file bucket in map order."""
        with self.lock:
            if not self.modes[2] or self.heavy_order != 'expert' or self.startup_mode is not None:
                return False
            if self.selector_builder is not None:
                return False
            occupied = {path for ids in self.selected_buckets for path in ids}
            if not self.buckets:
                return False
            buckets = self.buckets if buckets is None else buckets
            eligible = self.expert_eligible_indices(buckets) if eligible is None else eligible
            count = len(buckets)
            for offset in range(count):
                index = (self.selector_next + offset) % count
                if index not in eligible:
                    continue
                ids = buckets[index]
                if any(path in occupied for path in ids):
                    continue
                if not any(path in self.entry_priorities for path in ids):
                    continue
                self.selector_pool = CandidatePool()
                self.expert_queue.append(ids)
                self.selector_next = (index + 1) % count
                self.wake.set()
                return True
            return False
    # SELECTOR-ONLY: ENQUEUE THE NEXT ELIGIBLE FILE BUCKET IN MAP ORDER ]
    # SNAPSHOT UNDER THE SHARED LOCK; BUILD ONCE OUTSIDE IT [
    def prepare_expert_pool(self):
        """Snapshot under the shared lock; build once outside it."""
        with self.lock:
            if not self.modes[2] or self.heavy_order != 'expert' or self.startup_mode is not None:
                return False
            buckets = self.buckets
            if self.selector_catalog is not buckets:
                self.selector_pool = CandidatePool()
                self.selector_catalog = buckets
                self.selector_empty_signature = None
                self.selector_builder = None
            if self.selector_pool:
                return True
            signature = (self.priority_revision, self.selection_revision, self.epochs)
            if self.selector_builder is not None or signature == self.selector_empty_signature:
                return False
            token = self.selector_builder = object()
            priorities = self.entry_priorities.copy()
            occupied_buckets = self.selected_buckets
        try:
            occupied = {path for ids in occupied_buckets for path in ids}
            eligible = self.expert_eligible_indices(buckets, priorities)
            pool = CandidatePool(sorted(index for index in eligible
                                        if not any(path in occupied for path in buckets[index])))
            with self.lock:
                if (self.selector_builder is not token or self.buckets is not buckets or
                        not self.modes[2] or self.heavy_order != 'expert' or
                        self.startup_mode is not None):
                    return False
                self.selector_pool = pool
                self.selector_empty_signature = signature if not pool else None
                return bool(pool)
        finally:
            with self.lock:
                if self.selector_builder is token:
                    self.selector_builder = None
    # SNAPSHOT UNDER THE SHARED LOCK; BUILD ONCE OUTSIDE IT ]
    # ENQUEUE EXPERT BATCH [
    def enqueue_expert_batch(self):
        if not self.prepare_expert_pool():
            return 0
        with self.lock:
            if (not self.modes[2] or self.heavy_order != 'expert' or
                    self.startup_mode is not None or self.selector_catalog is not self.buckets or
                    not self.selector_pool):
                return 0
            requested = min(random.randint(1, 20), len(self.selector_pool))
            first = random.choice(self.selector_pool)
            chosen = self.selector_pool.consume(first, requested)
            for index in chosen:
                self.expert_queue.append(self.buckets[index])
            self.selector_next = (chosen[-1] + 1) % len(self.buckets)
            self.selector_batch = len(chosen)
            self.wake.set()
            return len(chosen)
    # ENQUEUE EXPERT BATCH ]
    # CLAIM EXPERT FOR SCAN CONTROLS [
    def claim_expert(self):
        with self.lock:
            if (not self.modes[2] or self.heavy_order != 'expert' or
                    self.expert_current is not None or not self.expert_queue):
                return None
            self.expert_current = self.expert_queue.popleft()
            return self.expert_current
    # CLAIM EXPERT FOR SCAN CONTROLS ]
    # FINISH EXPERT FOR SCAN CONTROLS [
    def finish_expert(self, interrupted=False):
        with self.lock:
            ids = self.expert_current
            self.expert_current = None
            if interrupted and ids and self.heavy_order == 'expert':
                self.expert_queue.appendleft(ids)
    # FINISH EXPERT FOR SCAN CONTROLS ]
    # CANCEL STARTUP FOR SCAN CONTROLS [
    def cancel_startup(self):
        with self.lock:
            if self.startup_mode is not None:
                self.startup_mode = None
                self.epochs = tuple(value + 1 for value in self.epochs)
    # CANCEL STARTUP FOR SCAN CONTROLS ]
    # ADVANCE STARTUP FOR SCAN CONTROLS [
    def advance_startup(self, mode):
        with self.lock:
            if self.startup_mode == mode:
                self.startup_mode = mode + 1 if mode < 3 else None
                self.modes = tuple(self.startup_mode == index for index in (1, 2, 3))
                self.run_revisions = tuple(value + (self.startup_mode == i + 1)
                                           for i, value in enumerate(self.run_revisions))
    # ADVANCE STARTUP FOR SCAN CONTROLS ]
    # TOGGLE ORDER FOR SCAN CONTROLS [
    def toggle_order(self):
        with self.lock:
            self.cancel_startup()
            self.heavy_order = 'expert' if self.heavy_order == 'normal' else 'normal'
            self.expert_queue.clear()
            self.selector_builder = None
            self.selector_empty_signature = None
            self.selector_pool = CandidatePool()
            self.epochs = tuple(value + (i == 2) for i, value in enumerate(self.epochs))
            self.wake.set()
    # TOGGLE ORDER FOR SCAN CONTROLS ]
    # TOGGLE FOR SCAN CONTROLS [
    def toggle(self, mode):
        with self.lock:
            self.cancel_startup()
            self.modes = tuple(not value if index == mode - 1 else value
                               for index, value in enumerate(self.modes))
            if self.modes[mode - 1]:
                self.run_revisions = tuple(value + (i == mode - 1)
                                           for i, value in enumerate(self.run_revisions))
            self.epochs = tuple(value + (index == mode - 1)
                                for index, value in enumerate(self.epochs))
            self.wake.set()
    # TOGGLE FOR SCAN CONTROLS ]
    # START FROM FOR SCAN CONTROLS [
    def start_from(self, mode, path):
        with self.lock:
            self.cancel_startup()
            index = mode - 1
            self.run_revisions = tuple(value + (i == index)
                                       for i, value in enumerate(self.run_revisions))
            self.requests = tuple((value[0] + 1, path) if i == index else value
                                  for i, value in enumerate(self.requests))
            self.epochs = tuple(value + (i == index) for i, value in enumerate(self.epochs))
            self.modes = tuple(True if i == index else value for i, value in enumerate(self.modes))
            if mode == 3 and self.heavy_order == 'expert':
                self.selector_builder = None
                self.selector_empty_signature = None
                self.selector_pool = CandidatePool()
                self.expert_queue.clear()
                selected = next(((i, ids) for i, ids in enumerate(self.buckets) if path in ids), None)
                if selected:
                    bucket_index, ids = selected
                    self.expert_queue.append(ids)
                    self.selector_batch = 1
                    self.selector_next = (bucket_index + 1) % len(self.buckets)
            self.wake.set()
    # START FROM FOR SCAN CONTROLS ]
# COORDINATE SCAN MODES AND PENDING WORK ]
# DISCOVER AND VERIFY FILES IN BACKGROUND SCAN PASSES [
class DriveScanner:
    """One disk worker with independently enabled discovery/metadata/hash passes."""
    # INITIALIZE DRIVE SCANNER [
    def __init__(self, db, path, events, stop, interval=5, controls=None, entries=(), root_names=(), timing=None, scan_roots=(), storage_path=None):
        self.source = db
        self.root_names = tuple(root_names)
        self.path = path.rstrip('/')
        self.scan_roots = tuple(scan_roots)
        self.storage_path = storage_path or self.path or '/'
        self.events, self.stop, self.interval = events, stop, interval
        self.controls = controls or ScanControls()
        self.timing = timing if timing is not None else ScanTiming()
        self.entries = {entry.id: replace(entry, progress=None) for entry in entries}
        self.previous_ids = set(self.entries)
        self.remembered = set()
        self.paths_table_ready = False
        self.current_path = self.path or '/'
        self.bytes_read = self.paths = self.size_scanned = 0
        self.started = time.monotonic()
        self.last_stats = 0.
        self.current_mode = 0
        self.elapsed = 0.
        self.checkpoints = None
        self.requests_seen = [0, 0, 0]
        self.active_epoch = 0
        self.expert_scanned = False
        self.selector_thread = None
        self.selector_stop = Event()
        self.rate_samples = deque()
        self.hash_samples = deque()
        self.hash_started = None
        self.baseline_known = {}
        self.expert_initialized = False
        self.checksums = None
    # INITIALIZE DRIVE SCANNER ]
    # DELIVER SCANNER EVENTS WITH BACKPRESSURE [
    def emit(self, event):
        while not self.stop.is_set():
            try:
                self.events.put(event, timeout=.1)
                return
            except Full:
                pass
    # DELIVER SCANNER EVENTS WITH BACKPRESSURE ]
    # REPORT STATS FOR DRIVE SCANNER [
    def report_stats(self, *, path=None, read=0, completed_size=None, force=False, active=True):
        if path is not None:
            self.current_path = path
        self.bytes_read += read
        now = time.monotonic()
        if read:
            if self.hash_samples and now - self.hash_samples[-1][0] < .1:
                stamp, size = self.hash_samples.pop()
                self.hash_samples.append((stamp, size + read))
            else:
                self.hash_samples.append((now, read))
        while self.hash_samples and now - self.hash_samples[0][0] >= 1:
            self.hash_samples.popleft()
        if completed_size is not None:
            if self.rate_samples and now - self.rate_samples[-1][0] < .1:
                stamp, paths, size = self.rate_samples.pop()
                self.rate_samples.append((stamp, paths + 1, size + completed_size))
            else:
                self.rate_samples.append((now, 1, completed_size))
        while self.rate_samples and now - self.rate_samples[0][0] >= 5:
            self.rate_samples.popleft()
        if force or now - self.last_stats >= .1:
            self.emit(('stats', ScanStats(self.current_path, self.bytes_read,
                                         self.elapsed + max(0., now - self.started), active,
                                         self.paths, self.size_scanned, tuple(self.rate_samples),
                                         tuple(self.hash_samples), self.hash_started)))
            self.last_stats = now
    # REPORT STATS FOR DRIVE SCANNER ]
    # CHECK WHETHER THE REQUESTED SCAN MODE CAN RUN [
    def enabled(self, mode):
        return (not self.stop.is_set() and self.controls.modes[mode - 1] and
                (self.current_mode != mode or
                 self.active_epoch == self.controls.epochs[mode - 1]))
    # CHECK WHETHER THE REQUESTED SCAN MODE CAN RUN ]
    # BEGIN MODE FOR DRIVE SCANNER [
    def begin_mode(self, mode):
        self.timing.switch(mode, self.controls.run_revisions[mode - 1])
        self.current_mode = mode
        self.active_epoch = self.controls.epochs[mode - 1]
        revision, anchor = self.controls.requests[mode - 1]
        key = str(mode)
        if revision != self.requests_seen[mode - 1]:
            self.requests_seen[mode - 1] = revision
            paths = list(self.entries)
            if anchor in paths:
                paths = paths[paths.index(anchor):]
            if mode in (1, 2):
                frontier = self.discovery_frontier(paths)
                self.checkpoints['1' if mode == 1 else '2-discovery'] = {
                    'stack': list(reversed(frontier or list(self.scan_roots or (self.path,)))),
                    'seen': [], 'partial': True}
            if mode != 1:
                self.checkpoints[key] = {'remaining': paths, 'first': anchor}
        if self.checkpoints.get(key) is None:
            self.checkpoints[key] = (
                {'stack': list(self.scan_roots or (self.path,)), 'seen': [], 'partial': False} if mode == 1
                else {'remaining': ([] if mode == 3 and self.controls.heavy_order == 'expert'
                                    and self.controls.startup_mode is None else list(self.entries)),
                      'first': None})
        # The empty expert checkpoint is a transient bucket placeholder, not
        # resumable work. Persist the actual bucket remainder after processing.
        if not (mode == 3 and self.controls.heavy_order == 'expert' and
                self.controls.startup_mode is None and
                not self.checkpoints[key]['remaining']):
            self.save_positions()
    # BEGIN MODE FOR DRIVE SCANNER ]
    # DISCOVERY FRONTIER FOR DRIVE SCANNER [
    def discovery_frontier(self, paths):
        frontier, selected = [], set()
        for path in paths:
            parent = path.rpartition('/')[0]
            while parent and parent not in selected:
                parent = parent.rpartition('/')[0]
            if not parent:
                frontier.append(path)
                selected.add(path)
        return frontier
    # DISCOVERY FRONTIER FOR DRIVE SCANNER ]
    # FINISH STARTUP MODE [
    def finish_startup_mode(self, mode):
        if (self.enabled(mode) and self.checkpoints.get(str(mode)) is None and
                (mode != 2 or self.checkpoints.get('2-discovery') is None)):
            self.controls.advance_startup(mode)
    # FINISH STARTUP MODE ]
    # SAVE POSITIONS FOR DRIVE SCANNER [
    def save_positions(self):
        self.store.put('position', self.storage_path, self.checkpoints)
    # SAVE POSITIONS FOR DRIVE SCANNER ]
    # SELECT BUCKETS FOR DRIVE SCANNER [
    def select_buckets(self):
        exhausted = None
        while not self.stop.is_set() and not self.selector_stop.is_set():
            with self.controls.lock:
                signature = (id(self.controls.buckets), self.controls.priority_revision,
                             self.controls.modes, self.controls.heavy_order,
                             self.controls.startup_mode, len(self.controls.expert_queue),
                             self.controls.expert_current)
            selected = (0 if signature == exhausted else
                        self.controls.enqueue_expert_batch())
            exhausted = None if selected else signature
            self.selector_stop.wait(random.uniform(.2, 1.0) if selected else .05)
    # SELECT BUCKETS FOR DRIVE SCANNER ]
    # RUN DRIVE SCANNER [
    def run(self):
        self.selector_thread = Thread(target=self.select_buckets,
                                      name='drive-bucket-selector', daemon=True)
        self.selector_thread.start()
        db = self.source
        owns_connection = isinstance(db, SQLiteDBAdapter)
        try:
            if owns_connection:
                if hasattr(self.source, 'routes'):
                    db = type(self.source)(self.source.db_path)
                    db.conn.execute('PRAGMA busy_timeout=2000')
                else:
                    db = object.__new__(SQLiteDBAdapter)
                    db.conn = sqlite3.connect(self.source.db_path, timeout=2)
                    db.conn.row_factory = sqlite3.Row
            while not self.stop.is_set():
                self.controls.wake.clear()
                if not any(self.controls.modes):
                    self.emit(('phase', 'Stopped'))
                    while not self.stop.is_set() and not self.controls.wake.wait(.1):
                        pass
                    continue
                self.scan_once(db)
                if self.controls.modes[2] and self.controls.heavy_order == 'expert':
                    if not self.expert_scanned:
                        self.controls.wake.wait(.1)
                    continue
                self.emit(('phase', f'Watching — next scan in {self.interval:g} seconds'
                           if any(self.controls.modes) else 'Stopped'))
                # Short waits also honor popup cancellation while every mode is stopped.
                deadline = time.monotonic() + self.interval
                while not self.stop.is_set() and time.monotonic() < deadline:
                    if self.controls.wake.wait(.1):
                        break
        except Exception as exc:
            self.report_stats(force=True, active=False)
            self.emit(('phase', f'Scan stopped: {exc}'))
        finally:
            self.selector_stop.set()
            self.selector_thread.join(2)
            if owns_connection and db is not self.source:
                db.conn.close()
    # RUN DRIVE SCANNER ]
    # PERSIST THE SCANNED FILE ID TO PATH MAPPING [
    def remember(self, db, entry):
        if entry.id in self.remembered:
            return
        if isinstance(db, SQLiteDBAdapter):
            if not self.paths_table_ready:
                with db.write_transaction():
                    db.conn.execute('CREATE TABLE IF NOT EXISTS scan_paths (id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE)')
                self.paths_table_ready = True
            existing = db.conn.execute('SELECT path FROM scan_paths WHERE id=?', (entry.id,)).fetchone()
            if existing is None:
                with db.write_transaction():
                    db.conn.execute('INSERT INTO scan_paths VALUES (?, ?)', (entry.id, entry.path))
        elif hasattr(db, 'client'):
            existing = db.client.hget('scan_paths', entry.id)
            if isinstance(existing, bytes):
                existing = existing.decode()
            if existing != entry.path:
                db.client.hset('scan_paths', entry.id, entry.path)
        else:
            if not hasattr(db, 'scan_paths'):
                db.scan_paths = {}
            if db.scan_paths.get(entry.id) != entry.path:
                db.scan_paths[entry.id] = entry.path
        self.remembered.add(entry.id)
    # PERSIST THE SCANNED FILE ID TO PATH MAPPING ]
    # LOOK UP IMPORTED OR SAVED CHECKSUM BASELINES [
    def baseline(self, db, path):
        node = db.get_root()
        for part in path.strip('/').split('/') if path else []:
            node = db.get_child(node, part) if node else None
        if node is None or (not node.is_dir and not node.info.get('hash') and not node.info.get('hashinfo')):
            saved = self.checksums.get(path)
            if saved:
                node = VFSNode(path, path.rsplit('/', 1)[-1], False,
                               size=saved['size'], info={'hash': saved['hash']})
        node = node or self.checksum_dirs.get(path)
        self.baseline_known[path] = bool(node and (node.is_dir or node.info.get('hash') or
                                                 node.info.get('hashinfo')))
        return node
    # LOOK UP IMPORTED OR SAVED CHECKSUM BASELINES ]
    # READ LOCAL FILE METADATA AND CAPTURE ERRORS [
    def disk_info(self, path):
        try:
            return os.lstat(get_real_path(path)), ''
        except (FileNotFoundError, NotADirectoryError):
            return None, ''
        except OSError as exc:
            return None, str(exc)
    # READ LOCAL FILE METADATA AND CAPTURE ERRORS ]
    # PUBLISH UPDATED FILE STATE TO SCANNER CONSUMERS [
    def publish(self, db, entry):
        new = entry.id not in self.entries
        self.entries[entry.id] = entry
        if new and self.current_mode == 2 and self.checkpoints.get('2') is not None:
            self.checkpoints['2']['remaining'].append(entry.id)
        with db.write_transaction() if isinstance(db, SQLiteDBAdapter) else nullcontext():
            self.remember(db, entry)
            self.store.put('entry', entry.id, asdict(entry))
        self.emit(('entry', entry))
        self.paths += 1
        self.size_scanned += entry.size if not entry.is_dir else 0
        self.update_priority(entry)
        self.report_stats(path=entry.path, completed_size=entry.size, force=True)
    # PUBLISH UPDATED FILE STATE TO SCANNER CONSUMERS ]
    # UPDATE PRIORITY FOR DRIVE SCANNER [
    def update_priority(self, entry):
        if entry.state in ('unknown', 'new'):
            priority = 1 if self.baseline_known.get(entry.id, False) else 0
        else:
            priority = 3 if entry.state == 'verified' else 2 if entry.state == 'modified' else 4
        with self.controls.lock:
            old = self.controls.entry_priorities.get(entry.id)
            if entry.is_dir:
                self.controls.entry_priorities.pop(entry.id, None)
            else:
                self.controls.entry_priorities[entry.id] = priority
            if old != self.controls.entry_priorities.get(entry.id):
                self.controls.priority_revision += 1
    # UPDATE PRIORITY FOR DRIVE SCANNER ]
    # SCAN ONCE FOR DRIVE SCANNER [
    def scan_once(self, db):
        try:
            self._scan_once(db)
        finally:
            self.timing.switch(0)
    # SCAN ONCE FOR DRIVE SCANNER ]
    # SCAN ONCE FOR DRIVE SCANNER [
    def _scan_once(self, db):
        self.store = ScanStore(db)
        if self.checkpoints is None:
            self.checkpoints = self.store.get('position', self.storage_path, {})
        self.current_mode = 0
        self.started = time.monotonic()
        expert_only = (self.controls.modes == (False, False, True) and
                       self.controls.heavy_order == 'expert' and
                       self.controls.startup_mode is None)
        if self.checksums is None or not expert_only:
            self.checksums = {path: value for path, value in self.store.items('checksum').items()
                              if path == self.path or path.startswith(self.path + '/')}
            self.checksum_dirs, self.checksum_children = {}, {}
            for path in self.checksums:
                child = path
                while child != self.path:
                    parent, _, name = child.rpartition('/')
                    self.checksum_children.setdefault(parent, set()).add(name)
                    self.checksum_dirs.setdefault(parent, VFSNode(
                        parent, parent.rsplit('/', 1)[-1], True))
                    child = parent
        if self.enabled(1):
            self.begin_mode(1)
            self.emit(('phase', 'Lite — finding paths'))
            self.discover(db)
            self.finish_startup_mode(1)
        for mode in (2, 3):
            self.current_mode = 0
            if not self.enabled(mode):
                continue
            self.begin_mode(mode)
            self.emit(('phase', 'Medium — verifying metadata' if mode == 2 else 'Heavy — checksums'))
            if mode == 2:
                self.discover(db, mode=2, new_only=True)
            if (mode == 3 and self.controls.heavy_order == 'expert' and
                    self.controls.startup_mode is None):
                if not self.expert_initialized:
                    for entry in self.entries.values():
                        if not entry.is_dir and entry.id not in self.controls.entry_priorities:
                            self.baseline(db, entry.path)
                            self.update_priority(entry)
                    self.expert_initialized = True
                self.scan_expert(db)
            else:
                self.verify_pending(db, mode)
                self.finish_startup_mode(mode)
        self.current_mode = 0
        self.report_stats(force=True, active=False)
        self.elapsed += max(0., time.monotonic() - self.started)
    # SCAN ONCE FOR DRIVE SCANNER ]
    # VERIFY PENDING FOR DRIVE SCANNER [
    def verify_pending(self, db, mode):
        checkpoint = self.checkpoints.get(str(mode))
        pending = (checkpoint['remaining'] if checkpoint is not None else list(self.entries))
        pending = [path for path in pending if path in self.entries and not self.entries[path].is_dir]
        first = checkpoint.get('first') if checkpoint else None
        new = {path for path in pending if self.baseline(db, path) is None} if mode == 3 else set()
        bucket_indices = {path: index for index, ids in enumerate(self.controls.buckets)
                          for path in ids} if mode == 3 and not (
                              self.controls.heavy_order == 'expert' and
                              self.controls.startup_mode is None) else {}
        ordered_new = deque(path for path in pending if path in new)
        original_order = list(pending)
        ordered_all = deque(pending)
        pending = set(pending)
        while pending and self.enabled(mode):
            while ordered_all and ordered_all[0] not in pending:
                ordered_all.popleft()
            while ordered_new and ordered_new[0] not in pending:
                ordered_new.popleft()
            prefer_new = mode == 3 and self.controls.new_first and ordered_new
            if prefer_new and bucket_indices and ordered_all:
                prefer_new = (bucket_indices.get(ordered_new[0]) ==
                              bucket_indices.get(ordered_all[0]))
            order = ordered_new if prefer_new else ordered_all
            path = first if first in pending else order.popleft()
            first = None
            if path not in pending:
                continue
            baseline = self.baseline(db, path)
            disk_stat, error = self.disk_info(path)
            old = self.entries[path]
            entry = replace(old, progress=None, error='',
                            is_dir=stat.S_ISDIR(disk_stat.st_mode) if disk_stat else old.is_dir,
                            size=(0 if disk_stat and stat.S_ISDIR(disk_stat.st_mode) else
                                  disk_stat.st_size if disk_stat else old.size))
            self.report_stats(path=path, force=True)
            self.emit(('entry', replace(entry, progress=0)))
            result = self.verify(entry, baseline, disk_stat, error)
            if not self.enabled(mode):
                first = path
                self.emit(('entry', old))
                break
            self.publish(db, result)
            pending.remove(path)
        self.checkpoints[str(mode)] = (
            {'remaining': [path for path in original_order if path in pending],
             'first': first} if pending else None)
        self.save_positions()
    # VERIFY PENDING FOR DRIVE SCANNER ]
    # SCAN EXPERT FOR DRIVE SCANNER [
    def scan_expert(self, db):
        self.expert_scanned = False
        ids = self.controls.claim_expert()
        if ids is None:
            # Timed background additions must not starve a faster scan worker.
            # Both producers share the candidate pool and queue under one lock.
            self.controls.enqueue_expert_batch()
            ids = self.controls.claim_expert()
        if ids is None:
            self.emit(('phase', 'Heavy expert — waiting for selected buckets'))
            return
        paths = [path for path in ids if path in self.entries and not self.entries[path].is_dir]
        self.expert_scanned = bool(paths)
        try:
            pending = self.checkpoints.get('3')
            # Resume an interrupted bucket; never extend its work to later buckets.
            remaining = [path for path in (pending['remaining'] if pending else ()) if path in paths]
            if not remaining:
                remaining = paths
            anchor = pending.get('first') if pending and pending.get('first') in remaining else None
            self.checkpoints['3'] = {'remaining': remaining, 'first': anchor}
            if paths:
                self.emit(('expert', {'id': paths[0]}))
            self.verify_pending(db, 3)
        finally:
            self.controls.finish_expert(
                interrupted=self.checkpoints.get('3') is not None and
                self.controls.requests[2][0] == self.requests_seen[2])
    # SCAN EXPERT FOR DRIVE SCANNER ]
    # DISCOVER FILES AND RESUME DIRECTORY TRAVERSAL [
    def discover(self, db, mode=1, new_only=False):
        key = '1' if mode == 1 else '2-discovery'
        checkpoint = self.checkpoints.get(key)
        stack = list(checkpoint['stack']) if checkpoint else list(self.scan_roots or (self.path,))
        seen = set(checkpoint['seen']) if checkpoint else set()
        partial = bool(checkpoint and checkpoint.get('partial'))
        while stack and self.enabled(mode):
            path = stack[-1]
            if self.scan_roots and not any(path == root or path.startswith(root + '/') for root in self.scan_roots):
                stack.pop()
                continue
            if new_only and path in self.entries and not self.entries[path].is_dir:
                seen.add(path)
                stack.pop()
                continue
            baseline = self.baseline(db, path)
            saved = self.store.get('entry', path)
            disk_stat, error = None, ''
            # Known directories must still be enumerated to find new descendants.
            if path and (baseline is None or baseline.is_dir or self.controls.read_known):
                disk_stat, error = self.disk_info(path)
            is_dir = stat.S_ISDIR(disk_stat.st_mode) if disk_stat else bool(baseline and baseline.is_dir)
            if path:
                info = baseline.info if baseline else {}
                state = (saved['state'] if saved else info.get(
                    'state', {'deleted': 'missing', 'new': 'unknown'}.get(
                        info.get('status'), 'unknown')))
                if state not in ('new', 'unknown', 'missing', 'modified', 'verified', 'directory'):
                    state = 'unknown'
                size = (disk_stat.st_size if disk_stat and not is_dir else
                        baseline.size if baseline and not is_dir else 0)
                entry = ScanEntry(path, path, is_dir, size, state, error=error)
                if baseline and self.controls.read_known and not entry.is_dir:
                    entry = self.verify_metadata(entry, baseline, disk_stat, error)
                if not self.enabled(mode):
                    break
                if not new_only or path not in self.entries:
                    self.publish(db, entry)
            seen.add(path)
            stack.pop()
            if not path or is_dir:
                children = {child.name: child for child in db.get_children(baseline)} if baseline and baseline.is_dir else {}
                for name in self.checksum_children.get(path, ()):
                    children.setdefault(name, self.baseline(db, path + '/' + name))
                names = set(children)
                if not path:
                    names.update(aliases)
                    names.update(self.root_names)
                elif disk_stat and stat.S_ISDIR(disk_stat.st_mode):
                    try:
                        with os.scandir(get_real_path(path)) as disk_children:
                            names.update(child.name for child in disk_children)
                    except OSError as exc:
                        self.publish(db, replace(entry, state='unknown', error=str(exc)))
                stack.extend(path + '/' + name for name in sorted(names, reverse=True))
        if not stack and not partial:
            removed = set(self.entries) - seen
            for path in removed:
                self.entries.pop(path, None)
                with self.controls.lock:
                    if self.controls.entry_priorities.pop(path, None) is not None:
                        self.controls.priority_revision += 1
            if removed:
                self.emit(('removed', removed))
            self.previous_ids = seen
        self.checkpoints[key] = {'stack': stack, 'seen': list(seen), 'partial': partial} if stack else None
        self.save_positions()
    # DISCOVER FILES AND RESUME DIRECTORY TRAVERSAL ]
    # VERIFY METADATA FOR DRIVE SCANNER [
    def verify_metadata(self, entry, baseline, disk_stat, error):
        if entry.is_dir:
            return replace(entry, state='directory', progress=None)
        if error:
            return replace(entry, state='unknown', error=error)
        if disk_stat is None:
            return replace(entry, state='missing' if baseline else 'unknown')
        if baseline is None:
            return replace(entry, state='unknown')
        changed = (entry.is_dir != baseline.is_dir or
                   (not baseline.is_dir and (not stat.S_ISREG(disk_stat.st_mode) or
                                             disk_stat.st_size != baseline.size)))
        return replace(entry, state='modified' if changed else 'verified')
    # VERIFY METADATA FOR DRIVE SCANNER ]
    # VERIFY FILE CONTENTS AGAINST CHECKSUM BASELINES [
    def verify(self, entry, baseline, disk_stat, error):
        if entry.is_dir:
            return replace(entry, state='directory', progress=None)
        if self.current_mode == 2:
            return self.verify_metadata(entry, baseline, disk_stat, error)
        if error:
            return replace(entry, state='unknown', error=error)
        if disk_stat is None:
            return replace(entry, state='missing' if baseline else 'unknown')
        if baseline is None and self.current_mode != 3:
            return replace(entry, state='unknown')
        if baseline and entry.is_dir != baseline.is_dir:
            return replace(entry, state='modified')
        if not stat.S_ISREG(disk_stat.st_mode):
            return replace(entry, state='unknown', error='Not a regular file; content verification skipped')
        digest = baseline.info.get('hash', '') if baseline else ''
        if not digest and baseline:
            digest = (baseline.info.get('hashinfo') or '').rsplit(':', 1)[0]
        algorithm, _, expected = digest.rpartition(':')
        if not algorithm:
            algorithm, expected = 'md5', digest
        add_checksum = not digest
        algorithm = algorithm.lower().replace('-', '')
        try:
            hasher = hashlib.new(algorithm)
            if not add_checksum and (len(expected) != hasher.digest_size * 2 or any(c not in '0123456789abcdefABCDEF' for c in expected)):
                raise ValueError('No supported baseline checksum')
            read = 0
            last_event = 0
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
            with os.fdopen(os.open(get_real_path(entry.path), flags), 'rb') as stream:
                # Reject replacements, symlinks and special files without blocking.
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    return replace(entry, state='unknown', error='Not a regular file')
                if (before.st_ino, before.st_dev, before.st_mtime_ns, before.st_size) != (
                        disk_stat.st_ino, disk_stat.st_dev, disk_stat.st_mtime_ns, disk_stat.st_size):
                    return replace(entry, state='unknown', error='File changed while opening; retrying next scan')
                if self.hash_started is None:
                    self.hash_started = time.monotonic()
                while self.enabled(3):
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    read += len(chunk)
                    self.report_stats(read=len(chunk))
                    if time.monotonic() - last_event >= .1:
                        self.emit(('entry', replace(entry, progress=min(99, int(read * 100 / max(1, entry.size))))))
                        last_event = time.monotonic()
                after = os.fstat(stream.fileno())
            if not self.enabled(3):
                return replace(entry, progress=None, state='unknown')
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                return replace(entry, state='unknown', error='File changed during verification; retrying next scan')
            digest = algorithm + ':' + hasher.hexdigest()
            verified = add_checksum or hasher.hexdigest().lower() == expected.lower()
            db = self.store.db
            # Hash reads and progress events happen before taking a write lock.
            with db.write_transaction() if isinstance(db, SQLiteDBAdapter) else nullcontext():
                if add_checksum:
                    saved = {'size': after.st_size, 'hash': digest}
                    self.store.put('checksum', entry.path, saved)
                if verified:
                    db.add_scanned_file(entry.path, digest, after.st_size)
            if add_checksum:
                self.checksums[entry.path] = saved
                self.baseline_known[entry.id] = True
            return replace(entry, state='verified' if verified else 'modified')
        except (OSError, ValueError) as exc:
            return replace(entry, state='unknown', error=str(exc))
    # VERIFY FILE CONTENTS AGAINST CHECKSUM BASELINES ]
# DISCOVER AND VERIFY FILES IN BACKGROUND SCAN PASSES ]
# MANAGE BUCKET FOR THE SCANNER WORKFLOW [
class Bucket:
    # INITIALIZE BUCKET FOR BUCKET [
    def __init__(self):
        self.ids = []
        self.weight = 0
        self.counts = Counter()
        self.size = 0
        self.files = 0
        self.file_states = Counter()
        self.active = 0
        self.updated = 0.
    # INITIALIZE BUCKET FOR BUCKET ]
# MANAGE BUCKET FOR THE SCANNER WORKFLOW ]
# GROUP SCANNED FILES INTO DISPLAY BUCKETS [
class FileMap:
    """Incremental sequential packing; fixed maps grow capacity geometrically."""
    # INITIALIZE FILE MAP [
    def __init__(self):
        self.entries = {}
        self.buckets = []
        self.locations = {}
        self.mode = 'count'
        self.fixed = True
        self.cells = 192
        self.limit = 100
        self.byte_limit = 64 * 1024 * 1024
        self.capacity = 1
    # INITIALIZE FILE MAP ]
    # CALCULATE THE BUCKET CAPACITY CONTRIBUTION [
    def weight(self, entry):
        return max(1, entry.size) if self.mode == 'size' else 1
    # CALCULATE THE BUCKET CAPACITY CONTRIBUTION ]
    # REBUILD DISPLAY BUCKETS FROM FILE ENTRIES [
    def rebuild(self, minimum=1):
        self.buckets = []
        self.locations = {}
        total = sum(self.weight(e) for e in self.entries.values())
        self.capacity = max(minimum, math.ceil(total / self.cells)) if self.fixed else (
            self.byte_limit if self.mode == 'size' else self.limit)
        for entry in self.entries.values():
            self._append(entry)
        # Indivisible files may need more capacity than the average predicts.
        while self.fixed and len(self.buckets) > self.cells:
            self.capacity *= 2
            self.buckets = []
            self.locations = {}
            for entry in self.entries.values():
                self._append(entry)
    # REBUILD DISPLAY BUCKETS FROM FILE ENTRIES ]
    # APPEND FOR FILE MAP [
    def _append(self, entry):
        weight = self.weight(entry)
        if not self.buckets or (self.buckets[-1].weight + weight > self.capacity
                                or (not self.fixed and len(self.buckets[-1].ids) >= self.limit)):
            self.buckets.append(Bucket())
        bucket = self.buckets[-1]
        self.locations[entry.id] = len(self.buckets) - 1
        bucket.ids.append(entry.id)
        self._account(bucket, entry, 1)
    # APPEND FOR FILE MAP ]
    # ACCOUNT FOR FILE MAP [
    def _account(self, bucket, entry, sign):
        bucket.weight += sign * self.weight(entry)
        bucket.counts[entry.state] += sign
        bucket.size += sign * entry.size
        bucket.files += sign * int(not entry.is_dir)
        bucket.file_states[entry.state] += sign * int(not entry.is_dir)
        bucket.active += sign * int(entry.progress is not None)
    # ACCOUNT FOR FILE MAP ]
    # UPDATE FILE MAP [
    def update(self, entry, rebuild=True):
        old = self.entries.get(entry.id)
        self.entries[entry.id] = entry
        if old is None:
            self._append(entry)
            if self.fixed and len(self.buckets) > self.cells:
                if not rebuild:
                    return True
                self.rebuild(minimum=self.capacity * 2)
        else:
            bucket = self.buckets[self.locations[entry.id]]
            self._account(bucket, old, -1)
            self._account(bucket, entry, 1)
            if self.mode == 'size' and old.size != entry.size:
                if not rebuild:
                    return True
                self.rebuild()
        self.buckets[self.locations[entry.id]].updated = time.monotonic()
    # UPDATE FILE MAP ]
# GROUP SCANNED FILES INTO DISPLAY BUCKETS ]
# ONE-BASED PAGES WITH A WIDTH-LIMITED WINDOW AND FIRST/LAST ANCHORS [
class Pagination:
    """One-based pages with a width-limited window and first/last anchors."""
    # INITIALIZE PAGINATION FOR PAGINATION [
    def __init__(self):
        self.page = 1
    # INITIALIZE PAGINATION FOR PAGINATION ]
    # SELECT PAGINATION FOR PAGINATION [
    def select(self, page, pages):
        self.page = max(1, min(page, max(1, pages)))
    # SELECT PAGINATION FOR PAGINATION ]
    # CHOOSE ELIGIBLE EXPERT SCAN BUCKETS [
    def choices(self, pages, width):
        pages = max(1, pages)
        self.select(self.page, pages)
        capacity = max(0, width // (len(str(pages)) + 2))
        if not capacity:
            return []
        if pages <= capacity:
            return list(range(1, pages + 1))
        if capacity < 5:
            start = max(1, min(self.page - capacity // 2, pages - capacity + 1))
            return list(range(start, start + capacity))
        # Use as many slots as fit, including the ellipses between distant pages.
        for count in range(capacity - 2, 0, -1):
            start = max(2, min(self.page - count // 2, pages - count))
            end = start + count - 1
            choices = ([1] + ([None] if start > 2 else []) + list(range(start, end + 1))
                       + ([None] if end < pages - 1 else []) + [pages])
            if len(choices) <= capacity:
                return choices
    # CHOOSE ELIGIBLE EXPERT SCAN BUCKETS ]
# ONE-BASED PAGES WITH A WIDTH-LIMITED WINDOW AND FIRST/LAST ANCHORS ]
