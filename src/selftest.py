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
