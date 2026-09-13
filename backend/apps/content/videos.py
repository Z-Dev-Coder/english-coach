"""Watch on YouTube: real videos at the learner's level, with a lesson around each.

The learner watches on YouTube itself. The app picks the video for their
level, prepares them before watching (what it's about, expressions to catch,
moments to listen for) and checks them after (questions, a speaking prompt).
The list of videos is in video_library.json. The notes for each video are
written by the model from its transcript, once, by `prepare_videos`.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.profiles.constants import CEFR_ORDER

from .models import VideoLesson, VideoProgress
from .scenes import learner_level

LIBRARY = Path(__file__).with_name("video_library.json")


def ensure_library() -> None:
    """Add any listed video that isn't in the database yet. Safe on every request."""
    if not LIBRARY.exists():
        return
    existing = {video.video_id: video for video in VideoLesson.objects.all()}
    for entry in json.loads(LIBRARY.read_text(encoding="utf-8")):
        video = existing.get(entry["video_id"])
        if video is None:
            # The page asks for the next video and the list at the same moment, so two
            # requests can load a new library together; the loser just reads the row.
            try:
                with transaction.atomic():
                    video = VideoLesson.objects.create(
                        video_id=entry["video_id"],
                        title=entry["title"][:300],
                        channel=entry["channel"][:120],
                        level=entry["level"],
                        kind=entry.get("kind", "")[:40],
                        duration_seconds=int(entry.get("duration_seconds") or 0),
                    )
            except IntegrityError:
                video = VideoLesson.objects.get(video_id=entry["video_id"])
        notes = entry.get("notes")
        if notes and video.prepared_at is None:
            # Notes written with the library travel with it, so every install has them.
            video.summary = notes.get("summary", "")
            video.expressions = notes.get("expressions", [])
            video.listen_for = notes.get("listen_for", [])
            video.questions = notes.get("questions", [])
            video.speaking_prompt = notes.get("speaking_prompt", "")
            video.prepared_at = timezone.now()
            video.save()


def videos_for(user) -> tuple[str, list[VideoLesson]]:
    """Videos at the learner's level, or the nearest level that has some."""
    ensure_library()
    level = learner_level(user)
    order = list(CEFR_ORDER)
    here = order.index(level) if level in order else order.index("B1")
    for candidate in sorted(order, key=lambda item: (abs(order.index(item) - here), order.index(item))):
        items = list(VideoLesson.objects.filter(level=candidate).order_by("id"))
        if items:
            # Prepared lessons first: a video with notes is a lesson, without is only a link.
            items.sort(key=lambda video: video.prepared_at is None)
            return level, items
    return level, []


def done_ids(user) -> set[int]:
    return set(VideoProgress.objects.filter(user=user).values_list("video_id", flat=True))


def next_video(user) -> VideoLesson | None:
    level, items = videos_for(user)
    done = done_ids(user)
    fresh = [video for video in items if video.id not in done]
    if fresh:
        return fresh[0]
    if not items:
        return None
    finished = {row.video_id: row.completed_at for row in VideoProgress.objects.filter(user=user, video__in=items)}
    return min(items, key=lambda video: finished.get(video.id))


def complete(user, video: VideoLesson) -> None:
    VideoProgress.objects.get_or_create(user=user, video=video)


PREP_SCHEMA = {
    "type": "object",
    "required": ["summary", "expressions", "listen_for", "questions", "speaking_prompt"],
    "properties": {
        "summary": {"type": "string"},
        "expressions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["expression", "meaning", "example"],
                "properties": {
                    "expression": {"type": "string"},
                    "meaning": {"type": "string"},
                    "example": {"type": "string"},
                },
            },
        },
        "listen_for": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["time", "note"],
                "properties": {"time": {"type": "string"}, "note": {"type": "string"}},
            },
        },
        "questions": {"type": "array", "items": {"type": "string"}},
        "speaking_prompt": {"type": "string"},
    },
}


def prep_prompt(video: VideoLesson, transcript: str) -> str:
    return f"""You are an English teacher preparing a learner at CEFR {video.level} to watch a real
YouTube video: "{video.title}" ({video.channel}).

TIMED TRANSCRIPT (for your reference only; do not reproduce it)
{transcript[:24000]}

Return JSON, all in your own words, pitched at {video.level}:
- summary: 2-3 sentences on what happens in the video, without spoiling the answers.
- expressions: 6-8 natural expressions, phrasal verbs or idioms the speakers actually
  use, copied exactly, each with `meaning` (plain words) and `example` (a new everyday
  sentence, not from the video).
- listen_for: 4-6 moments, each with `time` ("m:ss" from the transcript) and `note`
  saying what to catch there, e.g. how a speaker disagrees politely or a reduced form
  like "gonna". Describe it; don't quote more than a few words.
- questions: 4-5 questions to answer after watching, about content and how people speak.
- speaking_prompt: one question that gets the learner talking about the same topic
  from their own life, for 1-2 minutes.
"""


def prepare(video: VideoLesson, transcript: str) -> bool:
    """Write the lesson notes for a video from its transcript. The transcript isn't stored."""
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider

    try:
        data = get_ai_provider().generate_json(
            prep_prompt(video, transcript), schema=PREP_SCHEMA, tier=TIER_MEDIUM, temperature=0.3
        )
    except AIError:
        return False

    expressions = [
        {k: str(item.get(k, "")).strip() for k in ("expression", "meaning", "example")}
        for item in data.get("expressions") or []
        if isinstance(item, dict) and item.get("expression") and item.get("meaning")
    ]
    listen_for = [
        {"time": str(item.get("time", "")).strip()[:8], "note": str(item.get("note", "")).strip()}
        for item in data.get("listen_for") or []
        if isinstance(item, dict) and item.get("note")
    ]
    questions = [str(q).strip() for q in data.get("questions") or [] if str(q).strip()]
    if len(expressions) < 3 or len(questions) < 2:
        return False

    video.summary = str(data.get("summary") or "").strip()
    video.expressions = expressions[:8]
    video.listen_for = listen_for[:6]
    video.questions = questions[:5]
    video.speaking_prompt = str(data.get("speaking_prompt") or "").strip()
    video.prepared_at = timezone.now()
    video.save()
    return True


def timed_text(fragments: list[dict]) -> str:
    """Caption fragments as "[m:ss] text" lines, which is what the prompt reads."""
    lines = []
    for fragment in fragments:
        text = str(fragment.get("text", "")).strip()
        if not text or text.startswith("["):
            continue
        seconds = int(float(fragment.get("start_ms", 0)) // 1000)
        lines.append(f"[{seconds // 60}:{seconds % 60:02d}] {text}")
    return "\n".join(lines)
