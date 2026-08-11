from ranging import Ranger, median, StillnessDetector


def test_median_odd_and_even():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2
    assert median([]) is None


def feed(ranger, values):
    out = None
    for v in values:
        out = ranger.push(v)
    return out


def test_reports_median_of_window():
    r = Ranger(window=5)
    assert feed(r, [100, 102, 101, 103, 99]) == 101


def test_window_slides_and_drops_oldest():
    r = Ranger(window=3)
    feed(r, [100, 100, 100])
    assert feed(r, [200, 200, 200]) == 200


def test_single_outlier_is_rejected():
    r = Ranger(window=5, outlier_jump_mm=500, outlier_persist=3)
    feed(r, [1000, 1000, 1000, 1000, 1000])
    assert r.push(50) == 1000
    assert r.push(1000) == 1000


def test_sustained_jump_is_adopted():
    r = Ranger(window=5, outlier_jump_mm=500, outlier_persist=3)
    feed(r, [1000, 1000, 1000, 1000, 1000])
    assert r.push(200) == 1000
    assert r.push(205) == 1000
    assert r.push(210) == 205


def test_out_of_range_and_zero_are_no_target():
    r = Ranger(window=5, max_valid_mm=4000, no_target_clears=3)
    feed(r, [1000, 1000, 1000])
    assert r.push(5000) == 1000
    assert r.push(0) == 1000
    assert r.push(None) is None
    assert r.distance is None


def test_recovers_after_no_target():
    r = Ranger(window=5, no_target_clears=3)
    feed(r, [1000, 1000, 1000])
    feed(r, [None, None, None])
    assert r.push(700) == 700


def test_reports_settled_after_the_hold_period():
    d = StillnessDetector(still_mm=20, still_seconds=10.0)
    assert d.update(1000, 0.0) is False
    assert d.update(1005, 5.0) is False
    assert d.update(1010, 9.9) is False
    assert d.update(1008, 10.0) is True


def test_small_drift_does_not_reset_the_timer():
    d = StillnessDetector(still_mm=20, still_seconds=10.0)
    d.update(1000, 0.0)
    d.update(1019, 9.0)
    assert d.update(1001, 10.0) is True


def test_large_move_resets_the_timer():
    d = StillnessDetector(still_mm=20, still_seconds=10.0, wake_move_mm=50)
    d.update(1000, 0.0)
    assert d.update(500, 5.0) is False
    assert d.update(505, 14.0) is False
    assert d.update(500, 15.0) is True


def test_settled_latches_until_movement():
    d = StillnessDetector(still_mm=20, still_seconds=10.0, wake_move_mm=50)
    d.update(1000, 0.0)
    assert d.update(1000, 10.0) is True
    assert d.update(1000, 30.0) is True
    assert d.update(800, 31.0) is False


def test_none_reading_resets():
    d = StillnessDetector(still_seconds=10.0)
    d.update(1000, 0.0)
    assert d.update(None, 5.0) is False
    assert d.update(1000, 12.0) is False


def test_reset_clears_state():
    d = StillnessDetector(still_seconds=10.0)
    d.update(1000, 0.0)
    d.reset()
    assert d.update(1000, 10.0) is False


def test_settled_survives_drift_within_the_wake_threshold():
    d = StillnessDetector(still_mm=20, still_seconds=10.0, wake_move_mm=50)
    d.update(1000, 0.0)
    assert d.update(1000, 10.0) is True
    assert d.update(1030, 11.0) is True
    assert d.update(1060, 12.0) is False
