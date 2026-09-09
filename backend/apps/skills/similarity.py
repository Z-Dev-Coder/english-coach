"""Comparing what the learner produced against what was expected.

Pure functions: no Django, no database. Used by dictation, shadowing and the
Listen-Speak-Write drill, all of which need the same question answered — how
close was that, and *which words* were wrong?

Design note: a single similarity percentage is nearly useless to a learner.
"You scored 82%" teaches nothing; "you wrote 'realise' where the sentence said
'realised'" teaches the past tense. So the primary output here is a word-level
diff, and the score is derived from it rather than the other way round.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

# Contractions are expanded in two passes, because the apostrophe carries real
# information.
#
# Pass 1 runs while apostrophes are still present, which makes these
# unambiguous: "it's" can only be "it is".
APOSTROPHE_CONTRACTIONS = {
    "can't": "can not",
    "won't": "will not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "wouldn't": "would not",
    "couldn't": "could not",
    "shouldn't": "should not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "it's": "it is",
    "that's": "that is",
    "what's": "what is",
    "there's": "there is",
    "let's": "let us",
    "i'm": "i am",
    "i've": "i have",
    "i'll": "i will",
    "i'd": "i would",
    "you're": "you are",
    "you've": "you have",
    "we're": "we are",
    "we've": "we have",
    "we'll": "we will",
    "they're": "they are",
    "they've": "they have",
    "he's": "he is",
    "she's": "she is",
    "cannot": "can not",
}

# Pass 2 runs after apostrophes are stripped, catching learners and speech
# recognition engines that omit them entirely.
#
# It deliberately excludes forms that collide with real words: "its"
# (possessive), "ill" (sick), "id", "well", "were", "shed", "hed". Expanding
# those would corrupt correct text, which is worse than missing a match — and
# pass 1 already handles them whenever the apostrophe is actually typed.
BARE_CONTRACTIONS = {
    "cant": "can not",
    "wont": "will not",
    "dont": "do not",
    "doesnt": "does not",
    "didnt": "did not",
    "isnt": "is not",
    "arent": "are not",
    "wasnt": "was not",
    "werent": "were not",
    "wouldnt": "would not",
    "couldnt": "could not",
    "shouldnt": "should not",
    "havent": "have not",
    "hasnt": "has not",
    "hadnt": "had not",
    "thats": "that is",
    "whats": "what is",
    "theres": "there is",
    "lets": "let us",
    "im": "i am",
    "ive": "i have",
    "youre": "you are",
    "youve": "you have",
    "theyre": "they are",
    "theyve": "they have",
    "weve": "we have",
}

_APOSTROPHE = re.compile(r"['’ʼ]")
_PUNCTUATION = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")
_APOSTROPHE_WORD = re.compile(
    # Longest first, so "shouldn't" is never partially matched by a shorter key.
    r"\b("
    + "|".join(re.escape(key) for key in sorted(APOSTROPHE_CONTRACTIONS, key=len, reverse=True))
    + r")\b"
)


def normalize(text: str, *, expand_contractions: bool = True) -> str:
    """Reduce text to what actually matters for comparison.

    Case, punctuation and accents are stripped: a learner typing a dictation
    should not lose marks for a missing comma, which is a different skill from
    hearing the words. Contraction spelling does not count against them either.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    # Curly apostrophes are everywhere in pasted text and phone keyboards.
    text = _APOSTROPHE.sub("'", text.lower().strip())

    if expand_contractions:
        text = _APOSTROPHE_WORD.sub(lambda match: APOSTROPHE_CONTRACTIONS[match.group(0)], text)

    # Delete remaining apostrophes rather than replacing them with a space:
    # "didn t" could no longer be matched as one word.
    text = _APOSTROPHE.sub("", text)
    text = _PUNCTUATION.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()

    if expand_contractions and text:
        text = " ".join(BARE_CONTRACTIONS.get(word, word) for word in text.split())

    return text


def tokenize(text: str, **kwargs) -> list[str]:
    normalized = normalize(text, **kwargs)
    return normalized.split() if normalized else []


class Op(str, Enum):
    CORRECT = "correct"
    WRONG = "wrong"      # said something else
    MISSING = "missing"  # left a word out
    EXTRA = "extra"      # added a word that was not there


@dataclass
class DiffToken:
    op: Op
    expected: str = ""
    actual: str = ""


@dataclass
class Comparison:
    """The result of comparing an attempt with the expected text."""

    accuracy: float                      # 0..1, word-level
    tokens: list[DiffToken] = field(default_factory=list)
    expected_words: int = 0
    correct_words: int = 0

    @property
    def percentage(self) -> int:
        return round(self.accuracy * 100)

    @property
    def is_perfect(self) -> bool:
        """No mistakes of any kind — not merely a high score."""
        return not self.mistakes

    @property
    def mistakes(self) -> list[DiffToken]:
        return [token for token in self.tokens if token.op != Op.CORRECT]

    def summary(self) -> str:
        """One short line a learner can act on."""
        if self.is_perfect:
            return "Word perfect."
        missing = sum(1 for token in self.tokens if token.op == Op.MISSING)
        wrong = sum(1 for token in self.tokens if token.op == Op.WRONG)
        extra = sum(1 for token in self.tokens if token.op == Op.EXTRA)
        parts = []
        if wrong:
            parts.append(f"{wrong} word{'s' if wrong > 1 else ''} different")
        if missing:
            parts.append(f"{missing} missed")
        if extra:
            parts.append(f"{extra} extra")
        return ", ".join(parts).capitalize() or "Close."


def compare(expected: str, actual: str, **kwargs) -> Comparison:
    """Word-level diff of an attempt against the expected text.

    Uses difflib's sequence matcher so a single dropped word shifts the
    alignment rather than marking everything after it wrong — which is what a
    naive position-by-position comparison would do, and would be both incorrect
    and demoralising.
    """
    expected_words = tokenize(expected, **kwargs)
    actual_words = tokenize(actual, **kwargs)

    if not expected_words:
        return Comparison(accuracy=1.0 if not actual_words else 0.0, expected_words=0)

    matcher = difflib.SequenceMatcher(None, expected_words, actual_words, autojunk=False)
    tokens: list[DiffToken] = []
    correct = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for word in expected_words[i1:i2]:
                tokens.append(DiffToken(Op.CORRECT, word, word))
            correct += i2 - i1
        elif tag == "replace":
            # Pair them up so the learner sees what they said instead.
            for offset in range(max(i2 - i1, j2 - j1)):
                tokens.append(
                    DiffToken(
                        Op.WRONG,
                        expected_words[i1 + offset] if i1 + offset < i2 else "",
                        actual_words[j1 + offset] if j1 + offset < j2 else "",
                    )
                )
        elif tag == "delete":
            for word in expected_words[i1:i2]:
                tokens.append(DiffToken(Op.MISSING, word, ""))
        elif tag == "insert":
            for word in actual_words[j1:j2]:
                tokens.append(DiffToken(Op.EXTRA, "", word))

    # Divide by the LONGER of the two, so padding an answer with extra words
    # cannot score full marks. Dividing by the expected length alone measures
    # recall only, and would give "a b c" 100% against an expected "a c".
    denominator = max(len(expected_words), len(actual_words))
    return Comparison(
        accuracy=correct / denominator if denominator else 1.0,
        tokens=tokens,
        expected_words=len(expected_words),
        correct_words=correct,
    )


def similarity(a: str, b: str) -> float:
    """Character-level closeness, 0..1.

    Complements `compare`: it catches near-misses inside a single word
    ("realise" vs "realised") that word-level matching scores as a flat miss.
    """
    normalized_a, normalized_b = normalize(a), normalize(b)
    if not normalized_a and not normalized_b:
        return 1.0
    return difflib.SequenceMatcher(None, normalized_a, normalized_b).ratio()


# --- Readability -----------------------------------------------------------
_SENTENCE_END = re.compile(r"[.!?]+")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def count_syllables(word: str) -> int:
    """Approximate syllable count. Good enough for a difficulty estimate.

    Deliberately simple: exact syllabification needs a pronunciation dictionary,
    and this estimate only has to be stable enough to rank passages.
    """
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    count = len(_VOWEL_GROUP.findall(word))
    # A trailing silent "e" is not a syllable, unless it is the only vowel.
    if word.endswith("e") and count > 1 and not word.endswith(("le", "ee")):
        count -= 1
    return max(1, count)


def flesch_reading_ease(text: str) -> float:
    """Classic readability score. Higher is easier; roughly 0-100."""
    sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
    words = tokenize(text, expand_contractions=False)
    if not sentences or not words:
        return 100.0
    syllables = sum(count_syllables(word) for word in words)
    return 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))


# Flesch bands mapped onto CEFR. Approximate by nature — readability formulas
# know nothing about idiom or topic familiarity — so this is a starting estimate
# that AI or learner feedback can override, never a verdict.
FLESCH_TO_CEFR = (
    (90, "A1"),
    (80, "A2"),
    (65, "B1"),
    (50, "B2"),
    (30, "C1"),
)


def estimate_level(text: str) -> str:
    score = flesch_reading_ease(text)
    for threshold, level in FLESCH_TO_CEFR:
        if score >= threshold:
            return level
    return "C2"


def split_sentences(text: str) -> list[str]:
    """Split into sentences, keeping their end punctuation."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]
