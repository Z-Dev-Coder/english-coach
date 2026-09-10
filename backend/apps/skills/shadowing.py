"""Turn a sentence into a shadowing guide: where to stop, what to stress, where the pitch moves.

Shadowing means speaking along with a recording a beat behind it. The thing
that makes it hard for a learner is not the words -- it is that fluent English
is delivered in chunks with stress and pitch on top, and a beginner tries to
say it one flat word at a time. So the guide has to answer three questions the
raw text does not:

  where do I stop      -- chunk boundaries, sized to the learner's level
  what do I hit        -- which syllables carry the beat
  where does pitch go  -- rising to signal "not finished", falling to close

All pure functions over a string. No AI: chunking and stress in English follow
regular rules that a model would only approximate more expensively and less
predictably, and this runs on every sentence of every passage.

The rules here are deliberately the well-established ones -- content words take
stress, function words do not; non-final chunks rise, final statements fall --
rather than anything invented. They are approximations, and they are the same
approximations a teacher writes on a whiteboard.
"""
from __future__ import annotations

import re

# Roughly how many words a learner can hold and reproduce in one breath group.
# Lower levels get shorter chunks: the point is to succeed at a phrase, not to
# fail at a sentence.
WORDS_PER_CHUNK = {
    "A1": 3,
    "A2": 4,
    "B1": 6,
    "B2": 8,
    "C1": 11,
    "C2": 14,
}

# Function words. English rhythm puts the beats on the words that carry
# meaning and reduces everything else -- that reduction is most of what makes
# a learner sound non-native, and it is invisible in the spelling.
FUNCTION_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "so", "yet", "for",
    "at", "by", "in", "of", "off", "on", "to", "up", "as", "into", "onto",
    "from", "with", "without", "about", "over", "under", "than", "then",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "this", "that",
    "these", "those", "there", "here", "who", "whom", "whose",
    "if", "when", "while", "because", "that", "not", "no",
}

# Natural places to break a long chunk, in the order a speaker would.
BREAK_BEFORE = {
    "and", "but", "or", "so", "because", "which", "who", "that", "when",
    "while", "if", "before", "after", "until", "unless", "although",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:—–])\s+")
_WORD = re.compile(r"[A-Za-z'’-]+")

# Pause lengths in milliseconds, as a hint to the UI rather than a promise of
# timing accuracy.
PAUSE_WITHIN_SENTENCE = 250
PAUSE_AT_CLAUSE = 400
PAUSE_AT_SENTENCE = 700

# A chunk shorter than this reads as a stumble rather than a phrase.
MIN_TAIL_WORDS = 3


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _split_long(piece: str, limit: int) -> list[str]:
    """Break an over-long piece at the most natural point available.

    Prefers a conjunction, because that is where a speaker would draw breath.
    Falls back to splitting near the middle -- an awkward chunk is still better
    than one the learner cannot hold.
    """
    tokens = piece.split()
    if len(tokens) <= limit:
        return [piece]

    for index in range(limit, 0, -1):
        if index < len(tokens) and tokens[index].strip(",.;:!?").lower() in BREAK_BEFORE:
            head = " ".join(tokens[:index])
            return [head] + _split_long(" ".join(tokens[index:]), limit)

    # No conjunction to break at, so split on length -- but never leave an
    # orphan. Cutting "...say what they / mean" strands the verb in a chunk of
    # its own, which teaches the opposite of chunking: the learner practises a
    # pause exactly where a speaker would not take one.
    split = limit
    if 0 < len(tokens) - split < MIN_TAIL_WORDS:
        split = max(2, len(tokens) - MIN_TAIL_WORDS)

    head = " ".join(tokens[:split])
    return [head] + _split_long(" ".join(tokens[split:]), limit)


def stressed_indices(chunk: str) -> list[int]:
    """Which words in the chunk carry a beat.

    Content words, with one guard: if the rule marks nothing -- a chunk of pure
    function words like "and then it was" -- the last word takes the beat, so
    every chunk has something to hit rather than being read flat.
    """
    words = _words(chunk)
    marked = [
        index
        for index, word in enumerate(words)
        if word.lower().strip("'’-") not in FUNCTION_WORDS and len(word) > 1
    ]
    if not marked and words:
        return [len(words) - 1]
    return marked


def intonation_for(chunk: str, *, is_final: bool) -> str:
    """Which way the pitch moves at the end of this chunk.

    The two rules worth teaching: a question that can be answered yes or no
    rises; everything else falls at the end of a sentence, and rises slightly
    mid-sentence to signal there is more coming.
    """
    stripped = chunk.strip()
    if stripped.endswith("?"):
        first = (_words(stripped) or [""])[0].lower()
        # Wh- questions fall; yes/no questions rise. Getting this backwards is
        # one of the most audible non-native patterns there is.
        if first in {"what", "where", "when", "why", "who", "whom", "whose", "which", "how"}:
            return "fall"
        return "rise"
    if not is_final:
        return "rise"
    return "fall"


def build_guide(text: str, *, level: str = "B1") -> dict:
    """The full shadowing guide for a passage or sentence."""
    limit = WORDS_PER_CHUNK.get((level or "B1").upper(), WORDS_PER_CHUNK["B1"])

    sentences = [s for s in _SENTENCE_SPLIT.split((text or "").strip()) if s.strip()]
    chunks: list[dict] = []

    for sentence_index, sentence in enumerate(sentences):
        pieces: list[str] = []
        for clause in _CLAUSE_SPLIT.split(sentence):
            clause = clause.strip()
            if clause:
                pieces.extend(_split_long(clause, limit))

        for piece_index, piece in enumerate(pieces):
            last_in_sentence = piece_index == len(pieces) - 1
            ends_clause = piece.rstrip().endswith((",", ";", ":", "—", "–"))

            if last_in_sentence:
                pause = PAUSE_AT_SENTENCE
            elif ends_clause:
                pause = PAUSE_AT_CLAUSE
            else:
                pause = PAUSE_WITHIN_SENTENCE

            chunks.append(
                {
                    "text": piece,
                    "words": _words(piece),
                    "stress": stressed_indices(piece),
                    "intonation": intonation_for(piece, is_final=last_in_sentence),
                    "pause_ms": pause,
                    "sentence": sentence_index,
                }
            )

    return {
        "level": (level or "B1").upper(),
        "words_per_chunk": limit,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
