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
