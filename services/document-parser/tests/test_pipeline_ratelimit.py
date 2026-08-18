"""Unit tests for pipeline/ratelimit.py — proactive CourtListener pacing (KD-83).

The limiter's whole purpose is that a call is paced *before* it is sent and that
running out of quota is a distinguishable outcome (BudgetExhausted) rather than
a silent miss. These tests drive a fake clock, so they run instantly.
"""

import pytest
from pipeline.ratelimit import (
    BudgetExhausted,
    NullRateLimiter,
    RateLimiter,
    get_courtlistener_limiter,
    reset_courtlistener_limiter,
)


class _FakeClock:
    """Monotonic stand-in whose sleeps advance time instead of blocking."""

    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _limiter(clock, **kw):
    kw.setdefault("min_interval_sec", 15.0)
    kw.setdefault("per_minute", 5)
    kw.setdefault("per_hour", 50)
    kw.setdefault("run_budget", 45)
    return RateLimiter(clock=clock, sleeper=clock.sleep, **kw)


def test_first_call_is_immediate():
    clock = _FakeClock()
    _limiter(clock).acquire()
    assert clock.slept == []


def test_consecutive_calls_are_spaced_by_min_interval():
    clock = _FakeClock()
    lim = _limiter(clock)
    for _ in range(3):
        lim.acquire()
    # Even spacing is the point — bursts of five are what poisoned the live runs.
    assert clock.slept == [15.0, 15.0]
    assert lim.spent == 3


def test_time_already_elapsed_is_credited():
    clock = _FakeClock()
    lim = _limiter(clock)
    lim.acquire()
    clock.now += 20.0          # caller did slow work between calls
    lim.acquire()
    assert clock.slept == []   # no artificial wait on top


def test_per_minute_window_holds_even_with_no_min_interval():
    clock = _FakeClock()
    lim = _limiter(clock, min_interval_sec=0.0)
    for _ in range(5):
        lim.acquire()
    lim.acquire()              # 6th within the same minute
    assert clock.slept and clock.slept[-1] == pytest.approx(60.0)


def test_run_budget_exhaustion_raises():
    clock = _FakeClock()
    lim = _limiter(clock, run_budget=3)
    for _ in range(3):
        lim.acquire()
    with pytest.raises(BudgetExhausted):
        lim.acquire()
    assert lim.remaining() == 0


def test_wait_beyond_max_wait_raises_instead_of_sleeping_an_hour():
    clock = _FakeClock()
    # Hourly window full, budget still nominally available: the limiter must
    # give up rather than park an unattended cron for the rest of the hour.
    lim = _limiter(clock, min_interval_sec=0.0, per_minute=0, per_hour=2,
                   run_budget=None, max_wait_sec=180.0)
    lim.acquire()
    lim.acquire()
    with pytest.raises(BudgetExhausted):
        lim.acquire()
    assert sum(clock.slept) < 180.0


def test_hourly_window_reopens_once_calls_age_out():
    clock = _FakeClock()
    lim = _limiter(clock, min_interval_sec=0.0, per_minute=0, per_hour=2, run_budget=None)
    lim.acquire()
    lim.acquire()
    clock.now += 3601.0
    lim.acquire()              # window has rolled over
    assert clock.slept == []


def test_penalize_charges_the_budget_and_cools_down():
    clock = _FakeClock()
    lim = _limiter(clock, min_interval_sec=0.0)
    lim.penalize(8.0)
    # A 429 consumed quota upstream, so it must cost the same as a real call.
    assert lim.spent == 1
    lim.acquire()
    assert clock.slept == [pytest.approx(8.0)]


def test_can_afford_reflects_remaining_budget():
    clock = _FakeClock()
    lim = _limiter(clock, run_budget=2)
    assert lim.can_afford(2)
    lim.acquire()
    assert not lim.can_afford(2)
    assert lim.can_afford(1)


def test_unbudgeted_limiter_can_always_afford():
    lim = _limiter(_FakeClock(), run_budget=None)
    assert lim.remaining() is None
    assert lim.can_afford(10_000)


def test_null_limiter_never_paces_or_raises():
    lim = NullRateLimiter()
    for _ in range(50):
        lim.acquire()
    assert lim.can_afford(1)


def test_singleton_is_shared_and_resettable():
    reset_courtlistener_limiter()
    try:
        a = get_courtlistener_limiter(run_budget=7)
        b = get_courtlistener_limiter(run_budget=99)   # overrides ignored once built
        # Discovery and retrieval MUST spend one budget, not one each.
        assert a is b
        assert a.remaining() == 7
    finally:
        reset_courtlistener_limiter()
