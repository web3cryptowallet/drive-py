"""Reusable random-access candidates with ordered, constant-work removals."""

# IMPORT SCANNER POOL DEPENDENCIES [
from array import array
from collections.abc import Sequence
# IMPORT SCANNER POOL DEPENDENCIES ]
# CONSUME CIRCULAR RANGES OF SORTED, UNIQUE BUCKET INDICES [
class CandidatePool(Sequence):
    """Consume circular ranges of sorted, unique bucket indices.

    Sequence positions are intentionally unordered: a dense slot array makes
    ``random.choice(pool)`` uniform without searching or shifting survivors.
    Separate circular links retain map order for ``consume``. Construction is
    O(N), selection is O(1), and consuming K candidates is O(K). The caller
    supplies increasing, unique indices and owns synchronization.
    """

    # INITIALIZE CANDIDATE POOL [
    def __init__(self, indices=()):
        self._indices = tuple(indices)
        count = len(self._indices)
        self._slots = {index: slot for slot, index in enumerate(self._indices)}
        # Compact numeric links avoid several Python objects per candidate.
        kind = 'i' if count <= 2**31 - 1 else 'q'
        self._dense = array(kind, range(count))
        self._positions = array(kind, self._dense)
        self._next = array(kind, range(1, count + 1))
        self._previous = array(kind, range(-1, count - 1))
        if count:
            self._next[-1] = 0
            self._previous[0] = count - 1
    # INITIALIZE CANDIDATE POOL ]
    # COUNT AVAILABLE SCAN CANDIDATES [
    def __len__(self):
        return len(self._dense)
    # COUNT AVAILABLE SCAN CANDIDATES ]
    # LOOK UP A CANDIDATE BY INDEX [
    def __getitem__(self, position):
        if isinstance(position, slice):
            return [self._indices[slot] for slot in self._dense[position]]
        return self._indices[self._dense[position]]
    # LOOK UP A CANDIDATE BY INDEX ]
    # CONTAINS FOR CANDIDATE POOL [
    def __contains__(self, index):
        slot = self._slots.get(index)
        return slot is not None and self._positions[slot] >= 0
    # CONTAINS FOR CANDIDATE POOL ]
    # REMOVE UP TO COUNT CANDIDATES FROM FIRST_INDEX IN MAP ORDER [
    def consume(self, first_index, count):
        """Remove up to count candidates from first_index in map order."""
        if count <= 0 or not self:
            return []
        slot = self._slots[first_index]
        if self._positions[slot] < 0:
            raise KeyError(first_index)
        chosen = []
        for _ in range(min(count, len(self))):
            chosen.append(self._indices[slot])
            following = self._next[slot]
            previous = self._previous[slot]
            self._next[previous] = following
            self._previous[following] = previous

            position = self._positions[slot]
            last = self._dense.pop()
            if position < len(self._dense):
                self._dense[position] = last
                self._positions[last] = position
            self._positions[slot] = -1
            slot = following
        return chosen
    # REMOVE UP TO COUNT CANDIDATES FROM FIRST_INDEX IN MAP ORDER ]
# CONSUME CIRCULAR RANGES OF SORTED, UNIQUE BUCKET INDICES ]
