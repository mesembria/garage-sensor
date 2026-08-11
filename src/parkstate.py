"""Display state machine. Pure logic: no hardware, no wall-clock reads."""

import gauge


class ParkStateMachine:
    """Converts filtered distance, button, and sensor health into a display state."""

    def __init__(self, arrive_tol_mm=30, arrive_release_mm=60, overshoot_mm=50,
                 wake_mm=3000, still_mm=20, still_seconds=10.0, wake_move_mm=50,
                 max_consec_fails=5, recover_good_reads=3, calibrate_hold_s=2.0):
        self._arrive_tol_mm = arrive_tol_mm
        self._arrive_release_mm = arrive_release_mm
        self._overshoot_mm = overshoot_mm
        self._wake_mm = wake_mm
        self._still_mm = still_mm
        self._still_seconds = still_seconds
        self._wake_move_mm = wake_move_mm
        self._max_consec_fails = max_consec_fails
        self._recover_good_reads = recover_good_reads
        self._calibrate_hold_s = calibrate_hold_s
        self._state = gauge.IDLE

    @property
    def state(self):
        """Current display state, one of the constants in `gauge`."""
        return self._state

    def update(self, distance_mm, stop_mm, now, button_down, read_ok):
        """Advance the machine one tick and return the new state."""
        self._state = self._parking_state(distance_mm, stop_mm)
        return self._state

    def _parking_state(self, distance_mm, stop_mm):
        if distance_mm is None or distance_mm > self._wake_mm:
            return gauge.IDLE

        if distance_mm < stop_mm - self._overshoot_mm:
            return gauge.OVERSHOOT

        offset = abs(distance_mm - stop_mm)
        if self._state == gauge.ARRIVED:
            if offset <= self._arrive_release_mm:
                return gauge.ARRIVED
        elif offset <= self._arrive_tol_mm:
            return gauge.ARRIVED

        return gauge.APPROACHING
