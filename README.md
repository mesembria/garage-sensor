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

The tests run on desktop CPython. `src/code.py`, `src/selftest.py`, and
`src/sensortest.py` are the only files that import CircuitPython hardware
modules, and none of them is imported by any test.

**Note on pytest configuration:** `pyproject.toml` carries `addopts = "-p no:debugging"`.
This is load-bearing and non-obvious: `src/code.py` must keep that exact name for
CircuitPython, but it shadows Python's stdlib `code` module once `src/` is on `sys.path`.
pytest's debugging plugin imports `pdb` → `code`, picks up ours, hits `import board`,
and the entire suite becomes uncollectable. The tradeoff is that `--pdb` and `--trace`
are unavailable in this project.

## Deploying to the board

1. Install CircuitPython 9.x on the Feather RP2040.
2. Copy `adafruit_us100.mpy` and `neopixel.mpy` from the Adafruit CircuitPython
   library bundle into `CIRCUITPY/lib/`.
3. Copy everything in `src/` to the root of `CIRCUITPY`.

The board runs `code.py` on boot.

## Running the on-device tools

`selftest.py` and `sensortest.py` are hardware files, not standalone scripts —
CircuitPython only runs whatever is named `code.py`. To run one:

- Rename it to `code.py` (rename the real `code.py` out of the way first), or
- Connect a serial REPL (e.g. `screen`, `mpremote`, or the Mu editor) and run
  `import selftest` or `import sensortest` directly.

Restore the real `code.py` afterward.

## Bring-up sequence

Do these in order — riskiest assumption first — before trusting the unit:

1. **Ring blink test.** Run `selftest.py`. Its pixel walk confirms count,
   offset, and direction; watch pixel zero specifically (see Wiring below).
2. **Sensor read test at a desk, against a tape measure.** Run `sensortest.py`
   and confirm the live distance readings track the tape measure. This
   confirms UART direction, the jumper position, and library operation.
3. **Aim at the actual car before mounting anything.** With the car parked,
   use `sensortest.py` to take 100 readings at each of 0.5m, 1.0m, and 2.0m.
   The unit passes if, at each distance: the median is within 2% of a tape
   measure, the interquartile range is 10mm or less, and no more than 5% of
   samples deviate more than 100mm from the median. `sensortest.py` prints
   all of these. Bimodal readings jumping by 10-20cm indicate multipath
   through the grille — lower the aim point (license plate or solid bumper,
   not the open grille mesh) and retest.
4. **Confirm the temperature reading is sane.** `sensortest.py` prints it
   once at startup; a plausible ambient value confirms compensation is
   active.
5. **Re-check readings in a cold garage**, since the speed of sound (and so
   the sensor's compensation) shifts with temperature.

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

The ring must NOT be run from 3V3: WS2812B drivers are specified for 3.5–5.3V and go dim and colour-shifted below that.

Button: D6 to GND.

**Pixel-zero contingency.** A WS2812B running at 5V wants a logic high of at
least 0.7 × VDD = 3.5V, and the RP2040 drives 3.3V. This usually works, but
the classic symptom when it doesn't is the *first pixel* misbehaving while the
rest are fine. If that happens during the ring blink test (Bring-up sequence step 1, above), put a
1N4001-class diode in series with the ring's 5V lead: it drops supply to
~4.3V and the threshold with it, to ~3.0V. A diode sits in a breadboard with
no soldering. Don't add it pre-emptively — only insert it if pixel zero
actually misbehaves.

## First run

The board boots uncalibrated and shows two rotating amber pixels. Pull the car
to where you want it to stop, then hold the button for two seconds. The ring
spins green to confirm and the distance is written to NVM.

**Recalibrating** later works the same way: pull the car to wherever you now
want it to stop and hold the button for two seconds again. The new distance
overwrites the old one in NVM.

## Changing ring size

Edit `PIXEL_COUNT`, `PIXEL_ZERO_OFFSET`, and `CLOCKWISE` in `src/ringconfig.py`
— it's the single place both `code.py` and `selftest.py` read these from, so
editing it there is enough for both. Run `selftest.py` to find the right
offset and direction for the new ring — the pixel walk prints and lights each
position in turn.

## Tuning constants

`APPROACH_SPAN_MM` (in `code.py`, default 2000) is a starting guess for how
far above the stop point the arc should start filling. Tune it once the unit
is mounted and you can see how it reads at parking speed.

The distance filter (`ranging.Ranger`, constructed in `code.py`) has one more
constant than `code.py`'s own list documents: `no_target_clears` (default 3).
It controls how many consecutive no-target readings are tolerated before the
filter drops its held distance and reports "nothing there" — i.e. how long a
stale distance is held after the target actually vanishes. It sits alongside
`MEDIAN_WINDOW`, `OUTLIER_JUMP_MM`, and `OUTLIER_PERSIST` as a filter-behaviour
knob, even though it isn't currently exposed as a `code.py` constant.

## Reading the display

| Display | Meaning |
|---|---|
| Dark | Nothing in range, or parked and settled |
| Shrinking green-to-amber arc | Keep coming; the arc is distance remaining |
| Solid red ring | Stop |
| Flashing red ring | Too far, back up |
| Slow blue pulse | Sensor fault — the reading is not trustworthy |
| One green pixel rotating | Calibration in progress — keep holding the button |
| Two rotating amber pixels | Never calibrated; hold the button while parked |
