"""Watch on YouTube: one real video lesson at a time, found when the learner needs it.

Nothing is a fixed list. Each learner has one current video. When they finish
it, the next is found then: the newest video they haven't had from YouTube
channels that suit their level (read from YouTube's public channel feeds, free
and keyless), and the lesson for it is written then by the model. A video
prepared for one learner is reused for the next who reaches it, so the model
is asked once per video, not once per learner.

The learner watches on YouTube itself. The app is the teacher around the
video: what to expect, expressions to catch, what to listen for, questions and
a speaking prompt afterwards.

YouTube offers no free way for a server to read captions, so lessons are
written from the title and description. The expressions are what the topic
naturally calls for, not quotes from the video, and the lesson says so.
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from pathlib import Path

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.profiles.constants import CEFR_ORDER

from .models import VideoLesson, VideoProgress
from .scenes import learner_level

CHANNELS = Path(__file__).with_name("video_channels.json")
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
FEED_CACHE_SECONDS = 6 * 60 * 60


def channels_for(level: str) -> list[dict]:
    """Channels pitched at this level, falling back to the nearest level that has some."""
    channels = json.loads(CHANNELS.read_text(encoding="utf-8"))
    order = list(CEFR_ORDER)
    here = order.index(level) if level in order else order.index("B1")
    for candidate in sorted(order, key=lambda item: (abs(order.index(item) - here), order.index(item))):
        matching = [channel for channel in channels if candidate in channel["levels"]]
        if matching:
            return matching
    return []


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 english-coach"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_feed(xml: str) -> list[dict]:
    """[{video_id, title, description}] newest first, without Shorts."""
    videos = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        video_id = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", entry)
        title = re.search(r"<media:title>(.*?)</media:title>", entry, re.S)
        description = re.search(r"<media:description>(.*?)</media:description>", entry, re.S)
        link = re.search(r'<link rel="alternate" href="([^"]+)"', entry)
        if not video_id or not title:
            continue
        title_text = html.unescape(title.group(1)).strip()
        if "#shorts" in title_text.lower() or (link and "/shorts/" in link.group(1)):
            continue  # too short to build a lesson around
        videos.append({
            "video_id": video_id.group(1).strip(),
            "title": title_text,
            "description": html.unescape(description.group(1)).strip() if description else "",
        })
    return videos


def feed(channel: dict) -> list[dict]:
    key = f"yt-feed:{channel['channel_id']}"
    items = cache.get(key)
    if items is None:
        try:
            items = parse_feed(_fetch(FEED.format(channel["channel_id"])))
        except Exception:
            items = []
        cache.set(key, items, FEED_CACHE_SECONDS if items else 300)
    return items


def current(user) -> VideoLesson | None:
    """The video this learner is on now, if they haven't finished it."""
    row = (
        VideoProgress.objects.filter(user=user, completed_at__isnull=True)
        .select_related("video")
        .order_by("-assigned_at")
        .first()
    )
    return row.video if row else None


def _candidates(level: str, seen: set[str]):
    """Unseen videos from the level's channels, taking turns across channels, newest first."""
    lists = [(channel, [item for item in feed(channel) if item["video_id"] not in seen]) for channel in channels_for(level)]
    depth = max((len(items) for _, items in lists), default=0)
    for index in range(depth):
        for channel, items in lists:
            if index < len(items):
                yield channel, items[index]


def _get_or_create(level: str, channel: dict, item: dict) -> VideoLesson:
    try:
        with transaction.atomic():
            return VideoLesson.objects.create(
                video_id=item["video_id"],
                title=item["title"][:300],
                channel=channel["name"][:120],
                level=level,
                kind=channel.get("kind", "")[:40],
                description=item.get("description", "")[:3000],
            )
    except IntegrityError:
        return VideoLesson.objects.get(video_id=item["video_id"])


def next_video(user, *, use_ai: bool = True) -> VideoLesson | None:
    """The learner's current video, or a new one found and prepared now."""
    video = current(user)
    if video is not None:
        if video.prepared_at is None and use_ai:
            prepare(video)
        return video

    level = learner_level(user)
    seen = set(VideoProgress.objects.filter(user=user).values_list("video__video_id", flat=True))
    for channel, item in _candidates(level, seen):
        video = _get_or_create(level, channel, item)
        if video.prepared_at is None and use_ai and not prepare(video):
            continue  # try the next video rather than hand over a lesson with nothing in it
        return assign(user, video)

    # Feeds unreachable: offer a prepared video someone else studied that this learner hasn't.
    fallback = (
        VideoLesson.objects.filter(level=level, prepared_at__isnull=False)
        .exclude(video_id__in=seen)
        .order_by("-prepared_at")
        .first()
    )
    return assign(user, fallback) if fallback else None


def assign(user, video: VideoLesson) -> VideoLesson:
    VideoProgress.objects.get_or_create(user=user, video=video)
    return video


def complete(user, video: VideoLesson) -> None:
    progress, _ = VideoProgress.objects.get_or_create(user=user, video=video)
    if progress.completed_at is None:
        progress.completed_at = timezone.now()
        progress.save(update_fields=["completed_at"])


def history(user) -> list[VideoProgress]:
    return list(
        VideoProgress.objects.filter(user=user, completed_at__isnull=False)
        .select_related("video")
        .order_by("-completed_at")[:20]
    )


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
        "listen_for": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "speaking_prompt": {"type": "string"},
    },
}


def prep_prompt(video: VideoLesson) -> str:
    return f"""You are an English teacher. A learner at CEFR {video.level} is about to watch this real
YouTube video on YouTube:

TITLE: {video.title}
CHANNEL: {video.channel} ({video.kind})
DESCRIPTION: {video.description[:1500] or "(none)"}

You have not seen the video, only the title and description. Don't invent details of what
people say in it. Prepare the learner for the topic instead. Return JSON, pitched at {video.level}:
- summary: 1-2 sentences on what the video is about, from the title and description.
- expressions: 6-8 natural expressions, phrasal verbs or collocations people typically use
  when talking about this topic, each with `meaning` (plain words) and `example` (an
  everyday sentence).
- listen_for: 3-5 short tasks to do while watching, e.g. "Notice how the speakers agree
  and disagree", "Listen for any of the expressions above", "Write down one opinion".
- questions: 4-5 questions to answer after watching. Keep them open (what did they say
  about..., do you agree...) since you don't know the exact content.
- speaking_prompt: one question that gets the learner talking for 1-2 minutes about the
  same topic from their own life.
"""


def prepare(video: VideoLesson) -> bool:
    """Write the lesson for a video. Returns False if the model couldn't be reached."""
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider

    try:
        data = get_ai_provider().generate_json(
            prep_prompt(video), schema=PREP_SCHEMA, tier=TIER_MEDIUM, temperature=0.4
        )
    except AIError:
        return False

    expressions = [
        {k: str(item.get(k, "")).strip() for k in ("expression", "meaning", "example")}
        for item in data.get("expressions") or []
        if isinstance(item, dict) and item.get("expression") and item.get("meaning")
    ]
    questions = [str(q).strip() for q in data.get("questions") or [] if str(q).strip()]
    if len(expressions) < 3 or len(questions) < 2:
        return False

    video.summary = str(data.get("summary") or "").strip()
    video.expressions = expressions[:8]
    video.listen_for = [str(t).strip() for t in data.get("listen_for") or [] if str(t).strip()][:5]
    video.questions = questions[:5]
    video.speaking_prompt = str(data.get("speaking_prompt") or "").strip()
    video.prepared_at = timezone.now()
    video.save()
    return True
