"""Look a word up, cheaply and without ever failing loudly.

Lookup order, and why:

1. **Our own expressions.** If the learner has already met this word in the
   app, the curated meaning beats a general dictionary's: it is written at
   their level and carries the register.
2. **The local cache.** One row per word, forever, including genuine misses.
3. **dictionaryapi.dev**, then **en.wiktionary.org**. Both are free and need
   no key or account, which is what keeps this inside the project's
   zero-recurring-cost rule.

Two sources rather than one because the first is a hobby project that was
returning nothing at all when this was written, while Wiktionary is run by the
Wikimedia Foundation and stays up. The order is not reliability though -- it is
sense ordering. dictionaryapi.dev leads with the common meaning; Wiktionary
orders by etymology, so "commute" starts at "to exchange substantially" and
reaches "a regular journey between home and work" several senses later. For
someone reading a sentence about a train, that is the wrong way round, so the
better-ordered source is asked first and the reliable one catches the failures.

Deliberately *not* the language model. A definition is a lookup, not a
generation: the model would be slower, would cost tokens on every hover, and
could invent a plausible meaning for a word it does not know -- the one failure
this feature must not have.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import quote

import requests
from django.db import IntegrityError

from .dictionary import (
    candidate_forms,
    candidate_phrases,
    clean_text,
    normalize_phrase,
    normalize_word,
    parse_entries,
    parse_wiktionary,
)
from .models import Expression, WordDefinition

logger = logging.getLogger(__name__)

DICTIONARY_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
WIKTIONARY_URL = "https://en.wiktionary.org/api/rest_v1/page/definition/{word}"
USER_AGENT = "EnglishCoach/1.0 (personal learning app)"
# Short, because this runs while someone is hovering a word: a definition that
# arrives after they have moved on is worse than none.
FETCH_TIMEOUT = 4


class Unreachable(Exception):
    """The source could not be asked -- as distinct from having no such word.

    The difference matters more than it looks. A word the dictionary genuinely
    does not have should be cached as a miss, so it is never looked up again.
    A word we simply could not ask about must not be, or one flaky minute
    poisons the cache permanently and the word stays undefined forever.
    """


# How long a source stays "skip it" once it has been tripped. Long enough that a
# sustained outage costs one timeout every few minutes rather than one per word;
# short enough that it heals without anyone restarting anything.
FAILURE_COOLDOWN = 300

# One timeout is ordinary internet weather. Tripping a source on a single slow
# response took a healthy dictionary offline for five minutes at a time.
FAILURES_BEFORE_COOLDOWN = 2

# Deliberately in-process rather than in the shared cache. This is a personal
# app on one server, the state is a latency optimisation rather than
# correctness, and losing it on restart is harmless: the worst case is one slow
# lookup. Anything more durable would be machinery for no benefit.
_last_failure: dict[str, float] = {}
_consecutive_failures: dict[str, int] = {}


def _recently_failed(url: str) -> bool:
    if _consecutive_failures.get(url, 0) < FAILURES_BEFORE_COOLDOWN:
        return False
    failed_at = _last_failure.get(url)
    return failed_at is not None and (time.monotonic() - failed_at) < FAILURE_COOLDOWN


def _note_failure(url: str) -> None:
    _last_failure[url] = time.monotonic()
    _consecutive_failures[url] = _consecutive_failures.get(url, 0) + 1


def _note_success(url: str) -> None:
    _last_failure.pop(url, None)
    _consecutive_failures.pop(url, None)


def _get_json(url: str, word: str) -> object:
    """Fetch and decode, mapping every transport problem onto Unreachable."""
    try:
        response = requests.get(
            # Wiktionary paths use underscores for spaces; dictionaryapi.dev
            # tolerates them in the same position, so one substitution serves
            # both rather than each source needing its own URL builder.
            url.format(word=quote(word.replace(" ", "_"))),
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
    except requests.RequestException as exc:
        logger.info("Lookup of %r could not reach %s: %s", word, url, exc)
        raise Unreachable from exc

    # 404 is the ordinary "no such word" for both sources, and is an answer.
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        logger.info("Lookup of %r returned %s", word, response.status_code)
        raise Unreachable

    try:
        return response.json()
    except ValueError as exc:
        logger.info("Lookup of %r returned non-JSON", word)
        raise Unreachable from exc


def _fetch(word: str) -> list[dict]:
    """Ask each source in turn for one word.

    Returns the parsed entries, or raises Unreachable if no source could be
    asked at all. An empty list means the sources answered and none knew the
    word.

    A source that has just failed is skipped rather than retried. Without this,
    a source being down costs its full timeout on *every* lookup before the
    working source is even tried -- measured at over four seconds per word
    while dictionaryapi.dev was unreachable, for a panel that opens under the
    pointer. One failure buys a few minutes of not asking again, which brings
    the same lookup back under half a second.
    """
    sources = ((DICTIONARY_URL, parse_entries), (WIKTIONARY_URL, parse_wiktionary))

    live = [source for source in sources if not _recently_failed(source[0])]
    # The cooldown exists to skip *past* a dead source to a live one. With none
    # left it would instead mean answering "no dictionary" without asking
    # anyone, so fall back to trying everything. A slow lookup is worth more
    # than a confident wrong answer.
    if not live:
        live = list(sources)

    reachable = False
    for url, parse in live:
        try:
            payload = _get_json(url, word)
        except Unreachable:
            _note_failure(url)
            continue
        _note_success(url)
        reachable = True
        if payload is None:
            continue
        entries = parse(payload, word=word)
        if entries:
            return entries

    if not reachable:
        raise Unreachable
    return []


def _from_expression(word: str) -> list[dict] | None:
    """Our own curated entry, if this word is one we teach."""
    expression = Expression.objects.filter(normalized=word).order_by("id").first()
    if expression is None:
        return None

    sense = {
        "part_of_speech": expression.part_of_speech,
        "definition": expression.meaning,
        "example": "",
    }
    example = expression.examples.order_by("position").first()
    if example is not None:
        sense["example"] = clean_text(example.text, 200)

    return [
        {
            "word": expression.text,
            "phonetic": expression.pronunciation,
            "senses": [sense],
            "register": expression.register,
            "cefr_level": expression.cefr_level,
        }
    ]


def _miss(word: str, *, source: str = "none") -> dict:
    return {"word": word, "found": False, "entries": [], "source": source}


def look_up(raw_word: str) -> dict:
    """Resolve a clicked token to a definition.

    Always returns the same shape, so the caller never has to branch on
    whether the word was found.
    """
    # A phrase if it has a space, a word otherwise. Both end up in the same
    # cache, so an expression looked up here is free on the next lesson too.
    word = normalize_word(raw_word) or normalize_phrase(raw_word)
    if not word or len(word) > 64:
        return _miss(raw_word)
    is_phrase = " " in word

    own = _from_expression(word)
    if own is not None:
        return {"word": word, "found": True, "entries": own, "source": "app"}

    cached = WordDefinition.objects.filter(word=word).first()
    if cached is not None:
        return {
            "word": word,
            "found": cached.found,
            "entries": cached.entries,
            "source": cached.source,
        }

    # The word as written first, then plausible base forms. Most hits are on
    # the first try; the rest are what makes "commuting" work.
    entries: list[dict] = []
    matched = word
    for candidate in (candidate_phrases(word) if is_phrase else candidate_forms(word)):
        try:
            found = _fetch(candidate)
        except Unreachable:
            # Nothing was reachable. Answer honestly for this hover and write
            # nothing, so the word is tried again once the network is back.
            return _miss(word, source="unavailable")
        if isinstance(found, list) and found:
            entries = found
            matched = candidate
            break

    # Stored under the word as clicked, so the next hover on this exact token
    # is a cache hit whichever base form actually matched.
    try:
        WordDefinition.objects.create(
            word=word,
            entries=entries,
            source="dictionary" if entries else "none",
        )
    except IntegrityError:
        # Two hovers raced. The other wrote the same thing; nothing to do.
        pass

    return {
        "word": matched,
        "found": bool(entries),
        "entries": entries,
        "source": "dictionary" if entries else "none",
    }
