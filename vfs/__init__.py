"""Virtual filesystem API shared by the drive browser and action screens."""

# EXPOSE THE PUBLIC VIRTUAL FILESYSTEM API [

from .actions import DriveActionsList
from .adapter.base import BaseDBAdapter
from .filesystem import VirtualFS
from .adapter.memory import MemoryDBAdapter
from .nodes import Node, VFSNode
from .paths import aliases, disabled_prefixes, prefixes, check_disabled_prefixes, get_real_path, get_stat_info, path_update_prefix
from .adapter.redis import RedisDBAdapter
from .adapter.sqlite import SQLiteDBAdapter
from .utils import batched, format_size, normalize_path
from .demo import test_vfs

# EXPOSE THE PUBLIC VIRTUAL FILESYSTEM API ]

__all__ = [
    "DriveActionsList",
    "BaseDBAdapter",
    "VirtualFS",
    "MemoryDBAdapter",
    "Node",
    "VFSNode",
    "aliases",
    "disabled_prefixes",
    "prefixes",
    "check_disabled_prefixes",
    "get_real_path",
    "get_stat_info",
    "path_update_prefix",
    "RedisDBAdapter",
    "SQLiteDBAdapter",
    "batched",
    "format_size",
    "normalize_path",
    "test_vfs",
]
