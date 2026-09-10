"""Turning the daily plan into a concrete lesson.

Architecture note: generation is a **hybrid**, deliberately.

The *structure* of a lesson — which skills, how many minutes, in what order,
pointing at which passage or review queue — is computed from the database. It is
deterministic, testable, and works with no model running.

The *content* — a theme tying the day together, a writing prompt that uses the
learner's interests, expressions drawn from their weak areas — is AI-enriched
when a model is available.

Doing it the other way round (asking the model to invent the whole lesson,
including how long each part should be) would make the single most important
screen in the app dependent on a local model behaving, and would let a
hallucination decide the learner's schedule.
"""
from __future__ import annotations

import datetime as dt

from django.db import transaction
from django.utils import timezone

from apps.profiles.constants import Skill
from apps.profiles.models import LearnerProfile
from apps.profiles.services import build_daily_plan

from .models import Lesson, LessonActivity

# Where each activity kind sends the learner in the frontend.
ROUTES = {
    "review": "/review",
    "vocabulary": "/review",
    "listening": "/practice",
    "reading": "/practice",
    "writing": "/practice",
    "speaking": "/speaking",
    "drill": "/drill",
}

# Fallback instructions, used when no model is available. Written to be
# genuinely useful on their own rather than as placeholders.
TEMPLATE_INSTRUCTIONS = {
    "review": "Clear your due cards. Try to answer out loud before revealing each one.",
    "vocabulary": "Work through the vocabulary that is due, and say each expression in a sentence of your own.",
    "listening": "Play each sentence, then type what you hear. Use the slow button only after two normal plays.",
    "reading": "Read the passage once for gist, then again for the phrases you would not have produced yourself.",
    "writing": "Write your answer, then read it back out loud before submitting it.",
    "speaking": "Generate a script and run the roleplay out loud. Speaking quietly still counts.",
    "drill": "One sentence, five ways: listen, repeat, write it from memory, change a word, then make it about you.",
}

TEMPLATE_TITLES = {
    "review": "Review what is due",
    "vocabulary": "Vocabulary practice",
    "listening": "Listening and dictation",
    "reading": "Read and notice",
    "writing": "Writing practice",
    "speaking": "Speaking practice",
    "drill": "Listen, speak, write",
}

DEFAULT_WRITING_PROMPTS = [
    "What did you do today? Write it as if you were telling a friend.",
    "Describe something that went wrong recently and how you handled it.",
    "What is something you have changed your mind about?",
]


def learner_context(user, minutes: int | None = None) -> dict:
    """Assemble everything the generator needs to know about this learner.

    Pure read: no writes, no AI. This is the structured context the master
    prompt calls for — level, weaknesses, recent mistakes, due vocabulary,
    interests, time available — and it is built from facts in the database
    rather than anything the model is asked to remember.
    """
    from apps.mistakes.services import persistent, weak_categories
    from apps.review.services import due_count

    profile = LearnerProfile.objects.get(user=user)
    plan = build_daily_plan(user, minutes=minutes)

    skills = list(user.skill_progress.all())
    weak = [sp.skill for sp in sorted(skills, key=lambda sp: sp.score) if sp.is_weak][:3]

    # Mistake categories come from the bank, which counts repeats across every
    # activity rather than looking at the last few attempts.
    recent_mistakes = weak_categories(user)
    repeated = [
        {"incorrect": m.incorrect, "correct": m.correct, "times": m.occurrences}
        for m in persistent(user, limit=3)
    ]

    return {
        "overall_level": profile.overall_level,
        "target_level": profile.target_level,
        "interests": list(profile.interests or []),
        "weak_skills": weak,
        "recent_mistakes": recent_mistakes[:5],
        "repeated_mistakes": repeated,
        "due_count": due_count(user),
        "total_minutes": sum(block.minutes for block in plan),
        "plan": [{"skill": block.skill, "minutes": block.minutes} for block in plan],
        "skill_scores": {sp.skill: round(sp.score) for sp in skills},
    }


# How far back to look when deciding what counts as "recently used". Long
# enough that a week does not repeat itself; short enough that a small library
# still comes round again rather than running dry.
ROTATION_WINDOW_DAYS = 21


def _recently_used_passage_ids(user) -> list[int]:
    """Passage ids this learner has already been given, most recent first.

    Across listening *and* reading, because they draw on one library. Tracking
    them separately let the same text be "fresh" for one skill the day after
    it was used for the other.
    """
    from apps.lessons.models import LessonActivity

    cutoff = timezone.now().date() - dt.timedelta(days=ROTATION_WINDOW_DAYS)
    recent = (
        LessonActivity.objects.filter(
            lesson__user=user,
            lesson__date__gte=cutoff,
            kind__in=("listening", "reading"),
        )
        .order_by("-lesson__date", "-position")
        .values_list("params", flat=True)
    )

    seen: list[int] = []
    for params in recent:
        passage_id = (params or {}).get("passage_id")
        if isinstance(passage_id, int) and passage_id not in seen:
            seen.append(passage_id)
    return seen


def _passage_for(user, level: str):
    """Pick a passage at the learner's level that they have not just done.

    Level first, because a plan that says B1 and then hands over a C1 text is
    not a plan. Only if nothing at that level is left unused does it widen --
    repeating a passage at the right level beats moving to the wrong one.
    """
    from django.db.models import Q

    from apps.skills.models import Passage

    pool = list(
        Passage.objects.filter(Q(owner=user) | Q(owner__isnull=True)).order_by("id")
    )
    if not pool:
        return None

    used = _recently_used_passage_ids(user)

    def pick(candidates):
        if not candidates:
            return None
        fresh = [item for item in candidates if item.id not in used]
        if fresh:
            return fresh[0]
        # Everything here has been used: take the one used longest ago, so the
        # library cycles instead of sticking on whichever came first.
        return max(candidates, key=lambda item: used.index(item.id))

    at_level = [item for item in pool if item.level == level]
    own = [item for item in at_level if item.owner_id == user.id]

    # Their own text first: they chose it, so it is the most relevant thing
    # available at the right level.
    return pick(own) or pick(at_level) or pick(pool)


def _writing_prompt_for(user) -> str:
    """A writing prompt the learner has not had recently.

    Was indexed by the activity's position in the plan, which meant the same
    prompt every day whenever writing landed in the same slot.
    """
    from apps.lessons.models import LessonActivity

    cutoff = timezone.now().date() - dt.timedelta(days=ROTATION_WINDOW_DAYS)
    used = list(
        LessonActivity.objects.filter(
            lesson__user=user, lesson__date__gte=cutoff, kind="writing"
        )
        .order_by("-lesson__date", "-position")
        .values_list("prompt", flat=True)
    )

    for prompt in DEFAULT_WRITING_PROMPTS:
        if prompt not in used:
            return prompt
    # All of them used: take the one used longest ago.
    return max(DEFAULT_WRITING_PROMPTS, key=lambda prompt: used.index(prompt))


def _template_activities(user, context: dict) -> list[dict]:
    """Build the concrete activity list from the plan alone. Never fails."""
    activities: list[dict] = []
    level = context["overall_level"]
    passage_of_the_day = None

    for position, block in enumerate(context["plan"]):
        kind = block["skill"]
        activity = {
            "position": position,
            "kind": kind,
            "title": TEMPLATE_TITLES.get(kind, kind.title()),
            "instructions": TEMPLATE_INSTRUCTIONS.get(kind, ""),
            "minutes": block["minutes"],
            "prompt": "",
            "target_expressions": [],
            "route": ROUTES.get(kind, "/practice"),
            "params": {},
        }

        if kind == "review":
            activity["params"] = {"due": context["due_count"]}
            activity["title"] = (
                f"Review {context['due_count']} due items"
                if context["due_count"]
                else "Review (nothing due)"
            )
        elif kind in {"listening", "reading"}:
            # One text for the day. Reading it and then hearing it is worth
            # more than two unrelated texts in a twenty-minute session.
            if passage_of_the_day is None:
                passage_of_the_day = _passage_for(user, level)
            passage = passage_of_the_day
            if passage:
                activity["params"] = {"passage_id": passage.id, "tab": kind}
                activity["title"] = f"{TEMPLATE_TITLES[kind]}: {passage.title}"
        elif kind == "writing":
            activity["params"] = {"tab": "writing"}
            activity["prompt"] = _writing_prompt_for(user)

        activities.append(activity)

    # The drill covers listening, speaking and writing at once, so it is worth
    # adding whenever two of those are on the day's plan.
    planned = {block["skill"] for block in context["plan"]}
    if len(planned & {Skill.LISTENING, Skill.SPEAKING, Skill.WRITING}) >= 2:
        activities.append(
            {
                "position": len(activities),
                "kind": "drill",
                "title": TEMPLATE_TITLES["drill"],
                "instructions": TEMPLATE_INSTRUCTIONS["drill"],
                "minutes": 3,
                "prompt": "",
                "target_expressions": [],
                "route": ROUTES["drill"],
                "params": {},
            }
        )

    return activities


def _enrich_with_ai(activities: list[dict], context: dict) -> tuple[list[dict], dict, bool]:
    """Overlay AI-written titles, instructions and prompts onto the skeleton.

    The skeleton's kinds, minutes and routing are authoritative: only text is
    taken from the model, and only where it actually supplied something. A model
    that returns three activities for a six-block plan therefore improves three
    of them and leaves the rest intact, instead of producing a broken lesson.
    """
    from apps.ai import prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    try:
        provider = get_ai_provider()
        data = cached(
            "lesson",
            {
                "level": context["overall_level"],
                "weak": context["weak_skills"],
                "mistakes": context["recent_mistakes"],
                "interests": context["interests"],
                "plan": context["plan"],
            },
            lambda: provider.generate_json(
                prompts.generate_lesson(context),
                schema=prompts.LESSON_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.7,
            ),
        )
    except AIError:
        return activities, {}, False

    generated = data.get("activities") or []
    by_kind: dict[str, list[dict]] = {}
    for item in generated:
        by_kind.setdefault(str(item.get("kind", "")).lower(), []).append(item)

    for activity in activities:
        candidates = by_kind.get(activity["kind"])
        if not candidates:
            continue
        item = candidates.pop(0)
        if item.get("title"):
            activity["title"] = str(item["title"])[:200]
        if item.get("instructions"):
            activity["instructions"] = str(item["instructions"])
        if item.get("prompt"):
            activity["prompt"] = str(item["prompt"])
        expressions = item.get("target_expressions")
        if isinstance(expressions, list):
            activity["target_expressions"] = [str(e) for e in expressions][:4]

    meta = {
        "title": str(data.get("title", ""))[:200],
        "theme": str(data.get("theme", "")),
        "encouragement": str(data.get("encouragement", "")),
    }
    return activities, meta, True


@transaction.atomic
def generate_lesson(user, *, date: dt.date | None = None, minutes: int | None = None, use_ai: bool = True) -> Lesson:
    """Get or create today's lesson.

    Idempotent per day: a second call returns the existing lesson rather than
    regenerating, so refreshing the page never discards progress or swaps the
    material out from under the learner.
    """
    date = date or timezone.localdate()
    existing = Lesson.objects.filter(user=user, date=date).first()
    if existing:
        return existing

    context = learner_context(user, minutes=minutes)
    activities = _template_activities(user, context)

    meta: dict = {}
    enriched = False
    if use_ai:
        activities, meta, enriched = _enrich_with_ai(activities, context)

    focus = [block["skill"] for block in context["plan"] if block["skill"] != "review"][:2]
    lesson = Lesson.objects.create(
        user=user,
        date=date,
        title=meta.get("title") or f"Today: {' and '.join(focus) or 'a mixed session'}",
        theme=meta.get("theme", ""),
        encouragement=meta.get("encouragement", ""),
        total_minutes=context["total_minutes"],
        focus_skills=focus,
        origin=Lesson.Origin.AI if enriched else Lesson.Origin.TEMPLATE,
        context=context,
    )

    LessonActivity.objects.bulk_create(
        [LessonActivity(lesson=lesson, **activity) for activity in activities]
    )
    return lesson


def regenerate(
    user, *, date: dt.date | None = None, minutes: int | None = None, use_ai: bool = True
) -> Lesson:
    """Throw today's lesson away and build a new one.

    Explicit, because it discards progress. Only ever called from a deliberate
    "give me something else" action, never automatically.
    """
    date = date or timezone.localdate()
    Lesson.objects.filter(user=user, date=date).delete()
    return generate_lesson(user, date=date, minutes=minutes, use_ai=use_ai)
