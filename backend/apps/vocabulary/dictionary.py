"""Word lookup: normalisation, inflection guessing, and payload parsing.

Pure functions over strings and dicts. No network and no database, so the
awkward parts -- possessives, plurals, a dictionary API that returns a
different shape for half its entries -- can be tested against fixtures instead
of against the live internet.

**Everything parsed here is untrusted.** Definitions arrive from a third-party
API over the network, so they are stripped of markup, stripped of control
characters, length-capped, and never passed to a model as instructions. The
project rule is that retrieved content is data; a dictionary entry is no
different from an article body in that respect.
"""
from __future__ import annotations

import html
import re
import unicodedata

# Definitions are read in a small popover, so anything longer than this is
# noise. Capping also bounds what a hostile or broken upstream can store.
MAX_DEFINITION_CHARS = 320
MAX_EXAMPLE_CHARS = 200
MAX_SENSES = 4

# Elements whose *contents* are not text. Stripping only the tags would leave
# a stylesheet's body in the middle of a definition -- which is exactly what
# Wiktionary returned for "nightmare": "A very unpleasant dream .mw-parser-output".
_SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
# Tags become spaces, which leaves a gap before any punctuation that followed
# one. "a dream</span>." would otherwise read "a dream ."
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")
# The same substitution can leave doubled stops behind.
_REPEATED_PUNCTUATION = re.compile(r"([,.;:!?])(\s*\1)+")
_WHITESPACE = re.compile(r"\s+")
# Curly and straight quotes both appear in real text; both are apostrophes.
_APOSTROPHE = re.compile(r"[‘’ʼ']")
_SPACE = re.compile(r"\s")
# A word for our purposes may carry internal apostrophes or hyphens
# ("don't", "well-being") but nothing else.
_WORD = re.compile(r"[^a-z\-]")


def clean_text(value: object, limit: int) -> str:
    """Make third-party text safe to store and show.

    Order matters: unescape entities *before* stripping tags, or `&lt;b&gt;`
    survives as literal markup that a later render could interpret.
    """
    if not isinstance(value, str):
        return ""
    text = html.unescape(value)
    text = _SCRIPT_OR_STYLE.sub(" ", text)
    text = _TAG.sub(" ", text)
    # Control characters, including the bidirectional overrides that can make
    # displayed text read differently from what is stored.
    text = "".join(char for char in text if unicodedata.category(char)[0] != "C")
    text = _WHITESPACE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
    text = _REPEATED_PUNCTUATION.sub(r"\1", text)
    text = _WHITESPACE.sub(" ", text).strip()
    # A hard cut can leave a dangling separator or half a word's worth of
    # trailing punctuation; trim it rather than showing "a journey ,".
    return text[:limit].strip().strip(" ,;:")


def normalize_word(raw: str) -> str:
    """Reduce a clicked token to a dictionary-lookup key.

    Handles the things that actually come off a click in running text:
    surrounding punctuation, a trailing possessive, a capital at the start of a
    sentence, and curly apostrophes from smart-quoted copy.
    """
    if not isinstance(raw, str):
        return ""
    word = unicodedata.normalize("NFKC", raw).strip().lower()
    # One word only. Without this, "a bit of a nightmare" would have its spaces
    # stripped along with the other punctuation and become the nonsense key
    # "abitofanightmare" -- a guaranteed miss, cached forever, after a wasted
    # request. This function answers "which word was clicked", so anything with
    # whitespace in it is a caller error rather than a word.
    if _SPACE.search(word):
        return ""
    word = _APOSTROPHE.sub("'", word)
    # Possessives are never dictionary entries; "commute's" should find
    # "commute". Done before stripping apostrophes so "its" is left alone.
    word = re.sub(r"'s$", "", word)
    word = word.replace("'", "")
    word = _WORD.sub("", word)
    return word.strip("-")


def candidate_forms(word: str) -> list[str]:
    """The word, then plausible base forms, in the order worth trying.

    This is a deliberately small set of suffix rules rather than a real
    lemmatiser. A proper one means a dependency and a data file for a feature
    that is one hover in a reading exercise, and the upstream dictionary
    already resolves most inflections itself. These rules cover the cases it
    does not: regular plurals and past tenses of ordinary verbs.

    Wrong guesses are safe -- a candidate that is not a word simply misses, and
    the next candidate is tried.
    """
    if not word:
        return []

    forms = [word]

    def add(candidate: str) -> None:
        if len(candidate) >= 2 and candidate not in forms:
            forms.append(candidate)

    if word.endswith("ies") and len(word) > 4:
        add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 3:
        add(word[:-2])
    if word.endswith("s") and not word.endswith("ss"):
        add(word[:-1])
    if word.endswith("ed") and len(word) > 3:
        add(word[:-2])         # walked -> walk
        add(word[:-1])         # commuted -> commute
        add(word[:-3])         # stopped -> stop (doubled consonant)
    if word.endswith("ing") and len(word) > 4:
        add(word[:-3])         # walking -> walk
        add(word[:-3] + "e")   # commuting -> commute
        add(word[:-4])         # stopping -> stop
    if word.endswith("ly") and len(word) > 4:
        add(word[:-2])
    if word.endswith("er") and len(word) > 4:
        add(word[:-2])
        add(word[:-1])

    return forms


# What a learner reading a sentence is most likely to have met, in order.
# Anything not listed sits between these and the trailing group below.
_PART_RANK = {
    "noun": 0,
    "verb": 1,
    "adjective": 2,
    "adverb": 3,
    "phrase": 4,
    "preposition": 5,
    "conjunction": 6,
    "pronoun": 7,
    "determiner": 8,
    "interjection": 9,
}
# Not word senses in any useful way: Wiktionary files language codes under
# Symbol, which is why "run" opened on the ISO code for Kirundi.
_PART_LAST = {"symbol", "letter", "abbreviation", "initialism", "acronym",
              "proper noun", "numeral", "prefix", "suffix", "particle"}


def _part_rank(part: str) -> int:
    part = (part or "").lower()
    if part in _PART_LAST:
        return 100
    return _PART_RANK.get(part, 50)


def _interleave(groups: list[list[dict]], limit: int) -> list[dict]:
    """One sense from each group in turn, until `limit` is reached.

    `groups` are the senses of one part of speech each, in source order. Taking
    them round-robin means a four-slot panel shows noun *and* verb rather than
    four senses of whichever came first.
    """
    # Rank first, so the round-robin starts from the word classes a reader is
    # most likely to want. Sorting is stable, so blocks of equal rank keep the
    # order the source gave them.
    groups = sorted(groups, key=lambda group: _part_rank(group[0].get("part_of_speech", "")))

    chosen: list[dict] = []
    depth = 0
    while len(chosen) < limit:
        added = False
        for group in groups:
            if depth < len(group):
                chosen.append(group[depth])
                added = True
                if len(chosen) >= limit:
                    break
        if not added:
            break
        depth += 1
    return chosen


def parse_entries(payload: object, *, word: str) -> list[dict]:
    """Turn a dictionaryapi.dev response into our own small shape.

    That API is loosely typed in practice -- fields go missing, `meanings` can
    be absent, examples are sometimes empty strings -- so every access here is
    defensive. A malformed entry yields no senses rather than an exception,
    because a failed word lookup must never break the page it was hovered on.
    """
    if not isinstance(payload, list):
        return []

    groups: list[list[dict]] = []
    phonetic = ""

    for entry in payload:
        if not isinstance(entry, dict):
            continue
        if not phonetic:
            phonetic = clean_text(entry.get("phonetic"), 40)
            if not phonetic:
                for item in entry.get("phonetics") or []:
                    if isinstance(item, dict) and item.get("text"):
                        phonetic = clean_text(item["text"], 40)
                        break

        for meaning in entry.get("meanings") or []:
            if not isinstance(meaning, dict):
                continue
            part = clean_text(meaning.get("partOfSpeech"), 24)
            group: list[dict] = []
            for definition in meaning.get("definitions") or []:
                if not isinstance(definition, dict):
                    continue
                text = clean_text(definition.get("definition"), MAX_DEFINITION_CHARS)
                if not text:
                    continue
                group.append(
                    {
                        "part_of_speech": part,
                        "definition": text,
                        "example": clean_text(definition.get("example"), MAX_EXAMPLE_CHARS),
                    }
                )
            if group:
                groups.append(group)

    senses = _interleave(groups, MAX_SENSES)
    if not senses:
        return []

    return [{"word": word, "phonetic": phonetic, "senses": senses}]


def parse_wiktionary(payload: object, *, word: str) -> list[dict]:
    """Turn an en.wiktionary.org REST response into our shape.

    Wiktionary is the fallback rather than the first choice for one reason:
    it orders senses by etymology and history, not by how often a word is used.
    Looking up "commute" gives "to exchange substantially; to abate but not
    abolish" before "a regular journey between home and work" -- correct, and
    the wrong way round for someone reading a sentence about a train.

    It is used anyway because it is run by the Wikimedia Foundation, needs no
    key, and stays up. Definitions arrive as HTML fragments full of wiki links
    and usage-label spans, so cleaning is not optional here.
    """
    if not isinstance(payload, dict):
        return []

    groups: list[list[dict]] = []
    # English only. The same endpoint returns French, German and others for
    # words that happen to be spelled the same.
    for block in payload.get("en") or []:
        if not isinstance(block, dict):
            continue
        part = clean_text(block.get("partOfSpeech"), 24).lower()
        group: list[dict] = []
        for definition in block.get("definitions") or []:
            if not isinstance(definition, dict):
                continue
            text = clean_text(definition.get("definition"), MAX_DEFINITION_CHARS)
            # Some entries are markup only -- a label span and nothing else --
            # and clean to an empty string.
            if not text:
                continue
            examples = definition.get("examples")
            example = ""
            if isinstance(examples, list) and examples:
                example = clean_text(examples[0], MAX_EXAMPLE_CHARS)
            group.append({"part_of_speech": part, "definition": text, "example": example})
        if group:
            groups.append(group)

    senses = _interleave(groups, MAX_SENSES)
    if not senses:
        return []
    return [{"word": word, "phonetic": "", "senses": senses}]
