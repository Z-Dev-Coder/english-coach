from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.TextChoices):
    GRAMMAR = "grammar", "Grammar"
    VOCABULARY = "vocabulary", "Vocabulary"
    WORD_CHOICE = "word_choice", "Word choice"
    PREPOSITION = "preposition", "Preposition"
    ARTICLE = "article", "Article"
    WORD_ORDER = "word_order", "Word order"
    PRONUNCIATION = "pronunciation", "Pronunciation"
    NATURALNESS = "naturalness", "Naturalness"
    COLLOCATION = "collocation", "Collocation"
    FLUENCY = "fluency", "Fluency"
    SPELLING = "spelling", "Spelling"


# Categories reported by the model that are really one of ours under a
# different name. Normalising here keeps the bank from fragmenting into
# near-duplicate buckets that never accumulate enough evidence to act on.
CATEGORY_ALIASES = {
    "tense": Category.GRAMMAR,
    "verb_tense": Category.GRAMMAR,
    "verb": Category.GRAMMAR,
    "agreement": Category.GRAMMAR,
    "plural": Category.GRAMMAR,
    "articles": Category.ARTICLE,
    "determiner": Category.ARTICLE,
    "prepositions": Category.PREPOSITION,
    "word choice": Category.WORD_CHOICE,
    "wordchoice": Category.WORD_CHOICE,
    "lexis": Category.VOCABULARY,
    "phrasing": Category.NATURALNESS,
    "natural": Category.NATURALNESS,
    "style": Category.NATURALNESS,
    "punctuation": Category.SPELLING,
    "capitalisation": Category.SPELLING,
    "capitalization": Category.SPELLING,
    "syntax": Category.WORD_ORDER,
}


def normalize_category(value: str) -> str:
    """Map a reported category onto ours, defaulting to grammar."""
    key = (value or "").strip().lower().replace("-", "_")
    if key in dict(Category.choices):
        return key
    return CATEGORY_ALIASES.get(key, CATEGORY_ALIASES.get(key.replace("_", " "), Category.GRAMMAR))


class Mistake(models.Model):
    """A specific error this learner makes, and how often they still make it.

    Keyed on the *corrected pair*, not on a free-text description: "discussed
    about" → "discussed" is one mistake however many times it appears and
    whichever activity surfaced it. That is what makes counting meaningful, and
    counting is what lets the system resurface the things that actually persist.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Still happening"
        IMPROVING = "improving", "Improving"
        RESOLVED = "resolved", "Resolved"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mistakes"
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    incorrect = models.CharField(max_length=300, help_text="What the learner wrote or said.")
    correct = models.CharField(max_length=300, help_text="The natural version.")
    explanation = models.TextField(blank=True)
    normalized_key = models.CharField(max_length=320, db_index=True, editable=False)

    occurrences = models.PositiveIntegerField(default=0)
    times_avoided = models.PositiveIntegerField(
        default=0, help_text="Later activities where this mistake could have appeared but did not."
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurrences", "-last_seen_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "normalized_key"], name="uniq_user_mistake")
        ]
        indexes = [models.Index(fields=["user", "status", "-occurrences"])]

    def __str__(self) -> str:
        return f"{self.incorrect} → {self.correct} (×{self.occurrences})"

    def save(self, *args, **kwargs):
        self.normalized_key = build_key(self.incorrect, self.correct)
        super().save(*args, **kwargs)

    @property
    def is_persistent(self) -> bool:
        """Made repeatedly and not yet outgrown — worth interrupting a lesson for."""
        return self.occurrences >= 2 and self.status == self.Status.ACTIVE


def build_key(incorrect: str, correct: str) -> str:
    """Stable identity for a mistake, ignoring case, spacing and punctuation."""
    from apps.skills.similarity import normalize

    return f"{normalize(incorrect)}→{normalize(correct)}"[:320]


class MistakeOccurrence(models.Model):
    """One time the mistake actually happened, with its context.

    Kept separate from the counter so the learner can see *where* they made it,
    and so analytics can ask questions the counter cannot answer.
    """

    class Origin(models.TextChoices):
        WRITING = "writing", "Writing"
        CONVERSATION = "conversation", "Conversation"
        SPEAKING = "speaking", "Speaking"
        DICTATION = "dictation", "Dictation"
        REVIEW = "review", "Review"

    mistake = models.ForeignKey(Mistake, on_delete=models.CASCADE, related_name="occurrence_log")
    origin = models.CharField(max_length=16, choices=Origin.choices)
    context = models.TextField(blank=True, help_text="The sentence it appeared in.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.mistake_id} in {self.origin}"
