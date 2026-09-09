from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .constants import ALL_SKILLS, CEFR, Skill, cefr_index


class ImmersionLevel(models.IntegerChoices):
    """How much English-only the learner gets (master prompt s22/s23)."""

    SUPPORTED = 0, "Native-language support"
    MIXED = 1, "English + optional translation"
    ENGLISH_ONLY = 2, "English only"


class LearnerProfile(models.Model):
    """The learner's durable identity: goals, interests, preferences.

    Deliberately separate from per-skill scores (SkillProgress) so that adding
    new skills never requires a migration on this table.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learner_profile"
    )
    target_level = models.CharField(max_length=2, choices=CEFR.choices, default=CEFR.C1)
    daily_minutes = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(5), MaxValueValidator(240)]
    )
    weekly_goal_sessions = models.PositiveSmallIntegerField(default=5)
    immersion_level = models.IntegerField(
        choices=ImmersionLevel.choices, default=ImmersionLevel.MIXED
    )
    interests = models.JSONField(
        default=list, blank=True, help_text='Topic slugs, e.g. ["technology", "movies", "work"]'
    )
    priority_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Skills the learner explicitly wants prioritised, on top of measured weakness.",
    )
    preferred_study_days = models.JSONField(
        default=list, blank=True, help_text="ISO weekdays 1=Mon .. 7=Sun. Empty means every day."
    )
    preferred_study_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile<{self.user}>"

    # -- derived values ----------------------------------------------------
    @property
    def overall_level(self) -> str:
        """Median-ish level across skills. Never used to *replace* per-skill levels;
        only for display and for picking default content difficulty."""
        levels = sorted(cefr_index(sp.level) for sp in self.user.skill_progress.all())
        if not levels:
            return CEFR.B1.value
        from .constants import CEFR_ORDER

        return CEFR_ORDER[levels[len(levels) // 2]]


class SkillProgress(models.Model):
    """Per-skill proficiency. One row per (user, skill).

    `score` is a 0-100 confidence-weighted estimate maintained by ProgressService;
    `level` is the CEFR band it maps to. Both are stored rather than derived so
    that history is auditable and scoring rules can change without rewriting data.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skill_progress"
    )
    skill = models.CharField(max_length=20, choices=Skill.choices)
    level = models.CharField(max_length=2, choices=CEFR.choices, default=CEFR.B1)
    score = models.FloatField(
        default=50.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="0-100 estimate of current ability in this skill.",
    )
    confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="How much evidence backs the score. Low confidence => more assessment activities.",
    )
    attempts = models.PositiveIntegerField(default=0)
    last_practiced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "skill"], name="uniq_user_skill")]
        ordering = ["skill"]
        verbose_name_plural = "skill progress"

    def __str__(self) -> str:
        return f"{self.user}:{self.skill}={self.score:.0f}"

    @property
    def is_weak(self) -> bool:
        """Weak means "measured as weak", not merely "unmeasured".

        A brand-new learner starts every skill at the neutral 50, which is below
        the threshold. Calling all eight skills weak on day one would be both
        wrong and demoralising, so a skill only counts as weak once there is at
        least some evidence behind its score.
        """
        return self.score < 60 and self.confidence > 0

    @property
    def is_unassessed(self) -> bool:
        return self.confidence == 0


class StudySession(models.Model):
    """One study sitting. Created when a session starts, closed when it ends."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_sessions"
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    planned_minutes = models.PositiveSmallIntegerField(default=30)
    active_seconds = models.PositiveIntegerField(
        default=0, help_text="Time actually spent on activities, not wall-clock."
    )
    skill_breakdown = models.JSONField(
        default=dict, blank=True, help_text='Seconds per skill, e.g. {"listening": 300}'
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "-started_at"])]

    def __str__(self) -> str:
        return f"Session<{self.user} {self.started_at:%Y-%m-%d}>"

    @property
    def active_minutes(self) -> int:
        return round(self.active_seconds / 60)

    def complete(self) -> None:
        self.status = self.Status.COMPLETED
        self.ended_at = timezone.now()
        self.save(update_fields=["status", "ended_at"])


def default_skill_rows(user) -> list["SkillProgress"]:
    """Create the full set of skill rows for a new learner."""
    return SkillProgress.objects.bulk_create(
        [SkillProgress(user=user, skill=skill) for skill in ALL_SKILLS],
        ignore_conflicts=True,
    )
