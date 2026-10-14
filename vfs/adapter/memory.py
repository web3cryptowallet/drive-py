"""In-memory filesystem storage."""

# IMPORT IN-MEMORY FILESYSTEM STORAGE DEPENDENCIES [

from .base import BaseDBAdapter
from ..nodes import VFSNode

# IMPORT IN-MEMORY FILESYSTEM STORAGE DEPENDENCIES ]
# STORE AND QUERY FILESYSTEM NODES IN MEMORY [

class MemoryDBAdapter(BaseDBAdapter):
    """In-Memory Node Tree Implementation."""
    # BUILD NODE AND CHILD LOOKUP INDEXES [

    def __init__(self):
        self.nodes = {}
        self.children_idx = {}
        self.hashes = {}

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

    def add_scanned_file(self, path, digest, size):
        metadata, ancestors = self.scanned_file_metadata(path, digest, size)
        if metadata['id'] in self.nodes:
            return False
        if any(key in self.nodes and not self.nodes[key].is_dir for key in ancestors):
            raise ValueError('A stored file occupies a parent directory')
        for index, key in enumerate(ancestors):
            if key not in self.nodes:
                node = VFSNode(key, key.rsplit('/', 1)[-1], True,
                               parent_id=ancestors[index - 1] if index else None)
                self.nodes[key] = node
                if node.parent_id is not None:
                    self.children_idx.setdefault(node.parent_id, {})[node.name] = node
            self.nodes[key].size += size
            self.nodes[key].total_files += 1
        node = VFSNode(**metadata)
        self.nodes[node.id] = node
        self.children_idx.setdefault(node.parent_id, {})[node.name] = node
        hashinfo = metadata['info']['hashinfo']
        self.hashes[hashinfo] = set(self.hashes.get(hashinfo, ())) | {metadata['info']['path']}
        return True

    # BUILD NODE AND CHILD LOOKUP INDEXES ]
    # QUERY IN MEMORY NODES AND DUPLICATES [

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

    # QUERY IN MEMORY NODES AND DUPLICATES ]

# STORE AND QUERY FILESYSTEM NODES IN MEMORY ]
