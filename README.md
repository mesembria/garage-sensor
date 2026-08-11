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
| One green pixel rotating | Calibration in progress — keep holding the button |
| Two rotating amber pixels | Never calibrated; hold the button while parked |
