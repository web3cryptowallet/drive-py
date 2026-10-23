"""Shared catalog configuration for the browser and maintenance commands."""
# LOAD DRIVE MAPPINGS AND APPLICATION SETTINGS [
import json
import os
import shlex
from pathlib import Path
from livelog2 import LiveLog
from .paths import aliases, disabled_prefixes, prefixes


def load_config(filename="config.sh"):
    if not Path(filename).is_file():
        return {}
    log = LiveLog(filename)
    log.load()
    mappings = log._tree._items.get('MAP DRIVES')
    if mappings is not None:
        for line in mappings._ss:
            parts = shlex.split(line)
            if len(parts) < 2:
                continue
            prefix, local = parts[0], os.path.expanduser(parts[1])
            alias = parts[2] if len(parts) > 2 else prefix
            aliases[alias] = local
            if local == '0':
                disabled_prefixes[prefix] = prefix
            else:
                prefixes[prefix] = {'local': local, 'alias': alias}

    settings = log._tree._items.get('SETTINGS JSON')
    return json.loads('\n'.join(settings._ss)) if settings is not None else {}
# LOAD DRIVE MAPPINGS AND APPLICATION SETTINGS ]
