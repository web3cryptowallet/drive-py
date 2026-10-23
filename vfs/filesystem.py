"""Filesystem navigation and duplicate inspection."""

# IMPORT FILESYSTEM NAVIGATION AND DUPLICATE INSPECTION DEPENDENCIES [

import os

from .adapter.memory import MemoryDBAdapter
from .nodes import VFSNode
from .paths import aliases, get_real_path, get_stat_info, path_update_prefix, catalog_identity_path
from .adapter.redis import RedisDBAdapter
from .adapter.sqlite import SQLiteDBAdapter
from .adapter.fragmented import FragmentedSQLiteDBAdapter
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
            self.db = (FragmentedSQLiteDBAdapter(**db_kwargs)
                       if db_kwargs.get('fragments') or db_kwargs.get('refragment')
                       or self._has_fragments(db_kwargs.get('db_path', 'drivevfs'))
                       else SQLiteDBAdapter(**db_kwargs))
        elif db_type == "redis":
            self.db = RedisDBAdapter(**db_kwargs)
        else:
            raise ValueError(f"Unknown db_type: {db_type}")

        if db_type == "memory" or rebuild_db:
            self.db.build(data["files"], data.get("hashes", {}))

        self._local_nodes = {}
        self.cwd = self.db.get_root()

    @staticmethod
    def _has_fragments(filename):
        import sqlite3
        if not os.path.isfile(filename):
            return False
        conn = sqlite3.connect(filename)
        try:
            return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name='db_fragments'").fetchone())
        finally:
            conn.close()

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
        return self.cwd.id or "/"

    def start_in_current_directory(self, path=None):
        """Open a local startup path (default: cwd), translating drive aliases."""
        explicit = path is not None
        path = os.path.abspath(os.path.expanduser(os.fspath(path))) if explicit else os.getcwd()
        if explicit and not os.path.isdir(path):
            raise ValueError(f'Startup path is not a directory: {path}')
        # Match physical targets so symlinked startup paths and mount roots
        # reuse the catalog alias instead of opening an unindexed local tree.
        path = os.path.realpath(path)
        mounts = [(alias, os.path.realpath(os.path.expanduser(local)))
                  for alias, local in aliases.items()]
        for alias, local in sorted(mounts, key=lambda item: len(item[1]), reverse=True):
            if path == local or path.startswith(local.rstrip('/') + '/'):
                path = '/' + alias + path[len(local):]
                break
        # Prefer an imported startup-relative catalog when opening launch cwd.
        startup = os.path.realpath(os.getcwd())
        relative_root = self.db.get_child(self.db.get_root(), '~:')
        if relative_root is not None and (path == startup or path.startswith(startup.rstrip('/') + '/')):
            path = '/~:' + ('/' + os.path.relpath(path, startup) if path != startup else '')
        node = self.get_from_path(path)
        if node and node.is_dir:
            self.cwd = node
        elif explicit:
            raise ValueError(f'Cannot open startup directory: {path}')

    def _parent(self, node):
        if node.parent_id is None:
            return None
        return self.get_from_path(node.parent_id)

    def _child(self, parent, name):
        node = self.db.get_child(parent, name)
        if node is not None:
            return node
        return self._local_node(parent.id + '/' + name, parent.id)

    def _local_node(self, path, parent_id):
        real = get_real_path(path)
        try:
            st = os.stat(real) if os.path.exists(real) else os.lstat(real)
        except OSError:
            return None
        node = VFSNode(path, path.rsplit('/', 1)[-1], os.path.isdir(real),
                       size=st.st_size, parent_id=parent_id,
                       info={'path': path, 'hashinfo': None, 'status': 'new'})
        if parent_id == "":
            self._local_nodes[path] = node
        return node

    def list_nodes(self, node=None):
        """Merge immediate disk entries with database nodes without changing storage."""
        node = node or self.cwd
        children = {child.name: child for child in self.db.get_children(node)}
        # The empty root is a virtual collection of drives, not the host root.
        if node.id:
            try:
                with os.scandir(get_real_path(node.id)) as entries:
                    for entry in entries:
                        if entry.name not in children:
                            child = self._local_node(node.id + '/' + entry.name, node.id)
                            if child:
                                children[entry.name] = child
            except OSError:
                pass
        else:
            for child in self._local_nodes.values():
                if child.parent_id == '' and child.name not in children:
                    children[child.name] = child
        for child in children.values():
            if child.info.get('status') != 'new':
                child.info['status'] = ('tracked' if os.path.exists(get_real_path(child.id))
                                        else 'deleted')
        return sorted(children.values(), key=lambda child: (not child.is_dir, child.name))

    def listdir(self, node = None):
        if node is None:
            node = self.cwd

        result = [("..", True)] if self._parent(node) else []
        result.extend((child.name, child.is_dir) for child in self.list_nodes(node))
        return result

    def enter(self, name):
        if name == "..":
            parent = self._parent(self.cwd)
            if parent:
                self.cwd = parent
            return

        node = self._child(self.cwd, name)
        if node and node.is_dir:
            self.cwd = node

    def get_cwd(self) -> VFSNode:
        return self.cwd

    def get(self, name) -> VFSNode:
        if name == "..":
            return self._parent(self.cwd)
        return self._child(self.cwd, name)

    # NAVIGATE AND LIST THE CURRENT DIRECTORY ]
    # INSPECT FILE METADATA AND DUPLICATE CONTENT [

    def get_full_info(self, node, only_stat=False):
        if node.is_dir:
            current_path = node.id
            info = get_stat_info(current_path)

            return info

        current_path = node.id
        info = get_stat_info(current_path)

        if only_stat:
            return info

        # ADD DUPS

        file_hash = node.info.get('hashinfo')
        
        # Fetch duplicates from the database instead of memory
        all_dups = self.get_hash_dups(file_hash)
        
        dups = [p for p in map(self.decode_source_path, all_dups) if p != current_path]
        
        dups_states = [get_stat_info(dup) for dup in dups]


        order = sorted(range(len(dups)), key=lambda i: dups[i].lower())
        dups = [dups[i] for i in order]
        dups_states = [dups_states[i] for i in order]

        info["dups"] = dups
        info["dups_states"] = dups_states

        return info

    def get_hash_dups(self, file_hash):
        """Returns a set of paths that share the same hash."""
        return self.db.get_hash_dups(file_hash) if file_hash else []

    # INSPECT FILE METADATA AND DUPLICATE CONTENT ]
    # LOOK UP A NODE BY VIRTUAL PATH [

    def decode_source_path(self, path):
        root = self.db.get_root()
        startup = self.db.get_child(root, '~:') if root is not None else None
        first = path.split('/', 1)[0]
        legacy = self.db.get_child(root, first) if root is not None and first else None
        if startup is not None or (not path.startswith('/') and legacy is None):
            path = catalog_identity_path(path)
        return '/' + normalize_path(path_update_prefix(path))[0]

    def get_from_path(self, fullpath):
        if not fullpath or fullpath == "/":
            return self.db.get_root()
        if not fullpath.startswith('/'):
            fullpath = self.decode_source_path(fullpath)
        path, parts = normalize_path(fullpath)
        node = self.db.get_root()
        for p in parts:
            node = self._child(node, p)
            if node is None:
                break
        return node

    # LOOK UP A NODE BY VIRTUAL PATH ]

# NAVIGATE FILES AND INSPECT DUPLICATES ]
