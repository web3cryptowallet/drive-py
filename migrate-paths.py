#!/usr/bin/env python3
"""Explicit maintenance command for legacy catalog source paths."""
# MIGRATE SOURCE PATHS ONLY ON EXPLICIT CLI REQUEST [
import argparse
from pathlib import Path
import sqlite3

from vfs import VirtualFS
from vfs.config import load_config
from vfs.path_migration import migrate_source_paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', nargs='?', default='drivevfs',
                        help='Existing SQLite catalog (default: drivevfs)')
    parser.add_argument('--config', default='config.sh',
                        help='Drive mapping configuration (default: config.sh in current directory)')
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Rows per batch (default: 500; smaller uses less memory)")
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if not Path(args.database).is_file():
        parser.error(f'Database does not exist: {args.database}')
    fs = None
    try:
        load_config(args.config)
        fs = VirtualFS(None, 'sqlite', db_path=args.database)
        count = migrate_source_paths(fs.db, batch_size=args.batch_size)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f'Migration failed: {exc}\n')
    finally:
        if fs is not None:
            fs.db.conn.close()
    print(f'Migrated {count} file records.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
# MIGRATE SOURCE PATHS ONLY ON EXPLICIT CLI REQUEST ]
