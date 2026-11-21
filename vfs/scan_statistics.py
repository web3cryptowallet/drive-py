"""Per-scope scan accounting, persisted independently of saved map snapshots."""
from copy import deepcopy
import sqlite3

from .adapter.sqlite import SQLiteDBAdapter
from .scanner import ScanStore


def empty_modes():
    return [[0, 0, 0.] for _ in range(3)]


def empty_record():
    return {name: empty_modes() for name in ('current', 'session', 'last', 'total')}


class ScanStatistics:
    def __init__(self, db):
        self.db = db
        self.store = ScanStore(db)
        if isinstance(db, SQLiteDBAdapter):
            db.conn.execute('CREATE TABLE IF NOT EXISTS scan_statistics '
                            '(path TEXT NOT NULL, scope TEXT NOT NULL, mode INTEGER NOT NULL, '
                            'files INTEGER NOT NULL, bytes INTEGER NOT NULL, seconds REAL NOT NULL, '
                            'PRIMARY KEY(path,scope,mode))')
            db.conn.commit()
            self.records = {}
            for path, scope, mode, files, size, seconds in db.conn.execute(
                    'SELECT path,scope,mode,files,bytes,seconds FROM scan_statistics'):
                self.records.setdefault(path, empty_record())[scope][mode - 1] = [files, size, seconds]
        else:
            self.records = self.store.items('statistics')
        self.previous = {}
        self.dirty = set()
        for path, record in self.records.items():
            if any(any(row) for row in record['session']):
                record['last'] = deepcopy(record['session'])
            record['session'] = empty_modes()
            record['current'] = empty_modes()
            self.dirty.add(path)
        self.save()

    def record(self, path):
        return self.records.setdefault(path, empty_record())

    def begin(self, path, token, elapsed):
        self.record(path)['current'] = empty_modes()
        self.previous[token] = [[0, 0, value] for value in elapsed]
        self.dirty.add(path)

    def update(self, path, token, counts, current_counts, elapsed, current_elapsed):
        record = self.record(path)
        previous = self.previous[token]
        changed = False
        for mode in range(3):
            cumulative = [*counts[mode], elapsed[mode]]
            delta = [max(0, value - old) for value, old in zip(cumulative, previous[mode])]
            current = [*current_counts[mode], current_elapsed[mode]]
            changed |= any(delta) or record['current'][mode] != current
            for scope in ('session', 'total'):
                record[scope][mode] = [old + value for old, value in zip(record[scope][mode], delta)]
            record['current'][mode] = current
            previous[mode] = cumulative
        if changed:
            self.dirty.add(path)

    def save(self, *, nonblocking=False):
        if isinstance(self.db, SQLiteDBAdapter):
            if self.dirty:
                conn = self.db.conn
                timeout = conn.execute('PRAGMA busy_timeout').fetchone()[0] if nonblocking else None
                try:
                    if nonblocking:
                        conn.execute('PRAGMA busy_timeout=0')
                    with self.db.write_transaction():
                        for path in self.dirty:
                            conn.executemany(
                                'INSERT OR REPLACE INTO scan_statistics(path,scope,mode,files,bytes,seconds) '
                                'VALUES (?,?,?,?,?,?)',
                                [(path, scope, mode, *row) for scope, rows in self.records[path].items()
                                 for mode, row in enumerate(rows, 1)])
                except sqlite3.OperationalError as exc:
                    code = getattr(exc, 'sqlite_errorcode', 0) & 255
                    if nonblocking and (code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                                        or 'locked' in str(exc).lower()):
                        return False
                    raise
                finally:
                    if nonblocking:
                        conn.execute(f'PRAGMA busy_timeout={timeout}')
        else:
            for path in self.dirty:
                self.store.put('statistics', path, self.records[path])
        self.dirty.clear()
        return True
