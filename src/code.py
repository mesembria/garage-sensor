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
