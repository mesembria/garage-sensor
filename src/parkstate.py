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
        self._fails = 0
        self._goods = 0
        self._in_fault = False
        self._button_since = None
        self._calibrated_this_tick = None

    @property
    def state(self):
        """Current display state, one of the constants in `gauge`."""
        return self._state

    @property
    def calibration_captured(self):
        """Distance in mm to persist, set for exactly one tick after a hold."""
        return self._calibrated_this_tick

    def update(self, distance_mm, stop_mm, now, button_down, read_ok):
        """Advance the machine one tick and return the new state."""
        self._calibrated_this_tick = None

        if self._track_health(read_ok):
            self._stillness.reset()
            self._button_since = None
            # Early return, before _parking_state runs: reset _parking so a fault
            # doesn't leave a stale wide release band in place for the tick after
            # recovery. The first good reading afterward must be judged as a fresh
            # arrival against the tight tolerance, not the release band.
            self._parking = gauge.IDLE
            self._state = gauge.FAULT
            return self._state

        if self._track_button(distance_mm, now, button_down):
            self._stillness.reset()
            # Same reasoning as the FAULT branch above: don't let calibration ticks
            # leave a stale _parking value to be consulted after this returns.
            self._parking = gauge.IDLE
            self._state = gauge.CALIBRATE
            return self._state

        if stop_mm is None:
            self._stillness.reset()
            # Same reasoning as the FAULT branch above: don't let uncalibrated ticks
            # leave a stale _parking value to be consulted once calibration completes.
            self._parking = gauge.IDLE
            self._state = gauge.UNCALIBRATED
            return self._state

        parking = self._parking_state(distance_mm, stop_mm)
        # _parking is the underlying classification used for hysteresis; _state is
        # what the display shows and may be SETTLED.
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

    def _track_health(self, read_ok):
        """Update the failure counters. Returns True while in fault."""
        if read_ok:
            self._fails = 0
            if self._in_fault:
                self._goods += 1
                if self._goods >= self._recover_good_reads:
                    self._in_fault = False
                    self._goods = 0
        else:
            self._goods = 0
            self._fails += 1
            if self._fails >= self._max_consec_fails:
                self._in_fault = True
        return self._in_fault

    def _track_button(self, distance_mm, now, button_down):
        """Update the calibration hold timer. Returns True while calibrating."""
        if not button_down or distance_mm is None:
            self._button_since = None
            return False

        if self._button_since is None:
            self._button_since = now
            return False

        if (now - self._button_since) < self._calibrate_hold_s:
            return False

        if self._state != gauge.CALIBRATE:
            self._calibrated_this_tick = distance_mm
        return True

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
