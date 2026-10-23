"""Recover source path namespaces using bounded batches and disk-backed plans."""
# MIGRATE LEGACY CATALOG PATHS WITH A SQLITE BACKUP [
import json
from pathlib import Path
import sqlite3
import tempfile
from .paths import catalog_source_path, catalog_identity_path, path_update_prefix
from .utils import normalize_path


def _batches(cursor, size):
    while batch := cursor.fetchmany(size):
        yield batch


def migrate_source_paths(db, batch_size=500):
    """Plan on temporary disk storage, then apply atomically under a writer lock."""
    if batch_size < 1:
        raise ValueError('batch_size must be positive')
    plans = []
    with tempfile.TemporaryDirectory(prefix='drive-path-migration-') as folder:
        try:
            with db.write_transaction():
                for index, store in enumerate(getattr(db, 'stores', {'': db}).values()):
                    scratch = sqlite3.connect(str(Path(folder) / f'{index}.sqlite'))
                    scratch.row_factory = sqlite3.Row
                    plans.append((store, scratch, 0))
                    scratch.executescript('''
                        PRAGMA cache_size=-1024;
                        PRAGMA temp_store=FILE;
                        CREATE TABLE sources (id TEXT PRIMARY KEY, source TEXT);
                        CREATE TABLE hashes (hash_id TEXT, path TEXT, UNIQUE(hash_id,path));
                        CREATE TABLE files (id TEXT PRIMARY KEY, name TEXT, is_dir INTEGER,
                            size INTEGER, parent_id TEXT, info TEXT);
                        CREATE TABLE nodes AS SELECT * FROM files;
                        CREATE UNIQUE INDEX node_id ON nodes(id);
                        CREATE TABLE origins (destination TEXT PRIMARY KEY, origin TEXT);
                        CREATE TABLE targets (origin TEXT, destination TEXT,
                            PRIMARY KEY(origin,destination));
                        CREATE TABLE empty_dirs (id TEXT, name TEXT, is_dir INTEGER,
                            size INTEGER, parent_id TEXT, info TEXT, depth INTEGER);
                        CREATE INDEX empty_depth ON empty_dirs(depth);
                    ''')
                    changed = _plan(store, scratch, batch_size)
                    scratch.commit()
                    plans[-1] = (store, scratch, changed)
                # Validate every plan before backing up or replacing any catalog.
                for store, _, changed in plans:
                    if changed:
                        _backup(db, store)
                for store, scratch, changed in plans:
                    if not changed:
                        continue
                    for table, columns in (('nodes', 'id,name,is_dir,size,parent_id,info'),
                                           ('hashes', 'hash_id,path')):
                        store.conn.execute(f'DELETE FROM {table}')
                        cursor = scratch.execute(f'SELECT {columns} FROM {table}')
                        placeholders = ','.join('?' for _ in columns.split(','))
                        for batch in _batches(cursor, batch_size):
                            store.conn.executemany(f'INSERT INTO {table} VALUES ({placeholders})', batch)
                return sum(changed for _, _, changed in plans)
        finally:
            for _, scratch, _ in plans:
                scratch.close()


def _plan(store, scratch, batch_size):
    """Keep provenance, collision checks, ancestors and deduplication on disk."""
    for batch in _batches(store.conn.execute('SELECT hash_id,path FROM hashes'), batch_size):
        for digest, source in batch:
            old_id = '/' + normalize_path(catalog_identity_path(source))[0]
            row = store.conn.execute('SELECT is_dir FROM nodes WHERE id=?', (old_id,)).fetchone()
            if row is None:
                old_id = '/' + normalize_path(path_update_prefix(source))[0]
                row = store.conn.execute('SELECT is_dir FROM nodes WHERE id=?', (old_id,)).fetchone()
            source = catalog_source_path(source)
            scratch.execute('INSERT OR IGNORE INTO hashes VALUES (?,?)', (digest, source))
            if row and not row['is_dir']:
                previous = scratch.execute('SELECT source FROM sources WHERE id=?', (old_id,)).fetchone()
                if previous and previous[0] != source:
                    raise ValueError('Ambiguous legacy source paths; rebuild the catalog from original logs')
                scratch.execute('INSERT OR IGNORE INTO sources VALUES (?,?)', (old_id, source))
    changed = 0
    collision = False
    for batch in _batches(store.conn.execute('SELECT * FROM nodes'), batch_size):
        for original in batch:
            row = dict(original)
            if row['is_dir']:
                if row['size'] == 0:
                    scratch.execute('INSERT INTO empty_dirs VALUES (:id,:name,:is_dir,:size,:parent_id,:info,:depth)',
                                    {**row, 'depth': row['id'].count('/')})
                continue
            source = scratch.execute('SELECT source FROM sources WHERE id=?', (row['id'],)).fetchone()
            if source:
                source = source[0]
                info = json.loads(row['info'])
                new_id = '/' + normalize_path(catalog_identity_path(source))[0]
                changed += new_id != row['id'] or info.get('path') != source
                info['path'] = source
                row.update(id=new_id, name=new_id.rsplit('/', 1)[-1],
                           parent_id=new_id.rpartition('/')[0], info=json.dumps(info))
            old_parent, new_parent = original['parent_id'], row['parent_id']
            while old_parent:
                scratch.execute('INSERT OR IGNORE INTO origins VALUES (?,?)', (new_parent, old_parent))
                scratch.execute('INSERT OR IGNORE INTO targets VALUES (?,?)', (old_parent, new_parent))
                old_parent = old_parent.rpartition('/')[0]
                new_parent = new_parent.rpartition('/')[0]
            try:
                scratch.execute('INSERT INTO files VALUES (:id,:name,:is_dir,:size,:parent_id,:info)', row)
            except sqlite3.IntegrityError:
                collision = True
    if not changed:
        return 0
    if collision:
        raise ValueError('Source path migration would merge files; rebuild from original logs')
    scratch.execute('INSERT INTO nodes SELECT * FROM files')
    for batch in _batches(scratch.execute('SELECT * FROM files'), batch_size):
        for row in batch:
            parent = row['parent_id']
            while parent is not None:
                ancestor = scratch.execute('SELECT * FROM nodes WHERE id=?', (parent,)).fetchone()
                if ancestor is not None and not ancestor['is_dir']:
                    raise ValueError('Source path migration conflicts with a file parent')
                if ancestor is None:
                    origin = scratch.execute('SELECT origin FROM origins WHERE destination=?', (parent,)).fetchone()
                    original = store.conn.execute('SELECT info FROM nodes WHERE id=?',
                                                  (origin[0] if origin else parent,)).fetchone()
                    scratch.execute('INSERT INTO nodes VALUES (?,?,1,0,?,?)',
                                    (parent, parent.rsplit('/', 1)[-1],
                                     parent.rpartition('/')[0] if parent else None,
                                     original[0] if original else '{}'))
                scratch.execute('UPDATE nodes SET size=size+? WHERE id=?', (row['size'], parent))
                parent = parent.rpartition('/')[0] if parent else None
    for batch in _batches(scratch.execute('SELECT * FROM empty_dirs ORDER BY depth'), batch_size):
        for row in batch:
            if (scratch.execute('SELECT 1 FROM nodes WHERE id=?', (row['id'],)).fetchone()
                    or scratch.execute('SELECT 1 FROM targets WHERE origin=?', (row['id'],)).fetchone()):
                continue
            destinations = scratch.execute('SELECT destination FROM targets WHERE origin=? LIMIT 2',
                                           (row['parent_id'],)).fetchall()
            parent = destinations[0][0] if len(destinations) == 1 else row['parent_id']
            new_id = parent + '/' + row['name'] if parent is not None else ''
            if parent is None or scratch.execute('SELECT 1 FROM nodes WHERE id=?', (parent,)).fetchone():
                scratch.execute('INSERT OR IGNORE INTO nodes VALUES (?,?,1,0,?,?)',
                                (new_id, row['name'], parent, row['info']))
                scratch.execute('INSERT OR IGNORE INTO targets VALUES (?,?)', (row['id'], new_id))
    return changed


def _backup(db, store):
    schema = getattr(store.conn, 'schema', 'main')
    filename = Path(next(row[2] for row in db.conn.execute('PRAGMA database_list') if row[1] == schema))
    backup = filename.with_name(filename.name + '.source-paths-backup.sqlite')
    if backup.exists():
        raise FileExistsError(f'Path migration backup already exists: {backup}')
    source_conn = sqlite3.connect(str(filename))
    target = sqlite3.connect(backup)
    try:
        source_conn.backup(target, pages=256)
    finally:
        source_conn.close()
        target.close()
# MIGRATE LEGACY CATALOG PATHS WITH A SQLITE BACKUP ]
