"""Turn a written choose-the-answer task into something a learner can check.

The lesson generator writes exercises as prose in a step's prompt:

    1. I need to drop ___ the post office. (by / off / in) 2. Can you pick ___ ...

Shown as text, the learner could read the options but never find out whether
they were right -- there was no answer key anywhere. This module parses that
prose into items and gets an answer key for them, once, so the page can offer
the options as choices and say right or wrong with a reason.

The key comes from the AI mentor and is cached per exercise, then stored on the
activity, so a given exercise costs one call ever. An answer that is not one of
the item's own options is discarded rather than trusted: a key that can mark a
correct choice wrong is worse than no key.
"""
from __future__ import annotations

import re

_ITEM_SPLIT = re.compile(r"(?:^|\s)(\d{1,2})[.)]\s+")
_OPTIONS = re.compile(r"\(([^()]*/[^()]*)\)\s*[.?!]?\s*$")
_BLANK = re.compile(r"_{2,}|\.{3,}|…")


def parse_choice_items(prompt: str) -> list[dict]:
    """Numbered items that end in "(a / b / c)" options, in order.

    Returns [] unless every numbered item has options: a half-parsed exercise
    would render some sentences as choices and silently drop the others.
    """
    text = (prompt or "").strip()
    if not text:
        return []

    parts = _ITEM_SPLIT.split(" " + text)
    # split -> [prefix, num, body, num, body, ...]
    bodies = [parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)]
    if len(bodies) < 2:
        return []

    items = []
    for body in bodies:
        match = _OPTIONS.search(body)
        if not match:
            return []
        options = [option.strip() for option in match.group(1).split("/") if option.strip()]
        if len(options) < 2:
            return []
        sentence = body[: match.start()].strip()
        if not _BLANK.search(sentence):
            # No gap to fill means this isn't a choose-the-word item.
            return []
        items.append({"sentence": sentence, "options": options[:5]})
    return items


# Room for both halves of an explanation: why the answer fits, and why the
# other options don't. A 240-character cap cut the second half off mid-word.
MAX_EXPLANATION = 600


def _trim(text: str) -> str:
    """Shorten only if needed, and then at a sentence end, never mid-word."""
    if len(text) <= MAX_EXPLANATION:
        return text
    cut = text[:MAX_EXPLANATION]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end > 0 else cut.rsplit(" ", 1)[0] + "…"


def apply_key(items: list[dict], key: object) -> list[dict]:
    """Attach answers and explanations, keeping only answers that are real options."""
    answers = key.get("answers") if isinstance(key, dict) else None
    if not isinstance(answers, list) or len(answers) != len(items):
        return []

    keyed = []
    for item, answer in zip(items, answers):
        if not isinstance(answer, dict):
            return []
        chosen = str(answer.get("answer") or "").strip().lower()
        match = next((option for option in item["options"] if option.lower() == chosen), None)
        if match is None:
            return []
        keyed.append(
            {
                **item,
                "answer": match,
                "explanation": _trim(str(answer.get("explanation") or "").strip()),
            }
        )
    return keyed


def answer_key(prompt: str) -> list[dict]:
    """Parsed items with answers, from the model; [] if unparseable or unavailable."""
    from apps.ai import prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached

    items = parse_choice_items(prompt)
    if not items:
        return []
    try:
        key = cached(
            "choice_answer_key",
            {"items": items},
            lambda: get_ai_provider().generate_json(
                prompts.choice_answer_key(items),
                schema=prompts.CHOICE_KEY_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.0,
            ),
        )
    except AIError:
        return []
    return apply_key(items, key)
