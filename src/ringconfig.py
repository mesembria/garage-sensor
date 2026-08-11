"""Ring geometry, shared by code.py and selftest.py (and sensortest.py, which
doesn't need it but could).

This is the single place to edit when swapping ring size: 12, 16, and 24-pixel
rings are all owned, and two independent copies of these constants (one in
code.py, one in selftest.py) will eventually drift, leaving one of the two
entry points wrong about the ring it's driving. A 24-pixel ring driven with
PIXEL_COUNT = 12 lights only half the ring and leaves the rest permanently
dark, which reads as a wiring fault rather than a stale config value.

After changing PIXEL_COUNT, run selftest.py: its pixel walk lights each
logical position in turn and prints the physical index it maps to, which is
how you find the right PIXEL_ZERO_OFFSET and CLOCKWISE for the new ring's
wiring. This module imports nothing, so it is safe to import from both
desktop pytest and CircuitPython.
"""

PIXEL_COUNT = 12
PIXEL_ZERO_OFFSET = 0
CLOCKWISE = True
