"""Content ingestion and the Today in English feed.

Pipeline: fetch → parse → validate → sanitise → store metadata → prepare
material → publish. Ingestion is idempotent at the database level, so running it
twice, or on an overlapping feed window, cannot duplicate anything.
"""
from __future__ import annotations

import logging

import requests
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.profiles.constants import CEFR
from apps.profiles.models import LearnerProfile

from .models import Article, ContentSource
from .rss import FeedError, parse_feed, strip_html

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 20
MAX_ITEMS_PER_FETCH = 25
USER_AGENT = "EnglishCoach/1.0 (personal learning app)"

# Feed summaries below this are not worth generating material from: the model
# would have to invent the story, which is exactly what it must not do.
MIN_SUMMARY_CHARS = 120


def fetch_feed(source: ContentSource) -> str:
    """Download a feed. Network failures become FeedError, never a 500."""
    try:
        response = requests.get(
            source.feed_url,
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml"},
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise FeedError(f"Could not fetch {source.feed_url}: {exc}") from exc


@transaction.atomic
def store_items(source: ContentSource, items) -> tuple[int, int]:
    """Store new entries. Returns (added, skipped).

    Relies on the database constraints for idempotency rather than checking
    first: a get-or-create race would still let a duplicate through, and the
    constraint is the only thing that actually cannot be raced.
    """
    added = skipped = 0
    for item in items[:MAX_ITEMS_PER_FETCH]:
        try:
            with transaction.atomic():
                Article.objects.create(
                    source=source,
                    guid=item.guid[:500],
                    url=item.url[:800],
                    title=strip_html(item.title, limit=400) or "Untitled",
                    summary=item.summary,
                    author=strip_html(item.author, limit=200),
                    topic=source.topic,
                    published_at=item.published_at,
                )
                added += 1
        except IntegrityError:
            skipped += 1  # Already have it. This is the normal case on re-runs.
    return added, skipped


def ingest(source: ContentSource) -> dict:
    """Fetch one source and store whatever is new."""
    try:
        feed = parse_feed(fetch_feed(source))
    except FeedError as exc:
        logger.warning("Feed failed for %s: %s", source.name, exc)
        source.record_failure(str(exc))
        return {"source": source.name, "ok": False, "error": str(exc), "added": 0, "skipped": 0}

    added, skipped = store_items(source, feed.items)
    source.record_success(added)
    return {
        "source": source.name,
        "ok": True,
        "added": added,
        "skipped": skipped,
        "total": len(feed.items),
    }


def ingest_all(topic: str = "") -> list[dict]:
    sources = ContentSource.objects.filter(is_active=True)
    if topic:
        sources = sources.filter(topic=topic)
    return [ingest(source) for source in sources]


def prepare(article: Article, *, level: str = "B1") -> Article:
    """Generate our own learning material about an article.

    Cached on (article, level): the same story at the same level is expensive to
    produce and identical every time.
    """
    from apps.ai import prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    if len(article.summary or "") < MIN_SUMMARY_CHARS:
        article.status = Article.Status.FAILED
        article.preparation_error = (
            "The feed summary was too short to build material from without inventing facts."
        )
        article.save(update_fields=["status", "preparation_error"])
        return article

    try:
        data = cached(
            "article_material",
            {"url": article.url, "level": level},
            lambda: get_ai_provider().generate_json(
                prompts.article_material(article.title, article.summary, level=level),
                schema=prompts.ARTICLE_MATERIAL_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.6,
            ),
        )
    except AIError as exc:
        article.status = Article.Status.FAILED
        article.preparation_error = str(exc)[:500]
        article.save(update_fields=["status", "preparation_error"])
        return article

    article.adapted_text = str(data.get("adapted_text", ""))
    # The level asked for, not the level the model claims it wrote at. Storing
    # the claim made "already prepared at your level?" unanswerable, so a story
    # adapted once was shown to every learner whatever their level.
    article.level = level
    article.vocabulary = [item for item in data.get("vocabulary", []) if isinstance(item, dict)][:8]
    article.phrases = [str(item) for item in data.get("phrases", [])][:5]
    article.questions = [str(item) for item in data.get("questions", [])][:5]
    article.speaking_prompt = str(data.get("speaking_prompt", ""))
    article.writing_prompt = str(data.get("writing_prompt", ""))
    article.status = Article.Status.PREPARED
    article.prepared_at = timezone.now()
    article.preparation_error = ""
    article.save()
    return article


def today_in_english(user, *, limit: int = 6, prepare_count: int = 0) -> list[Article]:
    """A handful of current stories, biased toward the learner's interests.

    Interests raise a story's chances rather than filtering everything else out:
    a feed that only ever shows one topic stops being a window on the world,
    which is the point of this section.
    """
    profile = LearnerProfile.objects.get(user=user)
    interests = [topic.lower() for topic in (profile.interests or [])]

    queryset = Article.objects.select_related("source")
    preferred = list(
        queryset.filter(topic__in=interests).order_by("-published_at", "-fetched_at")[:limit]
    ) if interests else []

    remaining = limit - len(preferred)
    if remaining > 0:
        others = queryset.exclude(id__in=[article.id for article in preferred]).order_by(
            "-published_at", "-fetched_at"
        )[:remaining]
        preferred.extend(others)

    # Preparing material is slow on a local model, so it is opt-in and capped.
    if prepare_count:
        from .scenes import learner_level

        level = learner_level(user, "reading")
        for article in preferred[:prepare_count]:
            if not article.is_prepared or article.level != level:
                prepare(article, level=level)

    return preferred


def search(query: str, *, topic: str = "", limit: int = 30):
    queryset = Article.objects.select_related("source")
    if topic:
        queryset = queryset.filter(topic=topic)
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(summary__icontains=query))
    return queryset[:limit]


def study_dialogue(user, text: str, *, level: str = "") -> dict:
    """Mine a short dialogue excerpt the learner supplied.

    Deliberately user-supplied only: we do not scrape or redistribute subtitles.
    The learner pastes a few lines from something they are watching, and we
    explain the spoken English in it.
    """
    from apps.ai import prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    profile = LearnerProfile.objects.get(user=user)
    level = level or profile.overall_level

    try:
        data = cached(
            "dialogue",
            {"text": text.strip()[:2000], "level": level},
            lambda: get_ai_provider().generate_json(
                prompts.dialogue_study(text, level=level),
                schema=prompts.DIALOGUE_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.5,
            ),
        )
    except AIError as exc:
        return {"available": False, "error": str(exc), "expressions": []}

    data["available"] = True
    return data
