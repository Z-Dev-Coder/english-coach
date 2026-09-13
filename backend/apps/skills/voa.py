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
}

CREDIT = "VOA Learning English (public domain)"

_ARTICLE_LINK = re.compile(r'href="(/a/[^"]+\.html)"')
_MP3 = re.compile(r"https://voa-audio[^\"'&\s]+?\.mp3")
_TITLE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_PARAGRAPH = re.compile(r"<p[^>]*>(.*?)</p>", re.S)

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
    for raw in _PARAGRAPH.findall(body):
        line = _clean(raw)
        if not line:
            continue
        if re.match(r"^_{3,}|^words in this story", line, re.I):
            break
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
