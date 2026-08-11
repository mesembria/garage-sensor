import gauge


def test_fraction_is_one_at_full_span_and_beyond():
    assert gauge.approach_fraction(2600, 600, 2000) == 1.0
    assert gauge.approach_fraction(9000, 600, 2000) == 1.0


def test_fraction_is_zero_at_and_past_the_stop_point():
    assert gauge.approach_fraction(600, 600, 2000) == 0.0
    assert gauge.approach_fraction(300, 600, 2000) == 0.0


def test_fraction_is_linear_in_between():
    assert gauge.approach_fraction(1600, 600, 2000) == 0.5


def test_fraction_defaults_to_one_when_unknown():
    assert gauge.approach_fraction(None, 600, 2000) == 1.0
    assert gauge.approach_fraction(1000, None, 2000) == 1.0


def test_lit_count_spans_zero_to_pixel_count():
    assert gauge.lit_count(1.0, 12) == 12
    assert gauge.lit_count(0.0, 12) == 0
    assert gauge.lit_count(0.5, 12) == 6


def test_physical_index_applies_offset_and_direction():
    assert gauge.physical_index(0, 12, 3, True) == 3
    assert gauge.physical_index(2, 12, 3, True) == 5
    assert gauge.physical_index(2, 12, 3, False) == 1
    assert gauge.physical_index(11, 12, 0, True) == 11


def test_arc_closes_symmetrically_around_twelve_oclock():
    assert gauge.arc_pixels(1, 12, 0, True) == [0]
    assert sorted(gauge.arc_pixels(3, 12, 0, True)) == [0, 1, 11]
    assert sorted(gauge.arc_pixels(5, 12, 0, True)) == [0, 1, 2, 10, 11]


def test_arc_respects_offset():
    assert sorted(gauge.arc_pixels(3, 12, 6, True)) == [5, 6, 7]


def test_arc_endpoints():
    assert gauge.arc_pixels(0, 12, 0, True) == []
    assert sorted(gauge.arc_pixels(12, 12, 0, True)) == list(range(12))


def test_arc_works_for_other_ring_sizes():
    for count in (16, 24):
        assert len(gauge.arc_pixels(count, count, 0, True)) == count
        assert sorted(gauge.arc_pixels(count, count, 0, True)) == list(range(count))
        assert gauge.arc_pixels(1, count, 0, True) == [0]


def test_arc_color_endpoints():
    assert gauge.arc_color(1.0) == gauge.GREEN
    assert gauge.arc_color(0.0) == gauge.AMBER


def test_arc_color_interpolates():
    mid = gauge.arc_color(0.5)
    assert gauge.AMBER[0] > mid[0] > gauge.GREEN[0]
    assert gauge.GREEN[1] > mid[1] > gauge.AMBER[1]


def test_render_returns_one_color_per_pixel():
    for state in (gauge.IDLE, gauge.APPROACHING, gauge.ARRIVED,
                  gauge.OVERSHOOT, gauge.SETTLED, gauge.CALIBRATE,
                  gauge.FAULT, gauge.UNCALIBRATED):
        frame = gauge.render(state, 0.5, 12, 0, True, 0.0)
        assert len(frame) == 12
        assert all(len(c) == 3 for c in frame)


def test_idle_and_settled_are_dark():
    assert gauge.render(gauge.IDLE, 0.5, 12, 0, True, 0.0) == [gauge.OFF] * 12
    assert gauge.render(gauge.SETTLED, 0.5, 12, 0, True, 0.0) == [gauge.OFF] * 12


def test_approaching_lights_only_the_arc():
    frame = gauge.render(gauge.APPROACHING, 0.25, 12, 0, True, 0.0)
    assert frame.count(gauge.OFF) == 9
    assert len([c for c in frame if c != gauge.OFF]) == 3


def test_approaching_floors_to_one_pixel_near_the_stop_point():
    # A tiny non-zero fraction rounds to 0 lit pixels via lit_count, but the
    # ring must never go dark while still APPROACHING.
    frame = gauge.render(gauge.APPROACHING, 0.001, 12, 0, True, 0.0)
    assert frame != [gauge.OFF] * 12
    assert len([c for c in frame if c != gauge.OFF]) == 1


def test_arrived_fills_the_whole_ring_red():
    assert gauge.render(gauge.ARRIVED, 0.0, 12, 0, True, 0.0) == [gauge.RED] * 12


def test_overshoot_flashes_at_two_hertz():
    on = gauge.render(gauge.OVERSHOOT, 0.0, 12, 0, True, 0.0)
    off = gauge.render(gauge.OVERSHOOT, 0.0, 12, 0, True, 0.25)
    assert on == [gauge.RED] * 12
    assert off == [gauge.OFF] * 12


def test_fault_is_blue_and_pulses():
    dim = gauge.render(gauge.FAULT, 0.0, 12, 0, True, 0.0)
    bright = gauge.render(gauge.FAULT, 0.0, 12, 0, True, 1.0)
    assert all(c[0] == 0 and c[1] == 0 for c in dim)
    assert bright[0][2] > dim[0][2]
    # The dimmest point of the pulse must still be visibly blue, never fully
    # off: a broken sensor must never be pixel-for-pixel identical to IDLE.
    assert dim[0][2] > 0


def test_calibrate_lights_a_single_moving_pixel():
    frame = gauge.render(gauge.CALIBRATE, 0.0, 12, 0, True, 0.0)
    assert len([c for c in frame if c != gauge.OFF]) == 1
    later = gauge.render(gauge.CALIBRATE, 0.0, 12, 0, True, 0.5)
    assert frame != later


def test_uncalibrated_shows_opposing_amber_pixels():
    frame = gauge.render(gauge.UNCALIBRATED, 0.0, 12, 0, True, 0.0)
    assert len([c for c in frame if c == gauge.AMBER]) == 2
