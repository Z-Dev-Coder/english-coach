from django.conf import settings
from django.db import models

from apps.vocabulary.models import VocabularyProgress


class ExerciseType(models.TextChoices):
    """How the item was tested.

    Reviews must not all be recognition (master prompt section 53). Producing an
    expression from memory is a different, harder skill than recognising it, and
    the queue deliberately mixes them.
    """

    MEET = "meet", "First encounter"
    RECALL = "recall", "Recall the meaning"
    PRODUCE = "produce", "Produce the expression"
    CLOZE = "cloze", "Fill the gap"
    USE = "use", "Use it in your own sentence"


# Which exercises count as the learner producing language rather than
# recognising it. Used to credit `successful_productions`.
PRODUCTIVE_EXERCISES = {ExerciseType.PRODUCE, ExerciseType.CLOZE, ExerciseType.USE}


class Review(models.Model):
    """An immutable log of one review.

    Stored in full — before and after values, elapsed time, how it was tested —
    so that scheduling can be audited, analytics can be recomputed, and the FSRS
    weights could later be optimised against this learner's real history.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    progress = models.ForeignKey(
        VocabularyProgress, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        choices=[(1, "Again"), (2, "Hard"), (3, "Good"), (4, "Easy")]
    )
    exercise = models.CharField(
        max_length=10, choices=ExerciseType.choices, default=ExerciseType.RECALL
    )

    state_before = models.CharField(max_length=10)
    stability_before = models.FloatField(null=True, blank=True)
    difficulty_before = models.FloatField(null=True, blank=True)
    stability_after = models.FloatField()
    difficulty_after = models.FloatField()

    elapsed_days = models.FloatField(help_text="Real days waited, which FSRS uses as evidence.")
    scheduled_days = models.PositiveIntegerField(help_text="Interval granted by this review.")
    retrievability = models.FloatField(
        help_text="Estimated recall probability at the moment of review."
    )
    duration_ms = models.PositiveIntegerField(default=0)
    reviewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-reviewed_at"]
        indexes = [models.Index(fields=["user", "-reviewed_at"])]

    def __str__(self) -> str:
        return f"{self.progress.expression} rated {self.rating} ({self.scheduled_days}d)"

    @property
    def was_successful(self) -> bool:
        return self.rating > 1
