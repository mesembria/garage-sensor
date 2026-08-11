"""Distance filtering. Pure logic, no hardware, no wall-clock reads."""


def median(values):
    """Median of a list of ints, or None if empty. Even counts average the middle pair."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


class Ranger:
    """Sliding-median filter with outlier rejection and no-target handling."""

    def __init__(self, window=5, max_valid_mm=4000, outlier_jump_mm=500,
                 outlier_persist=3, no_target_clears=3):
        self._window_size = window
        self._max_valid_mm = max_valid_mm
        self._outlier_jump_mm = outlier_jump_mm
        self._outlier_persist = outlier_persist
        self._no_target_clears = no_target_clears
        self._samples = []
        self._pending = []
        self._misses = 0
        self._current = None

    @property
    def distance(self):
        """Last accepted distance in mm, or None."""
        return self._current

    def push(self, raw_mm):
        """Feed one raw reading. Returns the filtered distance in mm, or None."""
        if raw_mm is None or raw_mm <= 0 or raw_mm > self._max_valid_mm:
            self._misses += 1
            if self._misses >= self._no_target_clears:
                self._samples = []
                self._pending = []
                self._current = None
            return self._current

        self._misses = 0

        if self._samples and abs(raw_mm - self._current) > self._outlier_jump_mm:
            self._pending.append(raw_mm)
            if len(self._pending) < self._outlier_persist:
                return self._current
            self._samples = list(self._pending)
            self._pending = []
        else:
            self._pending = []
            self._samples.append(raw_mm)
            if len(self._samples) > self._window_size:
                self._samples.pop(0)

        self._current = median(self._samples)
        return self._current
