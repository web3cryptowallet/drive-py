"""Read-only filesystem probes for the F4 worker, never the render path."""
from pathlib import Path
import shutil

from .utils import format_size


def storage_status(database_paths, browsing_path=None):
    def size(value):
        return format_size(value, 0).strip()

    lines = ['Storage']
    total_size = 0
    volumes = set()

    def volume(path, label):
        try:
            device = path.stat().st_dev
            if device in volumes:
                return
            usage = shutil.disk_usage(path)
            volumes.add(device)
            lines.append(f'  Disk containing {label}: {path}')
            lines.append(f'    Total {size(usage.total)} · used {size(usage.used)} · free {size(usage.free)}')
        except OSError as exc:
            lines.append(f'  Disk space unavailable for {path}: {exc}')

    for filename in dict.fromkeys(database_paths):
        if filename == ':memory:':
            lines.append('  SQLite database: in memory (no database file)')
            continue
        path = Path(filename).absolute()
        try:
            main_size = path.stat().st_size
            side_size = 0
            for suffix in ('-wal', '-shm', '-journal'):
                try:
                    side_size += Path(str(path) + suffix).stat().st_size
                except FileNotFoundError:
                    pass
            total_size += main_size + side_size
            lines.append(f'  Database: {path}')
            lines.append(f'    File {size(main_size)} · sidecars {size(side_size)} · total {size(main_size + side_size)}')
            volume(path, 'database')
        except OSError as exc:
            lines.append(f'  Database size unavailable for {path}: {exc}')
    if database_paths:
        lines.append(f'  Database files total (including sidecars): {size(total_size)}')
    else:
        lines.append('  No local database files (memory or remote backend)')
    if browsing_path:
        volume(Path(browsing_path), 'browsed files')
    return lines
