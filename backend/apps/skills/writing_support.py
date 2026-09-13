"""What a learner needs before writing on a topic, and whether they used it.

A writing prompt on its own -- "Write a short message asking a colleague to
postpone a meeting" -- tells a learner what to write and nothing about how. They
fall back on the English they already have, which is exactly the English they
came here to move past. So each writing task becomes a lesson: topic
vocabulary, phrasal verbs, expressions, sentence patterns, a paragraph plan and
a model text -- and then the learner writes, and the app checks which of those
items they actually used.

The check is the point. Teaching language and then accepting any text at all
lets the lesson and the exercise drift apart; counting what was used ties the
exercise to what was taught and tells the learner what to try next.
"""
from __future__ import annotations

import re

from apps.skills.similarity import normalize

# Used when no model is reachable: structure and functional language that fit
# almost any short text. Honest about being general -- the topic-specific lists
# stay empty rather than being invented.
FALLBACK = {
    "genre": "",
    "vocabulary": [],
    "phrasal_verbs": [],
    "expressions": [
        {"text": "I'm writing to", "meaning": "a clear way to start by saying why you are writing.",
         "example": "I'm writing to ask about the meeting on Friday."},
        {"text": "as far as I know", "meaning": "based on the information I have.",
         "example": "As far as I know, the office is closed on Monday."},
        {"text": "on the other hand", "meaning": "introduces a different point of view.",
         "example": "It's cheap. On the other hand, it's quite far away."},
        {"text": "let me know", "meaning": "tell me (a friendly way to ask for a reply).",
         "example": "Let me know if Thursday works for you."},
    ],
    "sentence_patterns": [
        {"pattern": "I was wondering if you could ...", "use": "a polite request",
         "example": "I was wondering if you could send me the file."},
        {"pattern": "The main reason is that ...", "use": "explaining why",
         "example": "The main reason is that the train was cancelled."},
        {"pattern": "If ..., I'll ...", "use": "a plan or promise",
         "example": "If you're free, I'll call you at six."},
    ],
    "plan": [
        {"part": "Opening", "what_to_write": "Say why you are writing, in one sentence.",
         "starter": "I'm writing to ..."},
        {"part": "Main point", "what_to_write": "Give the details and your reasons.",
         "starter": "The main reason is that ..."},
        {"part": "Closing", "what_to_write": "Say what you want to happen next.",
         "starter": "Let me know ..."},
    ],
    "model_text": "",
    "style_tips": [
        "Keep sentences short and clear; one idea per sentence.",
        "Match the tone to the reader: friendly for a friend, polite for work.",
    ],
    "word_target": 80,
}


def _clean_items(items, limit):
    cleaned = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        meaning = str(item.get("meaning") or "").strip()
        if text and meaning:
            cleaned.append({
                "text": text[:80],
                "meaning": meaning[:240],
                "example": str(item.get("example") or "").strip()[:240],
            })
    return cleaned[:limit]


def build_lesson(*, task: str, level: str) -> dict:
    """The writing lesson for a task, from the model when it can be reached.

    Cached on task and level, so a given prompt costs one call ever.
    """
    from apps.ai import prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    if not task.strip():
        return {**FALLBACK, "is_fallback": True, "level": level}

    try:
        data = cached(
            "writing_lesson",
            {"task": task.strip(), "level": level},
            lambda: get_ai_provider().generate_json(
                prompts.writing_lesson(task=task, level=level),
                schema=prompts.WRITING_LESSON_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.6,
            ),
        )
    except AIError:
        return {**FALLBACK, "is_fallback": True, "level": level}

    lesson = {
        "genre": str(data.get("genre") or "").strip()[:40],
        "vocabulary": _clean_items(data.get("vocabulary"), 8),
        "phrasal_verbs": _clean_items(data.get("phrasal_verbs"), 5),
        "expressions": _clean_items(data.get("expressions"), 6),
        "sentence_patterns": [
            {
                "pattern": str(item.get("pattern") or "").strip()[:120],
                "use": str(item.get("use") or "").strip()[:160],
                "example": str(item.get("example") or "").strip()[:240],
            }
            for item in data.get("sentence_patterns") or []
            if isinstance(item, dict) and item.get("pattern")
        ][:4],
        "plan": [
            {
                "part": str(item.get("part") or "").strip()[:60],
                "what_to_write": str(item.get("what_to_write") or "").strip()[:240],
                "starter": str(item.get("starter") or "").strip()[:160],
            }
            for item in data.get("plan") or []
            if isinstance(item, dict) and item.get("part")
        ][:6],
        "model_text": str(data.get("model_text") or "").strip(),
        "style_tips": [str(tip).strip() for tip in data.get("style_tips") or [] if str(tip).strip()][:4],
        "word_target": data.get("word_target") if isinstance(data.get("word_target"), int) else 80,
        "is_fallback": False,
        "level": level,
    }
    if not (lesson["vocabulary"] or lesson["expressions"]) or not lesson["plan"]:
        return {**FALLBACK, "is_fallback": True, "level": level}
    return lesson


# Words a learner is free to change when using a taught item: "pick up" still
# counts as "picked up", "an issue" as "the issue". Ellipses in patterns
# ("I was wondering if you could ...") mark where their own words go.
_DROPPABLE = {"a", "an", "the", "my", "your", "his", "her", "our", "their", "sb", "sth", "someone", "something"}


def _stem(word: str) -> str:
    for suffix in ("ing", "ied", "ies", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _key_words(item: str) -> list[str]:
    item = re.sub(r"\.\.\.|…", " ", item)
    words = normalize(item, expand_contractions=False).split()
    return [_stem(word) for word in words if word not in _DROPPABLE]


def used_items(text: str, items: list[str]) -> list[str]:
    """Which taught items appear in the learner's text.

    Matched on stems and in order, allowing a few words in between, so natural
    use counts: "we could put the meeting off" uses "put off". A strict string
    match would mark correct use of a phrasal verb as missing, which punishes
    exactly the thing the lesson taught.
    """
    words = [_stem(word) for word in normalize(text or "", expand_contractions=False).split()]
    used = []
    for item in items:
        keys = _key_words(item)
        if not keys:
            continue
        position = 0
        found = True
        for index, key in enumerate(keys):
            window = words[position:] if index == 0 else words[position:position + 4]
            try:
                offset = window.index(key)
            except ValueError:
                found = False
                break
            position += offset + 1
        if found:
            used.append(item)
    return used
