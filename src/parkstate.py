"""Display state machine. Pure logic: no hardware, no wall-clock reads."""

import gauge
from ranging import StillnessDetector


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
        self._parking = gauge.IDLE
        self._stillness = StillnessDetector(still_mm=still_mm,
                                            still_seconds=still_seconds,
                                            wake_move_mm=wake_move_mm)

    @property
    def state(self):
        """Current display state, one of the constants in `gauge`."""
        return self._state

    def update(self, distance_mm, stop_mm, now, button_down, read_ok):
        """Advance the machine one tick and return the new state."""
        parking = self._parking_state(distance_mm, stop_mm)
        # _parking is the underlying classification used for hysteresis; _state is what
        # the display shows and may be SETTLED.
        self._parking = parking

        if parking == gauge.IDLE:
            self._stillness.reset()
            self._state = gauge.IDLE
            return self._state

        if self._stillness.update(distance_mm, now):
            self._state = gauge.SETTLED
            return self._state

        self._state = parking
        return self._state

    def _parking_state(self, distance_mm, stop_mm):
        if distance_mm is None or distance_mm > self._wake_mm:
            return gauge.IDLE

        if distance_mm < stop_mm - self._overshoot_mm:
            return gauge.OVERSHOOT

        # OVERSHOOT is treated as part of the stop zone so that backing out of it
        # returns to ARRIVED rather than APPROACHING, preventing display flicker.
        in_stop_zone = self._parking == gauge.ARRIVED or self._parking == gauge.OVERSHOOT
        band = self._arrive_release_mm if in_stop_zone else self._arrive_tol_mm

        if abs(distance_mm - stop_mm) <= band:
            return gauge.ARRIVED

        return gauge.APPROACHING
