"""Bring-up tool for the sensor's primary risk: grille multipath.

Prints a live distance reading (aim the sensor and check it against a tape
measure, per bring-up steps 2-3) and the temperature once at startup (step
4, confirming temperature compensation is active), then collects 100 samples
and checks them against the design's aim-point acceptance criteria: median
within 2% of a tape measure, interquartile range at or below 10mm, no more
than 5% of samples deviating more than 100mm from the median.

Same convention as selftest.py: a hardware file, copy over code.py to run on
CircuitPython, or `import sensortest` from the REPL. Not imported by any test.
"""

import time

import board
import busio

import adafruit_us100

from ranging import median
from rangefinder import Rangefinder

PREVIEW_READINGS = 10
SAMPLE_COUNT = 100
SAMPLE_INTERVAL_S = 0.1

uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=0.2)
finder = Rangefinder(adafruit_us100.US100(uart))

print("temperature C:", finder.read_temperature_c())

print("Live distance, check against a tape measure:")
for _ in range(PREVIEW_READINGS):
    print("distance mm:", finder.read_mm())
    time.sleep(0.5)

print("Collecting", SAMPLE_COUNT, "samples...")
samples = []
for _ in range(SAMPLE_COUNT):
    mm = finder.read_mm()
    if mm is not None:
        samples.append(mm)
    time.sleep(SAMPLE_INTERVAL_S)

valid = len(samples)
print("valid readings:", valid, "/", SAMPLE_COUNT)

if valid:
    ordered = sorted(samples)
    med = median(samples)
    lower_q = median(ordered[:valid // 2])
    upper_q = median(ordered[(valid + 1) // 2:])
    iqr = (upper_q - lower_q) if lower_q is not None and upper_q is not None else None
    deviating = sum(1 for v in samples if abs(v - med) > 100)

    print("median mm:", med)
    print("interquartile range mm:", iqr)
    print("min mm:", min(samples), "max mm:", max(samples))
    print("deviating >100mm from median:", deviating, "/", valid)
    if iqr is not None:
        print("IQR <= 10mm:", "PASS" if iqr <= 10 else "FAIL")
else:
    print("No valid readings; check wiring and aim before trusting this mount point.")
