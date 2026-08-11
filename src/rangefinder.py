"""Adapter over adafruit_us100. The sensor object is injected, so this is testable."""


class Rangefinder:
    """Reads the US-100, returning integer millimetres or None on any failure."""

    def __init__(self, sensor):
        self._sensor = sensor

    def read_mm(self):
        """Distance in mm, or None if the sensor did not return a usable reading."""
        try:
            cm = self._sensor.distance
        except Exception:
            # The adafruit_us100 library can raise several unrelated error types
            # on a timeout or a malformed reply, and every one of them means the
            # same thing: no reading this tick. The state machine turns sustained
            # failures into the blue fault display.
            return None
        if cm is None or cm <= 0:
            return None
        return int(round(cm * 10.0))

    def read_temperature_c(self):
        """Sensor temperature in degrees C, or None. Used to confirm compensation."""
        try:
            return self._sensor.temperature
        except Exception:
            return None
