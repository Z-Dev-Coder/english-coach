"""The mistake bank: notice, count, resurface, retire.

Every correction the system produces — from writing feedback, from conversation
review — is funnelled through `record()`. That single entry point is what turns
scattered one-off corrections into a picture of what this learner actually keeps
getting wrong.
"""
from __future__ import annotations

import datetime as dt

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import Category, Mistake, MistakeOccurrence, build_key, normalize_category

# A mistake not seen for this long, having been seen at least twice, is treated
# as improving rather than active. Long enough that a quiet week does not clear
# a real habit; short enough that the bank reflects the present.
IMPROVING_AFTER_DAYS = 21
RESOLVED_AFTER_DAYS = 60

# Corrections shorter than this are usually punctuation noise from a small
# model ("Yes" → "Yes,"), not a language mistake worth tracking.
MIN_LENGTH = 3


def is_trackable(incorrect: str, correct: str) -> bool:
    """Filter out corrections that are not really mistakes.

    Small local models produce a lot of comma advice. Recording it would bury
    the genuine, repeated errors under noise, which defeats the purpose of the
    bank.
    """
    incorrect, correct = (incorrect or "").strip(), (correct or "").strip()
    if len(incorrect) < MIN_LENGTH or len(correct) < MIN_LENGTH:
        return False
    if incorrect.lower() == correct.lower():
        return False

    from apps.skills.similarity import normalize

    # If they differ only in punctuation or case, there is no lesson in it.
    return normalize(incorrect) != normalize(correct)


@transaction.atomic
def record(
    user,
    *,
    incorrect: str,
    correct: str,
    category: str = "",
    explanation: str = "",
    origin: str = MistakeOccurrence.Origin.WRITING,
    context: str = "",
) -> Mistake | None:
    """Log one correction. Returns None if it was not worth tracking."""
    if not is_trackable(incorrect, correct):
        return None

    incorrect, correct = incorrect.strip()[:300], correct.strip()[:300]
    mistake, created = Mistake.objects.get_or_create(
        user=user,
        normalized_key=build_key(incorrect, correct),
        defaults={
            "incorrect": incorrect,
            "correct": correct,
            "category": normalize_category(category),
            "explanation": explanation,
        },
    )

    mistake.occurrences += 1
    mistake.last_seen_at = timezone.now()
    mistake.status = Mistake.Status.ACTIVE  # It just happened again.
    if explanation and not mistake.explanation:
        mistake.explanation = explanation
    mistake.save(update_fields=["occurrences", "last_seen_at", "status", "explanation"])

    MistakeOccurrence.objects.create(
        mistake=mistake, origin=origin, context=context[:1000]
    )
    return mistake


def record_from_feedback(user, issues, *, origin: str, context: str = "") -> list[Mistake]:
    """Ingest a list of corrections from AI feedback.

    Accepts both shapes the system produces: writing feedback uses
    `original`/`correction`, conversation feedback uses `original`/`natural`.
    """
    recorded = []
    for issue in issues or []:
        if not isinstance(issue, dict):
            continue
        mistake = record(
            user,
            incorrect=issue.get("original", ""),
            correct=issue.get("correction") or issue.get("natural") or "",
            category=issue.get("category", ""),
            explanation=issue.get("explanation", ""),
            origin=origin,
            context=context,
        )
        if mistake:
            recorded.append(mistake)
    return recorded


def refresh_statuses(user, now: dt.datetime | None = None) -> int:
    """Age mistakes out of the active set.

    Silence is weak evidence of improvement, so this only ever downgrades
    status; the moment a mistake reappears, `record()` makes it active again.
    """
    now = now or timezone.now()
    improving = Mistake.objects.filter(
        user=user,
        status=Mistake.Status.ACTIVE,
        last_seen_at__lt=now - dt.timedelta(days=IMPROVING_AFTER_DAYS),
    ).update(status=Mistake.Status.IMPROVING)

    resolved = Mistake.objects.filter(
        user=user,
        status=Mistake.Status.IMPROVING,
        last_seen_at__lt=now - dt.timedelta(days=RESOLVED_AFTER_DAYS),
    ).update(status=Mistake.Status.RESOLVED)

    return improving + resolved


def persistent(user, limit: int = 5) -> list[Mistake]:
    """The mistakes worth putting in front of the learner today."""
    return list(
        Mistake.objects.filter(
            user=user, status=Mistake.Status.ACTIVE, occurrences__gte=2
        ).order_by("-occurrences", "-last_seen_at")[:limit]
    )


def recent(user, limit: int = 10) -> list[Mistake]:
    return list(Mistake.objects.filter(user=user).order_by("-last_seen_at")[:limit])


def weak_categories(user, limit: int = 3) -> list[str]:
    """Which kinds of mistake dominate, for the lesson generator."""
    rows = (
        Mistake.objects.filter(user=user, status=Mistake.Status.ACTIVE)
        .values("category")
        .annotate(total=Count("id"))
        .order_by("-total")[:limit]
    )
    return [row["category"] for row in rows]


def summary(user) -> dict:
    """Counts for the progress screen."""
    queryset = Mistake.objects.filter(user=user)
    by_category = {
        row["category"]: row["total"]
        for row in queryset.values("category").annotate(total=Count("id")).order_by("-total")
    }
    return {
        "total": queryset.count(),
        "active": queryset.filter(status=Mistake.Status.ACTIVE).count(),
        "improving": queryset.filter(status=Mistake.Status.IMPROVING).count(),
        "resolved": queryset.filter(status=Mistake.Status.RESOLVED).count(),
        "persistent": queryset.filter(
            status=Mistake.Status.ACTIVE, occurrences__gte=2
        ).count(),
        "by_category": by_category,
        "categories": [
            {"value": value, "label": label} for value, label in Category.choices
        ],
    }


def practice_items(user, limit: int = 5) -> list[dict]:
    """Turn persistent mistakes into something to actually practise.

    A mistake the learner keeps making should not merely be *listed* at them —
    the point of the bank is that it changes what they do next.
    """
    items = []
    for mistake in persistent(user, limit=limit):
        example = mistake.occurrence_log.exclude(context="").first()
        items.append(
            {
                "id": mistake.id,
                "category": mistake.category,
                "incorrect": mistake.incorrect,
                "correct": mistake.correct,
                "explanation": mistake.explanation,
                "occurrences": mistake.occurrences,
                "context": example.context if example else "",
                "task": f"Write two sentences using “{mistake.correct}” correctly.",
            }
        )
    return items


def mark_avoided(user, mistake_id: int) -> Mistake | None:
    """Record that the learner got this right when they could have got it wrong."""
    mistake = Mistake.objects.filter(user=user, pk=mistake_id).first()
    if not mistake:
        return None
    mistake.times_avoided += 1
    # Three clean runs is decent evidence the habit is going.
    if mistake.times_avoided >= 3 and mistake.status == Mistake.Status.ACTIVE:
        mistake.status = Mistake.Status.IMPROVING
    mistake.save(update_fields=["times_avoided", "status"])
    return mistake
