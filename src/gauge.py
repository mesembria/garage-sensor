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
        # lit_count rounds to zero for a stretch of small-but-nonzero fractions
        # (with the shipped config, the last ~83mm before the stop point). Without
        # the floor of one pixel, that stretch renders bit-identical to IDLE and
        # SETTLED, so the ring appears to switch off right when the driver is
        # closest and needs it most. APPROACHING is only reachable with
        # fraction > 0, so flooring at one pixel here can never mask the actual
        # stop point (ARRIVED takes over well before fraction reaches 0).
        lit = lit_count(fraction, pixel_count) or 1
        for index in arc_pixels(lit, pixel_count, zero_offset, clockwise):
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
