"""Drive mapping and local filesystem metadata."""

# IMPORT DRIVE MAPPING AND LOCAL FILESYSTEM METADATA DEPENDENCIES [

import os
import stat

from .utils import normalize_path

# CONFIGURE SHARED DRIVE MAPPINGS [

disabled_prefixes = {}
prefixes = {}
aliases = {}  # alias : local

# CONFIGURE SHARED DRIVE MAPPINGS ]

# IMPORT DRIVE MAPPING AND LOCAL FILESYSTEM METADATA DEPENDENCIES ]
# CHECK DISABLED DRIVE PREFIXES [

def check_disabled_prefixes(prefix):
    for prefix in disabled_prefixes:
        if path.startswith(prefix):
            return True
    return False

# CHECK DISABLED DRIVE PREFIXES ]
# REPLACE DRIVE PREFIXES WITH ALIASES [

def path_update_prefix(path):
    for prefix in prefixes:
        new_prefix = prefixes[prefix]['local']
        new_prefix = prefixes[prefix]['alias']
        if path.startswith(prefix):
            path = new_prefix + path[len(prefix):]
            break
    return path

# REPLACE DRIVE PREFIXES WITH ALIASES ]
# RESOLVE ALIASES TO LOCAL PATHS [

def get_real_path(path):
    _, parts = normalize_path(path)
    alias = aliases.get(parts[0])
    if alias:
        parts[0] = alias
        path = '/'.join(parts)

    return path

# RESOLVE ALIASES TO LOCAL PATHS ]
# READ LOCAL FILE METADATA [

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

# READ LOCAL FILE METADATA ]
