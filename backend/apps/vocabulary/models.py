from django.conf import settings
from django.db import models

from apps.profiles.constants import CEFR, Register


class Kind(models.TextChoices):
    """What sort of lexical item this is.

    The product deliberately favours multi-word items: "figure out" is more
    useful to a learner than "figure", and collocations are where learner
    English most often sounds unnatural.
    """

    WORD = "word", "Word"
    PHRASE = "phrase", "Phrase"
    IDIOM = "idiom", "Idiom"
    PHRASAL_VERB = "phrasal_verb", "Phrasal verb"
    COLLOCATION = "collocation", "Collocation"
    PATTERN = "pattern", "Sentence pattern"


MULTI_WORD_KINDS = {
    Kind.PHRASE,
    Kind.IDIOM,
    Kind.PHRASAL_VERB,
    Kind.COLLOCATION,
    Kind.PATTERN,
}


def normalize(text: str) -> str:
    """Key used for deduplication. Case and surrounding space are not meaning."""
    return " ".join(text.strip().lower().split())


class Expression(models.Model):
    """A word, phrase, idiom, phrasal verb, collocation or sentence pattern.

    Shared across users rather than owned by one: the same expression learned by
    two people is the same expression, and per-learner state lives in
    VocabularyProgress. That keeps the door open to multi-user without a
    migration, and means AI-generated explanations are generated once.
    """

    class Source(models.TextChoices):
        SEED = "seed", "Built-in starter set"
        LEARNER = "learner", "Added by the learner"
        AI = "ai", "AI extracted"
        CONTENT = "content", "Extracted from an article"

    text = models.CharField(max_length=200)
    normalized = models.CharField(max_length=200, db_index=True, editable=False)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PHRASE)
    meaning = models.TextField()
    part_of_speech = models.CharField(max_length=40, blank=True)
    register = models.CharField(
        max_length=20, choices=Register.choices, default=Register.NEUTRAL
    )
    cefr_level = models.CharField(max_length=2, choices=CEFR.choices, default=CEFR.B1)
    topic = models.CharField(max_length=40, blank=True)
    pronunciation = models.CharField(
        max_length=120, blank=True, help_text="IPA or a simple respelling."
    )
    collocations = models.JSONField(default=list, blank=True)
    synonyms = models.JSONField(default=list, blank=True)
    antonyms = models.JSONField(default=list, blank=True)
    common_mistake = models.TextField(
        blank=True, help_text="The mistake learners typically make with this item."
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.SEED)
    source_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["normalized"]
        constraints = [
            # Same surface form can exist as different kinds ("well" the adverb
            # vs. a fixed phrase), but not twice as the same kind.
            models.UniqueConstraint(fields=["normalized", "kind"], name="uniq_expression"),
        ]
        indexes = [models.Index(fields=["cefr_level", "topic"])]

    def __str__(self) -> str:
        return self.text

    def save(self, *args, **kwargs):
        self.normalized = normalize(self.text)
        super().save(*args, **kwargs)

    @property
    def is_multi_word(self) -> bool:
        return self.kind in MULTI_WORD_KINDS or " " in self.normalized


class ExampleSentence(models.Model):
    """A natural sentence showing the expression in use.

    Ordered, because the first example is the one shown on a flashcard and it
    should be the clearest one.
    """

    expression = models.ForeignKey(
        Expression, on_delete=models.CASCADE, related_name="examples"
    )
    text = models.TextField()
    translation = models.TextField(blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return self.text[:60]

    def cloze(self) -> str:
        """The sentence with the expression blanked out, for gap-fill practice.

        Falls back to the untouched sentence when the expression does not appear
        verbatim (an inflected form, for instance) — a gap-fill that blanks
        nothing is better than one that blanks the wrong words.
        """
        target = self.expression.text
        lowered = self.text.lower()
        index = lowered.find(target.lower())
        if index == -1:
            return self.text
        return f"{self.text[:index]}______{self.text[index + len(target):]}"


class MasteryState(models.TextChoices):
    NEW = "new", "New"
    LEARNING = "learning", "Learning"
    REVIEW = "review", "Review"
    WEAK = "weak", "Weak"
    MASTERED = "mastered", "Mastered"


# Stability thresholds, in days, that separate the states. These are display
# categories layered on top of FSRS, not inputs to it: the scheduler works from
# stability alone, and these just let the learner see where an item stands.
LEARNING_CEILING = 7.0
MASTERED_FLOOR = 180.0
WEAK_LAPSES = 3


class VocabularyProgress(models.Model):
    """One learner's memory of one expression: the FSRS state plus history."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vocabulary"
    )
    expression = models.ForeignKey(
        Expression, on_delete=models.CASCADE, related_name="learner_progress"
    )

    # --- FSRS memory state (null until the first review) ---
    stability = models.FloatField(null=True, blank=True)
    difficulty = models.FloatField(null=True, blank=True)
    due_at = models.DateTimeField(db_index=True)

    # --- History ---
    state = models.CharField(max_length=10, choices=MasteryState.choices, default=MasteryState.NEW)
    reps = models.PositiveIntegerField(default=0)
    lapses = models.PositiveIntegerField(default=0)
    successful_productions = models.PositiveIntegerField(
        default=0, help_text="Times the learner produced this from memory, not just recognised it."
    )
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    last_interval_days = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["due_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "expression"], name="uniq_user_expression")
        ]
        indexes = [models.Index(fields=["user", "due_at"]), models.Index(fields=["user", "state"])]
        verbose_name_plural = "vocabulary progress"

    def __str__(self) -> str:
        return f"{self.user}:{self.expression} ({self.state})"

    def recompute_state(self) -> str:
        """Derive the mastery label from the FSRS numbers and the lapse count.

        Weak wins over everything except New: an item you keep forgetting is the
        most important thing to know about it, however stable it looks today.
        """
        if self.reps == 0:
            return MasteryState.NEW
        if self.lapses >= WEAK_LAPSES:
            return MasteryState.WEAK
        stability = self.stability or 0
        if stability >= MASTERED_FLOOR:
            return MasteryState.MASTERED
        if stability < LEARNING_CEILING:
            return MasteryState.LEARNING
        return MasteryState.REVIEW

    @property
    def success_rate(self) -> float:
        if self.reps == 0:
            return 0.0
        return (self.reps - self.lapses) / self.reps
