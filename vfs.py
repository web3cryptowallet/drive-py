import os
import stat

from dataclasses import dataclass, field

# VIRTUAL FS [

# MAP DRIVES [

disabled_prefixes = {}
prefixes = {}
aliases = {}

def check_disabled_prefixes(prefix):
    for prefix in disabled_prefixes:
        if path.startswith(prefix):
            return True
    return False

def path_update_prefix(path):
    for prefix in prefixes:
        new_prefix = prefixes[prefix]['local']
        new_prefix = prefixes[prefix]['alias']
        if path.startswith(prefix):
            path = new_prefix + path[len(prefix):]
            break
    return path

def get_real_path(path):
    _, parts = normalize_path(path)
    alias = aliases.get(parts[0])
    if alias:
        parts[0] = alias
        path = '/'.join(parts)

    return path

# MAP DRIVES ]
# UTIL [

def format_size(size, type):
    if size is None:
        return "N/A"

    if type == 0:
        units = ["bytes", "KB", "MB", "GB", "TB"]
    else:
        units = ["", "KB", "MB", "GB", "TB"]

    size = float(size)

    for unit in units:
        if size < 1024:
            return f"{round(size)} {unit}"
        size /= 1024

    return f"{round(size)} PB"


def normalize_path(path):
    parts = path.replace("//", "/").lstrip("/").rstrip("/").split("/")

    path = "/".join(parts)

    return (path, parts) 

# UTIL ]
# DRIVE ACTIONS LIST [

class DriveActionsList:
    actions = []
    
    def __init__(self):
        pass

    def append(self, action):
        self.actions.append(action)

    def clear(self):
        self.actions.clear()

# DRIVE ACTIONS LIST ]

@dataclass
class Node:
    name: str
    is_dir: bool
    parent: "Node | None" = None
    children: dict[str, "Node"] = field(default_factory=dict)
    info: dict | None = None
    size: int = 0

def get_stat_info(dup):
    try:
        p = get_real_path(dup)
        st = os.stat(p)
        return {
            "exists": True,
            "is_dir": stat.S_ISDIR(st.st_mode),
            "is_file": stat.S_ISREG(st.st_mode),
            "created": st.st_ctime,
            "modified": st.st_mtime,
            "size": st.st_size,
        }
    except FileNotFoundError:
        return {
            "exists": False,
        }

# VIRTUAL FS

# class VirtualFS:
#     def __init__(self, data):
#         self.root = Node("", True)
#         self.data = data
#         self.cwd = self.root
#         self._build(data["files"])

#     def _build(self, files):
#         print("VFS: Building..")

#         total_dirs = 0
#         total_files = 0
#         total_size = 0

#         for path, hashes in files.items():

# #            # CHECK DISABLED [
# #
# #            if (check_disabled_prefixes(prefix)):
# #                continue
# #
# #            # CHECK DISABLED ]

#             path = path_update_prefix(path)

#             path, parts = normalize_path(path)
            
#             total_files += 1

#             if total_files % 100000 == 0:
#                 print(f'{total_files}/{len(files)} files')

#             hashinfo = next(iter(hashes))
#             md5, size = hashinfo.rsplit(":", 1)

#             size = int(size)

#             cur = self.root

#             for part in parts[:-1]:
#                 if part not in cur.children:
#                     cur.children[part] = Node(part, True, parent=cur)
#                     total_dirs += 1
#                 cur.children[part].size += size
#                 cur = cur.children[part]

#             total_size += size

#             cur.children[parts[-1]] = Node(
#                 name=parts[-1],
#                 is_dir=False,
#                 parent=cur,
#                 info={
#                     "path": path,
#                     "hashinfo": hashinfo, 
#                     "hash": md5,
#                 },
#                 size = size,
#             )
#         print(f"VFS: built {total_dirs} dirs and {total_files} files {format_size(total_size, 0)}")

#     def pwd(self):
#         node = self.cwd
#         parts = []
#         while node.parent:
#             parts.append(node.name)
#             node = node.parent
#         return "/" + "/".join(reversed(parts))

#     def listdir(self):
#         result = []

#         if self.cwd.parent:
#             result.append(("..", True))

#         dirs = []
#         files = []

#         for node in self.cwd.children.values():
#             if node.is_dir:
#                 dirs.append(node)
#             else:
#                 files.append(node)

#         dirs.sort(key=lambda n: n.name)
#         files.sort(key=lambda n: n.name)

#         for n in dirs:
#             result.append((n.name, True))

#         for n in files:
#             result.append((n.name, False))

#         return result

#     def enter(self, name):
#         if name == "..":
#             if self.cwd.parent:
#                 self.cwd = self.cwd.parent
#             return

#         node = self.cwd.children[name]

#         if node.is_dir:
#             self.cwd = node

#     def get_cwd(self):
#         return self.cwd


#     def get(self, name):
#         if name == "..":
#             return self.cwd.parent
#         return self.cwd.children[name]


#     def get_full_info(self, node):

#         # for directory
#         if node.is_dir:
#             current_path = self.pwd() + '/' + node.name
#             info = get_stat_info(current_path)
#             info["dups"] = []
#             info["dups_states"] = []
#             return info
        
#         # 1. Get all paths sharing this hash (defaults to empty set if not found)
#         file_hash = node.info['hashinfo']
#         all_dups = self.data['hashes'].get(file_hash, set())
        
#         # 2. Filter out the current file's path
#         current_path = node.info['path']

#         dups = [p for p in map(lambda x: path_update_prefix('/' + normalize_path(x)[0]), all_dups) if p != current_path]

#         dups_states = []

#         for dup in dups:
#             dups_states.append(get_stat_info(dup))

#         info = get_stat_info(current_path)
#         info["dups"] = dups
#         info["dups_states"] = dups_states

#         return info

import json
import sqlite3
from abc import ABC, abstractmethod

# Try to import redis, but don't crash if it's not installed
try:
    import redis
except ImportError:
    redis = None

# ==========================================
# 1. Core Data Structures
# ==========================================

class VFSNode:
    """Standardized node abstraction returned by all DB adapters."""
    def __init__(self, id, name, is_dir, size=0, parent_id=None, info=None):
        self.id = id
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.parent_id = parent_id
        self.info = info or {}


# ==========================================
# 2. Database Adapters
# ==========================================

class BaseDBAdapter(ABC):
    @abstractmethod
    def build(self, files): pass
    @abstractmethod
    def get_root(self): pass
    @abstractmethod
    def get_children(self, node): pass
    @abstractmethod
    def get_child(self, node, name): pass
    @abstractmethod
    def get_parent(self, node): pass

    def _parse_files_to_dicts(self, files):
        """
        Pre-computes the tree structure, calculates directory sizes, and 
        returns a flattened dictionary mapping node IDs to their attributes.
        """
        print("VFS: Building tree data...")
        nodes = {}
        # Root node
        nodes[""] = {"id": "", "name": "", "is_dir": True, "size": 0, "parent_id": None, "info": {}}

        total_dirs = 0
        total_files = 0
        total_size = 0

        for path, hashes in files.items():
            # Assumes path_update_prefix and normalize_path exist in global scope
            path = path_update_prefix(path)
            path, parts = normalize_path(path)
            
            total_files += 1
            if total_files % 100000 == 0:
                print(f'{total_files}/{len(files)} files processed...')

            hashinfo = next(iter(hashes))
            md5, size = hashinfo.rsplit(":", 1)
            size = int(size)
            total_size += size

            file_id = "/" + "/".join(parts)
            parent_id = "/" + "/".join(parts[:-1]) if len(parts) > 1 else ""

            nodes[file_id] = {
                "id": file_id,
                "name": parts[-1],
                "is_dir": False,
                "size": size,
                "parent_id": parent_id,
                "info": {"path": path, "hashinfo": hashinfo, "hash": md5}
            }

            nodes[""]["size"] += size
            
            # Create missing intermediate directories & accumulate sizes
            current_id = ""
            for part in parts[:-1]:
                parent_dir_id = current_id
                current_id = (current_id + "/" + part) if current_id else ("/" + part)
                
                if current_id not in nodes:
                    nodes[current_id] = {
                        "id": current_id, "name": part, "is_dir": True,
                        "size": 0, "parent_id": parent_dir_id, "info": {}
                    }
                    total_dirs += 1
                nodes[current_id]["size"] += size
                
        # Assumes format_size exists in global scope
        try:
            sz_fmt = format_size(total_size, 0)
        except NameError:
            sz_fmt = f"{total_size} bytes"
            
        print(f"VFS: parsed {total_dirs} dirs and {total_files} files ({sz_fmt})")
        return nodes


class MemoryDBAdapter(BaseDBAdapter):
    """In-Memory Node Tree Implementation."""
    def __init__(self):
        self.nodes = {}
        self.children_idx = {}

    def build(self, files, hashes):
        self.hashes = hashes
        nodes_data = self._parse_files_to_dicts(files)
        
        for nd in nodes_data.values():
            node = VFSNode(**nd)
            self.nodes[node.id] = node
            
            if node.parent_id is not None:
                if node.parent_id not in self.children_idx:
                    self.children_idx[node.parent_id] = {}
                self.children_idx[node.parent_id][node.name] = node

    def get_root(self):
        return self.nodes.get("")
        
    def get_children(self, node):
        return list(self.children_idx.get(node.id, {}).values())
        
    def get_child(self, node, name):
        return self.children_idx.get(node.id, {}).get(name)
        
    def get_parent(self, node):
        if node.parent_id is None:
            return None
        return self.nodes.get(node.parent_id)

    def get_hash_dups(self, hash_id):
        return self.hashes.get(hash_id, [])

# SQLITE

from itertools import islice

def batched(iterable, size):
    it = iter(iterable)
    while batch := list(islice(it, size)):
        yield batch

class SQLiteDBAdapter(BaseDBAdapter):
    """SQLite Implementation. Efficient for large filesystems."""
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

    def _row_to_node(self, row):
        if not row: return None
        return VFSNode(
            id=row["id"], name=row["name"], is_dir=bool(row["is_dir"]),
            size=row["size"], parent_id=row["parent_id"], 
            info=json.loads(row["info"]) if row["info"] else {}
        )

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
            batch = []
            end_index = min(start_index + n, len(file_items))
            for i in range(start_index, end_index):
                path, hashes = file_items[i]
                
                path = path_update_prefix(path)
                path, parts = normalize_path(path)
                
                base_file_id = "/" + "/".join(parts)
                name = parts[-1]
                
                # Handle duplicates by appending #<index> to name and id
                if base_file_id in seen_counts:
                    dup_index = seen_counts[base_file_id]
                    seen_counts[base_file_id] += 1
                    file_id = f"{base_file_id}#{dup_index}"
                    name = f"{name}#{dup_index}"
                else:
                    seen_counts[base_file_id] = 0
                    file_id = base_file_id
                
                hashinfo = next(iter(hashes))
                md5, size_str = hashinfo.rsplit(":", 1)
                size = int(size_str)
                
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
            return batch

        with self.conn:
            n = 100_000
            # Insert files in batches of 100k using generate_nodes
            for start_idx in range(0, len(file_items), n):
                print(f'sqlite: {start_idx}/{len(file_items)} files processed...')
                batch = generate_nodes(start_idx, n=n)

#                print(f'seen_counts {len(seen_counts)} dirs {len(dirs)}')

#                continue

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

#            print(f"sqlite: {len(dirs)} dirs")
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

# REDIS

class RedisDBAdapter(BaseDBAdapter):
    """Redis Implementation. Good for multi-process distributed caches."""
    def __init__(self, host='localhost', port=6379, db=0):
        if redis is None:
            raise ImportError("redis module is not installed. Run `pip install redis`.")
        self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    def _dict_to_node(self, d):
        if not d or "id" not in d: return None
        parent_id = d.get("parent_id")
        if parent_id == "NULL": parent_id = None
        return VFSNode(
            id=d["id"], name=d["name"], is_dir=bool(int(d["is_dir"])),
            size=int(d["size"]), parent_id=parent_id,
            info=json.loads(d.get("info", "{}"))
        )

    def build(self, files, hashes=None):
        nodes = self._parse_files_to_dicts(files)
        pipe = self.client.pipeline()
        
        for n in nodes.values():
            n_copy = n.copy()
            n_copy["info"] = json.dumps(n["info"])
            n_copy["is_dir"] = 1 if n["is_dir"] else 0
            if n_copy["parent_id"] is None:
                n_copy["parent_id"] = "NULL"
                
            pipe.hset(f"node:{n['id']}", mapping=n_copy)
            
            # Map parent's children for fast lookups
            if n["parent_id"] is not None:
                pipe.sadd(f"children:{n['parent_id']}", n["id"])
                pipe.hset(f"dir_map:{n['parent_id']}", n["name"], n["id"])

        if hashes:
            for h, paths in hashes.items():
                if paths:
                    # Unpack the set of paths into sadd
                    pipe.sadd(f"hash:{h}", *paths)
                    
        pipe.execute()

    def get_root(self):
        return self._dict_to_node(self.client.hgetall("node:"))

    def get_children(self, node):
        child_ids = self.client.smembers(f"children:{node.id}")
        if not child_ids: return []
        
        pipe = self.client.pipeline()
        for cid in child_ids:
            pipe.hgetall(f"node:{cid}")
        return [self._dict_to_node(d) for d in pipe.execute() if d]

    def get_child(self, node, name):
        child_id = self.client.hget(f"dir_map:{node.id}", name)
        if not child_id: return None
        return self._dict_to_node(self.client.hgetall(f"node:{child_id}"))

    def get_parent(self, node):
        if node.parent_id is None: return None
        return self._dict_to_node(self.client.hgetall(f"node:{node.parent_id}"))

    def get_hash_dups(self, hash_id):
        return self.client.smembers(f"hash:{hash_id}") or set()

# ==========================================
# 3. VirtualFS Refactored Client
# ==========================================

class VirtualFS:
    def __init__(self, data, db_type="memory", rebuild_db=False, **db_kwargs):
        #self.data = data
        
        # Instantiate adapter dynamically based on db_type
        if db_type == "memory":
            self.db = MemoryDBAdapter(**db_kwargs)
        elif db_type == "sqlite":
            self.db = SQLiteDBAdapter(**db_kwargs)
        elif db_type == "redis":
            self.db = RedisDBAdapter(**db_kwargs)
        else:
            raise ValueError(f"Unknown db_type: {db_type}")

        if db_type == "memory" or rebuild_db:
            self.db.build(data["files"], data["hashes"])

        self.cwd = self.db.get_root()


    def pwd(self):
        node = self.cwd
        parts = []
        while True:
            parent = self.db.get_parent(node)
            if parent is None:
                break
            parts.append(node.name)
            node = parent
        return "/" + "/".join(reversed(parts))

    def listdir(self):
        result = []

        if self.db.get_parent(self.cwd):
            result.append(("..", True))

        dirs = []
        files = []

        children = self.db.get_children(self.cwd)

        for node in children:
            if node.is_dir:
                dirs.append(node)
            else:
                files.append(node)

        dirs.sort(key=lambda n: n.name)
        files.sort(key=lambda n: n.name)

        for n in dirs:
            result.append((n.name, True))

        for n in files:
            result.append((n.name, False))

        return result

    def enter(self, name):
        if name == "..":
            parent = self.db.get_parent(self.cwd)
            if parent:
                self.cwd = parent
            return

        node = self.db.get_child(self.cwd, name)
        if node and node.is_dir:
            self.cwd = node

    def get_cwd(self):
        return self.cwd

    def get(self, name):
        if name == "..":
            return self.db.get_parent(self.cwd)
        return self.db.get_child(self.cwd, name)

    def get_full_info(self, node):
        file_hash = node.info.get('hashinfo')
        
        # Fetch duplicates from the database instead of memory
        all_dups = self.db.get_hash_dups(file_hash)
        
        current_path = node.info.get('path')
        dups = [p for p in map(lambda x: path_update_prefix('/' + normalize_path(x)[0]), all_dups) if p != current_path]
        
        # Assumes get_stat_info exists in global scope
        dups_states = [get_stat_info(dup) for dup in dups]
        
        info = get_stat_info(current_path)
        info["dups"] = dups
        info["dups_states"] = dups_states

        return info

    def get_hash_dups(self, file_hash):
        """Returns a set of paths that share the same hash."""
        return self.db.get_hash_dups(file_hash)

    # def get_full_info(self, node):
    #     file_hash = node.info.get('hashinfo')
    #     all_dups = self.data['hashes'].get(file_hash, set())
        
    #     current_path = node.info.get('path')
    #     dups = [p for p in map(lambda x: path_update_prefix('/' + normalize_path(x)[0]), all_dups) if p != current_path]
        
    #     # Assumes get_stat_info exists in global scope
    #     dups_states = [get_stat_info(dup) for dup in dups]
        
    #     info = get_stat_info(current_path)
    #     info["dups"] = dups
    #     info["dups_states"] = dups_states

    #     return info
    
    def get_from_path(self, fullpath):
        path, parts = normalize_path(fullpath)
        node = self.root
        for p in parts:
            node = node.children.get(p)
            if node is None:
                break
        return node

# VIRTUAL FS ]
# VIRTUAL FS TEST [

def test_vfs():
    data = {
        "files": {
            "test0/t0/fileA": {"MD5:c6f057b86584942e415435ffb1fa93d4:3"},
            "test0/t0/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
            "test0/t1/fileA": {"MD5:202cb962ac59075b964b07152d234b70:3"},
            "test0/t1/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
            "test0/t1/fileC": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
        }
    }

    vfs = VirtualFS(data)

    print(vfs.pwd())
    print(vfs.listdir())

    vfs.enter("test0")
    print(vfs.listdir())

    vfs.enter("t1")
    print(vfs.listdir())

    file = vfs.get("fileC")
    print(file.info)

# VIRTUAL FS TEST ]
