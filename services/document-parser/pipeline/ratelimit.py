"""Proactive rate limiting for the CourtListener REST API (KD-83).

Why this exists
---------------
CourtListener's authenticated REST tier allows roughly **5 requests/minute and
50/hour** — a quota that *discovery* (``pipeline/discovery.py``) and *Form 204
retrieval* (``pipeline/retrieval.py``) share, because both talk to the same
account.  Both modules already back off **reactively** on a 429, but that cannot
help once the quota is spent: the retries 429 as well.  The 2026-08-17 intake run
made that concrete — **493 x HTTP 429 and zero successful REST calls**, with every
case logged as "RECAP: no archived Form 204".  Those were *false misses*,
indistinguishable in the logs from a genuine "not archived".

So the limiter here is **proactive**: it paces calls *before* they are sent, and
when the run's budget is spent it raises :class:`BudgetExhausted` rather than
issuing a request that is certain to 429.  A paced probe answered the whole
coverage question in 6 calls, so pacing is not merely defensive — it is the only
mode in which a retrieval result means anything.

Design notes
------------
- **Even spacing, not bursts.** ``min_interval_sec`` (default 15s) is the setting
  proven to work against the live API.  A pure 5-per-60s window would allow a
  burst of five back-to-back calls, which is what poisoned the earlier runs.
  The rolling windows are kept as belt-and-braces behind the spacing.
- **A run budget, deliberately small.** ``run_budget`` caps total calls per
  process so an unattended cron cannot sit for hours creeping through an hourly
  window.  Exhaustion is a *first-class outcome* the caller must handle (hold the
  watermark, report honestly), never a silent miss.
- **``max_wait_sec``** stops ``acquire`` from sleeping out a full hourly window;
  a wait longer than this raises ``BudgetExhausted`` too.
- **Off-budget calls.** PDF downloads from ``storage.courtlistener.com`` are
  unauthenticated and do NOT count against the REST quota — they must not be
  routed through this limiter.

``clock``/``sleeper`` are injectable so tests run instantly.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Live-verified limits for the authenticated REST tier (2026-08-16 probe).
DEFAULT_MIN_INTERVAL_SEC = 15.0
DEFAULT_PER_MINUTE = 5
DEFAULT_PER_HOUR = 50
# Below the hourly ceiling: leaves headroom for a retry or an ad-hoc probe, and
# bounds a run at roughly 45 x 15s ~ 11 minutes of wall clock.
DEFAULT_RUN_BUDGET = 45
DEFAULT_MAX_WAIT_SEC = 180.0


class BudgetExhausted(RuntimeError):
    """The run's CourtListener call budget is spent.

    Callers MUST treat this as "unknown", not "not found": stop making calls,
    hold any watermark over the un-attempted work, and say so in the run report.
    """


class RateLimiter:
    """Paces calls to a quota'd API; raises BudgetExhausted instead of 429ing.

    Thread-safe (the pipeline is single-threaded today, but the limiter is a
    process-wide singleton and cheap to lock).
    """

    def __init__(
        self,
        *,
        name: str = "courtlistener",
        min_interval_sec: float = DEFAULT_MIN_INTERVAL_SEC,
        per_minute: int = DEFAULT_PER_MINUTE,
        per_hour: int = DEFAULT_PER_HOUR,
        run_budget: int | None = DEFAULT_RUN_BUDGET,
        max_wait_sec: float = DEFAULT_MAX_WAIT_SEC,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._name = name
        self._min_interval = max(0.0, min_interval_sec)
        self._windows: list[tuple[float, int, deque[float]]] = []
        if per_minute > 0:
            self._windows.append((60.0, per_minute, deque()))
        if per_hour > 0:
            self._windows.append((3600.0, per_hour, deque()))
        self._run_budget = run_budget
        self._max_wait = max_wait_sec
        self._clock = clock
        self._sleep = sleeper
        self._lock = threading.Lock()
        self._spent = 0
        self._last_call: float | None = None
        self._cooldown_until: float = 0.0

    # -- introspection -------------------------------------------------------
    @property
    def spent(self) -> int:
        return self._spent

    def remaining(self) -> int | None:
        """Calls left in the run budget, or None when unbudgeted."""
        if self._run_budget is None:
            return None
        return max(0, self._run_budget - self._spent)

    def can_afford(self, calls: int) -> bool:
        """True if ``calls`` more requests fit in the run budget.

        Lets a caller skip an *optional* extra step (e.g. retrieval's
        docket-entries walk) rather than spend the last of the budget on it.
        """
        remaining = self.remaining()
        return remaining is None or remaining >= calls

    # -- the pacing primitive ------------------------------------------------
    def acquire(self) -> None:
        """Block until a call may be made, then record it.

        Raises :class:`BudgetExhausted` when the run budget is spent or when the
        required wait exceeds ``max_wait_sec`` (i.e. an hourly window is full).
        """
        with self._lock:
            while True:
                if self._run_budget is not None and self._spent >= self._run_budget:
                    raise BudgetExhausted(
                        f"{self._name}: run budget of {self._run_budget} calls is spent"
                    )
                now = self._clock()
                wait = self._wait_needed(now)
                if wait <= 0:
                    self._record(now)
                    return
                if wait > self._max_wait:
                    raise BudgetExhausted(
                        f"{self._name}: next call would wait {wait:.0f}s "
                        f"(> {self._max_wait:.0f}s cap) — quota window is full"
                    )
                logger.debug("%s: pacing — sleeping %.1fs before next call", self._name, wait)
                self._sleep(wait)

    def penalize(self, seconds: float) -> None:
        """Record a 429: hold off for ``seconds`` before the next call.

        This does NOT charge the budget again: ``acquire`` already recorded the
        call before it was sent, and a rejected request must cost the same as a
        successful one — charging twice would exhaust the budget in half the
        requests and report exhaustion long before it happened.
        """
        with self._lock:
            now = self._clock()
            self._cooldown_until = max(self._cooldown_until, now + max(0.0, seconds))
            logger.warning("%s: 429 — cooling down %.0fs (spent %d)",
                           self._name, seconds, self._spent)

    # -- internals -----------------------------------------------------------
    def _wait_needed(self, now: float) -> float:
        waits = [self._cooldown_until - now]
        if self._last_call is not None:
            waits.append(self._last_call + self._min_interval - now)
        for span, limit, stamps in self._windows:
            while stamps and stamps[0] <= now - span:
                stamps.popleft()
            if len(stamps) >= limit:
                waits.append(stamps[0] + span - now)
        return max(waits) if waits else 0.0

    def _record(self, now: float) -> None:
        for _span, _limit, stamps in self._windows:
            stamps.append(now)
        self._last_call = now
        self._spent += 1


class NullRateLimiter(RateLimiter):
    """Unpaced, unbudgeted limiter — for tests and one-off scripts."""

    def __init__(self) -> None:
        super().__init__(name="null", min_interval_sec=0.0, per_minute=0,
                         per_hour=0, run_budget=None)


_limiter: RateLimiter | None = None


def get_courtlistener_limiter(**overrides) -> RateLimiter:
    """Process-wide limiter shared by discovery and retrieval.

    Both stages spend the SAME account quota, so they must share one instance —
    a per-module limiter would let discovery's pages and retrieval's lookups
    each believe they had a full budget.
    """
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(**overrides)
    return _limiter


def reset_courtlistener_limiter() -> None:
    """Drop the singleton (tests, and any long-lived process starting a new run)."""
    global _limiter
    _limiter = None
