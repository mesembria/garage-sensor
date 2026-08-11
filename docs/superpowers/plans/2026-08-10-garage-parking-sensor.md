# Garage Parking Stop Sensor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CircuitPython garage parking indicator that reads a US-100 ultrasonic sensor and drives a NeoPixel ring as a shrinking-arc distance gauge, with a button-set stop point persisted in NVM.

**Architecture:** All logic lives in pure Python modules that import no hardware libraries, so they run under pytest on a desktop. `code.py` is a thin hardware-binding layer that wires those modules to `board`, `neopixel`, `busio`, and `microcontroller.nvm`. A state machine converts filtered distance readings into a display state; a gauge module converts that state into a list of RGB tuples.

**Tech Stack:** CircuitPython 9.x on an Adafruit Feather RP2040, `adafruit_us100` library, `neopixel` library, pytest 9 on desktop CPython 3.13 for the pure modules.

**Design spec:** `docs/superpowers/specs/2026-08-10-garage-parking-sensor-design.md`

## Global Constraints

These apply to every task. They are not optional style preferences — violating them breaks the build on the target hardware.

- **No type annotations anywhere in `src/`.** CircuitPython evaluates annotations at function-definition time and has no `typing` module. `int | None` syntax will fail on-device. Document types in docstrings instead.
- **No `statistics`, `dataclasses`, `enum`, or `typing` imports in `src/`.** None of these exist in CircuitPython. Use module-level string constants for states and hand-rolled helpers for median.
- **Only `code.py`, `selftest.py`, and `rangefinder.py` may reference hardware.** `settings.py`, `ranging.py`, `gauge.py`, and `parkstate.py` must import nothing beyond the standard library, and `rangefinder.py` receives its sensor object by injection rather than constructing one.
- **Time is always injected.** Pure modules never call `time.monotonic()` themselves; callers pass `now` as a float. Tests must never sleep.
- **Distances are integer millimetres** throughout. The `adafruit_us100` library reports centimetres as a float; conversion happens once, in `rangefinder.py`.
- **NVM is written only on button press.** Each write is a flash erase/write cycle.
- Config constant values are copied verbatim from the spec's "Configuration constants" section.

---

## File Structure

| File | Responsibility | Hardware? |
|---|---|---|
| `src/settings.py` | Encode/decode stop distance to the 4-byte NVM layout | No |
| `src/ranging.py` | Sliding median filter, outlier rejection, stillness detection | No |
| `src/gauge.py` | Distance + state → list of RGB tuples | No |
| `src/parkstate.py` | State machine over filtered distance, button, read health | No |
| `src/rangefinder.py` | Wrap an injected `adafruit_us100.US100`, return mm or `None` | Injected |
| `src/code.py` | Hardware binding and main loop | Yes |
| `src/selftest.py` | Walk every visual state on-device | Yes |
| `tests/test_settings.py` | NVM round-trip, magic/version handling | No |
| `tests/test_ranging.py` | Filter and stillness behavior | No |
| `tests/test_gauge.py` | Arc geometry, colours, per-state rendering | No |
| `tests/test_parkstate.py` | Every state transition | No |
| `tests/test_rangefinder.py` | Protocol wrapper against a fake sensor | No |

---

### Task 1: Project setup and NVM settings

**Files:**
- Create: `pyproject.toml`
- Create: `src/settings.py`
- Create: `.gitignore`
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: nothing
- Produces: `settings.MAGIC` (int `0x67`), `settings.VERSION` (int `0x01`), `settings.NVM_BYTES` (int `4`), `settings.encode(stop_mm)` → `bytes` of length 4, `settings.decode(raw)` → int mm or `None`, `settings.load(nvm)` → int mm or `None`, `settings.save(nvm, stop_mm)` → `None`. The `nvm` argument is any object supporting slice read and slice assignment, which `microcontroller.nvm` does.

- [ ] **Step 1: Create the project config and gitignore**

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`.gitignore`:

```
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
```

- [ ] **Step 2: Write the failing test**

`tests/test_settings.py`:

```python
import settings


def test_encode_produces_four_bytes_with_magic_and_version():
    raw = settings.encode(1234)
    assert len(raw) == 4
    assert raw[0] == settings.MAGIC
    assert raw[1] == settings.VERSION


def test_encode_decode_round_trip():
    assert settings.decode(settings.encode(1234)) == 1234


def test_decode_rejects_bad_magic():
    raw = bytearray(settings.encode(1234))
    raw[0] = 0x00
    assert settings.decode(bytes(raw)) is None


def test_decode_rejects_unknown_version():
    raw = bytearray(settings.encode(1234))
    raw[1] = 0x99
    assert settings.decode(bytes(raw)) is None


def test_decode_rejects_short_buffer():
    assert settings.decode(b"\x67\x01") is None


def test_encode_rejects_out_of_range():
    for bad in (-1, 65536):
        try:
            settings.encode(bad)
        except ValueError:
            continue
        raise AssertionError("expected ValueError for %d" % bad)


def test_load_and_save_against_fake_nvm():
    nvm = bytearray(64)
    assert settings.load(nvm) is None
    settings.save(nvm, 850)
    assert settings.load(nvm) == 850
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'settings'`

- [ ] **Step 4: Write the implementation**

`src/settings.py`:

```python
"""Persist the parking stop distance in microcontroller NVM.

Layout, 4 bytes total:
    offset 0: magic byte 0x67
    offset 1: format version 0x01
    offset 2-3: stop distance, uint16 little-endian, millimetres
"""

MAGIC = 0x67
VERSION = 0x01
NVM_BYTES = 4


def encode(stop_mm):
    """Return a 4-byte record for stop_mm. Raises ValueError if out of range."""
    if stop_mm < 0 or stop_mm > 0xFFFF:
        raise ValueError("stop_mm out of uint16 range")
    return bytes((MAGIC, VERSION, stop_mm & 0xFF, (stop_mm >> 8) & 0xFF))


def decode(raw):
    """Return the stop distance in mm, or None if the record is absent/unreadable."""
    if raw is None or len(raw) < NVM_BYTES:
        return None
    if raw[0] != MAGIC or raw[1] != VERSION:
        return None
    return raw[2] | (raw[3] << 8)


def load(nvm):
    """Read the stop distance from an NVM-like bytearray, or None if unset."""
    return decode(bytes(nvm[0:NVM_BYTES]))


def save(nvm, stop_mm):
    """Write the stop distance in a single assignment (one flash erase/write)."""
    nvm[0:NVM_BYTES] = encode(stop_mm)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_settings.py -v`
Expected: PASS, 7 tests

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore src/settings.py tests/test_settings.py
git commit -m "feat: persist stop distance in NVM"
```

---

### Task 2: Median filter with outlier rejection

**Files:**
- Create: `src/ranging.py`
- Test: `tests/test_ranging.py`

**Interfaces:**
- Consumes: nothing
- Produces: `ranging.median(values)` → int or `None`; `ranging.Ranger(window=5, max_valid_mm=4000, outlier_jump_mm=500, outlier_persist=3, no_target_clears=3)` with method `push(raw_mm)` → int mm or `None`, and read-only property `distance` → int mm or `None`.

Behavioural contract, which the tests below pin down:
- A reading of `None`, `0`, negative, or above `max_valid_mm` counts as no-target. After `no_target_clears` consecutive no-targets the filter resets and reports `None`. Before that it keeps reporting the last good value, so a single dropped ping does not blank the display.
- A reading differing from the current median by more than `outlier_jump_mm` is withheld. If `outlier_persist` consecutive readings all agree with the jump, the filter resets to them and adopts the new distance.

- [ ] **Step 1: Write the failing test**

`tests/test_ranging.py`:

```python
from ranging import Ranger, median


def test_median_odd_and_even():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2
    assert median([]) is None


def feed(ranger, values):
    out = None
    for v in values:
        out = ranger.push(v)
    return out


def test_reports_median_of_window():
    r = Ranger(window=5)
    assert feed(r, [100, 102, 101, 103, 99]) == 101


def test_window_slides_and_drops_oldest():
    r = Ranger(window=3)
    feed(r, [100, 100, 100])
    assert feed(r, [200, 200, 200]) == 200


def test_single_outlier_is_rejected():
    r = Ranger(window=5, outlier_jump_mm=500, outlier_persist=3)
    feed(r, [1000, 1000, 1000, 1000, 1000])
    assert r.push(50) == 1000
    assert r.push(1000) == 1000


def test_sustained_jump_is_adopted():
    r = Ranger(window=5, outlier_jump_mm=500, outlier_persist=3)
    feed(r, [1000, 1000, 1000, 1000, 1000])
    assert r.push(200) == 1000
    assert r.push(205) == 1000
    assert r.push(210) == 205


def test_out_of_range_and_zero_are_no_target():
    r = Ranger(window=5, max_valid_mm=4000, no_target_clears=3)
    feed(r, [1000, 1000, 1000])
    assert r.push(5000) == 1000
    assert r.push(0) == 1000
    assert r.push(None) is None
    assert r.distance is None


def test_recovers_after_no_target():
    r = Ranger(window=5, no_target_clears=3)
    feed(r, [1000, 1000, 1000])
    feed(r, [None, None, None])
    assert r.push(700) == 700
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_ranging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ranging'`

- [ ] **Step 3: Write the implementation**

`src/ranging.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_ranging.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add src/ranging.py tests/test_ranging.py
git commit -m "feat: add sliding median filter with outlier rejection"
```

---

### Task 3: Stillness detection

**Files:**
- Modify: `src/ranging.py` (append a class; leave `Ranger` and `median` untouched)
- Modify: `tests/test_ranging.py` (append tests)

**Interfaces:**
- Consumes: nothing
- Produces: `ranging.StillnessDetector(still_mm=20, still_seconds=10.0, wake_move_mm=50)` with `update(distance_mm, now)` → bool (True once the car has been stationary for `still_seconds`) and `reset()` → `None`.

Contract: the detector latches a reference distance the first time it sees a value. While readings stay within `still_mm` of that reference it accumulates time; once `still_seconds` have elapsed it reports True and keeps reporting True until a reading moves more than `wake_move_mm` from the reference, which resets it. A `None` reading resets it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ranging.py`:

```python
from ranging import StillnessDetector


def test_reports_settled_after_the_hold_period():
    d = StillnessDetector(still_mm=20, still_seconds=10.0)
    assert d.update(1000, 0.0) is False
    assert d.update(1005, 5.0) is False
    assert d.update(1010, 9.9) is False
    assert d.update(1008, 10.0) is True


def test_small_drift_does_not_reset_the_timer():
    d = StillnessDetector(still_mm=20, still_seconds=10.0)
    d.update(1000, 0.0)
    d.update(1019, 9.0)
    assert d.update(1001, 10.0) is True


def test_large_move_resets_the_timer():
    d = StillnessDetector(still_mm=20, still_seconds=10.0, wake_move_mm=50)
    d.update(1000, 0.0)
    assert d.update(500, 5.0) is False
    assert d.update(505, 14.0) is False
    assert d.update(500, 15.0) is True


def test_settled_latches_until_movement():
    d = StillnessDetector(still_mm=20, still_seconds=10.0, wake_move_mm=50)
    d.update(1000, 0.0)
    assert d.update(1000, 10.0) is True
    assert d.update(1000, 30.0) is True
    assert d.update(800, 31.0) is False


def test_none_reading_resets():
    d = StillnessDetector(still_seconds=10.0)
    d.update(1000, 0.0)
    assert d.update(None, 5.0) is False
    assert d.update(1000, 12.0) is False


def test_reset_clears_state():
    d = StillnessDetector(still_seconds=10.0)
    d.update(1000, 0.0)
    d.reset()
    assert d.update(1000, 10.0) is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_ranging.py -v`
Expected: FAIL with `ImportError: cannot import name 'StillnessDetector'`

- [ ] **Step 3: Write the implementation**

Append to `src/ranging.py`:

```python
class StillnessDetector:
    """Detects that the vehicle has stopped moving, so the display can sleep."""

    def __init__(self, still_mm=20, still_seconds=10.0, wake_move_mm=50):
        self._still_mm = still_mm
        self._still_seconds = still_seconds
        self._wake_move_mm = wake_move_mm
        self._reference = None
        self._since = None

    def reset(self):
        """Forget the reference distance and the elapsed timer."""
        self._reference = None
        self._since = None

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
            return False

        if abs(distance_mm - self._reference) > self._still_mm:
            self._since = now
            return False

        return (now - self._since) >= self._still_seconds
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_ranging.py -v`
Expected: PASS, 13 tests total

- [ ] **Step 5: Commit**

```bash
git add src/ranging.py tests/test_ranging.py
git commit -m "feat: add stillness detection for display sleep"
```

---

### Task 4: Ring geometry

**Files:**
- Create: `src/gauge.py`
- Test: `tests/test_gauge.py`

**Interfaces:**
- Consumes: nothing
- Produces: `gauge.approach_fraction(distance_mm, stop_mm, approach_span_mm)` → float in `[0.0, 1.0]`; `gauge.lit_count(fraction, pixel_count)` → int; `gauge.physical_index(logical, pixel_count, zero_offset, clockwise)` → int; `gauge.arc_pixels(lit, pixel_count, zero_offset, clockwise)` → list of physical indices.

Contract: `approach_fraction` returns 1.0 when the car is a full approach-span or more away and 0.0 at or past the stop point; `None` distance or `None` stop yields 1.0. `arc_pixels` returns the `lit` positions nearest twelve o'clock, so the arc closes symmetrically inward, and works for any pixel count.

- [ ] **Step 1: Write the failing test**

`tests/test_gauge.py`:

```python
import gauge


def test_fraction_is_one_at_full_span_and_beyond():
    assert gauge.approach_fraction(2600, 600, 2000) == 1.0
    assert gauge.approach_fraction(9000, 600, 2000) == 1.0


def test_fraction_is_zero_at_and_past_the_stop_point():
    assert gauge.approach_fraction(600, 600, 2000) == 0.0
    assert gauge.approach_fraction(300, 600, 2000) == 0.0


def test_fraction_is_linear_in_between():
    assert gauge.approach_fraction(1600, 600, 2000) == 0.5


def test_fraction_defaults_to_one_when_unknown():
    assert gauge.approach_fraction(None, 600, 2000) == 1.0
    assert gauge.approach_fraction(1000, None, 2000) == 1.0


def test_lit_count_spans_zero_to_pixel_count():
    assert gauge.lit_count(1.0, 12) == 12
    assert gauge.lit_count(0.0, 12) == 0
    assert gauge.lit_count(0.5, 12) == 6


def test_physical_index_applies_offset_and_direction():
    assert gauge.physical_index(0, 12, 3, True) == 3
    assert gauge.physical_index(2, 12, 3, True) == 5
    assert gauge.physical_index(2, 12, 3, False) == 1
    assert gauge.physical_index(11, 12, 0, True) == 11


def test_arc_closes_symmetrically_around_twelve_oclock():
    assert gauge.arc_pixels(1, 12, 0, True) == [0]
    assert sorted(gauge.arc_pixels(3, 12, 0, True)) == [0, 1, 11]
    assert sorted(gauge.arc_pixels(5, 12, 0, True)) == [0, 1, 2, 10, 11]


def test_arc_respects_offset():
    assert sorted(gauge.arc_pixels(3, 12, 6, True)) == [5, 6, 7]


def test_arc_endpoints():
    assert gauge.arc_pixels(0, 12, 0, True) == []
    assert sorted(gauge.arc_pixels(12, 12, 0, True)) == list(range(12))


def test_arc_works_for_other_ring_sizes():
    for count in (16, 24):
        assert len(gauge.arc_pixels(count, count, 0, True)) == count
        assert sorted(gauge.arc_pixels(count, count, 0, True)) == list(range(count))
        assert gauge.arc_pixels(1, count, 0, True) == [0]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_gauge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gauge'`

- [ ] **Step 3: Write the implementation**

`src/gauge.py`:

```python
"""Turn distance and display state into ring pixel colours. Pure logic."""


def approach_fraction(distance_mm, stop_mm, approach_span_mm):
    """Fraction of the approach remaining: 1.0 far away, 0.0 at the stop point."""
    if distance_mm is None or stop_mm is None or approach_span_mm <= 0:
        return 1.0
    raw = float(distance_mm - stop_mm) / float(approach_span_mm)
    if raw < 0.0:
        return 0.0
    if raw > 1.0:
        return 1.0
    return raw


def lit_count(fraction, pixel_count):
    """Number of pixels lit for a given remaining fraction."""
    count = int(round(fraction * pixel_count))
    if count < 0:
        return 0
    if count > pixel_count:
        return pixel_count
    return count


def physical_index(logical, pixel_count, zero_offset, clockwise):
    """Map a logical position (0 == twelve o'clock) to a physical pixel index."""
    step = logical if clockwise else -logical
    return (zero_offset + step) % pixel_count


def arc_pixels(lit, pixel_count, zero_offset, clockwise):
    """Physical indices of the `lit` pixels nearest twelve o'clock.

    Sorting by angular distance means the arc closes inward symmetrically and
    the result is correct for any pixel count, odd or even.
    """
    order = sorted(range(pixel_count),
                   key=lambda k: (min(k, pixel_count - k), k))
    return [physical_index(k, pixel_count, zero_offset, clockwise)
            for k in order[:lit]]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_gauge.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add src/gauge.py tests/test_gauge.py
git commit -m "feat: add ring arc geometry"
```

---

### Task 5: Colours and per-state rendering

**Files:**
- Modify: `src/gauge.py` (append; leave Task 4 functions untouched)
- Modify: `tests/test_gauge.py` (append)

**Interfaces:**
- Consumes: `gauge.arc_pixels`, `gauge.lit_count` from Task 4
- Produces: colour constants `gauge.GREEN`, `gauge.AMBER`, `gauge.RED`, `gauge.BLUE`, `gauge.OFF`; state constants `gauge.IDLE`, `gauge.APPROACHING`, `gauge.ARRIVED`, `gauge.OVERSHOOT`, `gauge.SETTLED`, `gauge.CALIBRATE`, `gauge.FAULT`, `gauge.UNCALIBRATED` (all lowercase strings); `gauge.arc_color(fraction)` → `(r, g, b)`; `gauge.render(state, fraction, pixel_count, zero_offset, clockwise, now)` → list of `(r, g, b)` of length `pixel_count`.

`render` takes `now` in seconds rather than a precomputed phase so each animation picks its own rate: overshoot flashes at 2Hz, fault pulses at 0.5Hz, calibrate spins once per second.

The state constants live in `gauge.py` and are imported by `parkstate.py` in Task 6, so both modules agree on one set of names.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gauge.py`:

```python
def test_arc_color_endpoints():
    assert gauge.arc_color(1.0) == gauge.GREEN
    assert gauge.arc_color(0.0) == gauge.AMBER


def test_arc_color_interpolates():
    mid = gauge.arc_color(0.5)
    assert gauge.AMBER[0] > mid[0] > gauge.GREEN[0]
    assert gauge.GREEN[1] > mid[1] > gauge.AMBER[1]


def test_render_returns_one_color_per_pixel():
    for state in (gauge.IDLE, gauge.APPROACHING, gauge.ARRIVED,
                  gauge.OVERSHOOT, gauge.SETTLED, gauge.CALIBRATE,
                  gauge.FAULT, gauge.UNCALIBRATED):
        frame = gauge.render(state, 0.5, 12, 0, True, 0.0)
        assert len(frame) == 12
        assert all(len(c) == 3 for c in frame)


def test_idle_and_settled_are_dark():
    assert gauge.render(gauge.IDLE, 0.5, 12, 0, True, 0.0) == [gauge.OFF] * 12
    assert gauge.render(gauge.SETTLED, 0.5, 12, 0, True, 0.0) == [gauge.OFF] * 12


def test_approaching_lights_only_the_arc():
    frame = gauge.render(gauge.APPROACHING, 0.25, 12, 0, True, 0.0)
    assert frame.count(gauge.OFF) == 9
    assert len([c for c in frame if c != gauge.OFF]) == 3


def test_arrived_fills_the_whole_ring_red():
    assert gauge.render(gauge.ARRIVED, 0.0, 12, 0, True, 0.0) == [gauge.RED] * 12


def test_overshoot_flashes_at_two_hertz():
    on = gauge.render(gauge.OVERSHOOT, 0.0, 12, 0, True, 0.0)
    off = gauge.render(gauge.OVERSHOOT, 0.0, 12, 0, True, 0.25)
    assert on == [gauge.RED] * 12
    assert off == [gauge.OFF] * 12


def test_fault_is_blue_and_pulses():
    dim = gauge.render(gauge.FAULT, 0.0, 12, 0, True, 0.0)
    bright = gauge.render(gauge.FAULT, 0.0, 12, 0, True, 1.0)
    assert all(c[0] == 0 and c[1] == 0 for c in dim)
    assert bright[0][2] > dim[0][2]


def test_calibrate_lights_a_single_moving_pixel():
    frame = gauge.render(gauge.CALIBRATE, 0.0, 12, 0, True, 0.0)
    assert len([c for c in frame if c != gauge.OFF]) == 1
    later = gauge.render(gauge.CALIBRATE, 0.0, 12, 0, True, 0.5)
    assert frame != later


def test_uncalibrated_shows_opposing_amber_pixels():
    frame = gauge.render(gauge.UNCALIBRATED, 0.0, 12, 0, True, 0.0)
    assert len([c for c in frame if c == gauge.AMBER]) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_gauge.py -v`
Expected: FAIL with `AttributeError: module 'gauge' has no attribute 'GREEN'`

- [ ] **Step 3: Write the implementation**

Append to `src/gauge.py`:

```python
GREEN = (0, 255, 0)
AMBER = (255, 140, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
OFF = (0, 0, 0)

IDLE = "idle"
APPROACHING = "approaching"
ARRIVED = "arrived"
OVERSHOOT = "overshoot"
SETTLED = "settled"
CALIBRATE = "calibrate"
FAULT = "fault"
UNCALIBRATED = "uncalibrated"

OVERSHOOT_FLASH_HZ = 2.0
FAULT_PULSE_HZ = 0.5
CALIBRATE_SPIN_HZ = 1.0


def _lerp(a, b, t):
    return int(round(a + (b - a) * t))


def arc_color(fraction):
    """Green when far, amber at the stop point, interpolated in between."""
    t = 1.0 - fraction
    return (_lerp(GREEN[0], AMBER[0], t),
            _lerp(GREEN[1], AMBER[1], t),
            _lerp(GREEN[2], AMBER[2], t))


def render(state, fraction, pixel_count, zero_offset, clockwise, now):
    """Return a list of (r, g, b) tuples, one per physical pixel."""
    frame = [OFF] * pixel_count

    if state == IDLE or state == SETTLED:
        return frame

    if state == APPROACHING:
        color = arc_color(fraction)
        for index in arc_pixels(lit_count(fraction, pixel_count),
                                pixel_count, zero_offset, clockwise):
            frame[index] = color
        return frame

    if state == ARRIVED:
        return [RED] * pixel_count

    if state == OVERSHOOT:
        phase = (now * OVERSHOOT_FLASH_HZ) % 1.0
        return [RED] * pixel_count if phase < 0.5 else frame

    if state == FAULT:
        phase = (now * FAULT_PULSE_HZ) % 1.0
        level = int(round(255 * (1.0 - abs(2.0 * phase - 1.0))))
        return [(0, 0, level)] * pixel_count

    if state == CALIBRATE:
        phase = (now * CALIBRATE_SPIN_HZ) % 1.0
        logical = int(phase * pixel_count) % pixel_count
        frame[physical_index(logical, pixel_count, zero_offset, clockwise)] = GREEN
        return frame

    if state == UNCALIBRATED:
        phase = (now * CALIBRATE_SPIN_HZ) % 1.0
        logical = int(phase * pixel_count) % pixel_count
        opposite = (logical + pixel_count // 2) % pixel_count
        frame[physical_index(logical, pixel_count, zero_offset, clockwise)] = AMBER
        frame[physical_index(opposite, pixel_count, zero_offset, clockwise)] = AMBER
        return frame

    return frame
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_gauge.py -v`
Expected: PASS, 20 tests total

- [ ] **Step 5: Commit**

```bash
git add src/gauge.py tests/test_gauge.py
git commit -m "feat: render ring frames for every display state"
```

---

### Task 6: Core parking state transitions

**Files:**
- Create: `src/parkstate.py`
- Test: `tests/test_parkstate.py`

**Interfaces:**
- Consumes: state constants from `gauge` (Task 5)
- Produces: `parkstate.ParkStateMachine(arrive_tol_mm=30, arrive_release_mm=60, overshoot_mm=50, wake_mm=3000, still_mm=20, still_seconds=10.0, wake_move_mm=50, max_consec_fails=5, recover_good_reads=3, calibrate_hold_s=2.0)` with `update(distance_mm, stop_mm, now, button_down, read_ok)` → state string, and read-only property `state`.

This task implements `IDLE`, `APPROACHING`, `ARRIVED`, and `OVERSHOOT` only. Tasks 7 and 8 add the rest. All keyword arguments are accepted from the start so the signature never changes between tasks.

Hysteresis contract: `ARRIVED` is entered when the car is within `arrive_tol_mm` of the stop point and left only once it exceeds `arrive_release_mm`, so the display cannot flicker at the boundary.

- [ ] **Step 1: Write the failing test**

`tests/test_parkstate.py`:

```python
import gauge
from parkstate import ParkStateMachine


def step(m, distance, now, stop_mm=600, button_down=False, read_ok=True):
    return m.update(distance_mm=distance, stop_mm=stop_mm, now=now,
                    button_down=button_down, read_ok=read_ok)


def test_starts_idle():
    m = ParkStateMachine()
    assert m.state == gauge.IDLE


def test_no_target_is_idle():
    m = ParkStateMachine()
    assert step(m, None, 0.0) == gauge.IDLE


def test_target_beyond_wake_range_is_idle():
    m = ParkStateMachine(wake_mm=3000)
    assert step(m, 3500, 0.0) == gauge.IDLE


def test_target_inside_wake_range_approaches():
    m = ParkStateMachine(wake_mm=3000)
    assert step(m, 2000, 0.0) == gauge.APPROACHING


def test_reaching_the_stop_point_arrives():
    m = ParkStateMachine(arrive_tol_mm=30)
    assert step(m, 620, 0.0) == gauge.ARRIVED


def test_passing_the_stop_point_overshoots():
    m = ParkStateMachine(arrive_tol_mm=30, overshoot_mm=50)
    assert step(m, 500, 0.0) == gauge.OVERSHOOT


def test_arrived_holds_through_the_hysteresis_band():
    m = ParkStateMachine(arrive_tol_mm=30, arrive_release_mm=60)
    step(m, 620, 0.0)
    assert step(m, 650, 0.1) == gauge.ARRIVED
    assert step(m, 700, 0.2) == gauge.APPROACHING


def test_overshoot_recovers_to_arrived_when_backing_up():
    m = ParkStateMachine(arrive_tol_mm=30, overshoot_mm=50)
    step(m, 500, 0.0)
    assert step(m, 610, 0.1) == gauge.ARRIVED
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_parkstate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'parkstate'`

- [ ] **Step 3: Write the implementation**

`src/parkstate.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_parkstate.py -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add src/parkstate.py tests/test_parkstate.py
git commit -m "feat: add core parking state transitions"
```

---

### Task 7: Sleep on stillness

**Files:**
- Modify: `src/parkstate.py`
- Modify: `tests/test_parkstate.py` (append)

**Interfaces:**
- Consumes: `ranging.StillnessDetector` (Task 3), `ParkStateMachine` (Task 6)
- Produces: no new public names. `update` gains `SETTLED` as a possible return value.

Contract: once the car has held still for `still_seconds`, the state becomes `SETTLED` regardless of where it is relative to the stop point, and stays there until the distance moves by more than `wake_move_mm`. A parked car must not hold the ring red overnight.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parkstate.py`:

```python
def test_settles_after_holding_still():
    m = ParkStateMachine(still_seconds=10.0, arrive_tol_mm=30)
    assert step(m, 620, 0.0) == gauge.ARRIVED
    assert step(m, 620, 5.0) == gauge.ARRIVED
    assert step(m, 620, 10.0) == gauge.SETTLED


def test_settled_persists_while_parked():
    m = ParkStateMachine(still_seconds=10.0)
    step(m, 620, 0.0)
    step(m, 620, 10.0)
    assert step(m, 621, 600.0) == gauge.SETTLED


def test_movement_wakes_from_settled():
    m = ParkStateMachine(still_seconds=10.0, wake_move_mm=50)
    step(m, 620, 0.0)
    assert step(m, 620, 10.0) == gauge.SETTLED
    assert step(m, 1500, 11.0) == gauge.APPROACHING


def test_settles_mid_approach_too():
    m = ParkStateMachine(still_seconds=10.0)
    assert step(m, 2000, 0.0) == gauge.APPROACHING
    assert step(m, 2000, 10.0) == gauge.SETTLED


def test_leaving_range_returns_to_idle_not_settled():
    m = ParkStateMachine(still_seconds=10.0)
    step(m, 620, 0.0)
    step(m, 620, 10.0)
    assert step(m, None, 11.0) == gauge.IDLE
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_parkstate.py -v`
Expected: FAIL — `test_settles_after_holding_still` gets `'arrived'` instead of `'settled'`

- [ ] **Step 3: Write the implementation**

In `src/parkstate.py`, add the import at the top:

```python
import gauge
from ranging import StillnessDetector
```

Add to the end of `__init__`:

```python
        self._stillness = StillnessDetector(still_mm=still_mm,
                                            still_seconds=still_seconds,
                                            wake_move_mm=wake_move_mm)
```

Replace `update` with:

```python
    def update(self, distance_mm, stop_mm, now, button_down, read_ok):
        """Advance the machine one tick and return the new state."""
        parking = self._parking_state(distance_mm, stop_mm)

        if parking == gauge.IDLE:
            self._stillness.reset()
            self._state = gauge.IDLE
            return self._state

        if self._stillness.update(distance_mm, now):
            self._state = gauge.SETTLED
            return self._state

        self._state = parking
        return self._state
```

Note the ordering: `_parking_state` is evaluated first so its hysteresis sees the real parking state, but its result is only assigned to `self._state` when the car is not settled.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_parkstate.py -v`
Expected: PASS, 13 tests total

- [ ] **Step 5: Commit**

```bash
git add src/parkstate.py tests/test_parkstate.py
git commit -m "feat: sleep the display once the car has settled"
```

---

### Task 8: Fault, calibration, and uncalibrated handling

**Files:**
- Modify: `src/parkstate.py`
- Modify: `tests/test_parkstate.py` (append)

**Interfaces:**
- Consumes: `ParkStateMachine` (Tasks 6–7)
- Produces: read-only property `ParkStateMachine.calibration_captured` → int mm or `None`. It is non-`None` for exactly one `update` call, on the tick the calibration hold completes, and carries the distance to write to NVM.

Priority order, highest first: `FAULT` beats everything (a broken sensor must never look like guidance), then `CALIBRATE`, then `UNCALIBRATED`, then the parking states.

Contract:
- `read_ok=False` for `max_consec_fails` consecutive ticks enters `FAULT`; `recover_good_reads` consecutive good reads leave it.
- Holding the button for `calibrate_hold_s` while a valid distance is present enters `CALIBRATE` and captures that distance once. Releasing the button resets the hold timer.
- A `stop_mm` of `None` means uncalibrated: the machine reports `UNCALIBRATED` rather than inventing a stop point.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parkstate.py`:

```python
def test_repeated_read_failures_enter_fault():
    m = ParkStateMachine(max_consec_fails=5)
    for i in range(4):
        assert step(m, None, i * 0.1, read_ok=False) == gauge.IDLE
    assert step(m, None, 0.5, read_ok=False) == gauge.FAULT


def test_fault_clears_after_good_reads():
    m = ParkStateMachine(max_consec_fails=2, recover_good_reads=3)
    step(m, None, 0.0, read_ok=False)
    assert step(m, None, 0.1, read_ok=False) == gauge.FAULT
    assert step(m, 2000, 0.2) == gauge.FAULT
    assert step(m, 2000, 0.3) == gauge.FAULT
    assert step(m, 2000, 0.4) == gauge.APPROACHING


def test_fault_outranks_parking_states():
    m = ParkStateMachine(max_consec_fails=1)
    assert step(m, 620, 0.0, read_ok=False) == gauge.FAULT


def test_uncalibrated_when_no_stop_distance_stored():
    m = ParkStateMachine()
    assert step(m, 2000, 0.0, stop_mm=None) == gauge.UNCALIBRATED


def test_holding_the_button_calibrates():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    assert step(m, 850, 0.0, button_down=True) == gauge.APPROACHING
    assert step(m, 850, 1.0, button_down=True) == gauge.APPROACHING
    assert step(m, 850, 2.0, button_down=True) == gauge.CALIBRATE
    assert m.calibration_captured == 850


def test_calibration_is_captured_only_once():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, 850, 0.0, button_down=True)
    step(m, 850, 2.0, button_down=True)
    assert m.calibration_captured == 850
    step(m, 850, 2.1, button_down=True)
    assert m.calibration_captured is None


def test_releasing_the_button_resets_the_hold():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, 850, 0.0, button_down=True)
    step(m, 850, 1.0, button_down=False)
    assert step(m, 850, 2.5, button_down=True) == gauge.APPROACHING


def test_calibration_works_while_uncalibrated():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, 850, 0.0, stop_mm=None, button_down=True)
    assert step(m, 850, 2.0, stop_mm=None, button_down=True) == gauge.CALIBRATE
    assert m.calibration_captured == 850


def test_no_calibration_without_a_valid_distance():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, None, 0.0, button_down=True)
    assert step(m, None, 2.0, button_down=True) == gauge.IDLE
    assert m.calibration_captured is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_parkstate.py -v`
Expected: FAIL — `test_repeated_read_failures_enter_fault` gets `'idle'` instead of `'fault'`

- [ ] **Step 3: Write the implementation**

Add to the end of `__init__` in `src/parkstate.py`:

```python
        self._fails = 0
        self._goods = 0
        self._in_fault = False
        self._button_since = None
        self._calibrated_this_tick = None
```

Add the property:

```python
    @property
    def calibration_captured(self):
        """Distance in mm to persist, set for exactly one tick after a hold."""
        return self._calibrated_this_tick
```

Replace `update` with:

```python
    def update(self, distance_mm, stop_mm, now, button_down, read_ok):
        """Advance the machine one tick and return the new state."""
        self._calibrated_this_tick = None

        if self._track_health(read_ok):
            self._stillness.reset()
            self._button_since = None
            self._state = gauge.FAULT
            return self._state

        if self._track_button(distance_mm, now, button_down):
            self._stillness.reset()
            self._state = gauge.CALIBRATE
            return self._state

        if stop_mm is None:
            self._stillness.reset()
            self._state = gauge.UNCALIBRATED
            return self._state

        parking = self._parking_state(distance_mm, stop_mm)

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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_parkstate.py -v`
Expected: PASS, 22 tests total

- [ ] **Step 5: Run the whole suite**

Run: `pytest -v`
Expected: PASS, 62 tests total (7 settings + 13 ranging + 20 gauge + 22 parkstate)

- [ ] **Step 6: Commit**

```bash
git add src/parkstate.py tests/test_parkstate.py
git commit -m "feat: add fault detection and button calibration"
```

---

### Task 9: US-100 sensor wrapper

**Files:**
- Create: `src/rangefinder.py`
- Test: `tests/test_rangefinder.py`

**Interfaces:**
- Consumes: nothing at test time; at runtime an `adafruit_us100.US100` instance is injected
- Produces: `rangefinder.Rangefinder(sensor)` with `read_mm()` → int mm or `None`, and `read_temperature_c()` → number or `None`.

The injected object need only expose `.distance` (centimetres as a float, or `None` on failure) and `.temperature` (degrees C, or `None`). Because it is injected, this module is testable on a desktop with no CircuitPython present.

Contract: any exception from the sensor, and any `None`, negative, or zero reading, becomes `None`. Centimetres convert to millimetres exactly once, here.

- [ ] **Step 1: Write the failing test**

`tests/test_rangefinder.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_rangefinder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rangefinder'`

- [ ] **Step 3: Write the implementation**

`src/rangefinder.py`:

```python
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
```

A bare `except Exception` is deliberate here. The `adafruit_us100` library can raise several unrelated error types on a timeout or a malformed reply, and every one of them means the same thing to us: no reading this tick. The state machine turns sustained failures into the blue fault display.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_rangefinder.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add src/rangefinder.py tests/test_rangefinder.py
git commit -m "feat: add US-100 rangefinder adapter"
```

---

### Task 10: Hardware binding and main loop

**Files:**
- Create: `src/code.py`

**Interfaces:**
- Consumes: `settings.load`, `settings.save`, `ranging.Ranger`, `gauge.approach_fraction`, `gauge.render`, `parkstate.ParkStateMachine`, `rangefinder.Rangefinder`
- Produces: nothing importable. This is the entry point CircuitPython runs on boot.

This task has no unit tests — it is the one file that cannot run off-device. It is verified by Task 11's selftest and by the bring-up sequence in the spec. Keep it free of logic: every decision belongs in a tested module.

- [ ] **Step 1: Write the main loop**

`src/code.py`:

```python
"""Garage parking stop sensor. Hardware binding only; logic lives in the modules."""

import time

import board
import busio
import digitalio
import microcontroller
import neopixel

import adafruit_us100

import gauge
import settings
from parkstate import ParkStateMachine
from ranging import Ranger
from rangefinder import Rangefinder

# --- Ring configuration. Change these three when swapping ring size. ---
PIXEL_COUNT = 12
PIXEL_ZERO_OFFSET = 0
CLOCKWISE = True

MAX_BRIGHTNESS = 0.3
APPROACH_SPAN_MM = 2000
WAKE_MM = 3000
MAX_VALID_MM = 4000
ARRIVE_TOL_MM = 30
ARRIVE_RELEASE_MM = 60
OVERSHOOT_MM = 50
MEDIAN_WINDOW = 5
OUTLIER_JUMP_MM = 500
OUTLIER_PERSIST = 3
LOOP_HZ = 15
STILL_MM = 20
STILL_SECONDS = 10.0
WAKE_MOVE_MM = 50
MAX_CONSEC_FAILS = 5
RECOVER_GOOD_READS = 3
CALIBRATE_HOLD_S = 2.0

uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=0.2)
finder = Rangefinder(adafruit_us100.US100(uart))

pixels = neopixel.NeoPixel(board.D5, PIXEL_COUNT,
                           brightness=MAX_BRIGHTNESS, auto_write=False)

button = digitalio.DigitalInOut(board.D6)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

ranger = Ranger(window=MEDIAN_WINDOW, max_valid_mm=MAX_VALID_MM,
                outlier_jump_mm=OUTLIER_JUMP_MM, outlier_persist=OUTLIER_PERSIST)

machine = ParkStateMachine(arrive_tol_mm=ARRIVE_TOL_MM,
                           arrive_release_mm=ARRIVE_RELEASE_MM,
                           overshoot_mm=OVERSHOOT_MM,
                           wake_mm=WAKE_MM,
                           still_mm=STILL_MM,
                           still_seconds=STILL_SECONDS,
                           wake_move_mm=WAKE_MOVE_MM,
                           max_consec_fails=MAX_CONSEC_FAILS,
                           recover_good_reads=RECOVER_GOOD_READS,
                           calibrate_hold_s=CALIBRATE_HOLD_S)

stop_mm = settings.load(microcontroller.nvm)
period = 1.0 / LOOP_HZ

while True:
    started = time.monotonic()

    raw_mm = finder.read_mm()
    distance_mm = ranger.push(raw_mm)

    state = machine.update(distance_mm=distance_mm,
                           stop_mm=stop_mm,
                           now=started,
                           button_down=not button.value,
                           read_ok=raw_mm is not None)

    captured = machine.calibration_captured
    if captured is not None:
        stop_mm = captured
        settings.save(microcontroller.nvm, stop_mm)

    fraction = gauge.approach_fraction(distance_mm, stop_mm, APPROACH_SPAN_MM)
    frame = gauge.render(state, fraction, PIXEL_COUNT,
                         PIXEL_ZERO_OFFSET, CLOCKWISE, started)

    for index in range(PIXEL_COUNT):
        pixels[index] = frame[index]
    pixels.show()

    elapsed = time.monotonic() - started
    if elapsed < period:
        time.sleep(period - elapsed)
```

Note `button_down=not button.value`: the pull-up makes the pin read high when the button is open, so pressed means low.

- [ ] **Step 2: Verify the pure modules still pass**

Run: `pytest -v`
Expected: PASS, 69 tests total. `code.py` is not imported by any test and must not be.

- [ ] **Step 3: Commit**

```bash
git add src/code.py
git commit -m "feat: add hardware binding and main loop"
```

---

### Task 11: On-device selftest and deployment docs

**Files:**
- Create: `src/selftest.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `gauge.render` and the state constants
- Produces: nothing importable

`selftest.py` is not run automatically. Copy it over `code.py` on the device, or rename it, when you want to check the display without a car present.

- [ ] **Step 1: Write the selftest**

`src/selftest.py`:

```python
"""Walk the ring through every display state. Copy over code.py to run on-device."""

import time

import board
import neopixel

import gauge

PIXEL_COUNT = 12
PIXEL_ZERO_OFFSET = 0
CLOCKWISE = True
MAX_BRIGHTNESS = 0.3

SECONDS_PER_STATE = 4.0

pixels = neopixel.NeoPixel(board.D5, PIXEL_COUNT,
                           brightness=MAX_BRIGHTNESS, auto_write=False)


def show(state, fraction, seconds):
    print("state:", state, "fraction:", fraction)
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        now = time.monotonic()
        frame = gauge.render(state, fraction, PIXEL_COUNT,
                             PIXEL_ZERO_OFFSET, CLOCKWISE, now)
        for index in range(PIXEL_COUNT):
            pixels[index] = frame[index]
        pixels.show()
        time.sleep(0.02)


print("Pixel walk: confirms count, offset, and direction.")
for logical in range(PIXEL_COUNT):
    for index in range(PIXEL_COUNT):
        pixels[index] = gauge.OFF
    physical = gauge.physical_index(logical, PIXEL_COUNT,
                                    PIXEL_ZERO_OFFSET, CLOCKWISE)
    pixels[physical] = gauge.GREEN
    pixels.show()
    print("logical", logical, "-> physical", physical)
    time.sleep(0.4)

print("Approach sweep: the arc should shrink smoothly to nothing.")
for tenth in range(10, -1, -1):
    show(gauge.APPROACHING, tenth / 10.0, 0.3)

for state in (gauge.ARRIVED, gauge.OVERSHOOT, gauge.SETTLED,
              gauge.CALIBRATE, gauge.FAULT, gauge.UNCALIBRATED):
    show(state, 0.0, SECONDS_PER_STATE)

print("Selftest complete.")
```

The pixel walk at the start is the tool for finding `PIXEL_ZERO_OFFSET` and `CLOCKWISE`: watch which physical LED lights for logical 0 and which way the sequence travels, then set the two constants in `code.py` and `selftest.py` to match.

- [ ] **Step 2: Write the README**

`README.md`:

```markdown
# Garage Parking Stop Sensor

A NeoPixel ring that shows how much further you can pull forward, driven by a
US-100 ultrasonic sensor on an Adafruit Feather RP2040.

See `docs/superpowers/specs/2026-08-10-garage-parking-sensor-design.md` for the
full design and `docs/superpowers/plans/` for the implementation plan.

## Layout

- `src/` — everything that gets copied to the CIRCUITPY drive
- `tests/` — desktop pytest suite for the pure logic modules

## Running the tests

    pytest

The tests run on desktop CPython. `src/code.py` and `src/selftest.py` are the
only files that import CircuitPython hardware modules, and neither is imported
by any test.

## Deploying to the board

1. Install CircuitPython 9.x on the Feather RP2040.
2. Copy `adafruit_us100.mpy` and `neopixel.mpy` from the Adafruit CircuitPython
   library bundle into `CIRCUITPY/lib/`.
3. Copy everything in `src/` to the root of `CIRCUITPY`.

The board runs `code.py` on boot.

## Wiring

| US-100 | Feather RP2040 |
|---|---|
| VCC | 3V3 (not USB — the RP2040 is not 5V tolerant) |
| Trig/TX | TX (straight through, not crossed) |
| Echo/RX | RX (straight through, not crossed) |
| GND | GND |

The jumper on the back of the US-100 must be installed to select serial mode.

| NeoPixel ring | Feather RP2040 |
|---|---|
| Data In | D5 |
| PWR | USB (5V) |
| GND | GND |

Button: D6 to GND.

## First run

The board boots uncalibrated and shows two rotating amber pixels. Pull the car
to where you want it to stop, then hold the button for two seconds. The ring
spins green to confirm and the distance is written to NVM.

## Changing ring size

Edit `PIXEL_COUNT`, `PIXEL_ZERO_OFFSET`, and `CLOCKWISE` at the top of
`code.py`. Run `selftest.py` to find the right offset and direction for the new
ring — the pixel walk prints and lights each position in turn.

## Reading the display

| Display | Meaning |
|---|---|
| Dark | Nothing in range, or parked and settled |
| Shrinking green-to-amber arc | Keep coming; the arc is distance remaining |
| Solid red ring | Stop |
| Flashing red ring | Too far, back up |
| Slow blue pulse | Sensor fault — the reading is not trustworthy |
| Two rotating amber pixels | Never calibrated; hold the button while parked |
```

- [ ] **Step 3: Verify the suite still passes**

Run: `pytest -v`
Expected: PASS, 69 tests total

- [ ] **Step 4: Commit**

```bash
git add src/selftest.py README.md
git commit -m "feat: add on-device selftest and deployment docs"
```

---

## After the plan: on-device bring-up

The code being correct is necessary but not sufficient — the spec's primary risk is physical. Work through the spec's bring-up sequence in order, riskiest assumption first:

1. Run `selftest.py`. Confirm pixel count, find `PIXEL_ZERO_OFFSET` and `CLOCKWISE`, and watch pixel zero for the WS2812B logic-level symptom described in the spec.
2. Read the sensor at a desk against a tape measure. If every reading is `None`, suspect the UART jumper or the straight-through wiring.
3. **Point it at the actual car before mounting anything.** Apply the spec's acceptance criteria: 100 readings at 0.5m, 1m, and 2m; median within 2% of tape; interquartile range at or below 10mm. Bimodal jumps of 10–20cm mean the ping is going through the grille — lower the aim point and retest.
4. Confirm `read_temperature_c()` returns a sane value, proving compensation is live.
5. Re-check in a cold garage.

Tune `APPROACH_SPAN_MM` once mounted; 2000 is a starting guess, not a measured value.
