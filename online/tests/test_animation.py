import math

from pet.animation import (
    breath_scale,
    sway_angle,
    BlinkScheduler,
    BLINK_DURATION,
)


def test_breath_scale_stays_in_range():
    for t in [0.0, 0.5, 1.0, 2.0, 3.99, 4.0, 7.3]:
        assert 1.0 <= breath_scale(t) <= 1.02


def test_breath_scale_is_periodic():
    assert math.isclose(breath_scale(1.0), breath_scale(5.0), abs_tol=1e-9)
    assert math.isclose(breath_scale(2.5), breath_scale(6.5), abs_tol=1e-9)


def test_breath_scale_peaks_at_half_period():
    assert math.isclose(breath_scale(2.0), 1.02, abs_tol=1e-9)
    assert math.isclose(breath_scale(0.0), 1.0, abs_tol=1e-9)


def test_sway_angle_stays_in_range():
    for t in [0.0, 0.5, 1.0, 3.0, 6.0, 9.9]:
        assert -1.5 <= sway_angle(t) <= 1.5


def test_sway_angle_zero_crossing():
    assert math.isclose(sway_angle(0.0), 0.0, abs_tol=1e-9)
    assert math.isclose(sway_angle(3.0), 0.0, abs_tol=1e-9)


def test_blink_not_blinking_initially():
    sched = BlinkScheduler(seed=42)
    assert sched.tick(0.0) is False


def test_blink_triggers_eventually():
    sched = BlinkScheduler(seed=42)
    t = 0.0
    saw_blink = False
    while t < 100.0:
        if sched.tick(t):
            saw_blink = True
            break
        t += 0.01
    assert saw_blink


def test_blink_duration_around_150ms():
    sched = BlinkScheduler(seed=42)
    t = 0.0
    while not sched.tick(t) and t < 100.0:
        t += 0.001
    start = t
    while sched.tick(t) and t < start + 1.0:
        t += 0.001
    duration = t - start
    assert 0.10 <= duration <= 0.20


def test_force_blink():
    sched = BlinkScheduler(seed=42)
    assert sched.tick(0.0) is False
    sched.force_blink(0.0)
    assert sched.tick(0.0) is True
