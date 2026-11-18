from rangefinder import Rangefinder


class FakeUART:
    def __init__(self):
        self.flushes = 0

    def reset_input_buffer(self):
        self.flushes += 1


class FakeSensor:
    def __init__(self, uart, distance=None, temperature=None, raises=False):
        self._uart = uart
        self._distance = distance
        self._temperature = temperature
        self._raises = raises
        self.flushes_before_distance = None
        self.flushes_before_temperature = None

    @property
    def distance(self):
        self.flushes_before_distance = self._uart.flushes
        if self._raises:
            raise RuntimeError("no reply from sensor")
        return self._distance

    @property
    def temperature(self):
        self.flushes_before_temperature = self._uart.flushes
        if self._raises:
            raise RuntimeError("no reply from sensor")
        return self._temperature


def make(distance=None, temperature=None, raises=False):
    """Build a Rangefinder over a fake sensor and its fake UART."""
    uart = FakeUART()
    sensor = FakeSensor(uart, distance, temperature, raises)
    return Rangefinder(sensor, uart), sensor, uart


def test_converts_centimetres_to_millimetres():
    finder, _, _ = make(distance=85.4)
    assert finder.read_mm() == 854


def test_rounds_to_the_nearest_millimetre():
    finder, _, _ = make(distance=85.46)
    assert finder.read_mm() == 855


def test_none_reading_becomes_none():
    finder, _, _ = make(distance=None)
    assert finder.read_mm() is None


def test_zero_and_negative_readings_pass_through_unchanged():
    # Zero/negative/out-of-range readings are not sensor failures; they mean
    # "no target," and it's Ranger's range gate that classifies them as such.
    # Conflating them with a driver failure would let an empty bay look like
    # a broken sensor.
    zero, _, _ = make(distance=0.0)
    assert zero.read_mm() == 0
    negative, _, _ = make(distance=-3.0)
    assert negative.read_mm() == -30


def test_sensor_exception_becomes_none():
    finder, _, _ = make(raises=True)
    assert finder.read_mm() is None


def test_nan_reading_becomes_none():
    finder, _, _ = make(distance=float("nan"))
    assert finder.read_mm() is None


def test_reads_temperature():
    finder, _, _ = make(temperature=21)
    assert finder.read_temperature_c() == 21


def test_temperature_exception_becomes_none():
    finder, _, _ = make(raises=True)
    assert finder.read_temperature_c() is None


# The following three tests exist because of a hardware failure observed during
# bring-up. The US-100 answers a distance command with 2 bytes and a temperature
# command with 1. If a single stray byte is ever left in the UART buffer — a
# reply still in flight when the board resets, or when a running program is
# interrupted mid-exchange — every subsequent read is offset by one byte and
# stays offset forever. The offset pairs decode as plausible in-range distances,
# so nothing raises and nothing looks broken: the ring would confidently show a
# wrong stop point with no fault indication. Observed on-device: a temperature
# of -45C and a distance of 5204cm from two stray bytes.
#
# Flushing immediately before each command makes every exchange independent, so
# a desync can survive at most one tick instead of persisting indefinitely.


def test_flushes_stale_bytes_before_every_distance_read():
    finder, sensor, uart = make(distance=21.3)
    finder.read_mm()
    assert sensor.flushes_before_distance == 1
    finder.read_mm()
    assert sensor.flushes_before_distance == 2


def test_flushes_stale_bytes_before_every_temperature_read():
    finder, sensor, uart = make(temperature=27)
    finder.read_temperature_c()
    assert sensor.flushes_before_temperature == 1


def test_flushes_even_when_the_read_then_fails():
    # A failing read must still leave the buffer clean, or the failure itself
    # becomes the stray byte that desyncs the next tick.
    finder, sensor, uart = make(raises=True)
    finder.read_mm()
    assert uart.flushes == 1
