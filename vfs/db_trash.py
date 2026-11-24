"""Recoverable database-only removal; source filesystem objects are untouched."""
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import os

from .adapter.sqlite import SQLiteDBAdapter
from .scanner import ScanStore
from .paths import catalog_identity_path, path_update_prefix, get_real_path
from .utils import normalize_path


class DBTrash:
    def __init__(self, db):
        self.db = db
        self.store = ScanStore(db)
        if isinstance(db, SQLiteDBAdapter):
            db.conn.execute('CREATE TABLE IF NOT EXISTS D '
                            '(path TEXT PRIMARY KEY, root TEXT NOT NULL, trashed_at TEXT NOT NULL, value TEXT NOT NULL)')
            db.conn.commit()

    def records(self):
        if isinstance(self.db, SQLiteDBAdapter):
            return {row[0]: dict(root=row[1], trashed_at=row[2], node=json.loads(row[3]))
                    for row in self.db.conn.execute('SELECT path,root,trashed_at,value FROM D ORDER BY path')}
        return self.store.items('trashed')

    def roots(self):
        return tuple(sorted({value['root'] for value in self.records().values()
                             if not os.path.exists(get_real_path(value['root']))}))

    def remove(self, paths=None):
        """Permanently forget exact archive rows, or all rows; never touch files."""
        db = self.db
        if isinstance(db, SQLiteDBAdapter):
            with db.write_transaction():
                if paths is None:
                    return db.conn.execute('DELETE FROM D').rowcount
                return sum(db.conn.execute('DELETE FROM D WHERE path=?', (path,)).rowcount
                           for path in set(paths))
        keys = self.records() if paths is None else set(paths)
        return sum(self.store.delete('trashed', path) for path in keys)

    def move(self, path, *, archive=True):
        if not path or path == '/':
            raise ValueError('Cannot trash the catalog root')
        node = self.db.get_root()
        for part in path.strip('/').split('/'):
            node = self.db.get_child(node, part) if node else None
        if node is None and archive:
            raise ValueError('This path has no active database record')
        nodes, pending = {}, [node] if node else []
        while pending:
            item = pending.pop()
            if item.id in nodes:
                continue
            nodes[item.id] = dict(vars(item))
            if item.is_dir:
                pending.extend(self.db.get_children(item))
        stamp = datetime.now(timezone.utc).isoformat()
        db = self.db
        relative_namespace = ('/~:' in getattr(db, 'nodes', {}) or
                              (hasattr(db, 'client') and db.client.exists('node:/~:')))
        def identity(value):
            value = catalog_identity_path(value) if relative_namespace else value
            return '/' + normalize_path(path_update_prefix(value))[0]
        context = db.write_transaction() if isinstance(db, SQLiteDBAdapter) else nullcontext()
        with context:
            for key, data in (nodes.items() if archive else ()):
                if isinstance(db, SQLiteDBAdapter):
                    db.conn.execute('INSERT OR REPLACE INTO D VALUES (?,?,?,?)',
                                    (key, path, stamp, json.dumps(data)))
                else:
                    self.store.put('trashed', key, dict(root=path, trashed_at=stamp, node=data))
            if isinstance(db, SQLiteDBAdapter):
                # Fragment stores share the coordinator transaction/connection.
                for store in getattr(db, 'stores', {'': db}).values():
                    removed_size = 0
                    for key in sorted(nodes, key=lambda key: nodes[key]['is_dir']):
                        row = store.conn.execute('SELECT * FROM nodes WHERE id=?', (key,)).fetchone()
                        if row is None:
                            continue
                        if not row['is_dir']:
                            removed_size += row['size']
                            info = json.loads(row['info'])
                            for candidate in store.conn.execute('SELECT rowid,path FROM hashes WHERE hash_id=?',
                                                                (info.get('hashinfo'),)).fetchall():
                                if store._duplicate_path_id(candidate['path']) == key:
                                    store.conn.execute('DELETE FROM hashes WHERE rowid=?', (candidate['rowid'],))
                        store.conn.execute('DELETE FROM nodes WHERE id=?', (key,))
                    parent = nodes[path]['parent_id'] if nodes else None
                    while parent is not None:
                        row = store.conn.execute('SELECT parent_id FROM nodes WHERE id=?', (parent,)).fetchone()
                        if row is None:
                            break
                        store.conn.execute('UPDATE nodes SET size=MAX(0,size-?) WHERE id=?', (removed_size, parent))
                        parent = row['parent_id']
            elif hasattr(db, 'nodes'):
                removed_size = sum(data['size'] for data in nodes.values() if not data['is_dir'])
                removed_files = sum(not data['is_dir'] for data in nodes.values())
                for key, data in nodes.items():
                    db.nodes.pop(key, None)
                    db.children_idx.pop(key, None)
                    db.children_idx.get(data['parent_id'], {}).pop(data['name'], None)
                for digest, paths in list(db.hashes.items()):
                    db.hashes[digest] = {value for value in paths if identity(value) not in nodes}
                parent = nodes[path]['parent_id'] if nodes else None
                while parent is not None and parent in db.nodes:
                    ancestor = db.nodes[parent]
                    ancestor.size = max(0, ancestor.size - removed_size)
                    ancestor.total_files = max(0, ancestor.total_files - removed_files)
                    parent = ancestor.parent_id
            elif hasattr(db, 'client'):
                pipe = db.client.pipeline(transaction=True)
                for key, data in nodes.items():
                    pipe.delete('node:' + key, 'children:' + key, 'dir_map:' + key)
                    if data['parent_id'] is not None:
                        pipe.srem('children:' + data['parent_id'], key)
                        pipe.hdel('dir_map:' + data['parent_id'], data['name'])
                    digest = data['info'].get('hashinfo')
                    if digest:
                        for value in db.client.smembers('hash:' + digest):
                            if identity(value) == key:
                                pipe.srem('hash:' + digest, value)
                removed_size = sum(data['size'] for data in nodes.values() if not data['is_dir'])
                parent = nodes[path]['parent_id'] if nodes else None
                while parent is not None:
                    ancestor = db.client.hgetall('node:' + parent)
                    if not ancestor:
                        break
                    pipe.hincrby('node:' + parent, 'size', -removed_size)
                    parent = ancestor.get('parent_id')
                    if parent == 'NULL':
                        break
                pipe.execute()
            else:
                raise ValueError('Database backend does not support trash')
            if not archive:
                matches = lambda key: key == path or key.startswith(path.rstrip('/') + '/')
                for kind in ('entry', 'checksum'):
                    for key in self.store.items(kind):
                        if matches(key):
                            self.store.delete(kind, key)
                for kind in ('map', 'position'):
                    for key in self.store.items(kind):
                        scope = key.partition('::selection:')[0].rstrip('/')
                        if matches(scope) or path.startswith(scope + '/'):
                            self.store.delete(kind, key)
        return len(nodes)
