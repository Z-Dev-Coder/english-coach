"""Real recorded English from VOA Learning English.

The browser's synthetic voice is fine for hearing a single word and poor for
everything a listener actually needs to learn: natural rhythm, linking,
reduction, real intonation. Shadowing a machine teaches the learner to sound
like the machine.

VOA Learning English publishes programmes read by real presenters, at a slowed
learner pace, each with a full transcript. As work of the US government it is
in the public domain, so the audio can be played and the transcript stored.
Audio is streamed from VOA's own servers, never copied.

Each category is pitched at a band, which becomes the passage level.
"""
from __future__ import annotations

import html
import re
import urllib.request

BASE = "https://learningenglish.voanews.com"

# Category page id -> (topic, CEFR level).
CATEGORIES: dict[str, tuple[str, str]] = {
    "3619": ("everyday", "A2"),   # English in a Minute
    "955": ("lifestyle", "B1"),   # Health & Lifestyle
    "3521": ("news", "B1"),       # As It Is
    "1579": ("science", "B2"),    # Science & Technology
    "986": ("culture", "B2"),     # Arts & Culture
    "1581": ("stories", "C1"),    # American Stories: full literature readings
}

# Levels with no programme of their own borrow the nearest one.
LEVEL_FALLBACK = {"C2": "C1"}


def categories_for(level: str) -> list[tuple[str, str, str]]:
    """(category id, topic, stored level) for programmes pitched at this level."""
    level = LEVEL_FALLBACK.get(level, level)
    return [(cid, topic, lvl) for cid, (topic, lvl) in CATEGORIES.items() if lvl == level]


def new_articles(level: str, known_urls: set[str], *, want: int = 3, max_pages: int = 8):
    """Yield (url, parsed, topic, level) for articles not yet imported, newest first.

    Walks each programme's listing page by page, so there is always more:
    VOA has years of back catalogue behind page 1.
    """
    found = 0
    for category, topic, stored_level in categories_for(level):
        for page in range(1, max_pages + 1):
            try:
                links = article_links(fetch(f"{BASE}/z/{category}?p={page}", timeout=15))
            except Exception:
                break
            if not links:
                break
            for url in links:
                if url in known_urls:
                    continue
                known_urls.add(url)
                try:
                    parsed = parse_article(fetch(url, timeout=15))
                except Exception:
                    continue
                if parsed:
                    yield url, parsed, topic, stored_level
                    found += 1
                    if found >= want:
                        return


def top_up_passages(level: str, *, want: int = 3) -> int:
    """Import the next real-voice passages for a level. Returns how many."""
    from .models import Passage

    known = set(Passage.objects.exclude(source_url="").values_list("source_url", flat=True))
    added = 0
    for url, parsed, topic, stored_level in new_articles(level, known, want=want):
        if Passage.objects.filter(source_url=url).exists():
            continue  # imported meanwhile by another request
        Passage.objects.create(
            title=parsed["title"], text=parsed["text"], level=stored_level, topic=topic,
            source=Passage.Source.FEED, source_url=url,
            audio_url=parsed["audio_url"], audio_credit=CREDIT,
        )
        added += 1
    return added


def top_up_if_needed(user, level: str, *, minimum: int = 2) -> None:
    """When a learner has few unstudied real recordings left, fetch more in the background.

    Content is never a fixed set: as learners work through the recordings at
    their level, the next ones are pulled from VOA's back catalogue.
    """
    import threading

    from django.conf import settings
    from django.core.cache import cache
    from django.db import close_old_connections

    from .models import Passage

    if not getattr(settings, "LIVE_CONTENT_FETCH", True) or not categories_for(level):
        return
    stored = LEVEL_FALLBACK.get(level, level)
    unstudied = (
        Passage.objects.filter(owner__isnull=True, level=stored)
        .exclude(audio_url="")
        .exclude(attempts__user=user)
        .distinct()
        .count()
    )
    if unstudied >= minimum:
        return

    # Opening the list and finishing an exercise can both ask at once; two fetches
    # running together imported every story twice. One fetch per level at a time.
    lock = f"voa-top-up:{stored}"
    if not cache.add(lock, True, timeout=300):
        return

    def work():
        try:
            top_up_passages(level)
        finally:
            cache.delete(lock)
            close_old_connections()

    threading.Thread(target=work, daemon=True).start()

CREDIT = "VOA Learning English (public domain)"

_ARTICLE_LINK = re.compile(r'href="(/a/[^"]+\.html)"')
_MP3 = re.compile(r"https://voa-audio[^\"'&\s]+?\.mp3")
_TITLE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
# Paragraphs and headings, in page order. Headings matter only as endings: the
# quiz, teacher notes and glossary after a story are introduced by <h2>s.
_PARAGRAPH = re.compile(r"<(p|h[2-6])(?:\s[^>]*)?>(.*?)</\1>", re.S)
_END_HEADING = re.compile(r"^(quiz\b|for teachers|words in (this|the) story|related|share|follow us)", re.I)
# The credit line closes the transcript ("X adapted this story for VOA Learning English").
_CREDIT_LINE = re.compile(r"\b(adapted|wrote|reported|produced)\b.*\b(for|with)\b.*\bVOA\b", re.I)

# Lines on the page that are player chrome or credits, not the transcript.
_NOISE = re.compile(
    r"^(no media source currently available|direct link|pop-out player|embed|share|"
    r"i['’]m [a-z .\-]+\.?$|___+|words in this story|.*\bwrote this story\b|.*\bedited\b|"
    r".*\b(reported|adapted)\b.*\bvoa learning english\b)",
    re.I,
)


_AGENCY = re.compile(r"\b(Associated Press|Reuters|Agence France-Presse|AFP)\b")


def fetch(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "english-coach/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def article_links(listing_html: str) -> list[str]:
    seen, links = set(), []
    for path in _ARTICLE_LINK.findall(listing_html):
        if path not in seen:
            seen.add(path)
            links.append(BASE + path)
    return links


def _clean(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_article(page_html: str) -> dict:
    """Title, audio and transcript; {} when the page has no audio or no text.

    Only the transcript itself is kept: it stops at "Words in this Story", the
    glossary VOA appends, since that is not what the presenter reads.
    """
    audio = [url for url in _MP3.findall(page_html) if not url.endswith("_hq.mp3")]
    start = page_html.find('class="wsw"')
    title_match = _TITLE.search(page_html)
    if not audio or start < 0 or not title_match:
        return {}

    body = re.sub(r"<script.*?</script>", "", page_html[start:], flags=re.S)
    paragraphs = []
    for tag, raw in _PARAGRAPH.findall(body):
        line = _clean(raw)
        if not line:
            continue
        # An underline is not an ending: American Stories put one between the
        # introduction and the story itself, and stopping there kept 83 words of a
        # 12-minute recording, so the highlight barely moved. What does end the
        # transcript is the credit line or the quiz / teachers / glossary heading.
        if re.match(r"^_{3,}$", line):
            continue
        if tag.startswith("h"):
            if _END_HEADING.match(line) or re.match(r"^words in (this|the) story", line, re.I):
                break
            continue
        if re.match(r"^words in (this|the) story", line, re.I):
            break
        if _CREDIT_LINE.search(line):
            # A credit line closes the transcript -- but only once there is one. An
            # "Editor's Note" at the top can mention VOA too, and ending there kept nothing.
            if sum(len(p.split()) for p in paragraphs) >= 60:
                break
            continue
        if _NOISE.match(line) or len(line) < 3:
            continue
        paragraphs.append(line)

    # Stories adapted from wire services stay the agency's copyright, not
    # public domain, so they are not imported at all.
    if _AGENCY.search(body):
        return {}

    text = "\n\n".join(paragraphs)
    if len(text.split()) < 60:
        return {}
    return {"title": _clean(title_match.group(1))[:200], "audio_url": audio[0], "text": text}
