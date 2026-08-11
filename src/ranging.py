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
        """Feed one raw reading. Returns the filtered distance in mm, or None.

        A no-target reading does not clear the pending-outlier buffer, so a
        sequence like outlier, miss, outlier, outlier still adopts once
        outlier_persist agreeing samples have been seen. This is intentional:
        a momentary miss between agreeing outliers shouldn't restart the count.
        """
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


class StillnessDetector:
    """Detects that the vehicle has stopped moving, so the display can sleep."""

    def __init__(self, still_mm=20, still_seconds=10.0, wake_move_mm=50):
        self._still_mm = still_mm
        self._still_seconds = still_seconds
        self._wake_move_mm = wake_move_mm
        self._reference = None
        self._since = None
        self._settled = False

    def reset(self):
        """Forget the reference distance and the elapsed timer."""
        self._reference = None
        self._since = None
        self._settled = False

    def update(self, distance_mm, now):
        """Feed a filtered distance and the current time. Returns True when settled."""
        if distance_mm is None:
            self.reset()
            return False

        if self._reference is None:
            self._reference = distance_mm
            self._since = now
            return False

        if abs(distance_mm - self._reference) > self._wake_move_mm:
            self._reference = distance_mm
            self._since = now
            self._settled = False
            return False

        if self._settled:
            return True

        if abs(distance_mm - self._reference) > self._still_mm:
            self._since = now
            return False

        if (now - self._since) >= self._still_seconds:
            self._settled = True
            return True

        return False
