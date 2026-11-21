"""Exit-persisted observed directory counts and background catalog recovery."""
from pathlib import Path
from contextlib import nullcontext
import sqlite3

from .scanner import ScanStore
from .adapter.sqlite import SQLiteDBAdapter


class DirectoryCounts:
    def __init__(self, db):
        self.store = ScanStore(db)
        self.saved = self.store.items('directory_count')
        self.observed = {}
        self.dirty = set()

    def get(self, path):
        return max(self.saved.get(path, 0), self.observed.get(path, 0))

    def remember(self, counts):
        for path, count in counts.items():
            count = max(0, int(count))
            if count > self.get(path) or path not in self.saved and path not in self.observed:
                self.observed[path] = max(count, self.observed.get(path, 0))
                self.dirty.add(path)

    def save(self):
        db = self.store.db
        with db.write_transaction() if isinstance(db, SQLiteDBAdapter) and self.dirty else nullcontext():
            for path in self.dirty:
                self.store.put('directory_count', path, self.get(path))
        self.saved.update({path: self.get(path) for path in self.dirty})
        self.dirty.clear()


def catalog_directory_counts(database, fragments, paths):
    """Read counts on a thread-owned read-only connection, without filesystem scans."""
    conn = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=0)
    try:
        schemas = ['main']
        for index, filename in enumerate(dict.fromkeys(fragments)):
            schema = f'count_fragment_{index}'
            conn.execute(f'ATTACH DATABASE ? AS {schema}', (Path(filename).resolve().as_uri() + '?mode=ro',))
            schemas.append(schema)
        seeds = [f'SELECT id,is_dir FROM {schema}.nodes WHERE id=?' for schema in schemas]
        branches = [f'SELECT node.id,node.is_dir FROM {schema}.nodes node JOIN tree ON node.parent_id=tree.id'
                    for schema in schemas]
        sql = 'WITH RECURSIVE tree(id,is_dir) AS (' + ' UNION '.join(seeds + branches) + ') '
        has_entries = conn.execute("SELECT 1 FROM sqlite_master WHERE name='scan_state'").fetchone()
        select = 'SELECT id FROM tree WHERE is_dir=0'
        if has_entries:
            select += (" UNION SELECT key FROM scan_state WHERE kind='entry' AND key>=? AND key<? "
                       "AND json_extract(value,'$.is_dir')=0 "
                       "AND COALESCE(json_extract(value,'$.blacklisted'),0)=0")
        sql += 'SELECT COUNT(*) FROM (' + select + ')'
        counts = {}
        for path, identity in paths.items():
            parameters = [identity] * len(schemas)
            if has_entries:
                prefix = identity.rstrip('/') + '/'
                parameters += [prefix, prefix[:-1] + '0']
            counts[path] = conn.execute(sql, parameters).fetchone()[0]
        return counts
    finally:
        conn.close()
