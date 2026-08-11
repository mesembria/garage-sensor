import gauge
from parkstate import ParkStateMachine


def step(m, distance, now, stop_mm=600, button_down=False, read_ok=True):
    return m.update(distance_mm=distance, stop_mm=stop_mm, now=now,
                    button_down=button_down, read_ok=read_ok)


def test_starts_idle():
    m = ParkStateMachine()
    assert m.state == gauge.IDLE


def test_no_target_is_idle():
    m = ParkStateMachine()
    assert step(m, None, 0.0) == gauge.IDLE


def test_target_beyond_wake_range_is_idle():
    m = ParkStateMachine(wake_mm=3000)
    assert step(m, 3500, 0.0) == gauge.IDLE


def test_target_inside_wake_range_approaches():
    m = ParkStateMachine(wake_mm=3000)
    assert step(m, 2000, 0.0) == gauge.APPROACHING


def test_reaching_the_stop_point_arrives():
    m = ParkStateMachine(arrive_tol_mm=30)
    assert step(m, 620, 0.0) == gauge.ARRIVED


def test_passing_the_stop_point_overshoots():
    m = ParkStateMachine(arrive_tol_mm=30, overshoot_mm=50)
    assert step(m, 500, 0.0) == gauge.OVERSHOOT


def test_arrived_holds_through_the_hysteresis_band():
    m = ParkStateMachine(arrive_tol_mm=30, arrive_release_mm=60)
    step(m, 620, 0.0)
    assert step(m, 650, 0.1) == gauge.ARRIVED
    assert step(m, 700, 0.2) == gauge.APPROACHING


def test_overshoot_recovers_to_arrived_when_backing_up():
    m = ParkStateMachine(arrive_tol_mm=30, overshoot_mm=50)
    step(m, 500, 0.0)
    assert step(m, 610, 0.1) == gauge.ARRIVED
