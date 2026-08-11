"""Adapter over adafruit_us100. The sensor object is injected, so this is testable."""


class Rangefinder:
    """Reads the US-100, returning integer millimetres or None on any failure."""

    def __init__(self, sensor):
        self._sensor = sensor

    def read_mm(self):
        """Distance in mm as reported by the sensor, or None if it did not answer.

        None means a genuine read failure. A zero or out-of-range number is
        passed through unchanged for the caller's range gate to classify as
        no-target: conflating the two would let an empty bay look like a
        broken sensor.
        """
        try:
            cm = self._sensor.distance
            if cm is None:
                return None
            return int(round(cm * 10.0))
        except Exception:
            # The adafruit_us100 library can raise several unrelated error types
            # on a timeout or a malformed reply, and every one of them means the
            # same thing: no reading this tick. The state machine turns sustained
            # failures into the blue fault display. A NaN or Infinity distance
            # also lands here: round(nan) raises ValueError, round(inf) raises
            # OverflowError, and both mean "not a usable reading" just as much
            # as a timeout does.
            return None

    def read_temperature_c(self):
        """Sensor temperature in degrees C, or None. Used to confirm compensation."""
        try:
            return self._sensor.temperature
        except Exception:
            return None
