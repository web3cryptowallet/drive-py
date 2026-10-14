"""Redis filesystem storage."""

# IMPORT REDIS FILESYSTEM STORAGE DEPENDENCIES [

import json

from .base import BaseDBAdapter
from ..nodes import VFSNode

# Redis remains optional for memory and SQLite users.
try:
    import redis
except ImportError:
    redis = None

# IMPORT REDIS FILESYSTEM STORAGE DEPENDENCIES ]
# STORE AND QUERY FILESYSTEM NODES IN REDIS [

class RedisDBAdapter(BaseDBAdapter):
    """Redis Implementation. Good for multi-process distributed caches."""
    # CONNECT TO REDIS AND DECODE NODE METADATA [

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

    # CONNECT TO REDIS AND DECODE NODE METADATA ]
    # INDEX NODES AND DUPLICATES IN REDIS [

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

    def add_scanned_file(self, path, digest, size):
        metadata, ancestors = self.scanned_file_metadata(path, digest, size)
        node_key = f"node:{metadata['id']}"
        while True:
            try:
                with self.client.pipeline() as pipe:
                    pipe.watch(node_key, *(f'node:{key}' for key in ancestors))
                    if pipe.exists(node_key):
                        return False
                    parents = [pipe.hgetall(f'node:{key}') for key in ancestors]
                    if any(parent and not int(parent['is_dir']) for parent in parents):
                        raise ValueError('A stored file occupies a parent directory')
                    pipe.multi()
                    for index, (key, parent) in enumerate(zip(ancestors, parents)):
                        if not parent:
                            parent_id = ancestors[index - 1] if index else 'NULL'
                            pipe.hset(f'node:{key}', mapping={
                                'id': key, 'name': key.rsplit('/', 1)[-1], 'is_dir': 1,
                                'size': 0, 'parent_id': parent_id, 'info': '{}'})
                            if index:
                                pipe.sadd(f'children:{parent_id}', key)
                                pipe.hset(f'dir_map:{parent_id}', key.rsplit('/', 1)[-1], key)
                        pipe.hincrby(f'node:{key}', 'size', size)
                    stored = dict(metadata, is_dir=0, info=json.dumps(metadata['info']))
                    pipe.hset(node_key, mapping=stored)
                    pipe.sadd(f"children:{metadata['parent_id']}", metadata['id'])
                    pipe.hset(f"dir_map:{metadata['parent_id']}", metadata['name'], metadata['id'])
                    pipe.sadd(f"hash:{metadata['info']['hashinfo']}", metadata['info']['path'])
                    pipe.execute()
                return True
            except redis.WatchError:
                continue

    # INDEX NODES AND DUPLICATES IN REDIS ]
    # QUERY REDIS NODES AND DUPLICATES [

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

    # QUERY REDIS NODES AND DUPLICATES ]

# STORE AND QUERY FILESYSTEM NODES IN REDIS ]
