from rangefinder import Rangefinder


class FakeSensor:
    def __init__(self, distance=None, temperature=None, raises=False):
        self._distance = distance
        self._temperature = temperature
        self._raises = raises

    @property
    def distance(self):
        if self._raises:
            raise RuntimeError("no reply from sensor")
        return self._distance

    @property
    def temperature(self):
        if self._raises:
            raise RuntimeError("no reply from sensor")
        return self._temperature


def test_converts_centimetres_to_millimetres():
    assert Rangefinder(FakeSensor(distance=85.4)).read_mm() == 854


def test_rounds_to_the_nearest_millimetre():
    assert Rangefinder(FakeSensor(distance=85.46)).read_mm() == 855


def test_none_reading_becomes_none():
    assert Rangefinder(FakeSensor(distance=None)).read_mm() is None


def test_zero_and_negative_readings_become_none():
    assert Rangefinder(FakeSensor(distance=0.0)).read_mm() is None
    assert Rangefinder(FakeSensor(distance=-3.0)).read_mm() is None


def test_sensor_exception_becomes_none():
    assert Rangefinder(FakeSensor(raises=True)).read_mm() is None


def test_reads_temperature():
    assert Rangefinder(FakeSensor(temperature=21)).read_temperature_c() == 21


def test_temperature_exception_becomes_none():
    assert Rangefinder(FakeSensor(raises=True)).read_temperature_c() is None
