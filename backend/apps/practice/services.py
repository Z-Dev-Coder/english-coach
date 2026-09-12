"""Speaking-practice services."""
from __future__ import annotations

from apps.ai.registry import get_ai_provider
from apps.profiles.constants import Skill
from apps.profiles.models import LearnerProfile, SkillProgress

from .models import SpeakingScript
from .scripts import build_portable_prompt, generate_ai_script, generate_template_script


def _speaking_level(user) -> str:
    """Speaking scripts are pitched at the speaking level, not the overall one.

    Someone who reads at B2 but speaks at A2 needs A2 speaking practice; using a
    single global level is exactly the failure the profile design avoids.
    """
    sp = SkillProgress.objects.filter(user=user, skill=Skill.SPEAKING).first()
    if sp:
        return sp.level
    return LearnerProfile.objects.get(user=user).overall_level


# Matches the passage rotation: long enough that a week does not repeat,
# short enough that a small set still comes round again.
SCENARIO_WINDOW = 12


def _next_scenario(user) -> str:
    """The situation this learner has gone longest without practising.

    Replaces a random pick. Random has no memory, so it both repeats and never
    finishes the set -- and the whole claim of the app is that it decides what
    you practise next based on what you have already done.
    """
    from apps.practice.scripts import TEMPLATES

    available = []
    for template in TEMPLATES:
        if template.scenario not in available:
            available.append(template.scenario)
    if not available:
        return ""

    recent = list(
        SpeakingScript.objects.filter(user=user)
        .order_by("-created_at")
        .values_list("scenario", flat=True)[:SCENARIO_WINDOW]
    )

    unused = [scenario for scenario in available if scenario not in recent]
    if unused:
        return unused[0]
    # All practised recently: take the one practised longest ago.
    return max(available, key=lambda scenario: recent.index(scenario))


def _full_dialogue(*, title, setting, goal, level, expressions, fallback):
    """A whole roleplay script, cached per situation and level.

    One model call per (situation, level) ever, which is what keeps a
    generated script inside the zero-recurring-cost rule -- there are six
    situations and six levels, so the whole space is a few dozen calls.

    Falls back to the hand-written opening. A short real script beats a long
    invented one, and inventing dialogue without a model would mean writing
    something generic enough to fit any situation.
    """
    from apps.ai import prompts as ai_prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.services import cached

    try:
        provider = get_ai_provider()
        data = cached(
            "speaking_dialogue",
            {"title": title, "level": level, "expressions": sorted(expressions)},
            lambda: provider.generate_json(
                ai_prompts.speaking_dialogue(
                    title=title, setting=setting, goal=goal, level=level, expressions=expressions
                ),
                schema=ai_prompts.ROLEPLAY_SCRIPT_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.7,
            ),
        )
    except AIError:
        return fallback

    lines = []
    for item in data.get("lines") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        # Anything that is not clearly the partner is the learner: a model that
        # writes "Interviewer" or "Me" should not break the script.
        speaker = "Partner" if str(item.get("speaker", "")).strip().lower().startswith("partner") else "You"
        line = {"speaker": speaker, "text": text[:400]}
        note = str(item.get("note") or "").strip()
        if note:
            line["note"] = note[:120]
        lines.append(line)

    # Too short to be a script means the model misunderstood; keep the
    # hand-written one rather than showing three stray lines.
    return lines if len(lines) >= 4 else fallback


def create_speaking_script(
    user, *, scenario: str = "", level: str = "", topic: str = "", use_ai: bool = False
) -> SpeakingScript:
    """Create and persist a practice script.

    `use_ai` is opt-in: the template path is instant and always works, so the
    default experience never waits on a local model.
    """
    level = level or _speaking_level(user)
    scenario = scenario or _next_scenario(user)

    if use_ai:
        weak = list(
            SkillProgress.objects.filter(user=user, score__lt=60).values_list("skill", flat=True)
        )
        data = generate_ai_script(
            get_ai_provider(), scenario=scenario or "casual", level=level, topic=topic, weak_points=weak
        )
    else:
        data = generate_template_script(scenario=scenario or None, level=level)

    # A generated dialogue only where the situation itself was generated. The
    # templates carry full hand-written scripts, which are instant, work
    # offline, cost nothing, and have been read before shipping -- none of
    # which is true of a model call on every page load.
    if use_ai:
        data["lines"] = _full_dialogue(
            title=data.get("title", ""),
            setting=data.get("setting", ""),
            goal=data.get("goal", ""),
            level=level,
            expressions=data.get("target_expressions") or [],
            fallback=data.get("lines") or [],
        )

    # Rebuild the portable prompt so the chatbot gets the rehearsed script too,
    # rather than inventing a different conversation from the same situation.
    data["portable_prompt"] = build_portable_prompt(
        title=data.get("title", ""),
        setting=data.get("setting", ""),
        goal=data.get("goal", ""),
        level=level,
        expressions=data.get("target_expressions") or [],
        questions=data.get("follow_up_questions") or [],
        sample_exchange=[(line["speaker"], line["text"]) for line in data["lines"]],
    )

    return SpeakingScript.objects.create(user=user, **data)
