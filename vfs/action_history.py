"""Persistent action records grouped in LiveLog subnodes."""
# STORE ACTION HISTORY AS ATOMIC LIVELOG SNAPSHOTS [
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile


class ActionHistory:
    def __init__(self, path):
        self.path = Path(path)
        self.entries = []
        self.error = ''
        try:
            for line in self.path.read_text(encoding='utf-8').splitlines():
                if line.startswith('{'):
                    entry = json.loads(line)
                    if (isinstance(entry, dict) and
                            all(isinstance(entry.get(k), str) for k in ('action', 'path', 'started', 'last_known'))):
                        self.entries.append(entry)
        except (OSError, ValueError) as exc:
            if not isinstance(exc, FileNotFoundError):
                self.error = str(exc)

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    def add(self, action, path, *, coalesce=False, **values):
        if coalesce and self.entries and self.entries[-1]['action'] == action and self.entries[-1]['path'] == path:
            return self.entries[-1]
        entry = dict(action=action, path=path, started=self.now(), last_known=self.now(), **values)
        self.entries.append(entry)
        self.save()
        return entry

    def update(self, entry, **values):
        if not any(item is entry for item in self.entries):
            return  # Deleted playback records must not reappear on progress.
        entry.update(values, last_known=self.now())
        self.save()

    def remove(self, entry):
        self.entries = [item for item in self.entries if item is not entry]
        self.save()

    def save(self):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.history-', delete=False) as output:
                temporary = output.name
                output.write('# history[\n')
                for entry in self.entries:
                    group = 'view image' if entry['action'] == 'view image' else 'action'
                    output.write(f'# {group}[\n')
                    output.write(json.dumps(entry, ensure_ascii=True) + '\n')
                    output.write(f'# {group}]\n')
                output.write('# history]\n')
            os.replace(temporary, self.path)
            temporary = None
            self.error = ''
        except OSError as exc:
            self.error = str(exc)
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
# STORE ACTION HISTORY AS ATOMIC LIVELOG SNAPSHOTS ]
