"""Single-worker disk verification and event-driven, sequential map buckets.

The scan index is deliberately separate from the imported comparison baseline.
Path IDs have the same meaning as nodes.id throughout the existing VFS.
"""
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import math
import os
from queue import Full
import sqlite3
import stat
import time

from .adapter.sqlite import SQLiteDBAdapter
from .paths import aliases, get_real_path


@dataclass(frozen=True)
class ScanEntry:
    id: str
    path: str
    is_dir: bool
    size: int = 0
    state: str = 'unknown'
    progress: int | None = None
    error: str = ''


@dataclass(frozen=True)
class ScanStats:
    path: str = ''
    bytes_read: int = 0
    elapsed: float = 0.
    active: bool = False

    @property
    def mb_per_second(self):
        return self.bytes_read / self.elapsed / 1_000_000 if self.active and self.elapsed > 0 else 0.


class DriveScanner:
    """Walk the union of disk and baseline paths off the Textual event loop."""

    def __init__(self, db, path, events, stop, interval=5):
        self.source = db
        self.path = path.rstrip('/')
        self.events = events
        self.stop = stop
        self.interval = interval
        self.previous_ids = set()
        self.remembered = set()
        self.current_path = self.path or '/'
        self.bytes_read = 0
        self.started = time.monotonic()
        self.last_stats = 0.

    def emit(self, event):
        while not self.stop.is_set():
            try:
                self.events.put(event, timeout=.1)
                return
            except Full:
                pass

    def report_stats(self, *, path=None, read=0, force=False, active=True):
        if path is not None:
            self.current_path = path
        self.bytes_read += read
        now = time.monotonic()
        if force or now - self.last_stats >= .1:
            self.emit(('stats', ScanStats(self.current_path, self.bytes_read,
                                         max(0., now - self.started), active)))
            self.last_stats = now

    def run(self):
        db = self.source
        owns_connection = isinstance(db, SQLiteDBAdapter)
        try:
            if owns_connection:
                # SQLite connections belong to their creating thread.
                db = object.__new__(SQLiteDBAdapter)
                db.conn = sqlite3.connect(self.source.db_path, timeout=2)
                db.conn.row_factory = sqlite3.Row
                db.conn.execute('''CREATE TABLE IF NOT EXISTS scan_paths (
                    id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE)''')
                db.conn.commit()
            elif not hasattr(db, 'scan_paths'):
                db.scan_paths = {}
            while not self.stop.is_set():
                self.emit(('phase', 'Scanning'))
                self.scan_once(db)
                if owns_connection:
                    db.conn.commit()
                self.emit(('phase', f'Watching — next scan in {self.interval:g} seconds'))
                if self.stop.wait(self.interval):
                    break
        except Exception as exc:
            self.report_stats(force=True, active=False)
            self.emit(('phase', f'Scan stopped: {exc}'))
        finally:
            if owns_connection and db is not self.source:
                db.conn.close()

    def remember(self, db, entry):
        if entry.id in self.remembered:
            return
        self.remembered.add(entry.id)
        if isinstance(db, SQLiteDBAdapter):
            db.conn.execute('INSERT OR IGNORE INTO scan_paths VALUES (?, ?)',
                            (entry.id, entry.path))
            # Do not hold a write transaction open while hashing a large file.
            db.conn.commit()
        elif hasattr(db, 'client'):
            db.client.hset('scan_paths', entry.id, entry.path)
        else:
            db.scan_paths[entry.id] = entry.path

    def scan_once(self, db):
        self.started = time.monotonic()
        self.bytes_read = 0
        self.report_stats(path=self.path or '/', force=True)
        node = db.get_root()
        for part in self.path.strip('/').split('/') if self.path else []:
            node = db.get_child(node, part) if node else None
        stack = [(self.path, node)]
        seen = set()
        while stack and not self.stop.is_set():
            path, baseline = stack.pop()
            seen.add(path)
            self.report_stats(path=path or '/', force=True)
            real = get_real_path(path) if path else None
            disk_stat = None
            error = ''
            if real:
                try:
                    disk_stat = os.lstat(real)
                except (FileNotFoundError, NotADirectoryError):
                    pass
                except OSError as exc:
                    error = str(exc)
            is_dir = bool(disk_stat and stat.S_ISDIR(disk_stat.st_mode))
            if path:
                entry = ScanEntry(path, path, is_dir if disk_stat else bool(baseline and baseline.is_dir),
                                  (disk_stat.st_size if disk_stat and not is_dir else
                                   baseline.size if baseline and not baseline.is_dir else 0))
                self.remember(db, entry)
                self.emit(('entry', replace(entry, progress=0)))
                entry = self.verify(entry, baseline, disk_stat, error)
                if self.stop.is_set():
                    return
                self.emit(('entry', entry))
                self.report_stats(force=True)
            if not path or is_dir or (baseline and baseline.is_dir):
                children = {child.name: child for child in db.get_children(baseline)
                            } if baseline and baseline.is_dir else {}
                names = set(children)
                if not path:
                    # The VFS root is a collection of mounts, never the host /.
                    names.update(aliases)
                elif is_dir:
                    try:
                        with os.scandir(real) as disk_children:
                            names.update(child.name for child in disk_children)
                    except OSError as exc:
                        self.emit(('entry', replace(entry, state='unknown', error=str(exc))))
                stack.extend((path + '/' + name, children.get(name))
                             for name in sorted(names, reverse=True))

        if not self.stop.is_set():
            removed = self.previous_ids - seen
            if removed:
                self.emit(('removed', removed))
            self.previous_ids = seen
            self.report_stats(force=True, active=False)

    def verify(self, entry, baseline, disk_stat, error):
        if error:
            return replace(entry, error=error)
        if disk_stat is None:
            return replace(entry, state='missing' if baseline else 'unknown')
        if baseline is None:
            return replace(entry, state='new')
        if entry.is_dir != baseline.is_dir:
            return replace(entry, state='modified')
        if entry.is_dir:
            return replace(entry, state='verified')
        if disk_stat.st_size != baseline.size:
            return replace(entry, state='modified')
        if not stat.S_ISREG(disk_stat.st_mode):
            return replace(entry, error='Not a regular file; content verification skipped')
        digest = baseline.info.get('hash', '')
        if not digest:
            digest = (baseline.info.get('hashinfo') or '').rsplit(':', 1)[0]
        algorithm, _, expected = digest.rpartition(':')
        if not algorithm:
            algorithm, expected = 'md5', digest
        algorithm = algorithm.lower().replace('-', '')
        try:
            hasher = hashlib.new(algorithm)
            if len(expected) != hasher.digest_size * 2 or any(c not in '0123456789abcdefABCDEF' for c in expected):
                raise ValueError('No supported baseline checksum')
            read = 0
            last_event = 0
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
            with os.fdopen(os.open(get_real_path(entry.path), flags), 'rb') as stream:
                # Reject replacements, symlinks and special files without blocking.
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    return replace(entry, error='Not a regular file')
                if (before.st_ino, before.st_dev, before.st_mtime_ns, before.st_size) != (
                        disk_stat.st_ino, disk_stat.st_dev, disk_stat.st_mtime_ns, disk_stat.st_size):
                    return replace(entry, state='unknown', error='File changed while opening; retrying next scan')
                while not self.stop.is_set():
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
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                return replace(entry, error='File changed during verification; retrying next scan')
            return replace(entry, state='verified' if hasher.hexdigest().lower() == expected.lower() else 'modified')
        except (OSError, ValueError) as exc:
            return replace(entry, error=str(exc))


class Bucket:
    def __init__(self):
        self.ids = []
        self.weight = 0
        self.counts = Counter()
        self.size = 0
        self.files = 0
        self.file_states = Counter()
        self.active = 0
        self.updated = 0.


class FileMap:
    """Incremental sequential packing; fixed maps grow capacity geometrically."""
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

    def weight(self, entry):
        return max(1, entry.size) if self.mode == 'size' else 1

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

    def _append(self, entry):
        weight = self.weight(entry)
        if not self.buckets or (self.buckets[-1].weight + weight > self.capacity
                                or (not self.fixed and len(self.buckets[-1].ids) >= self.limit)):
            self.buckets.append(Bucket())
        bucket = self.buckets[-1]
        self.locations[entry.id] = len(self.buckets) - 1
        bucket.ids.append(entry.id)
        self._account(bucket, entry, 1)

    def _account(self, bucket, entry, sign):
        bucket.weight += sign * self.weight(entry)
        bucket.counts[entry.state] += sign
        bucket.size += sign * entry.size
        bucket.files += sign * int(not entry.is_dir)
        bucket.file_states[entry.state] += sign * int(not entry.is_dir)
        bucket.active += sign * int(entry.progress is not None)

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


class Pagination:
    """One-based pages with a width-limited window and first/last anchors."""
    def __init__(self):
        self.page = 1

    def select(self, page, pages):
        self.page = max(1, min(page, max(1, pages)))

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
