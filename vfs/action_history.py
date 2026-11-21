"""Persistent action records grouped in LiveLog subnodes."""
# STORE ACTION HISTORY AS ATOMIC LIVELOG SNAPSHOTS [
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from threading import Event, Thread, Lock


class ActionHistory:
    def __init__(self, path):
        self.path = Path(path)
        self.entries = []
        self.error = ''
        self.revision = 0
        self._members = set()
        self._member_count = 0
        self._writer = None
        self._wake, self._stop = Event(), Event()
        self._io_lock = Lock()
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
        self._sync_members()
        entry = dict(action=action, path=path, started=self.now(), last_known=self.now(), **values)
        self.entries.append(entry)
        self._members.add(id(entry))
        self._member_count = len(self.entries)
        self.save()
        return entry

    def update(self, entry, **values):
        self._sync_members()
        if id(entry) not in self._members:
            return  # Deleted playback records must not reappear on progress.
        entry.update(values, last_known=self.now())
        self.save()

    def remove(self, entry):
        self.entries = [item for item in self.entries if item is not entry]
        self.save()

    def save(self):
        self._sync_members()
        self.revision += 1
        if self._writer is not None and self._writer.is_alive():
            self._wake.set()
            return
        self._write()

    def _sync_members(self):
        if self._member_count != len(self.entries):
            self._members = {id(entry) for entry in self.entries}
            self._member_count = len(self.entries)

    def clear(self):
        self.entries.clear()
        self._members.clear()
        self._member_count = 0
        self.save()

    def start_writer(self):
        if self._writer is not None and self._writer.is_alive():
            return
        self._stop.clear()
        def write_loop():
            while True:
                self._wake.wait()
                self._wake.clear()
                if not self._stop.is_set():
                    self._stop.wait(.5)
                self._wake.clear()
                version = self.revision
                self._write()
                if self.revision != version:
                    self._wake.set()
                elif self._stop.is_set():
                    return
        self._writer = Thread(target=write_loop, name='drive-history-writer', daemon=True)
        self._writer.start()

    def close_writer(self):
        if self._writer is not None:
            self._stop.set()
            self._wake.set()
            self._writer.join()
            self._writer = None

    def _write(self):
        with self._io_lock:
            self._write_snapshot([dict(entry) for entry in tuple(self.entries)])

    def _write_snapshot(self, entries):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.history-', delete=False) as output:
                temporary = output.name
                output.write('# history[\n')
                for entry in entries:
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
