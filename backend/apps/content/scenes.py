"""Choosing and producing Movies & TV lessons at the learner's level."""
from __future__ import annotations

import uuid

from django.db import IntegrityError

from apps.profiles.constants import CEFR_ORDER, Skill
from apps.profiles.models import LearnerProfile, SkillProgress

from .models import Scene, SceneProgress
from .scene_seeds import SEED_SCENES

GENRES = ["Sitcom", "Drama", "Crime", "Office Comedy", "Romantic Comedy", "Thriller"]


def learner_level(user, skill: str = Skill.LISTENING) -> str:
    """The learner's level for the skill this lesson trains.

    Scenes are listening first, so they follow the listening level; someone who
    reads at B2 but follows speech at A2 needs A2 scenes.
    """
    progress = SkillProgress.objects.filter(user=user, skill=skill).first()
    if progress:
        return progress.level
    return LearnerProfile.objects.get(user=user).overall_level


def ensure_seed_scenes() -> None:
    """Load the hand-written scenes once; safe to call on every request."""
    existing = set(Scene.objects.filter(source=Scene.Source.SEED).values_list("slug", flat=True))
    for seed in SEED_SCENES:
        if seed["slug"] in existing:
            continue
        try:
            Scene.objects.create(
                slug=seed["slug"],
                title=seed["title"],
                genre=seed["genre"],
                level=seed["level"],
                setting=seed["setting"],
                lines=[{"speaker": who, "text": text} for who, text in seed["lines"]],
                expressions=seed["expressions"],
                questions=seed["questions"],
                source=Scene.Source.SEED,
            )
        except IntegrityError:
            pass


def _nearest_levels(level: str) -> list[str]:
    """The learner's level first, then the closest ones outward."""
    order = list(CEFR_ORDER)
    if level not in order:
        level = "B1"
    here = order.index(level)
    return sorted(order, key=lambda item: (abs(order.index(item) - here), order.index(item)))


def scenes_for(user) -> tuple[str, list[Scene]]:
    """Scenes at the learner's level -- or the nearest level that has any."""
    ensure_seed_scenes()
    level = learner_level(user)
    for candidate in _nearest_levels(level):
        scenes = list(Scene.objects.filter(level=candidate).order_by("id"))
        if scenes:
            return level, scenes
    return level, []


def done_ids(user) -> set[int]:
    return set(SceneProgress.objects.filter(user=user).values_list("scene_id", flat=True))


def generate_scene(user, level: str) -> Scene | None:
    """A new scene at this level from the model; None if it can't be reached."""
    from apps.ai import prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    existing = list(Scene.objects.filter(level=level).values_list("title", flat=True))
    genre = GENRES[len(existing) % len(GENRES)]
    try:
        data = cached(
            "scene_lesson",
            {"level": level, "genre": genre, "n": len(existing)},
            lambda: get_ai_provider().generate_json(
                prompts.scene_lesson(level=level, genre=genre, avoid_titles=existing),
                schema=prompts.SCENE_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.8,
            ),
        )
    except AIError:
        return None

    lines = [
        {"speaker": str(item.get("speaker", "")).strip()[:40], "text": str(item.get("text", "")).strip()}
        for item in data.get("lines") or []
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    ]
    expressions = [
        {
            "expression": str(item.get("expression", "")).strip(),
            "meaning": str(item.get("meaning", "")).strip(),
            "literal_trap": str(item.get("literal_trap", "")).strip(),
            "example": str(item.get("example", "")).strip(),
        }
        for item in data.get("expressions") or []
        if isinstance(item, dict) and item.get("expression") and item.get("meaning")
    ]
    title = str(data.get("title") or "").strip()[:200]
    # Too thin to teach from, or a repeat: not worth storing.
    if len(lines) < 6 or len(expressions) < 3 or not title or title in existing:
        return None

    return Scene.objects.create(
        slug=f"ai-{level.lower()}-{uuid.uuid4().hex[:10]}",
        title=title,
        genre=str(data.get("genre") or genre)[:40],
        level=level,
        setting=str(data.get("setting") or "").strip(),
        lines=lines,
        expressions=expressions[:8],
        questions=[str(q) for q in data.get("questions") or [] if str(q).strip()][:5],
        source=Scene.Source.AI,
    )


def next_scene(user, *, use_ai: bool = True) -> Scene | None:
    """The next unfinished scene at the learner's level.

    When every scene at that level is done, a new one is written for them, so
    the lessons never simply run out. Without a model, the scene finished
    longest ago comes round again rather than nothing.
    """
    level, scenes = scenes_for(user)
    done = done_ids(user)
    fresh = [scene for scene in scenes if scene.id not in done]
    if fresh:
        return fresh[0]
    if use_ai:
        created = generate_scene(user, level)
        if created:
            return created
    if not scenes:
        return None
    finished = {
        row.scene_id: row.completed_at
        for row in SceneProgress.objects.filter(user=user, scene__in=scenes)
    }
    return min(scenes, key=lambda scene: finished.get(scene.id))


def complete_scene(user, scene: Scene) -> None:
    SceneProgress.objects.get_or_create(user=user, scene=scene)
