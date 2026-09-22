"""Virtual filesystem node representations."""

# IMPORT VIRTUAL FILESYSTEM NODE REPRESENTATIONS DEPENDENCIES [

from dataclasses import dataclass, field

# IMPORT VIRTUAL FILESYSTEM NODE REPRESENTATIONS DEPENDENCIES ]
# REPRESENT PARENT AND CHILD NODE RELATIONSHIPS [

@dataclass
class Node:
    name: str
    is_dir: bool
    parent: "Node | None" = None
    children: dict[str, "Node"] = field(default_factory=dict)
    info: dict | None = None
    size: int = 0

# REPRESENT PARENT AND CHILD NODE RELATIONSHIPS ]
# REPRESENT DATABASE NODE METADATA [

class VFSNode:
    """Standardized node abstraction returned by all DB adapters."""
    def __init__(self, id, name, is_dir, size=0, total_files=0, parent_id=None, info=None):
        self.id = id
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.total_files = total_files
        self.parent_id = parent_id
        self.info = info or {}

# REPRESENT DATABASE NODE METADATA ]
