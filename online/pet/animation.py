"""Animation logic for the cat desktop pet.

All timing constants live here so the animation feel can be tuned in one
place without touching the GUI layer.
"""
import math
import random

BREATH_PERIOD = 4.0        # seconds per full breath cycle
BREATH_AMPLITUDE = 0.02    # scale amplitude (1.0 -> 1.02)
SWAY_PERIOD = 6.0          # seconds per full sway cycle
SWAY_AMPLITUDE = 1.5       # degrees of rotation
BLINK_MIN_INTERVAL = 3.0   # seconds
BLINK_MAX_INTERVAL = 7.0   # seconds
BLINK_DURATION = 0.15      # seconds eyes stay closed


def breath_scale(t: float) -> float:
    """Return the breath scale factor at time t (seconds), in [1.0, 1.02]."""
    phase = (t % BREATH_PERIOD) / BREATH_PERIOD
    return 1.0 + BREATH_AMPLITUDE * (0.5 - 0.5 * math.cos(2 * math.pi * phase))


def sway_angle(t: float) -> float:
    """Return the sway rotation angle at time t (seconds), in degrees."""
    return SWAY_AMPLITUDE * math.sin(2 * math.pi * t / SWAY_PERIOD)


class BlinkScheduler:
    """Deterministic blink scheduling.

    A blink triggers every BLINK_MIN_INTERVAL..BLINK_MAX_INTERVAL seconds
    (uniformly random) and keeps the eyes closed for BLINK_DURATION seconds.
    """

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._next_blink = self._rng.uniform(BLINK_MIN_INTERVAL, BLINK_MAX_INTERVAL)
        self._blink_until = -1.0

    def tick(self, now: float) -> bool:
        """Advance to `now` (seconds since start); return whether eyes are closed."""
        if now >= self._next_blink and now >= self._blink_until:
            self._blink_until = now + BLINK_DURATION
            self._next_blink = now + self._rng.uniform(
                BLINK_MIN_INTERVAL, BLINK_MAX_INTERVAL
            )
        return now < self._blink_until

    def force_blink(self, now: float) -> None:
        """Close the eyes immediately for one blink duration."""
        self._blink_until = now + BLINK_DURATION
