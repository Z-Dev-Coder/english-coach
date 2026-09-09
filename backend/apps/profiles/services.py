"""Business logic for learner progress, streaks and the daily plan.

Everything here is a plain function over the database: no AI calls, no HTTP.
That keeps the planner fully unit-testable and means the app still produces a
sensible daily plan when Ollama is not running.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass

from django.db.models import Sum
from django.utils import timezone

from .constants import SCHEDULABLE_SKILLS
from .models import LearnerProfile, SkillProgress, StudySession

# --- Planner weights -------------------------------------------------------
# Documented rather than magic (master prompt section 48). Each schedulable
# skill gets a share of the day proportional to: a floor (so nothing is ever
# dropped entirely, which preserves interleaving), plus measured weakness, plus
# explicit learner priority, plus how long it has been neglected.
BASE_SHARE = 1.0          # every skill always gets at least this weight
WEAKNESS_WEIGHT = 2.5     # how hard low scores pull minutes toward a skill
PRIORITY_WEIGHT = 1.0     # the learner's own stated priorities
STALENESS_WEIGHT = 0.8    # skills untouched for a while resurface
STALENESS_DAYS = 7        # days after which a skill counts as fully stale
REVIEW_MINUTES_FLOOR = 3  # review always happens, even on a light day
REVIEW_SHARE = 0.17       # about 5 of 30 minutes by default


@dataclass
class PlanBlock:
    skill: str
    minutes: int
    reason: str


def _staleness(progress: SkillProgress, now: dt.datetime) -> float:
    """0.0 = practiced just now, 1.0 = untouched for STALENESS_DAYS or never."""
    if progress.last_practiced_at is None:
        return 1.0
    days = (now - progress.last_practiced_at).total_seconds() / 86400
    return min(1.0, days / STALENESS_DAYS)


def skill_weights(user, now: dt.datetime | None = None) -> dict[str, float]:
    """Relative pull of each schedulable skill on today's minutes."""
    now = now or timezone.now()
    profile = LearnerProfile.objects.get(user=user)
    priorities = set(profile.priority_skills or [])
    rows = {sp.skill: sp for sp in user.skill_progress.all()}

    weights: dict[str, float] = {}
    for skill in SCHEDULABLE_SKILLS:
        sp = rows.get(skill)
        score = sp.score if sp else 50.0
        weakness = max(0.0, (100.0 - score) / 100.0)
        weights[skill] = (
            BASE_SHARE
            + WEAKNESS_WEIGHT * weakness
            + (PRIORITY_WEIGHT if skill in priorities else 0.0)
            + STALENESS_WEIGHT * (_staleness(sp, now) if sp else 1.0)
        )
    return weights


def build_daily_plan(
    user, minutes: int | None = None, now: dt.datetime | None = None
) -> list[PlanBlock]:
    """Allocate today's minutes across review plus the schedulable skills.

    Uses largest-remainder allocation so the blocks always sum to exactly the
    requested minutes: no drift, and no zero-minute blocks that would render as
    empty cards in the UI.
    """
    profile = LearnerProfile.objects.get(user=user)
    total = minutes or profile.daily_minutes

    review_minutes = max(REVIEW_MINUTES_FLOOR, round(total * REVIEW_SHARE))
    remaining = max(0, total - review_minutes)

    weights = skill_weights(user, now=now)
    weight_sum = sum(weights.values()) or 1.0

    exact = {skill: remaining * w / weight_sum for skill, w in weights.items()}
    floors = {skill: int(value) for skill, value in exact.items()}
    leftover = remaining - sum(floors.values())
    for skill, _value in sorted(exact.items(), key=lambda kv: kv[1] - int(kv[1]), reverse=True):
        if leftover <= 0:
            break
        floors[skill] += 1
        leftover -= 1

    rows = {sp.skill: sp for sp in user.skill_progress.all()}
    priorities = set(profile.priority_skills or [])
    blocks = [PlanBlock("review", review_minutes, "Spaced repetition is due first every day.")]
    for skill, mins in sorted(floors.items(), key=lambda kv: kv[1], reverse=True):
        if mins <= 0:
            continue
        sp = rows.get(skill)
        if sp and sp.is_weak:
            reason = f"{skill.title()} is one of your weakest areas ({sp.score:.0f}/100)."
        elif skill in priorities:
            reason = f"You asked to prioritise {skill}."
        elif sp and sp.is_unassessed:
            reason = f"We have not measured your {skill} yet — this sets your baseline."
        else:
            reason = f"Keeping {skill} fresh."
        blocks.append(PlanBlock(skill, mins, reason))
    return blocks


def current_streak(user, today: dt.date | None = None) -> int:
    """Consecutive days, ending today or yesterday, with a completed session.

    Counting back from yesterday when today is empty means the streak is not
    shown as broken before the learner has had a chance to study today.
    """
    today = today or timezone.localdate()
    days = set(
        StudySession.objects.filter(
            user=user, status=StudySession.Status.COMPLETED
        ).values_list("started_at__date", flat=True)
    )
    if not days:
        return 0
    cursor = today if today in days else today - dt.timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= dt.timedelta(days=1)
    return streak


def _week_start(today: dt.date) -> dt.date:
    return today - dt.timedelta(days=today.weekday())


def weekly_minutes(user, today: dt.date | None = None) -> int:
    today = today or timezone.localdate()
    seconds = (
        StudySession.objects.filter(
            user=user, started_at__date__gte=_week_start(today)
        ).aggregate(total=Sum("active_seconds"))["total"]
        or 0
    )
    return round(seconds / 60)


def weak_skills(user, limit: int = 3) -> list[SkillProgress]:
    return list(user.skill_progress.order_by("score")[:limit])


def dashboard_payload(user) -> dict:
    """Everything the home screen needs, in one round trip."""
    profile = LearnerProfile.objects.get(user=user)
    plan = build_daily_plan(user)
    today = timezone.localdate()
    return {
        "learner": {
            "username": user.get_username(),
            "overall_level": profile.overall_level,
            "target_level": profile.target_level,
            "daily_minutes": profile.daily_minutes,
            "immersion_level": profile.immersion_level,
            "interests": profile.interests,
        },
        "streak_days": current_streak(user, today),
        "weekly_minutes": weekly_minutes(user, today),
        "weekly_goal_sessions": profile.weekly_goal_sessions,
        "sessions_this_week": StudySession.objects.filter(
            user=user,
            status=StudySession.Status.COMPLETED,
            started_at__date__gte=_week_start(today),
        ).count(),
        "focus": [b.skill for b in plan if b.skill != "review"][:2],
        "plan": [asdict(b) for b in plan],
        "skills": [
            {
                "skill": sp.skill,
                "level": sp.level,
                "score": round(sp.score, 1),
                "confidence": round(sp.confidence, 2),
                "is_weak": sp.is_weak,
                "last_practiced_at": sp.last_practiced_at,
            }
            for sp in user.skill_progress.all()
        ],
        "weak_areas": [
            {"skill": sp.skill, "score": round(sp.score, 1)} for sp in weak_skills(user)
        ],
    }


def _score_to_level(score: float) -> str:
    from .constants import CEFR

    for threshold, level in (
        (20, CEFR.A1),
        (35, CEFR.A2),
        (55, CEFR.B1),
        (75, CEFR.B2),
        (90, CEFR.C1),
    ):
        if score < threshold:
            return level.value
    return CEFR.C2.value


def record_practice(user, skill: str, score_delta: float) -> SkillProgress:
    """Nudge a skill score after an activity.

    Deliberately conservative: a single activity moves the score by a fraction
    of the raw delta, and confidence grows asymptotically with attempt count.
    This stops one unusually good or terrible session from rewriting the
    learner's whole profile.
    """
    sp, _created = SkillProgress.objects.get_or_create(user=user, skill=skill)
    damping = 0.3
    sp.score = max(0.0, min(100.0, sp.score + score_delta * damping))
    sp.attempts += 1
    sp.confidence = min(1.0, sp.attempts / (sp.attempts + 10))
    sp.last_practiced_at = timezone.now()
    sp.level = _score_to_level(sp.score)
    sp.save(
        update_fields=[
            "score",
            "attempts",
            "confidence",
            "last_practiced_at",
            "level",
            "updated_at",
        ]
    )
    return sp
