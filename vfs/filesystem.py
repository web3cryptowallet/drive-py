"""Filesystem navigation and duplicate inspection."""

# IMPORT FILESYSTEM NAVIGATION AND DUPLICATE INSPECTION DEPENDENCIES [

from .adapter.memory import MemoryDBAdapter
from .nodes import VFSNode
from .paths import get_stat_info, path_update_prefix
from .adapter.redis import RedisDBAdapter
from .adapter.sqlite import SQLiteDBAdapter
from .utils import normalize_path

# IMPORT FILESYSTEM NAVIGATION AND DUPLICATE INSPECTION DEPENDENCIES ]
# NAVIGATE FILES AND INSPECT DUPLICATES [

class VirtualFS:
    # SELECT AND INITIALIZE FILESYSTEM STORAGE [

    def __init__(self, data, db_type="memory", rebuild_db=False, **db_kwargs):
        
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

    # SELECT AND INITIALIZE FILESYSTEM STORAGE ]
    # MERGE LOG DATA AND REFRESH CURRENT DIRECTORY [

    def update(self, data):
        """Merge a log into SQLite and refresh the current directory metadata."""
        if not isinstance(self.db, SQLiteDBAdapter):
            raise NotImplementedError("Incremental updates require SQLite")
        current_path = self.cwd.id if self.cwd else ''
        self.db.update(data['files'], data.get('hashes'))
        self.cwd = self.get_from_path(current_path) if current_path else self.db.get_root()

    # MERGE LOG DATA AND REFRESH CURRENT DIRECTORY ]
    # NAVIGATE AND LIST THE CURRENT DIRECTORY [

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

    def listdir(self, node = None):
        if node is None:
            node = self.cwd

        result = []

        if self.db.get_parent(node):
            result.append(("..", True))

        dirs = []
        files = []

        children = self.db.get_children(node)

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

    def get_cwd(self) -> VFSNode:
        return self.cwd

    def get(self, name) -> VFSNode:
        if name == "..":
            return self.db.get_parent(self.cwd)
        return self.db.get_child(self.cwd, name)

    # NAVIGATE AND LIST THE CURRENT DIRECTORY ]
    # INSPECT FILE METADATA AND DUPLICATE CONTENT [

    def get_full_info(self, node, only_stat=False):
        if node.is_dir:
            current_path = node.id
            info = get_stat_info(current_path)

            return info

        current_path = node.info.get('path')
        info = get_stat_info(current_path)

        if only_stat:
            return info

        # ADD DUPS

        file_hash = node.info.get('hashinfo')
        
        # Fetch duplicates from the database instead of memory
        all_dups = self.db.get_hash_dups(file_hash)
        
        dups = [p for p in map(lambda x: path_update_prefix('/' + normalize_path(x)[0]), all_dups) if p != current_path]
        
        dups_states = [get_stat_info(dup) for dup in dups]


        order = sorted(range(len(dups)), key=lambda i: dups[i].lower())
        dups = [dups[i] for i in order]
        dups_states = [dups_states[i] for i in order]

        info["dups"] = dups
        info["dups_states"] = dups_states

        return info

    def get_hash_dups(self, file_hash):
        """Returns a set of paths that share the same hash."""
        return self.db.get_hash_dups(file_hash)

    # INSPECT FILE METADATA AND DUPLICATE CONTENT ]
    # LOOK UP A NODE BY VIRTUAL PATH [

    def get_from_path(self, fullpath):
        path, parts = normalize_path(fullpath)
        node = self.db.get_root()
        for p in parts:
            node = self.db.get_child(node, p)
            if node is None:
                break
        return node

    # LOOK UP A NODE BY VIRTUAL PATH ]

# NAVIGATE FILES AND INSPECT DUPLICATES ]
