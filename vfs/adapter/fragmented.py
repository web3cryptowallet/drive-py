"""Path fragments sharing one SQLite transaction and a combined catalog view."""
# IMPORT FRAGMENTED DEPENDENCIES [
import json
from pathlib import Path
import re
import sqlite3

from .sqlite import SQLiteDBAdapter
from ..paths import path_update_prefix
from ..utils import normalize_path
# IMPORT FRAGMENTED DEPENDENCIES ]
# NORMALIZE A PATH TO ITS CATALOG IDENTITY [
def catalog_path(path):
    return '/' + normalize_path(path_update_prefix(path))[0] if path else ''
# NORMALIZE A PATH TO ITS CATALOG IDENTITY ]
# ROUTE TABLE OPERATIONS THROUGH A SHARED SQLITE CONNECTION [
class FragmentConnection:
    """Qualify adapter table operations while sharing the coordinator connection."""
    # INITIALIZE FRAGMENT CONNECTION [
    def __init__(self, conn, schema):
        self.connection, self.schema = conn, schema
    # INITIALIZE FRAGMENT CONNECTION ]
    # QUALIFY SQL TABLES FOR FRAGMENT CONNECTION [
    def sql(self, sql):
        return re.sub(r'\b(FROM|JOIN|INTO|UPDATE|TABLE)\s+(nodes|hashes)\b',
                      lambda m: f'{m[1]} {self.schema}.{m[2]}', sql, flags=re.I)
    # QUALIFY SQL TABLES FOR FRAGMENT CONNECTION ]
    # EXECUTE A STATEMENT AGAINST THE SELECTED DATABASE FRAGMENT [
    def execute(self, sql, parameters=()):
        return self.connection.execute(self.sql(sql), parameters)
    # EXECUTE A STATEMENT AGAINST THE SELECTED DATABASE FRAGMENT ]
    # EXECUTE BATCHED STATEMENTS AGAINST THE SELECTED DATABASE FRAGMENT [
    def executemany(self, sql, parameters):
        return self.connection.executemany(self.sql(sql), parameters)
    # EXECUTE BATCHED STATEMENTS AGAINST THE SELECTED DATABASE FRAGMENT ]
    # DELEGATE ATTRIBUTE ACCESS FOR FRAGMENT CONNECTION [
    def __getattr__(self, name):
        return getattr(self.connection, name)
    # DELEGATE ATTRIBUTE ACCESS FOR FRAGMENT CONNECTION ]
    # ENTER FRAGMENT CONNECTION [
    def __enter__(self):
        self.connection.__enter__()
        return self
    # ENTER FRAGMENT CONNECTION ]
    # LEAVE FRAGMENT CONNECTION [
    def __exit__(self, *args):
        return self.connection.__exit__(*args)
    # LEAVE FRAGMENT CONNECTION ]
# ROUTE TABLE OPERATIONS THROUGH A SHARED SQLITE CONNECTION ]
# ROUTE CATALOG RECORDS ACROSS PATH FRAGMENTS [
class FragmentedSQLiteDBAdapter(SQLiteDBAdapter):
    # INITIALIZE FRAGMENTED SQLITE DBADAPTER [
    def __init__(self, db_path='drivevfs', fragments=None, refragment=False):
        super().__init__(db_path)
        self.fragments_config = fragments or {}
        self.conn.execute('CREATE TABLE IF NOT EXISTS db_fragments (prefix TEXT PRIMARY KEY, filename TEXT NOT NULL UNIQUE)')
        self.conn.commit()
        saved = dict(self.conn.execute('SELECT prefix, filename FROM db_fragments'))
        for filename in saved.values():
            if not Path(filename).is_file():
                self.conn.close()
                raise FileNotFoundError(f'Missing fragment database: {filename}')
        requested = {catalog_path(p): str(Path(f).expanduser().resolve())
                     for p, f in self.fragments_config.items()}
        if any(p in ('', '/') for p in requested):
            raise ValueError('Fragment prefixes must be non-root catalog paths')
        for prefix, filename in requested.items():
            if prefix in saved and saved[prefix] != filename:
                raise ValueError(f'Cannot change database filename for existing fragment {prefix}')
        if refragment:
            combined = {**saved, **requested}
            attached_limit = (self.conn.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED)
                              if hasattr(self.conn, 'getlimit') else 10)
            if len(combined) > attached_limit:
                raise ValueError('Too many fragments for this SQLite build')
            if len(set(combined.values()) | {str(Path(db_path).resolve())}) != len(combined) + 1:
                raise ValueError('Each fragment must have a distinct database filename')
            for prefix, filename in requested.items():
                if prefix not in saved:
                    Path(filename).parent.mkdir(parents=True, exist_ok=True)
                    initial = SQLiteDBAdapter(filename)
                    initial.conn.close()
            # Persist membership before moving anything: interrupted migration stays readable.
            with self.conn:
                self.conn.executemany('INSERT OR IGNORE INTO db_fragments VALUES (?, ?)', requested.items())
            saved = combined
        self.routes = saved
        self.stores = {'': self._store('main')}
        for index, (prefix, filename) in enumerate(sorted(saved.items())):
            if not Path(filename).is_file() and not refragment:
                raise FileNotFoundError(f'Missing fragment database: {filename}')
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            initial = SQLiteDBAdapter(filename)
            initial.conn.close()
            schema = f'fragment_{index}'
            self.conn.execute(f'ATTACH DATABASE ? AS {schema}', (filename,))
            self.stores[prefix] = self._store(schema)
    # INITIALIZE FRAGMENTED SQLITE DBADAPTER ]
    # BUILD AN ADAPTER FOR AN ATTACHED DATABASE [
    def _store(self, schema):
        store = object.__new__(SQLiteDBAdapter)
        store.conn = FragmentConnection(self.conn, schema)
        return store
    # BUILD AN ADAPTER FOR AN ATTACHED DATABASE ]
    # SELECT THE LONGEST MATCHING DATABASE FRAGMENT PREFIX [
    def owner(self, path):
        path = catalog_path(path)
        return next((p for p in sorted(self.routes, key=len, reverse=True)
                     if path == p or path.startswith(p + '/')), '')
    # SELECT THE LONGEST MATCHING DATABASE FRAGMENT PREFIX ]
    # MOVE BOUNDED BATCHES ATOMICALLY; RETAIN METADATA, HASHES AND ANCESTOR TOTALS [
    def refragment(self, batch_size=500, directory=None):
        """Move bounded batches atomically; retain metadata, hashes and ancestor totals."""
        for source_prefix, source in self.stores.items():
            cursor = ''
            while True:
                condition = '' if directory is None else ' AND parent_id=?'
                parameters = (cursor, batch_size) if directory is None else (cursor, directory, batch_size)
                with self.write_transaction():
                    rows = source.conn.execute(
                        'SELECT * FROM nodes WHERE is_dir=0 AND id>?' + condition + ' ORDER BY id LIMIT ?',
                        parameters).fetchall()
                    if not rows:
                        break
                    for row in rows:
                        cursor = row['id']
                        target_prefix = self.owner(row['id'])
                        if target_prefix == source_prefix:
                            continue
                        target = self.stores[target_prefix]
                        if target.conn.execute('SELECT 1 FROM nodes WHERE id=?', (row['id'],)).fetchone():
                            raise ValueError(f'Conflicting fragment record: {row["id"]}')
                        parents = []
                        parent = row['parent_id']
                        while parent is not None:
                            ancestor = source.conn.execute('SELECT * FROM nodes WHERE id=?', (parent,)).fetchone()
                            if ancestor is None:
                                raise ValueError(f'Missing ancestor: {parent}')
                            parents.append(ancestor)
                            parent = ancestor['parent_id']
                        for ancestor in reversed(parents):
                            values = list(ancestor)
                            values[3] = 0
                            target.conn.execute('INSERT OR IGNORE INTO nodes VALUES (?, ?, ?, ?, ?, ?)', values)
                            target.conn.execute('UPDATE nodes SET size=size+? WHERE id=?', (row['size'], ancestor['id']))
                            source.conn.execute('UPDATE nodes SET size=size-? WHERE id=?', (row['size'], ancestor['id']))
                        target.conn.execute('INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?)', tuple(row))
                        # Preserve every original hash/path spelling, including imported aliases.
                        info = json.loads(row['info'])
                        candidates = source.conn.execute('SELECT rowid, hash_id, path FROM hashes WHERE hash_id=?',
                                                         (info.get('hashinfo'),)).fetchall()
                        for candidate in candidates:
                            if source._duplicate_path_id(candidate['path']) == row['id']:
                                target.conn.execute('INSERT INTO hashes VALUES (?, ?)', tuple(candidate)[1:])
                                source.conn.execute('DELETE FROM hashes WHERE rowid=?', (candidate['rowid'],))
                        source.conn.execute('DELETE FROM nodes WHERE id=?', (row['id'],))
        # Empty directories carry metadata too. Move their authoritative record,
        # retaining zero-sized ancestors needed to navigate other fragments.
        for prefix, source in self.stores.items():
            with self.write_transaction():
                rows = source.conn.execute(
                    'SELECT * FROM nodes WHERE is_dir=1' +
                    ('' if directory is None else ' AND parent_id=?') + ' ORDER BY length(id)',
                    () if directory is None else (directory,)).fetchall()
                for row in rows:
                    owner = self.owner(row['id'])
                    if owner != prefix:
                        target = self.stores[owner]
                        target.conn.execute('INSERT OR IGNORE INTO nodes VALUES (?, ?, ?, 0, ?, ?)',
                                            (row['id'], row['name'], row['is_dir'], row['parent_id'], row['info']))
    # MOVE BOUNDED BATCHES ATOMICALLY; RETAIN METADATA, HASHES AND ANCESTOR TOTALS ]
    # MERGE FOR FRAGMENTED SQLITE DBADAPTER [
    def _merge(self, nodes):
        result = {}
        for node in nodes:
            if node is None:
                continue
            if node.id in result and node.is_dir and result[node.id].is_dir:
                result[node.id].size += node.size
            else:
                result[node.id] = node
        return list(result.values())
    # MERGE FOR FRAGMENTED SQLITE DBADAPTER ]
    # RESOLVE ROOT FOR FRAGMENTED SQLITE DBADAPTER [
    def get_root(self):
        roots = self._merge(store.get_root() for store in self.stores.values())
        return roots[0] if roots else None
    # RESOLVE ROOT FOR FRAGMENTED SQLITE DBADAPTER ]
    # RESOLVE CHILDREN FOR FRAGMENTED SQLITE DBADAPTER [
    def get_children(self, node):
        self.refragment(directory=node.id)
        return self._merge(child for store in self.stores.values() for child in store.get_children(node))
    # RESOLVE CHILDREN FOR FRAGMENTED SQLITE DBADAPTER ]
    # RESOLVE CHILD FOR FRAGMENTED SQLITE DBADAPTER [
    def get_child(self, node, name):
        self.refragment(directory=node.id)
        children = self._merge(store.get_child(node, name) for store in self.stores.values())
        return children[0] if children else None
    # RESOLVE CHILD FOR FRAGMENTED SQLITE DBADAPTER ]
    # RESOLVE PARENT FOR FRAGMENTED SQLITE DBADAPTER [
    def get_parent(self, node):
        parents = self._merge(store.get_parent(node) for store in self.stores.values())
        return parents[0] if parents else None
    # RESOLVE PARENT FOR FRAGMENTED SQLITE DBADAPTER ]
    # RESOLVE HASH DUPS [
    def get_hash_dups(self, hash_id):
        return set().union(*(store.get_hash_dups(hash_id) for store in self.stores.values()))
    # RESOLVE HASH DUPS ]
    # REMOVE SUBTREE FOR FRAGMENTED SQLITE DBADAPTER [
    def _remove_subtree(self, store, path):
        row = store.conn.execute('SELECT * FROM nodes WHERE id=?', (path,)).fetchone()
        if row is None:
            return
        rows = store.conn.execute("""WITH RECURSIVE subtree(id) AS (
            SELECT id FROM nodes WHERE id=? UNION ALL
            SELECT nodes.id FROM nodes JOIN subtree ON nodes.parent_id=subtree.id
        ) SELECT nodes.* FROM nodes JOIN subtree USING(id)""", (path,)).fetchall()
        for child in rows:
            if not child['is_dir']:
                info = json.loads(child['info'])
                candidates = store.conn.execute('SELECT rowid, path FROM hashes WHERE hash_id=?',
                                                (info.get('hashinfo'),)).fetchall()
                for candidate in candidates:
                    if store._duplicate_path_id(candidate['path']) == child['id']:
                        store.conn.execute('DELETE FROM hashes WHERE rowid=?', (candidate['rowid'],))
            store.conn.execute('DELETE FROM nodes WHERE id=?', (child['id'],))
        parent = row['parent_id']
        while parent is not None:
            ancestor = store.conn.execute('SELECT parent_id FROM nodes WHERE id=?', (parent,)).fetchone()
            if ancestor is None:
                break
            store.conn.execute('UPDATE nodes SET size=size-? WHERE id=?', (row['size'], parent))
            parent = ancestor['parent_id']
    # REMOVE SUBTREE FOR FRAGMENTED SQLITE DBADAPTER ]
    # UPDATE FRAGMENTED SQLITE DBADAPTER [
    def update(self, files, hashes=None):
        for path in files:
            parent = catalog_path(path).rsplit('/', 1)[0]
            self.refragment(directory=parent)
        # Validate and merge all fragments in one attached-database transaction.
        with self.write_transaction():
            # A replacement can cross fragment boundaries. Remove conflicting
            # directories and parent files from every physical tree first.
            for path in files:
                path = catalog_path(path)
                for store in self.stores.values():
                    row = store.conn.execute('SELECT is_dir FROM nodes WHERE id=?', (path,)).fetchone()
                    if row and row['is_dir']:
                        self._remove_subtree(store, path)
                    parent = path.rsplit('/', 1)[0]
                    while parent:
                        row = store.conn.execute('SELECT is_dir FROM nodes WHERE id=?', (parent,)).fetchone()
                        if row and not row['is_dir']:
                            self._remove_subtree(store, parent)
                        parent = parent.rsplit('/', 1)[0]
            for prefix, store in self.stores.items():
                subset = {p: h for p, h in files.items() if self.owner(p) == prefix}
                if subset:
                    # Base update owns its context; use a savepoint-free facade so
                    # it cannot commit before the outer transaction completes.
                    original = store.conn
                    store.conn = TransactionConnection(original)
                    try:
                        store.update(subset)
                    finally:
                        store.conn = original
    # UPDATE FRAGMENTED SQLITE DBADAPTER ]
    # ADD SCANNED FILE [
    def add_scanned_file(self, path, digest, size):
        self.refragment(directory=catalog_path(path).rsplit('/', 1)[0])
        key = catalog_path(path)
        for store in self.stores.values():
            if store.conn.execute('SELECT 1 FROM nodes WHERE id=?', (key,)).fetchone():
                return False
            parent = key.rsplit('/', 1)[0]
            while parent:
                row = store.conn.execute('SELECT is_dir FROM nodes WHERE id=?', (parent,)).fetchone()
                if row and not row['is_dir']:
                    raise ValueError('A stored file occupies a parent directory')
                parent = parent.rsplit('/', 1)[0]
        return self.stores[self.owner(path)].add_scanned_file(path, digest, size)
    # ADD SCANNED FILE ]
    # REBUILD DB FOR FRAGMENTED SQLITE DBADAPTER [
    def rebuild_db(self):
        with self.conn:
            for store in self.stores.values():
                store.conn.execute('DELETE FROM nodes')
                store.conn.execute('DELETE FROM hashes')
                store.conn.execute("INSERT INTO nodes VALUES ('', '', 1, 0, NULL, '{}')")
    # REBUILD DB FOR FRAGMENTED SQLITE DBADAPTER ]
    # BUILD CATALOG OR MAP CONTENTS [
    def build(self, files, hashes=None):
        self.rebuild_db()
        self.update(files, hashes)
    # BUILD CATALOG OR MAP CONTENTS ]
# ROUTE CATALOG RECORDS ACROSS PATH FRAGMENTS ]
# MANAGE TRANSACTION CONNECTION [
class TransactionConnection:
    # INITIALIZE TRANSACTION CONNECTION [
    def __init__(self, connection):
        self.connection = connection
    # INITIALIZE TRANSACTION CONNECTION ]
    # DELEGATE ATTRIBUTE ACCESS FOR TRANSACTION CONNECTION [
    def __getattr__(self, name):
        return getattr(self.connection, name)
    # DELEGATE ATTRIBUTE ACCESS FOR TRANSACTION CONNECTION ]
    # ENTER TRANSACTION CONNECTION [
    def __enter__(self):
        return self
    # ENTER TRANSACTION CONNECTION ]
    # LEAVE TRANSACTION CONNECTION [
    def __exit__(self, *args):
        return False
    # LEAVE TRANSACTION CONNECTION ]
# MANAGE TRANSACTION CONNECTION ]
