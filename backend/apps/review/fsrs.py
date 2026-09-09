"""FSRS-5 spaced repetition scheduling.

Pure functions over a small dataclass: no Django, no database, no clock. That
makes the algorithm testable in isolation and keeps the scheduling maths in one
auditable place.

FSRS (Free Spaced Repetition Scheduler) models each item with two numbers:

  stability  - days until recall probability falls to 90%
  difficulty - 1..10, how hard this item is for this learner

Both are updated after every review from the grade given and how long the item
had actually been waiting. Compared with SM-2 (Anki's old default), FSRS uses a
memory model fitted to millions of real reviews, so intervals adapt to the
individual item instead of applying fixed multipliers.

We implement it directly rather than adding the `fsrs` package: the algorithm is
about 120 lines, and vendoring it keeps the dependency surface small and the
behaviour pinned. The default parameters below are the published FSRS-5 defaults.

Reference: https://github.com/open-spaced-repetition/fsrs4anki/wiki
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum

# Published FSRS-5 default weights. Optimising these per learner needs a review
# history of a few hundred items; until then the defaults are the right choice.
DEFAULT_WEIGHTS: tuple[float, ...] = (
    0.40255, 1.18385, 3.173, 15.69105,   # w0-w3:  initial stability per grade
    7.1949, 0.5345,                       # w4-w5:  initial difficulty
    1.4604, 0.0046,                       # w6-w7:  difficulty update, mean reversion
    1.54575, 0.1192, 1.01925,             # w8-w10: stability on success
    1.9395, 0.11, 0.29605, 2.2698,        # w11-w14: stability after a lapse
    0.2315, 2.9898,                       # w15-w16: hard penalty, easy bonus
    0.51655, 0.6621,                      # w17-w18: same-day review
)

# The forgetting curve: R(t) = (1 + FACTOR * t / S) ** DECAY
DECAY = -0.5
FACTOR = 19 / 81  # = 0.9 ** (1 / DECAY) - 1, so interval == stability at R=0.9

MIN_STABILITY = 0.01
MAX_INTERVAL_DAYS = 3650  # ten years; beyond this the schedule is meaningless
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0


class Rating(IntEnum):
    """How the review went. These are the four standard FSRS grades."""

    AGAIN = 1  # failed to recall
    HARD = 2   # recalled, but with real effort
    GOOD = 3   # recalled correctly
    EASY = 4   # recalled instantly


@dataclass(frozen=True)
class MemoryState:
    """An item's memory model. `None` stability means it has never been reviewed."""

    stability: float | None = None
    difficulty: float | None = None

    @property
    def is_new(self) -> bool:
        return self.stability is None or self.difficulty is None


@dataclass(frozen=True)
class SchedulingResult:
    state: MemoryState
    interval_days: int
    retrievability_at_review: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def retrievability(elapsed_days: float, stability: float) -> float:
    """Probability of recalling the item right now, given how long it has waited.

    Returns 1.0 for a stability of zero or a negative elapsed time, so callers
    never have to special-case freshly created items.
    """
    if stability <= 0 or elapsed_days <= 0:
        return 1.0
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def interval_for(stability: float, desired_retention: float = 0.9) -> int:
    """Days until recall probability decays to `desired_retention`.

    Lowering desired_retention lengthens intervals and trades accuracy for
    volume; 0.9 is the FSRS default and a sensible target for language items.
    """
    if stability <= 0:
        return 1
    days = (stability / FACTOR) * (desired_retention ** (1 / DECAY) - 1)
    return int(_clamp(round(days), 1, MAX_INTERVAL_DAYS))


def initial_stability(rating: Rating, w: tuple[float, ...] = DEFAULT_WEIGHTS) -> float:
    return max(w[rating - 1], MIN_STABILITY)


def initial_difficulty(rating: Rating, w: tuple[float, ...] = DEFAULT_WEIGHTS) -> float:
    difficulty = w[4] - math.exp(w[5] * (rating - 1)) + 1
    return _clamp(difficulty, MIN_DIFFICULTY, MAX_DIFFICULTY)


def next_difficulty(
    difficulty: float, rating: Rating, w: tuple[float, ...] = DEFAULT_WEIGHTS
) -> float:
    """Update difficulty, with damping and mean reversion.

    Damping makes changes smaller as difficulty approaches its bounds; mean
    reversion pulls difficulty slowly back toward the "easy" baseline so a run
    of bad days does not permanently mark an item as impossible.
    """
    delta = -w[6] * (rating - 3)
    damped = difficulty + delta * (10 - difficulty) / 9
    reverted = w[7] * initial_difficulty(Rating.EASY, w) + (1 - w[7]) * damped
    return _clamp(reverted, MIN_DIFFICULTY, MAX_DIFFICULTY)


def stability_after_success(
    stability: float,
    difficulty: float,
    retention: float,
    rating: Rating,
    w: tuple[float, ...] = DEFAULT_WEIGHTS,
) -> float:
    """Growth is largest when the item was nearly forgotten but still recalled.

    That is the retrieval-practice effect: a review that was easy because it was
    due yesterday teaches you very little.
    """
    hard_penalty = w[15] if rating == Rating.HARD else 1.0
    easy_bonus = w[16] if rating == Rating.EASY else 1.0
    growth = (
        math.exp(w[8])
        * (11 - difficulty)
        * (stability ** -w[9])
        * (math.exp(w[10] * (1 - retention)) - 1)
        * hard_penalty
        * easy_bonus
    )
    return max(stability * (1 + growth), MIN_STABILITY)


def stability_after_lapse(
    stability: float,
    difficulty: float,
    retention: float,
    w: tuple[float, ...] = DEFAULT_WEIGHTS,
) -> float:
    """Stability after forgetting. Never above the pre-lapse value.

    FSRS's raw formula can exceed the previous stability for very low-stability
    items; clamping keeps the invariant that forgetting something never makes
    its schedule longer, which would be indefensible to a learner.
    """
    lapsed = (
        w[11]
        * (difficulty ** -w[12])
        * ((stability + 1) ** w[13] - 1)
        * math.exp(w[14] * (1 - retention))
    )
    return _clamp(lapsed, MIN_STABILITY, stability)


def stability_same_day(
    stability: float, rating: Rating, w: tuple[float, ...] = DEFAULT_WEIGHTS
) -> float:
    """Repeating an item on the day it was already reviewed.

    Handled separately because the normal formula assumes measurable elapsed
    time; without this, drilling an item repeatedly would inflate its schedule.
    """
    return max(stability * math.exp(w[17] * (rating - 3 + w[18])), MIN_STABILITY)


def review(
    state: MemoryState,
    rating: Rating,
    elapsed_days: float,
    *,
    desired_retention: float = 0.9,
    weights: tuple[float, ...] = DEFAULT_WEIGHTS,
) -> SchedulingResult:
    """Apply one review and return the new memory state plus the next interval.

    `elapsed_days` is the real time since the last review, not the scheduled
    interval — reviewing late is information, and FSRS uses it.
    """
    rating = Rating(rating)

    if state.is_new:
        stability = initial_stability(rating, weights)
        difficulty = initial_difficulty(rating, weights)
        return SchedulingResult(
            state=MemoryState(stability, difficulty),
            interval_days=interval_for(stability, desired_retention),
            retrievability_at_review=1.0,
        )

    retention = retrievability(elapsed_days, state.stability)
    difficulty = next_difficulty(state.difficulty, rating, weights)

    if elapsed_days < 1:
        stability = stability_same_day(state.stability, rating, weights)
    elif rating == Rating.AGAIN:
        stability = stability_after_lapse(state.stability, difficulty, retention, weights)
    else:
        stability = stability_after_success(
            state.stability, difficulty, retention, rating, weights
        )

    return SchedulingResult(
        state=MemoryState(stability, difficulty),
        interval_days=interval_for(stability, desired_retention),
        retrievability_at_review=retention,
    )
