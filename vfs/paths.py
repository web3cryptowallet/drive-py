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
# PRESERVE SOURCE PATH ORIGINS AT THE CATALOG IMPORT BOUNDARY [
def catalog_source_path(path):
    """Store a source path, retaining relative versus absolute spelling."""
    path = os.fspath(path)
    if path.startswith('/~:'):
        path = path[1:]
    if path.startswith('~:'):
        return os.path.normpath(path[2:].lstrip('/') or '.')
    if path.startswith('/:'):
        path = path[1:]
    if path.startswith(':/'):
        return os.path.normpath(path[1:])
    mapped = path_update_prefix(path)
    if mapped != path or path.lstrip('/').split('/')[0] in aliases:
        return '/' + mapped.lstrip('/')
    return os.path.normpath(path)


def catalog_identity_path(path):
    """Decode raw source spelling into the virtual tree's startup namespace."""
    source = catalog_source_path(path)
    if source.lstrip('/').split('/')[0] in aliases or os.path.isabs(source):
        return source
    return '~:' + ('' if source == '.' else source)


def catalog_source_data(data):
    """Canonicalize imported log paths before adapters normalize tree components."""
    result = dict(data)
    result['files'] = {}
    for path, values in data['files'].items():
        result['files'].setdefault(catalog_identity_path(path), set()).update(values)
    result['hashes'] = {digest: {catalog_source_path(path) for path in paths}
                        for digest, paths in data.get('hashes', {}).items()}
    return result
# PRESERVE SOURCE PATH ORIGINS AT THE CATALOG IMPORT BOUNDARY ]
# RESOLVE ALIASES TO LOCAL PATHS [

def get_real_path(path):
    path = os.fspath(path)
    # Explicit global paths bypass aliases, including the catalog's /: node.
    if path.startswith('/~:'):
        path = path[1:]
    if path in ('~:', '/~:'):
        return os.getcwd()
    if path.startswith('~:') and not path.startswith('~:/'):
        path = '~:/' + path[2:]
    if path in (':', '/:'):
        return '/'
    if path.startswith('/') and ':/' in path:
        path = path[1:]
    key, separator, rest = path.partition(':/')
    if separator:
        if key == '':
            return os.path.normpath('/' + rest)
        if key == '~':
            return os.path.abspath(rest or '.')
        if key in aliases:
            return os.path.abspath(os.path.join(os.path.expanduser(aliases[key]), rest))
    _, parts = normalize_path(path)
    alias = aliases.get(parts[0])
    if alias and alias != '0':
        path = os.path.join(os.path.expanduser(alias), *parts[1:])
    # Relative paths are anchored to process startup cwd; absolute paths keep /.
    return os.path.abspath(os.path.expanduser(path))

# RESOLVE ALIASES TO LOCAL PATHS ]
# READ LOCAL FILE METADATA [

def get_stat_info(dup):
    try:
        p = get_real_path(dup)
        symlink = os.path.islink(p)
        st = os.stat(p)
        return {
            "exists": True,
            "is_symlink": symlink,
            "is_dir": stat.S_ISDIR(st.st_mode),
            "is_file": stat.S_ISREG(st.st_mode),
            "created": st.st_ctime,
            "modified": st.st_mtime,
            "size": st.st_size,
        }
    except OSError:
        return {
            "exists": False,
            "is_symlink": os.path.islink(p),
        }

# READ LOCAL FILE METADATA ]
