from ranging import Ranger, median


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
