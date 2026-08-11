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
