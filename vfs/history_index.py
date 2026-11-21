"""Indexed history snapshots with viewport-only row formatting."""
from collections import OrderedDict
from collections.abc import Sequence
from prompt_toolkit.utils import get_cwidth


def stamp(value):
    return value.replace('T', ' ').removesuffix('+00:00')


def playback(entry):
    return (f"  start {entry.get('start_position', 0):.1f}s → {entry.get('position', 0):.1f}/"
            f"{entry.get('duration', 0):.1f}s · {stamp(entry['last_known'])}" if entry['action'] == 'play' else '')


class HistoryRows(Sequence):
    def __init__(self, index, request, safe):
        self.index, self.request, self.safe = index, request, safe
        self.cache = OrderedDict()

    def __len__(self):
        return len(self.index.visible)

    @property
    def maximum_width(self):
        return self.index.maximum_width

    def __getitem__(self, position):
        if isinstance(position, slice):
            return [self[i] for i in range(*position.indices(len(self)))]
        original = self.index.visible[position]
        entry = self.index.entries[original]
        present = self.index.presence.get(entry['path'])
        if present is None:
            self.request(entry['path'])
        key = original, present
        if key not in self.cache:
            style = 'class:muted' if present is None else 'class:green' if present else 'class:red'
            symbol = '?' if present is None else '●' if present else '○'
            self.cache[key] = [(style, self.safe(f"{original + 1:>{self.index.digits}} {symbol} {stamp(entry['started'])}  {entry['action']}  ")),
                               (style + ' class:literal', self.safe(entry['path'])),
                               (style, self.safe(playback(entry)))]
            if len(self.cache) > 512:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        return self.cache[key]


class HistoryIndex:
    def __init__(self, entries, presence, online, safe=str):
        self.entries = tuple(reversed(entries))
        self.presence = presence
        self.by_path = {}
        self.digits = len(str(max(1, len(self.entries))))
        self.widths = []
        for index, entry in enumerate(self.entries):
            self.by_path.setdefault(entry['path'], []).append(index)
            action, path = entry['action'], entry['path']
            action = action if action.isprintable() else safe(action)
            path = path if path.isprintable() else safe(path)
            self.widths.append(self.digits + 3 + len(stamp(entry['started'])) + 2
                + (len(action) if action.isascii() else get_cwidth(action)) + 2
                + (len(path) if path.isascii() else get_cwidth(path)) + len(playback(entry)))
        self.set_filter(online)

    def set_filter(self, online):
        self.online = online
        self.included = (set(range(len(self.entries))) if online is None else
                         {i for path, indices in self.by_path.items() if self.presence.get(path) is online for i in indices})
        self._visible()

    def _visible(self):
        self.visible = sorted(self.included)
        self.maximum_width = max((self.widths[i] for i in self.visible), default=0)

    def availability(self, values):
        self.presence.update(values)
        if self.online is not None:
            for path, value in values.items():
                indices = self.by_path.get(path, ())
                if value == self.online:
                    self.included.update(indices)
                else:
                    self.included.difference_update(indices)
            self._visible()
