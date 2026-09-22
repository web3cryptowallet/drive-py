"""SQLite filesystem storage."""

# IMPORT SQLITE FILESYSTEM STORAGE DEPENDENCIES [

import json
import os
import sqlite3

from .base import BaseDBAdapter
from ..nodes import VFSNode
from ..paths import path_update_prefix
from ..utils import batched, normalize_path

# IMPORT SQLITE FILESYSTEM STORAGE DEPENDENCIES ]
# STORE AND QUERY FILESYSTEM NODES IN SQLITE [

class SQLiteDBAdapter(BaseDBAdapter):
    """SQLite Implementation. Efficient for large filesystems."""
    # MANAGE THE SQLITE DATABASE AND SCHEMA [

    def __init__(self, db_path="drivevfs"):
        self.connect_db(db_path)

    def connect_db(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        print("sqlite: create tables")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                name TEXT,
                is_dir BOOLEAN,
                size INTEGER,
                parent_id TEXT,
                info JSON
            );
            CREATE INDEX IF NOT EXISTS idx_parent ON nodes(parent_id);
            CREATE INDEX IF NOT EXISTS idx_parent_name ON nodes(parent_id, name);
            
            CREATE TABLE IF NOT EXISTS hashes (
                hash_id TEXT,
                path TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_hash ON hashes(hash_id);
            CREATE INDEX IF NOT EXISTS idx_hash_path ON hashes(path);
        """)

    def drop_tables(self):
        print("sqlite: drop tables")
        self.conn.executescript("""
            DROP INDEX IF EXISTS idx_parent_name;
            DROP INDEX IF EXISTS idx_parent;
            DROP TABLE IF EXISTS nodes;
            DROP INDEX IF EXISTS idx_hash;
            DROP TABLE IF EXISTS hashes;
        """)
        self.conn.commit()

    def rebuild_db(self):
        print(f"sqlite: rebuild db {self.db_path}")
        self.conn.close()
        os.remove(self.db_path)
        self.connect_db(self.db_path)

    # MANAGE THE SQLITE DATABASE AND SCHEMA ]
    # DECODE STORED NODE METADATA [

    def _row_to_node(self, row):
        if not row: return None
        return VFSNode(
            id=row["id"], name=row["name"], is_dir=bool(row["is_dir"]),
            size=row["size"], parent_id=row["parent_id"], 
            info=json.loads(row["info"]) if row["info"] else {}
        )

    # DECODE STORED NODE METADATA ]
    # REBUILD FILE DIRECTORY AND DUPLICATE INDEXES [

    def build(self, files, hashes=None):
        # recreate db
        self.rebuild_db()

        # In-memory dictionary to track only directories and accumulate their sizes
        dirs = {
            "": {"id": "", "name": "", "is_dir": 1, "size": 0, "parent_id": None, "info": {}}
        }
        
        # Track duplicate counts for file IDs to append #0, #1, etc.
        seen_counts = {}

        # Convert to list to support start_index slicing
        file_items = list(files.items())
        
        def generate_nodes(start_index, n=100_000):
            clone_count = 0
            changed_count = 0
        
            batch = []
            end_index = min(start_index + n, len(file_items))
            for i in range(start_index, end_index):
                path, hashes = file_items[i]
                
                path = path_update_prefix(path)
                path, parts = normalize_path(path)
                
                base_file_id = "/" + "/".join(parts)
                name = parts[-1]

                hashinfo = next(iter(hashes))
                md5, size_str = hashinfo.rsplit(":", 1)
                size = int(size_str)

                # CHECK FILE CHANGES [

                file_id = base_file_id

                # Handle duplicates by appending #<index> to name and id
                if base_file_id in seen_counts:
                    clone_count += 1

                    # Check if file changed
                    dup_index, hashinfo1 = seen_counts[base_file_id]
                    if hashinfo != hashinfo1:
                        seen_counts[base_file_id][0] += 1
                        file_id = f"{base_file_id}#{dup_index}"
                        name = f"{name}#{dup_index}"

                        print(f"DIFF {base_file_id} {hashinfo} {hashinfo1}")
                        changed_count += 1
                    else:
                        # Skip if the same
                        continue

                else:
                    seen_counts[base_file_id] = [0, hashinfo]

                
                # CHECK FILE CHANGES ]
                
                # Accumulate size for root
                dirs[""]["size"] += size


                current_id = ""
                # Use original parts for directory hierarchy, so duplicate files 
                # reside in the same correct parent directory
                for part in parts[:-1]:
                    parent_dir_id = current_id
                    current_id = (current_id + "/" + part) if current_id else ("/" + part)
                    
                    if current_id not in dirs:
                        dirs[current_id] = {
                            "id": current_id, 
                            "name": part, 
                            "is_dir": 1,
                            "size": 0, 
                            "parent_id": parent_dir_id, 
                            "info": {}
                        }
                    # Accumulate size for current directory
                    dirs[current_id]["size"] += size

                parent_id = "/" + "/".join(parts[:-1]) if len(parts) > 1 else ""

                batch.append({
                    "id": file_id,
                    "name": name,
                    "is_dir": 0,
                    "size": size,
                    "parent_id": parent_id,
                    "info": json.dumps({"path": path, "hashinfo": hashinfo, "hash": md5})
                })
            
            if clone_count > 0 or changed_count > 0:
                print(f"{clone_count} clones {changed_count} changed")

            return batch


        with self.conn:
            n = 100_000
            # Insert files in batches of 100k using generate_nodes
            for start_idx in range(0, len(file_items), n):
                print(f'sqlite: {start_idx}/{len(file_items)} files processed...')
                batch = generate_nodes(start_idx, n=n)



                if not batch:
                    continue
                
                self.conn.executemany(
                    """
                    INSERT INTO nodes
                    (id, name, is_dir, size, parent_id, info)
                    VALUES (:id, :name, :is_dir, :size, :parent_id, :info)
                    """,
                    batch
                )

            n=50_000

            # Insert accumulated directories in batches of 100k
            dir_items = list(dirs.values())
            for start_idx in range(0, len(dir_items), n):
                dir_batch = dir_items[start_idx : start_idx + n]

                print(f'sqlite: {start_idx}/{len(dir_items)} dirs created')

                for d in dir_batch:
                    # Stringify json only once
                    if not isinstance(d["info"], str):
                        d["info"] = json.dumps(d["info"])
                
                self.conn.executemany(
                    """
                    INSERT INTO nodes
                    (id, name, is_dir, size, parent_id, info)
                    VALUES (:id, :name, :is_dir, :size, :parent_id, :info)
                    """,
                    dir_batch
                )

        if hashes:
            def generate_hashes():
                for h, paths in hashes.items():
                    for p in paths:
                        yield {"hash_id": h, "path": p}

            index = 0
            with self.conn:
                for batch in batched(generate_hashes(), 100_000):
                    index += len(batch)
                    print(f"sqlite: batch {index} - {len(hashes)} hashes")

                    if not batch:
                        continue
                    self.conn.executemany(
                        """
                        INSERT INTO hashes (hash_id, path)
                        VALUES (:hash_id, :path)
                        """,
                        batch
                    )

    # REBUILD FILE DIRECTORY AND DUPLICATE INDEXES ]
    # MERGE FILES WITHOUT REBUILDING SQLITE [

    def update(self, files, hashes=None):
        """Merge files without rebuilding; omitted files remain unchanged.

        Like build, files maps paths to hash:size collections. Duplicate-index
        entries are derived from each updated file; hashes is accepted for call
        compatibility with build. Files replace directories and their cached
        descendants; files needed as parents become directories. Invalid input
        rolls back the entire update.
        """
        directories = set()
        deltas = {}
        with self.conn:
            for source_path, values in files.items():
                # VALIDATE FILE METADATA AND EXISTING NODE TYPE [

                path, parts = normalize_path(path_update_prefix(source_path))
                if not path or not all(parts) or len(values) != 1:
                    raise ValueError(f"Expected a file path and one hash: {source_path!r}")
                hashinfo = next(iter(values))
                digest, size_text = hashinfo.rsplit(":", 1)
                size = int(size_text)
                if size < 0:
                    raise ValueError(f"Negative file size: {source_path!r}")
                file_id = '/' + '/'.join(parts)
                old = self.conn.execute(
                    "SELECT is_dir, size, info FROM nodes WHERE id = ?", (file_id,)
                ).fetchone()
                old_size = old['size'] if old else 0
                if old and old['is_dir']:
                    # REMOVE CACHED SUBTREE BEFORE REPLACING DIRECTORY WITH FILE [

                    old_size += deltas.get(file_id, 0)
                    subtree = self.conn.execute(
                        """WITH RECURSIVE subtree(id) AS (
                            SELECT id FROM nodes WHERE id = ?
                            UNION ALL
                            SELECT nodes.id FROM nodes JOIN subtree ON nodes.parent_id = subtree.id
                        ) SELECT nodes.* FROM nodes JOIN subtree USING (id)""",
                        (file_id,),
                    ).fetchall()
                    removed_ids = {row['id'] for row in subtree}
                    for row in subtree:
                        if not row['is_dir']:
                            metadata = json.loads(row['info'])
                            candidates = self.conn.execute(
                                'SELECT path FROM hashes WHERE hash_id = ?',
                                (metadata['hashinfo'],),
                            ).fetchall()
                            self.conn.executemany(
                                'DELETE FROM hashes WHERE path = ?',
                                ((candidate['path'],) for candidate in candidates
                                 if '/' + normalize_path(path_update_prefix(candidate['path']))[0]
                                 == row['id']),
                            )
                    self.conn.executemany('DELETE FROM nodes WHERE id = ?',
                                          ((node_id,) for node_id in removed_ids))
                    directories.difference_update(removed_ids)
                    for node_id in removed_ids:
                        deltas.pop(node_id, None)

                    # REMOVE CACHED SUBTREE BEFORE REPLACING DIRECTORY WITH FILE ]

                # VALIDATE FILE METADATA AND EXISTING NODE TYPE ]
                # CREATE MISSING ANCESTOR DIRECTORIES [

                ancestors = ['']
                parent = ''
                for part in parts[:-1]:
                    parent += '/' + part
                    ancestors.append(parent)
                for index, directory in enumerate(ancestors):
                    if directory in directories:
                        continue
                    existing = self.conn.execute(
                        "SELECT is_dir, size, info FROM nodes WHERE id = ?", (directory,)
                    ).fetchone()
                    if existing and not existing['is_dir']:
                        # REPLACE PARENT FILE WITH DIRECTORY AND REMOVE ITS HASH ENTRIES [

                        metadata = json.loads(existing['info'])
                        candidates = self.conn.execute(
                            'SELECT path FROM hashes WHERE hash_id = ?',
                            (metadata['hashinfo'],),
                        ).fetchall()
                        self.conn.executemany(
                            'DELETE FROM hashes WHERE path = ?',
                            ((candidate['path'],) for candidate in candidates
                             if '/' + normalize_path(path_update_prefix(candidate['path']))[0]
                             == directory),
                        )
                        for ancestor in ancestors[:index]:
                            deltas[ancestor] = deltas.get(ancestor, 0) - existing['size']
                        self.conn.execute(
                            "UPDATE nodes SET is_dir = 1, size = 0, info = '{}' WHERE id = ?",
                            (directory,),
                        )

                        # REPLACE PARENT FILE WITH DIRECTORY AND REMOVE ITS HASH ENTRIES ]
                    if not existing:
                        self.conn.execute(
                            "INSERT INTO nodes VALUES (?, ?, 1, 0, ?, '{}')",
                            (directory, directory.rsplit('/', 1)[-1],
                             ancestors[index - 1] if index else None),
                        )
                    directories.add(directory)

                # CREATE MISSING ANCESTOR DIRECTORIES ]
                # ACCUMULATE SIZE CHANGES AND UPSERT FILE METADATA [

                delta = size - old_size
                for directory in ancestors:
                    deltas[directory] = deltas.get(directory, 0) + delta
                info = json.dumps({'path': path, 'hashinfo': hashinfo, 'hash': digest})
                self.conn.execute(
                    """INSERT INTO nodes VALUES (?, ?, 0, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        size = excluded.size, info = excluded.info""",
                    (file_id, parts[-1], size, parent, info),
                )
                # ACCUMULATE SIZE CHANGES AND UPSERT FILE METADATA ]
                # REPLACE DUPLICATE HASH ENTRIES FOR THE UPDATED FILE [

                old_path = json.loads(old['info']).get('path', path) if old else path
                for duplicate_path in {source_path, path, '/' + path.lstrip('/'),
                                       old_path, '/' + old_path.lstrip('/')}:
                    self.conn.execute("DELETE FROM hashes WHERE path = ?", (duplicate_path,))
                self.conn.execute(
                    "INSERT INTO hashes (hash_id, path) VALUES (?, ?)", (hashinfo, source_path)
                )
                # REPLACE DUPLICATE HASH ENTRIES FOR THE UPDATED FILE ]

            # APPLY ACCUMULATED DIRECTORY SIZE CHANGES [

            self.conn.executemany(
                "UPDATE nodes SET size = size + ? WHERE id = ?",
                ((delta, directory) for directory, delta in deltas.items() if delta),
            )
            # APPLY ACCUMULATED DIRECTORY SIZE CHANGES ]

    # MERGE FILES WITHOUT REBUILDING SQLITE ]
    # QUERY SQLITE NODES AND DUPLICATES [

    def get_root(self):
        return self._row_to_node(self.conn.execute("SELECT * FROM nodes WHERE id = ''").fetchone())

    def get_children(self, node):
        return [self._row_to_node(row) for row in 
                self.conn.execute("SELECT * FROM nodes WHERE parent_id = ?", (node.id,))]

    def get_child(self, node, name):
        return self._row_to_node(
            self.conn.execute("SELECT * FROM nodes WHERE parent_id = ? AND name = ?", (node.id, name)).fetchone()
        )
    
    def get_parent(self, node):
        if node.parent_id is None: return None
        return self._row_to_node(self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node.parent_id,)).fetchone())

    def get_hash_dups(self, hash_id):
        rows = self.conn.execute("SELECT path FROM hashes WHERE hash_id = ?", (hash_id,)).fetchall()
        return {row["path"] for row in rows}

    # QUERY SQLITE NODES AND DUPLICATES ]

# STORE AND QUERY FILESYSTEM NODES IN SQLITE ]
