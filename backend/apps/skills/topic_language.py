"""The words and expressions to learn before listening to a text or starting a conversation.

Listening practice handed the learner a passage to dictate, and Talk dropped
them straight into a conversation. Neither taught anything first, so both
could only test the English the learner already had. This module supplies the
language for the topic -- vocabulary and expressions with meanings and
examples, plus a few tips -- so the exercise that follows can use it, and the
app can check whether it was used.

From the AI mentor when it can be reached, cached per topic and level so each
costs one call ever. Without a model: for conversations, the hand-written
expressions for that situation from the speaking scripts; for listening, an
honest empty result rather than invented words.
"""
from __future__ import annotations

from apps.skills.speaking_support import PHRASES, _band

KINDS = {"conversation", "listening"}


def _clean(items, limit):
    cleaned = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        meaning = str(item.get("meaning") or "").strip()
        if text and meaning:
            cleaned.append(
                {
                    "text": text[:80],
                    "meaning": meaning[:240],
                    "example": str(item.get("example") or "").strip()[:240],
                }
            )
    return cleaned[:limit]


def _conversation_fallback(scenario: str, level: str) -> dict:
    """The speaking-script expressions for this situation, without a model."""
    from apps.practice.scripts import TEMPLATES

    band_levels = {"low": ["A1", "A2"], "mid": ["B1"], "high": ["B2", "C1", "C2"]}[_band(level)]
    expressions = []
    for template in TEMPLATES:
        if template.scenario != scenario:
            continue
        pool = []
        for key in band_levels + ["B1", "A1", "B2"]:
            pool.extend(template.expressions.get(key, []))
        for text in dict.fromkeys(pool):
            expressions.append({"text": text, "meaning": "A natural phrase for this situation.", "example": ""})
    return {
        "vocabulary": [],
        "expressions": expressions[:6],
        "tips": [
            "Answer in full sentences, and add one reason or detail to each answer.",
            "If you get stuck, say one of these rather than going silent: "
            + " / ".join(PHRASES["buy_time"][_band(level)]),
        ],
        "questions": [],
        "is_fallback": True,
        "level": level,
    }


def build(*, kind: str, level: str, topic: str = "", text: str = "") -> dict:
    """Topic language for a conversation situation or a listening passage."""
    from apps.ai import prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    kind = kind if kind in KINDS else "conversation"
    empty = {"vocabulary": [], "expressions": [], "tips": [], "questions": [], "is_fallback": True, "level": level}
    if not (topic.strip() or text.strip()):
        return empty

    try:
        data = cached(
            "topic_language",
            {"kind": kind, "topic": topic.strip()[:300], "text": text.strip()[:3000], "level": level},
            lambda: get_ai_provider().generate_json(
                prompts.topic_language(kind=kind, topic=topic, text=text, level=level),
                schema=prompts.TOPIC_LANGUAGE_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.5,
            ),
        )
    except AIError:
        return _conversation_fallback(topic, level) if kind == "conversation" else empty

    result = {
        "vocabulary": _clean(data.get("vocabulary"), 8),
        "expressions": _clean(data.get("expressions"), 6),
        "tips": [str(tip).strip() for tip in data.get("tips") or [] if str(tip).strip()][:4],
        "questions": [str(q).strip() for q in data.get("questions") or [] if str(q).strip()][:4],
        "is_fallback": False,
        "level": level,
    }
    if not (result["vocabulary"] or result["expressions"]):
        return _conversation_fallback(topic, level) if kind == "conversation" else empty
    return result
