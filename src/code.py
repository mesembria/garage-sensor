"""Garage parking stop sensor. Hardware binding only; logic lives in the modules."""

import time

import board
import busio
import digitalio
import microcontroller
import neopixel

import adafruit_us100

import gauge
import ringconfig
import settings
from parkstate import ParkStateMachine
from ranging import Ranger
from rangefinder import Rangefinder

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

pixels = neopixel.NeoPixel(board.D5, ringconfig.PIXEL_COUNT,
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

# CircuitPython's time.monotonic() is a single-precision float. Its ULP grows
# with uptime, and by ~97 days it reaches 0.5s, at which point every
# representable `now` is an exact multiple of the 2Hz OVERSHOOT flash period
# and gauge.render's animation phase freezes. Feed the animation a clock that
# is wrapped well before precision loss becomes visible: 4s is an exact
# multiple of the 0.5s OVERSHOOT flash, the 2s FAULT pulse, and the 1s
# CALIBRATE spin, so wrapping introduces no visible seam, and re-deriving it
# from a small elapsed-ns value every tick keeps its resolution full-precision
# forever. `machine.update` still gets an ever-increasing `now`, since
# hysteresis and stillness timing must not wrap.
BOOT_NS = time.monotonic_ns()
PHASE_WRAP_NS = 4_000_000_000  # 4s: an exact multiple of every animation period

while True:
    tick_start_ns = time.monotonic_ns()
    ticks_ns = tick_start_ns - BOOT_NS
    started = ticks_ns / 1e9
    phase_now = (ticks_ns % PHASE_WRAP_NS) / 1e9

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
    frame = gauge.render(state, fraction, ringconfig.PIXEL_COUNT,
                         ringconfig.PIXEL_ZERO_OFFSET, ringconfig.CLOCKWISE,
                         phase_now)

    for index in range(ringconfig.PIXEL_COUNT):
        pixels[index] = frame[index]
    pixels.show()

    # monotonic_ns() throughout this tick, not monotonic(), so pacing never
    # mixes the float32-degrading clock with the wrapped/full-precision one.
    elapsed = (time.monotonic_ns() - tick_start_ns) / 1e9
    if elapsed < period:
        time.sleep(period - elapsed)
