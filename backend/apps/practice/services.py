"""Speaking-practice services."""
from __future__ import annotations

from apps.ai.registry import get_ai_provider
from apps.profiles.constants import Skill
from apps.profiles.models import LearnerProfile, SkillProgress

from .models import SpeakingScript
from .scripts import generate_ai_script, generate_template_script


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

    return SpeakingScript.objects.create(user=user, **data)
