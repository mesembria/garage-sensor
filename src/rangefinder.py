"""Adapter over adafruit_us100. The sensor and its UART are injected, so this
is testable on a desktop with no hardware present."""


class Rangefinder:
    """Reads the US-100, returning integer millimetres or None on any failure.

    Flushes the UART receive buffer before every command. The US-100 answers a
    distance command with 2 bytes and a temperature command with 1, and
    adafruit_us100 resets the buffer only once, in its constructor. So a single
    stray byte — a reply still in flight when the board resets, or when a
    running program is interrupted mid-exchange — offsets every subsequent read
    by one byte and keeps it offset indefinitely. The misaligned pairs decode as
    plausible in-range distances, so nothing raises and no fault is detected;
    the display would simply be wrong. Observed on-device during bring-up: two
    stray bytes produced a temperature of -45C and a distance of 5204cm.

    Flushing immediately before each command makes every exchange independent,
    so a desync can survive at most one tick rather than forever.
    """

    def __init__(self, sensor, uart):
        self._sensor = sensor
        self._uart = uart

    def read_mm(self):
        """Distance in mm as reported by the sensor, or None if it did not answer.

        None means a genuine read failure. A zero or out-of-range number is
        passed through unchanged for the caller's range gate to classify as
        no-target: conflating the two would let an empty bay look like a
        broken sensor.
        """
        try:
            self._uart.reset_input_buffer()
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
            self._uart.reset_input_buffer()
            return self._sensor.temperature
        except Exception:
            return None
