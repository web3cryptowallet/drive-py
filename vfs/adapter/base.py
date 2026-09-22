"""Database adapter contract and tree construction."""

# IMPORT DATABASE ADAPTER CONTRACT AND TREE CONSTRUCTION DEPENDENCIES [

from abc import ABC, abstractmethod

from ..paths import path_update_prefix
from ..utils import format_size, normalize_path

# IMPORT DATABASE ADAPTER CONTRACT AND TREE CONSTRUCTION DEPENDENCIES ]
# BUILD A COMMON TREE FOR DATABASE ADAPTERS [

class BaseDBAdapter(ABC):
    # DEFINE THE DATABASE NAVIGATION CONTRACT [

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

    # DEFINE THE DATABASE NAVIGATION CONTRACT ]
    # PARSE FILE HASHES AND ACCUMULATE DIRECTORY SIZES [

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

            # BUILD DIRS [
            
            # Create missing intermediate directories & accumulate sizes
            current_id = ""
            for part in parts[:-1]:
                parent_dir_id = current_id
                current_id = (current_id + "/" + part) if current_id else ("/" + part)
                
                if current_id not in nodes:
                    nodes[current_id] = {
                        "id": current_id, 
                        "name": part, 
                        "is_dir": True,
                        "size": 0, 
                        "total_files": 0,
                        "parent_id": parent_dir_id, 
                        "info": {}
                    }
                    total_dirs += 1
                nodes[current_id]["size"] += size
                nodes[current_id]["total_files"] += 1

            # BUILD DIRS ]

        try:
            sz_fmt = format_size(total_size, 0)
        except NameError:
            sz_fmt = f"{total_size} bytes"
            
        print(f"VFS: parsed {total_dirs} dirs and {total_files} files ({sz_fmt})")
        return nodes

    # PARSE FILE HASHES AND ACCUMULATE DIRECTORY SIZES ]

# BUILD A COMMON TREE FOR DATABASE ADAPTERS ]
