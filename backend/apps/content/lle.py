"""Real dialogue scenes from VOA's "Let's Learn English".

Movies & TV scenes written by the app can only ever be heard through a
synthetic voice, and a learner training their ear on a machine learns the
machine's rhythm. "Let's Learn English" is a video series of short workplace
and everyday scenes acted by real people, published with a line-by-line
transcript and an mp3. As US government work it is public domain.

Each lesson page links to the next, so the series is crawled by following
those links from the first lesson of each level.
"""
from __future__ import annotations

import html
import re

from apps.skills.voa import BASE, fetch

CREDIT = "VOA Learning English — Let's Learn English (public domain)"

# Starting lesson of each level, and the CEFR level of that series.
SERIES = [
    ("https://learningenglish.voanews.com/a/lets-learn-english-lesson-2-hello/3113733.html", "A1", 1),
    ("https://learningenglish.voanews.com/a/lets-learn-english-level-2-lesson1/3960391.html", "A2", 2),
]

_MP3 = re.compile(r"https://voa-audio[^\"'&\s]+?\.mp3")
_TITLE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
# Lines sit in <p> on newer lessons and in plain <div> on the older Level 1
# ones; headings mark where the dialogue ends. Only innermost blocks count.
_PARAGRAPH = re.compile(r"<(?:p|div|h2)(?:\s[^>]*)?>((?:(?!<(?:p|div)[\s>]).)*?)</(?:p|div|h2)>", re.S)
_LINE = re.compile(r"^([A-Z][A-Za-z.' ]{1,24}):\s*(.+)$")
# The series' animated teacher explains the lesson rather than acting in it.
_NARRATORS = {"professor bot", "narrator"}


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def parse_lesson(page_html: str) -> dict:
    """Title, audio and [{speaker, text}]; {} if not a usable dialogue."""
    audio = [url for url in _MP3.findall(page_html) if not url.endswith("_hq.mp3")]
    title_match = _TITLE.search(page_html)
    start = page_html.find('class="wsw"')
    if not audio or not title_match or start < 0:
        return {}

    body = re.sub(r"<script.*?</script>", "", page_html[start:], flags=re.S)
    lines = []
    for raw in _PARAGRAPH.findall(body):
        text = _clean(raw)
        if re.match(r"^_{3,}|^words in this story|^new words|^listening quiz|^quiz\b", text, re.I):
            break
        match = _LINE.match(text)
        if match:
            speaker, said = match.group(1).strip(), match.group(2).strip()
            if speaker.lower() not in _NARRATORS and said:
                lines.append({"speaker": speaker, "text": said})
        elif lines and text and not text.endswith(":") and len(text) < 300:
            # A speaker's turn split over two paragraphs.
            lines[-1]["text"] += " " + text
    if len(lines) < 6:
        return {}
    return {"title": _clean(title_match.group(1))[:200], "audio_url": audio[0], "lines": lines}


def next_lesson_url(page_html: str, level_number: int, lesson_number: int) -> str:
    """The link to lesson n+1 of the same level, if the page has one."""
    n = lesson_number + 1
    if level_number == 1:
        pattern = rf'href="(/a/lets-learn-english-lesson-{n}-[^"]+\.html)"'
    else:
        pattern = rf'href="(/a/lets-learn-english-level-{level_number}-lesson-?{n}/[^"]+\.html)"'
    match = re.search(pattern, page_html)
    return BASE + match.group(1) if match else ""


def _lesson_number(slug: str) -> int:
    return int(slug.rsplit("-", 1)[-1])


def import_next(level: str, *, use_ai: bool = True):
    """Fetch the next not-yet-imported real lesson for this level; None if none.

    Lessons are pulled one at a time, when a learner has finished what exists --
    nothing is a fixed list. The crawl resumes from the last imported lesson's
    page by following its link to the next one.
    """
    from .models import Scene

    series = next((item for item in SERIES if item[1] == level), None)
    if series is None:
        # Above A2 the acted series runs out; a real recorded story at the
        # learner's level is used instead of a machine-voiced scene.
        return import_story(level, use_ai=use_ai)
    start_url, _, level_number = series
    last = (
        Scene.objects.filter(slug__startswith=f"lle-{level_number}-")
        .exclude(source_url="")
        .order_by("-created_at")
        .first()
    )
    try:
        if last is None:
            url, lesson = start_url, 1 if level_number == 2 else 2
        else:
            lesson = _lesson_number(last.slug)
            url = next_lesson_url(fetch(last.source_url, timeout=15), level_number, lesson)
            lesson += 1
        # Skip lessons whose page has no usable dialogue, a few at most.
        for _ in range(3):
            if not url:
                return None
            page = fetch(url, timeout=15)
            parsed = parse_lesson(page)
            slug = f"lle-{level_number}-{lesson}"
            if parsed and not Scene.objects.filter(slug=slug).exists():
                study = (
                    study_material(level, parsed["lines"])
                    if use_ai
                    else {"setting": "", "expressions": [], "questions": []}
                )
                title = re.sub(r"^Let['’]s Learn English\s*[-–:]?\s*", "", parsed["title"], flags=re.I)
                return Scene.objects.create(
                    slug=slug,
                    title=title[:200] or parsed["title"],
                    genre="Real dialogue",
                    level=level,
                    setting=study["setting"],
                    lines=parsed["lines"],
                    expressions=study["expressions"],
                    questions=study["questions"],
                    source=Scene.Source.VOA,
                    audio_url=parsed["audio_url"],
                    audio_credit=CREDIT,
                    source_url=url,
                )
            url = next_lesson_url(page, level_number, lesson)
            lesson += 1
    except Exception:  # offline or VOA changed its pages: fall back to other sources
        return None
    return None


def story_lines(text: str, presenter: str = "Presenter") -> list[dict]:
    """A read story as scene lines: one or two sentences per line, so read-along
    highlighting moves at a followable pace."""
    from apps.skills.similarity import split_sentences

    sentences = [s.strip() for s in split_sentences(text) if s.strip()]
    lines, buffer = [], []
    for sentence in sentences:
        buffer.append(sentence)
        if len(" ".join(buffer)) > 110 or len(buffer) == 2:
            lines.append({"speaker": presenter, "text": " ".join(buffer)})
            buffer = []
    if buffer:
        lines.append({"speaker": presenter, "text": " ".join(buffer)})
    return lines


def import_story(level: str, *, use_ai: bool = True):
    """The next real recorded VOA story at this level, as a scene; None if none."""
    from apps.skills import voa

    from .models import Scene

    known = set(Scene.objects.exclude(source_url="").values_list("source_url", flat=True))
    try:
        for url, parsed, topic, _ in voa.new_articles(level, known, want=1):
            lines = story_lines(parsed["text"])
            if len(lines) < 6:
                continue
            study = (
                study_material(level, lines)
                if use_ai
                else {"setting": "", "expressions": [], "questions": []}
            )
            article_id = re.search(r"/(\d+)\.html$", url)
            return Scene.objects.create(
                slug=f"voa-{level.lower()}-{article_id.group(1) if article_id else abs(hash(url))}",
                title=parsed["title"],
                genre="Real story" if topic == "stories" else "Real report",
                level=level,
                setting=study["setting"],
                lines=lines,
                expressions=study["expressions"],
                questions=study["questions"],
                source=Scene.Source.VOA,
                audio_url=parsed["audio_url"],
                audio_credit=voa.CREDIT,
                source_url=url,
            )
    except Exception:
        return None
    return None


STUDY_SCHEMA = {
    "type": "object",
    "required": ["expressions", "questions", "setting"],
    "properties": {
        "setting": {"type": "string"},
        "expressions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["expression", "meaning"],
                "properties": {
                    "expression": {"type": "string"},
                    "meaning": {"type": "string"},
                    "literal_trap": {"type": "string"},
                    "example": {"type": "string"},
                },
            },
        },
        "questions": {"type": "array", "items": {"type": "string"}},
    },
}


def study_prompt(level: str, lines: list[dict]) -> str:
    script = "\n".join(f"{line['speaker']}: {line['text']}" for line in lines)
    return f"""This is a real dialogue from an English-learning video, for learners at CEFR {level}.

{script}

Return JSON:
- setting: one sentence saying who is talking, where, and what is going on.
- expressions: 5 to 8 phrasal verbs, idioms or fixed expressions actually used
  above (copy them exactly), each with `meaning` in plain words for a {level}
  learner, `literal_trap` (how the words could mislead, or "" if they don't)
  and `example` (a new everyday sentence using it).
- questions: 3 to 5 comprehension questions about what happens and why.
"""


def study_material(level: str, lines: list[dict]) -> dict:
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    try:
        data = cached(
            "lle_study",
            {"level": level, "lines": lines},
            lambda: get_ai_provider().generate_json(
                study_prompt(level, lines), schema=STUDY_SCHEMA, tier=TIER_MEDIUM, temperature=0.3
            ),
        )
    except AIError:
        return {"setting": "", "expressions": [], "questions": []}
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
    return {
        "setting": str(data.get("setting") or "").strip(),
        "expressions": expressions[:8],
        "questions": [str(q) for q in data.get("questions") or [] if str(q).strip()][:5],
    }
