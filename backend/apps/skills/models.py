from django.conf import settings
from django.db import models

from apps.profiles.constants import CEFR, Skill


class Passage(models.Model):
    """Text used for reading, listening and dictation.

    Shared rather than user-owned, for the same reason as Expression: the same
    passage studied by two learners is one passage. `owner` is set only for text
    a learner pasted in themselves, which stays private to them.
    """

    class Source(models.TextChoices):
        SEED = "seed", "Built-in"
        LEARNER = "learner", "Pasted by the learner"
        AI = "ai", "AI generated"
        FEED = "feed", "Ingested from a feed"

    title = models.CharField(max_length=200)
    text = models.TextField()
    level = models.CharField(max_length=2, choices=CEFR.choices, default=CEFR.B1)
    topic = models.CharField(max_length=40, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.SEED)
    source_url = models.URLField(blank=True)
    audio_url = models.URLField(blank=True, max_length=500, help_text="A real human recording of this text.")
    audio_credit = models.CharField(blank=True, max_length=120)
    word_timings = models.JSONField(
        default=list, blank=True, help_text="[[word_index, seconds]] from the recording (apps.skills.alignment)."
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="passages",
        help_text="Set only for learner-supplied text, which stays private.",
    )
    word_count = models.PositiveIntegerField(default=0)
    reading_ease = models.FloatField(
        null=True, blank=True, help_text="Flesch score, cached so lists do not recompute it."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["level", "topic"]), models.Index(fields=["owner"])]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        from .similarity import estimate_level, flesch_reading_ease, tokenize

        self.word_count = len(tokenize(self.text, expand_contractions=False))
        self.reading_ease = round(flesch_reading_ease(self.text), 1)
        if not self.level:
            self.level = estimate_level(self.text)
        super().save(*args, **kwargs)

    def sentences(self) -> list[str]:
        from .similarity import split_sentences

        return split_sentences(self.text)


class ActivityType(models.TextChoices):
    """The concrete things a learner can do.

    Each maps to exactly one skill for scoring, except the drill, which is
    scored against several — that is the point of it.
    """

    DICTATION = "dictation", "Dictation"
    SHADOWING = "shadowing", "Shadowing"
    COMPREHENSION = "comprehension", "Comprehension"
    READING = "reading", "Reading"
    WRITING = "writing", "Writing"
    SPEAKING = "speaking", "Speaking"
    DRILL = "drill", "Listen, speak, write drill"


# Which skill each activity primarily trains. The drill is handled separately
# because it credits listening, speaking and writing together.
ACTIVITY_SKILL = {
    ActivityType.DICTATION: Skill.LISTENING,
    ActivityType.SHADOWING: Skill.PRONUNCIATION,
    ActivityType.COMPREHENSION: Skill.LISTENING,
    ActivityType.READING: Skill.READING,
    ActivityType.WRITING: Skill.WRITING,
    ActivityType.SPEAKING: Skill.SPEAKING,
}

DRILL_SKILLS = (Skill.LISTENING, Skill.SPEAKING, Skill.WRITING)


class SkillAttempt(models.Model):
    """One completed activity.

    **Why one table rather than four:** listening, reading, writing and speaking
    attempts share every column that matters — who, what, how well, how long —
    and differ only in a payload that is genuinely activity-specific (word
    diffs, feedback issues, transcripts). Four near-identical tables would make
    the cross-skill queries that analytics actually needs ("accuracy by skill",
    "attempts this week") into four-way unions for no benefit.

    The activity-specific part lives in `detail`, which is written and read by
    exactly one service function per activity type, so it stays disciplined
    rather than becoming a junk drawer.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skill_attempts"
    )
    activity = models.CharField(max_length=20, choices=ActivityType.choices)
    skill = models.CharField(max_length=20, choices=Skill.choices)
    passage = models.ForeignKey(
        Passage, null=True, blank=True, on_delete=models.SET_NULL, related_name="attempts"
    )

    prompt = models.TextField(blank=True, help_text="What the learner was asked to do or repeat.")
    response = models.TextField(blank=True, help_text="What the learner produced.")
    accuracy = models.FloatField(
        null=True, blank=True, help_text="0..1 where the activity can be scored objectively."
    )
    score_delta = models.FloatField(
        default=0.0, help_text="How much this moved the skill score, before damping."
    )
    duration_ms = models.PositiveIntegerField(default=0)
    detail = models.JSONField(
        default=dict, blank=True, help_text="Activity-specific payload: diffs, feedback, transcript."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "skill", "-created_at"]),
        ]

    def __str__(self) -> str:
        score = f"{self.accuracy:.0%}" if self.accuracy is not None else "unscored"
        return f"{self.activity} by {self.user} ({score})"
