"""Shared vocabulary for levels and skills.

Kept in one module so every app (lessons, content, practice, review) agrees on
what a "skill" or a "CEFR level" is, and so difficulty comparisons are ordered
rather than string equality.
"""
from django.db import models


class CEFR(models.TextChoices):
    A1 = "A1", "A1 - Beginner"
    A2 = "A2", "A2 - Elementary"
    B1 = "B1", "B1 - Intermediate"
    B2 = "B2", "B2 - Upper intermediate"
    C1 = "C1", "C1 - Advanced"
    C2 = "C2", "C2 - Proficient"


CEFR_ORDER = [c.value for c in CEFR]


def cefr_index(level: str) -> int:
    """Ordinal position of a CEFR level, for difficulty comparison."""
    try:
        return CEFR_ORDER.index(level)
    except ValueError:
        return CEFR_ORDER.index(CEFR.B1)


def cefr_shift(level: str, steps: int) -> str:
    """Move a level up/down, clamped to the scale. Used for difficulty fit."""
    idx = max(0, min(len(CEFR_ORDER) - 1, cefr_index(level) + steps))
    return CEFR_ORDER[idx]


class Skill(models.TextChoices):
    LISTENING = "listening", "Listening"
    SPEAKING = "speaking", "Speaking"
    READING = "reading", "Reading"
    WRITING = "writing", "Writing"
    VOCABULARY = "vocabulary", "Vocabulary"
    GRAMMAR = "grammar", "Grammar"
    PRONUNCIATION = "pronunciation", "Pronunciation"
    FLUENCY = "fluency", "Fluency"


ALL_SKILLS = [s.value for s in Skill]

# Skills that a daily session can allocate minutes to. Grammar, pronunciation
# and fluency are trained *inside* the other activities rather than as blocks.
SCHEDULABLE_SKILLS = [
    Skill.LISTENING.value,
    Skill.SPEAKING.value,
    Skill.READING.value,
    Skill.WRITING.value,
    Skill.VOCABULARY.value,
]


class Register(models.TextChoices):
    FORMAL = "formal", "Formal"
    NEUTRAL = "neutral", "Neutral"
    CASUAL = "casual", "Casual"
    SLANG = "slang", "Slang"
    PROFESSIONAL = "professional", "Professional"
    ACADEMIC = "academic", "Academic"
