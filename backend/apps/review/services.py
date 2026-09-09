"""The review engine: what to study now, and what happens when it is answered.

No AI and no network — the queue is a database query plus scheduling maths, so
review works whether or not a model is running, and is fully deterministic
under test.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.vocabulary.models import Expression, MasteryState, VocabularyProgress

from .fsrs import MemoryState, Rating, review as fsrs_review
from .models import PRODUCTIVE_EXERCISES, ExerciseType, Review

# How many unseen expressions to introduce per day. Introducing too many at once
# is the classic way to build a review backlog that collapses a fortnight later.
DEFAULT_NEW_PER_DAY = 8

# Rough seconds per item, used to turn the planner's review minutes into a
# queue length. Deliberately generous: a queue the learner finishes is better
# than one they abandon.
SECONDS_PER_ITEM = 12


@dataclass
class QueueItem:
    progress: VocabularyProgress
    exercise: str

    @property
    def expression(self) -> Expression:
        return self.progress.expression


def due_queryset(user, now: dt.datetime | None = None):
    """Items whose scheduled time has arrived."""
    now = now or timezone.now()
    return (
        VocabularyProgress.objects.filter(user=user, due_at__lte=now)
        .exclude(state=MasteryState.NEW)
        .select_related("expression")
    )


def new_queryset(user):
    return VocabularyProgress.objects.filter(
        user=user, state=MasteryState.NEW
    ).select_related("expression")


def due_count(user, now: dt.datetime | None = None) -> int:
    return due_queryset(user, now).count()


def choose_exercise(progress: VocabularyProgress) -> str:
    """Pick how to test this item, based on how well it is known.

    The progression is recognition → recall → production. Weak items are pushed
    back to production rather than being allowed to sit in easy recognition,
    because recognising an item you keep forgetting proves very little.
    """
    state = progress.state
    if state == MasteryState.NEW:
        return ExerciseType.MEET
    if state == MasteryState.LEARNING:
        return ExerciseType.RECALL
    if state == MasteryState.WEAK:
        return ExerciseType.CLOZE
    if state == MasteryState.MASTERED:
        return ExerciseType.USE
    # REVIEW: alternate cloze and production so it never becomes one rote motion.
    return ExerciseType.CLOZE if progress.reps % 2 == 0 else ExerciseType.PRODUCE


def build_queue(
    user,
    *,
    limit: int | None = None,
    minutes: int | None = None,
    new_per_day: int = DEFAULT_NEW_PER_DAY,
    now: dt.datetime | None = None,
) -> list[QueueItem]:
    """Today's review queue: overdue items first, then a capped number of new ones.

    Ordering rationale:

    1. Due items come first and are sorted by how overdue they are. Leaving an
       item that is three weeks late while introducing new material is how
       learners lose vocabulary they already paid for.
    2. New items are capped per day and appended, so a heavy review day
       naturally introduces less new material.
    3. New items are interleaved into the tail rather than dumped in a block,
       which keeps the session from ending in a wall of unfamiliar words.
    """
    now = now or timezone.now()

    if limit is None:
        limit = max(5, round((minutes or 5) * 60 / SECONDS_PER_ITEM))

    due = list(due_queryset(user, now).order_by("due_at")[:limit])

    remaining = max(0, limit - len(due))
    introduced_today = Review.objects.filter(
        user=user, reviewed_at__date=timezone.localdate(), progress__reps=1
    ).count()
    new_allowance = max(0, min(remaining, new_per_day - introduced_today))
    new_items = list(new_queryset(user).order_by("first_seen_at", "id")[:new_allowance])

    items = [QueueItem(progress, choose_exercise(progress)) for progress in due]
    new_queue = [QueueItem(progress, ExerciseType.MEET) for progress in new_items]

    # Interleave the new items evenly through the back half of the session.
    if new_queue and items:
        step = max(1, len(items) // (len(new_queue) + 1))
        for offset, item in enumerate(new_queue):
            items.insert(min(len(items), (offset + 1) * step + offset), item)
    else:
        items.extend(new_queue)

    return items


@transaction.atomic
def answer(
    progress: VocabularyProgress,
    rating: int,
    *,
    exercise: str = ExerciseType.RECALL,
    duration_ms: int = 0,
    now: dt.datetime | None = None,
) -> Review:
    """Record a review, advance the FSRS state, and reschedule the item.

    Runs in a transaction: the log entry and the updated schedule must agree, or
    the learner's history stops explaining their queue.
    """
    now = now or timezone.now()
    rating = Rating(rating)

    elapsed_days = (
        (now - progress.last_reviewed_at).total_seconds() / 86400
        if progress.last_reviewed_at
        else 0.0
    )

    before = MemoryState(progress.stability, progress.difficulty)
    result = fsrs_review(before, rating, elapsed_days)

    log = Review(
        user_id=progress.user_id,
        progress=progress,
        rating=int(rating),
        exercise=exercise,
        state_before=progress.state,
        stability_before=progress.stability,
        difficulty_before=progress.difficulty,
        stability_after=result.state.stability,
        difficulty_after=result.state.difficulty,
        elapsed_days=elapsed_days,
        scheduled_days=result.interval_days,
        retrievability=result.retrievability_at_review,
        duration_ms=duration_ms,
    )

    progress.stability = result.state.stability
    progress.difficulty = result.state.difficulty
    progress.reps += 1
    if rating == Rating.AGAIN:
        progress.lapses += 1
    elif exercise in PRODUCTIVE_EXERCISES:
        progress.successful_productions += 1
    progress.last_reviewed_at = now
    progress.last_interval_days = result.interval_days
    progress.due_at = now + dt.timedelta(days=result.interval_days)
    progress.state = progress.recompute_state()
    progress.save()

    log.save()
    return log


def add_to_learning(user, expression: Expression, *, now: dt.datetime | None = None):
    """Start tracking an expression for a learner. Idempotent."""
    now = now or timezone.now()
    progress, _created = VocabularyProgress.objects.get_or_create(
        user=user, expression=expression, defaults={"due_at": now}
    )
    return progress


def stats(user, now: dt.datetime | None = None) -> dict:
    """Counts for the dashboard and the review screen."""
    now = now or timezone.now()
    counts = {state: 0 for state, _label in MasteryState.choices}
    for row in VocabularyProgress.objects.filter(user=user).values("state"):
        counts[row["state"]] = counts.get(row["state"], 0) + 1

    reviews = Review.objects.filter(user=user)
    total = reviews.count()
    successful = reviews.filter(rating__gt=1).count()

    return {
        "due_now": due_count(user, now),
        "total_tracked": sum(counts.values()),
        "by_state": counts,
        "reviews_all_time": total,
        "success_rate": round(successful / total, 3) if total else None,
        "reviewed_today": reviews.filter(reviewed_at__date=timezone.localdate()).count(),
    }


def forecast(user, days: int = 7, now: dt.datetime | None = None) -> list[dict]:
    """How many items fall due on each of the next `days` days.

    Lets the learner see a spike coming instead of being ambushed by it.
    """
    now = now or timezone.now()
    today = timezone.localdate()
    rows = []
    for offset in range(days):
        day = today + dt.timedelta(days=offset)
        window = Q(due_at__date=day)
        if offset == 0:
            # Day zero also carries everything already overdue.
            window = window | Q(due_at__lt=now)
        rows.append(
            {
                "date": day,
                "count": VocabularyProgress.objects.filter(user=user)
                .exclude(state=MasteryState.NEW)
                .filter(window)
                .count(),
            }
        )
    return rows
