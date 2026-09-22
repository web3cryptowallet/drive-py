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
