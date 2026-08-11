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


def test_backing_out_of_overshoot_returns_to_arrived_not_approaching():
    m = ParkStateMachine(arrive_tol_mm=30, arrive_release_mm=60, overshoot_mm=50)
    step(m, 545, 0.0)
    assert m.state == gauge.OVERSHOOT
    assert step(m, 551, 0.1) == gauge.ARRIVED


def test_overshoot_still_triggers_from_approaching():
    m = ParkStateMachine(arrive_tol_mm=30, arrive_release_mm=60, overshoot_mm=50)
    assert step(m, 2000, 0.0) == gauge.APPROACHING
    assert step(m, 500, 0.1) == gauge.OVERSHOOT


def test_settles_after_holding_still():
    m = ParkStateMachine(still_seconds=10.0, arrive_tol_mm=30)
    assert step(m, 620, 0.0) == gauge.ARRIVED
    assert step(m, 620, 5.0) == gauge.ARRIVED
    assert step(m, 620, 10.0) == gauge.SETTLED


def test_settled_persists_while_parked():
    m = ParkStateMachine(still_seconds=10.0)
    step(m, 620, 0.0)
    step(m, 620, 10.0)
    assert step(m, 621, 600.0) == gauge.SETTLED


def test_movement_wakes_from_settled():
    m = ParkStateMachine(still_seconds=10.0, wake_move_mm=50)
    step(m, 620, 0.0)
    assert step(m, 620, 10.0) == gauge.SETTLED
    assert step(m, 1500, 11.0) == gauge.APPROACHING


def test_settles_mid_approach_too():
    m = ParkStateMachine(still_seconds=10.0)
    assert step(m, 2000, 0.0) == gauge.APPROACHING
    assert step(m, 2000, 10.0) == gauge.SETTLED


def test_leaving_range_returns_to_idle_not_settled():
    m = ParkStateMachine(still_seconds=10.0)
    step(m, 620, 0.0)
    step(m, 620, 10.0)
    assert step(m, None, 11.0) == gauge.IDLE


def test_waking_from_settled_inside_the_release_band_returns_to_arrived():
    m = ParkStateMachine(arrive_tol_mm=30, arrive_release_mm=60,
                         wake_move_mm=50, still_seconds=10.0)
    assert step(m, 600, 0.0) == gauge.ARRIVED
    assert step(m, 600, 10.0) == gauge.SETTLED
    assert step(m, 655, 11.0) == gauge.ARRIVED
    assert step(m, 655, 12.0) == gauge.ARRIVED


def test_repeated_read_failures_enter_fault():
    m = ParkStateMachine(max_consec_fails=5)
    for i in range(4):
        assert step(m, None, i * 0.1, read_ok=False) == gauge.IDLE
    assert step(m, None, 0.5, read_ok=False) == gauge.FAULT


def test_fault_clears_after_good_reads():
    m = ParkStateMachine(max_consec_fails=2, recover_good_reads=3)
    step(m, None, 0.0, read_ok=False)
    assert step(m, None, 0.1, read_ok=False) == gauge.FAULT
    assert step(m, 2000, 0.2) == gauge.FAULT
    assert step(m, 2000, 0.3) == gauge.FAULT
    assert step(m, 2000, 0.4) == gauge.APPROACHING


def test_fault_outranks_parking_states():
    m = ParkStateMachine(max_consec_fails=1)
    assert step(m, 620, 0.0, read_ok=False) == gauge.FAULT


def test_uncalibrated_when_no_stop_distance_stored():
    m = ParkStateMachine()
    assert step(m, 2000, 0.0, stop_mm=None) == gauge.UNCALIBRATED


def test_holding_the_button_calibrates():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    assert step(m, 850, 0.0, button_down=True) == gauge.APPROACHING
    assert step(m, 850, 1.0, button_down=True) == gauge.APPROACHING
    assert step(m, 850, 2.0, button_down=True) == gauge.CALIBRATE
    assert m.calibration_captured == 850


def test_calibration_is_captured_only_once():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, 850, 0.0, button_down=True)
    step(m, 850, 2.0, button_down=True)
    assert m.calibration_captured == 850
    step(m, 850, 2.1, button_down=True)
    assert m.calibration_captured is None


def test_releasing_the_button_resets_the_hold():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, 850, 0.0, button_down=True)
    step(m, 850, 1.0, button_down=False)
    assert step(m, 850, 2.5, button_down=True) == gauge.APPROACHING


def test_calibration_works_while_uncalibrated():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, 850, 0.0, stop_mm=None, button_down=True)
    assert step(m, 850, 2.0, stop_mm=None, button_down=True) == gauge.CALIBRATE
    assert m.calibration_captured == 850


def test_no_calibration_without_a_valid_distance():
    m = ParkStateMachine(calibrate_hold_s=2.0)
    step(m, None, 0.0, button_down=True)
    assert step(m, None, 2.0, button_down=True) == gauge.IDLE
    assert m.calibration_captured is None
