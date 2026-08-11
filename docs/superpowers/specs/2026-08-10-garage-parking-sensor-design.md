# Garage Parking Stop Sensor — Design

Date: 2026-08-10

## Goal

A wall-mounted indicator that tells the driver when to stop pulling forward. A NeoPixel
ring shows a shrinking arc as the car approaches and blooms to solid red at the stop
point. The stop point is set by pressing a button while parked correctly, so it can be
adjusted without removing the unit from the wall.

## Non-goals

- Left/right centering guidance
- Multiple bays or multiple vehicles
- Network connectivity, phone notifications, or home-automation integration
- Garage door state awareness

These are deliberately excluded. The single-vehicle stop line is the whole product.

## Constraints

- **No soldering.** Every connection is a plug, a header, or a breadboard hole. The
  soldering iron stays packed.
- **Adafruit as parts source.**
- **Swappable ring size.** A 12-LED ring is in hand and pre-wired; 16 and 24 rings are
  also owned. Changing ring size must be a config edit, not a code rewrite.

## Bill of materials

Already owned:

| Item | Note |
|---|---|
| Adafruit Feather RP2040 | Headers installed |
| US-100 ultrasonic sensor ([#4019](https://www.adafruit.com/product/4019)) | UART jumper must be installed on the back |
| NeoPixel Ring — 12 × 5050 RGB | Already has wire leads attached from prior work |

To buy:

| Item | Note |
|---|---|
| Premium Female/Male extension jumpers, 12" ([#824](https://www.adafruit.com/product/824)) | Ribbon form; peel a 4-wide strip and chain three for a ~900mm umbilical |
| Tactile pushbutton, 6mm breadboard-friendly | Calibrate button |
| Half-size breadboard | If not already on hand |
| USB-C cable and 5V wall adapter | If not already on hand |
| 1N4001 diode | Contingency only — see NeoPixel wiring |

## Board selection rationale

The Feather RP2040 was chosen over the also-owned Feather 32u4 Bluefruit, QT Py RP2040,
and Arduino Uno because:

- CircuitPython gives edit-and-reload iteration with no toolchain
- RP2040 PIO gives reliable NeoPixel timing
- `busio.UART` works on any pin pair
- Ample RAM for a sliding median filter
- Roomy headers and USB-C

The 32u4 has 2.5KB RAM and no CircuitPython. The Uno is 5V-only. The QT Py RP2040 is the
same silicon with fewer pins and is the designated spare.

## Physical architecture

Two units, both on the front wall of the bay:

- **Head unit** at driver eye level: Feather, ring, and button on a breadboard, powered
  by USB-C from a wall adapter.
- **Sensor unit** at license-plate height, aimed head-on at the car's nose, connected by
  a ~900mm 4-wire umbilical.

### Why the long wire goes to the sensor, not the ring

The US-100 in UART mode runs at 9600 baud and draws ~2mA. At that speed and current, a
multi-metre run is electrically uninteresting — no reflections to worry about, no
meaningful voltage drop.

NeoPixel data is 800kHz single-ended with tight timing, prone to ringing and first-pixel
corruption over long runs, and a 12-LED ring can draw ~700mA at full white. Lengthening
that link would require a series resistor and likely a level shifter.

So the ring stays next to the Feather and the sensor goes on the umbilical.

### Aim point

Aim at the **front license plate** — flat, rigid, perpendicular, roughly 30×15cm. This is
close to an ideal ultrasonic target. If there is no front plate, use the solid painted
bumper below the grille.

**Do not aim at the open grille mesh.** See Risks.

Mount the sensor with tape or a clamp during bring-up so the aim height can be adjusted in
10cm increments before anything is permanent.

## Wiring

The Feather's logic is 3.3V throughout. The sensor is run at 3.3V so nothing above that
is ever driven into a GPIO. The ring is the one 5V device, and it only ever *receives*
signal, so no level shifter is required in either direction.

### US-100 → Feather RP2040

| US-100 pin | Feather pin | Note |
|---|---|---|
| VCC | **3V3** | Not USB 5V. RP2040 GPIO is not 5V tolerant, and the sensor's TX would return 5V into RX. |
| Trig/TX | TX | **Straight through, not crossed** |
| Echo/RX | RX | **Straight through, not crossed** |
| GND | GND | |

The US-100 is wired straight through rather than crossed, unlike every other UART device.
The jumper on the back of the sensor must be present to select serial mode.

Running the sensor at 3.3V rather than 5V may reduce its maximum range below the rated
4.5m. The garage needs roughly 3m, so this is acceptable.

### NeoPixel ring → Feather RP2040

| Ring lead | Feather pin |
|---|---|
| Data In | D5 |
| PWR | **USB (5V)** |
| GND | GND |

The Adafruit 5050 RGB rings use WS2812B drivers, which are specified for 3.5–5.3V. They
must **not** be run from 3V3 — below spec they go dim and colour-shifted. Power them from
the Feather's `USB` pin, which provides 5V whenever the board is USB-powered.

This introduces no 5V hazard to the microcontroller: the data line is an *output* from the
RP2040 to the ring, so nothing at 5V is ever driven back into a GPIO. (This is the
opposite of the US-100 situation, where the sensor's TX is an *input* to the Feather and
5V would be damaging.)

There is one marginal detail. A WS2812B running at 5V wants a logic high of at least
0.7 × VDD = 3.5V, and the RP2040 drives 3.3V. This usually works, but the classic symptom
when it does not is the **first pixel** misbehaving while the rest are fine. The fix is a
single 1N4001-class diode in series with the ring's 5V lead, dropping supply to ~4.3V and
the threshold to ~3.0V. A diode sits in a breadboard with no soldering, so keep one on
hand. Do not add it pre-emptively — build without it and only insert it if pixel zero
misbehaves.

Ring brightness is capped at 0.3 in software; 12 pixels at full white would draw ~700mA.

### Button → Feather RP2040

One leg to D6, other leg to GND. Internal pull-up, active low.

## Software architecture

Only `code.py` imports `board`, `neopixel`, or `busio`. Every other module is pure logic
and runs under pytest on a laptop.

| Module | Responsibility | Dependencies |
|---|---|---|
| `rangefinder.py` | Wrap `adafruit_us100`. Return distance in mm or `None`. | Injected UART object |
| `ranging.py` | Sliding median, outlier rejection, stationary detection | None |
| `gauge.py` | Map distance + state → list of RGB tuples | None |
| `settings.py` | Read/write stop distance to NVM | Injected NVM bytearray |
| `code.py` | State machine, main loop, hardware binding | All of the above |

`gauge.py` and `ranging.py` import nothing hardware-related, so ring-size swaps and filter
behavior are testable off-device.

## Configuration constants

Defined at the top of `code.py`:

```python
PIXEL_COUNT        = 12      # change to 16 or 24 when swapping rings
PIXEL_ZERO_OFFSET  = 0       # which physical index sits at 12 o'clock
CLOCKWISE          = True    # chain direction around the ring
MAX_BRIGHTNESS     = 0.3

APPROACH_SPAN_MM   = 2000    # gauge starts filling this far above the stop point
WAKE_MM            = 3000    # anything closer than this wakes the display
MAX_VALID_MM       = 4000
ARRIVE_TOL_MM      = 30      # enter ARRIVED within this band
ARRIVE_RELEASE_MM  = 60      # leave ARRIVED beyond this (hysteresis)
OVERSHOOT_MM       = 50      # this far past the stop point is overshoot

MEDIAN_WINDOW      = 5
OUTLIER_JUMP_MM    = 500
OUTLIER_PERSIST    = 3       # samples before a big jump is believed
LOOP_HZ            = 15

STILL_MM           = 20
STILL_SECONDS      = 10
WAKE_MOVE_MM       = 50

MAX_CONSEC_FAILS   = 5
RECOVER_GOOD_READS = 3
CALIBRATE_HOLD_S   = 2.0
```

Every ring zone boundary is computed as a fraction of `PIXEL_COUNT`. No fixed pixel
indices appear anywhere in the display logic.

## Gauge algorithm

Let `d` be the filtered distance in mm and `stop` the stored stop distance.

```
frac = clamp((d - stop) / APPROACH_SPAN_MM, 0.0, 1.0)
lit  = round(frac * PIXEL_COUNT)
```

`frac` is 1.0 when the car is a full approach-span away and 0.0 at the stop point, so the
lit arc **shrinks** as the car closes in.

Arc colour interpolates linearly in RGB from green `(0, 255, 0)` at `frac = 1.0` to amber
`(255, 140, 0)` at `frac = 0.0`.

The lit pixels are the `lit` pixels nearest 12 o'clock, measured by angular distance in
both directions, so the arc closes symmetrically inward. Physical index is resolved as:

```
physical(i) = (PIXEL_ZERO_OFFSET + (i if CLOCKWISE else -i)) % PIXEL_COUNT
```

This ordering works for any pixel count without special-casing odd or even.

Distance is encoded twice — by arc length and by colour — so the display is readable at a
glance and does not rely on colour discrimination alone.

## State machine

| State | Entry condition | Display |
|---|---|---|
| `IDLE` | No valid target within `WAKE_MM` | Off |
| `APPROACHING` | Target within `WAKE_MM`, `d > stop + ARRIVE_TOL_MM` | Shrinking green→amber arc |
| `ARRIVED` | `abs(d - stop) <= ARRIVE_TOL_MM` | Full ring solid red |
| `OVERSHOOT` | `d < stop - OVERSHOOT_MM` | Full ring flashing red, 2Hz |
| `SETTLED` | Distance stable within `STILL_MM` for `STILL_SECONDS` | Fade out over 1s, then off |
| `CALIBRATE` | Button held `CALIBRATE_HOLD_S` | Green spin animation, then confirm |
| `FAULT` | `MAX_CONSEC_FAILS` consecutive read failures | Slow blue pulse, 0.5Hz |

`ARRIVED` uses hysteresis: entered within `ARRIVE_TOL_MM`, left only beyond
`ARRIVE_RELEASE_MM`, so the display does not flicker at the boundary.

`SETTLED` is left when distance changes by more than `WAKE_MOVE_MM` from the settled
reference. This prevents a parked car from holding the ring red overnight.

`FAULT` is left after `RECOVER_GOOD_READS` consecutive successful reads.

## Filtering

- **Sliding** median of `MEDIAN_WINDOW` samples, recomputed every sample. Output stays at
  `LOOP_HZ` with roughly `MEDIAN_WINDOW / LOOP_HZ` ≈ 0.3s of lag. At parking speed
  (~0.8 m/s) that is ~10cm of travel.
- **Outlier rejection:** a reading differing from the running median by more than
  `OUTLIER_JUMP_MM` is discarded unless the next `OUTLIER_PERSIST` samples agree with it.
  This distinguishes a person walking through the beam from the car actually arriving.
- **Range gate:** readings of 0 or above `MAX_VALID_MM` are treated as no-target, never as
  a distance.

Note the limitation: the median filter rejects transient outliers. It does **not** correct
a stable-but-wrong reading, such as a consistent echo off the radiator behind the grille.
That failure mode is addressed by aim point selection, not by filtering.

## Calibration and persistence

Holding the button for `CALIBRATE_HOLD_S` captures the current filtered distance as the
new stop point, writes it to NVM, and confirms with a green spin animation.

NVM layout (4 bytes, written in a single assignment):

| Offset | Size | Meaning |
|---|---|---|
| 0 | 1 | Magic byte `0x67` |
| 1 | 1 | Format version `0x01` |
| 2–3 | 2 | Stop distance, uint16 little-endian, mm |

`microcontroller.nvm` is used rather than a settings file. Writing to the CircuitPython
filesystem from code requires remounting it read-write in `boot.py`, which makes the USB
drive read-only to the host and turns every code edit into a fight. NVM avoids this
entirely.

Each NVM assignment is a flash erase/write cycle, so the write happens **only** on button
press, never in the main loop.

If the magic byte does not match on boot, the stop distance is treated as unset. The unit
runs a distinct startup animation prompting calibration rather than guiding with an
invented stop distance.

## Failure handling

The governing principle: **a failed sensor must never resemble "keep coming."**

- Consecutive read failures drive the ring to a slow blue pulse. Blue appears in no other
  state, so it cannot be misread as parking guidance.
- Zero and out-of-range readings are classified as no-target, not as a large distance.
- An uncalibrated unit refuses to display a stop point and asks for calibration instead.

## Testing

### Off-device (pytest, on the laptop)

- `gauge.py`: arc length at representative distances; symmetric closing; correct behavior
  at `PIXEL_COUNT` of 12, 16, and 24; orientation offset and direction handling; colour
  interpolation endpoints.
- `ranging.py`: median correctness; transient outlier rejected; sustained jump accepted
  after `OUTLIER_PERSIST`; range gate; stationary detection timing.
- `settings.py`: round-trip encode/decode against a fake bytearray; unset detection on bad
  magic; version field respected.
- State machine: every transition in the table above, including hysteresis at the
  `ARRIVED` boundary and `FAULT` entry and recovery.

### On-device

`selftest.py` walks the ring through every visual state in sequence so the display can be
verified without a car present.

### Bring-up order

Riskiest assumption first:

1. Ring blink test — confirms wiring, pixel count, orientation offset, and direction.
   Watch pixel zero specifically; if it flickers or shows wrong colours while the rest are
   correct, insert the 1N4001 in series with the ring's 5V lead.
2. Sensor read test at a desk against a tape measure — confirms UART direction, jumper
   position, and library operation.
3. **Aim at the actual car before mounting anything.** See acceptance criteria below.
4. Verify the temperature reading is sane, confirming compensation is active.
5. Re-check readings in a cold garage.

### Aim-point acceptance criteria

With the car parked, take 100 readings at each of 0.5m, 1.0m, and 2.0m:

- Median within 2% of a tape measure
- Interquartile range at or below 10mm
- No more than 5% of samples deviating more than 100mm from the median

Bimodal readings jumping by 10–20cm indicate multipath through the grille. Lower the aim
point and retest.

## Risks

### Grille apertures (primary risk)

The US-100 operates at 40kHz, giving a wavelength of 8.6mm in air. Grille openings larger
than roughly that let a significant fraction of the energy pass through, diffract inside
the engine bay, and return off the radiator or fan shroud. Typical car grille openings are
10–25mm, so this is a live concern rather than a theoretical one.

The slats between openings still reflect, so a reading will likely be present. The hazard
is instability — the dominant return surface flipping between the grille plane and
something 15cm deeper as the angle shifts slightly. This produces a stable-but-wrong
reading that filtering cannot fix.

*Mitigation:* aim at the license plate or solid bumper, per Aim Point. Verify with the
acceptance criteria before mounting.

*Fallback:* if the entire front end proves to be a poor ultrasonic target, substitute a
[VL53L4CX](https://www.adafruit.com/product/5425) laser time-of-flight sensor, which
resolves the nearest strong return via histogram processing and is unaffected by
apertures. It connects over STEMMA QT rather than UART, so `rangefinder.py` is the only
module that changes. Do not buy until the US-100 has actually failed.

### Temperature drift

The speed of sound changes roughly 0.6 m/s per °C. An unheated garage swinging 20°C would
introduce ~3.5% error — about 7cm at 2m, enough to matter. The US-100 in UART mode returns
temperature-compensated millimetres, which is the main reason serial mode was chosen over
HC-SR04 trigger/echo mode.

### Reduced range at 3.3V

Powering the sensor below 5V may lower maximum range. The required range is ~3m against a
rated 4.5m, so there is margin, but this is confirmed in bring-up step 2.

### Raked front-end geometry

A steeply sloped hood or strongly curved bumper scatters the ping away from the sensor.
Addressed by aiming at the flattest available surface and by keeping the sensor mount
adjustable during bring-up.

## Open items

None. All design decisions above are settled.
