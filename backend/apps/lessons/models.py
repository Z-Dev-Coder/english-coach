from django.conf import settings
from django.db import models
from django.utils import timezone


class Lesson(models.Model):
    """One day's plan, made concrete.

    The planner (apps.profiles) decides how many minutes each skill gets. A
    Lesson turns that allocation into specific things to do, and remembers what
    was done.

    One *unfinished* lesson per learner, not one per day. An unfinished plan
    waits however long it takes to come back to -- a week off should not cost
    the learner their place, and keying this to the date meant every skipped
    morning silently threw away a half-finished plan and minted another. A new
    lesson is built only when the last one is complete.
    """

    class Status(models.TextChoices):
        READY = "ready", "Ready"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        # Started, never finished, and superseded. Kept rather than deleted:
        # these rows are the history that stops the next lesson handing out
        # material the learner has already seen. Calling them "completed"
        # would be simpler and would misreport what the learner actually did.
        ABANDONED = "abandoned", "Abandoned"

    class Origin(models.TextChoices):
        TEMPLATE = "template", "Built from the plan"
        AI = "ai", "AI enriched"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lessons"
    )
    date = models.DateField(default=timezone.localdate)
    title = models.CharField(max_length=200)
    theme = models.TextField(blank=True)
    encouragement = models.TextField(blank=True)
    total_minutes = models.PositiveSmallIntegerField(default=30)
    focus_skills = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.READY)
    origin = models.CharField(max_length=16, choices=Origin.choices, default=Origin.TEMPLATE)
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="The learner state this lesson was generated from, kept for auditing.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            # The real invariant, and still the thing that closes the race the
            # per-day constraint existed for: two simultaneous requests cannot
            # both create a plan. Per-day would now also block a learner who
            # finishes early from starting another on the same day.
            models.UniqueConstraint(
                fields=["user"],
                condition=~models.Q(status__in=["completed", "abandoned"]),
                name="uniq_unfinished_lesson_per_user",
            )
        ]
        indexes = [models.Index(fields=["user", "-date"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.date})"

    @property
    def progress(self) -> float:
        activities = list(self.activities.all())
        if not activities:
            return 0.0
        done = sum(1 for activity in activities if activity.completed_at)
        return done / len(activities)

    def refresh_status(self) -> str:
        """Keep status in step with the activities, without a separate write path.

        Counts in the database rather than through `self.progress`. That
        property reads `self.activities.all()`, which is the *prefetched* list
        whenever the lesson was loaded with `prefetch_related` -- captured
        before the activity that triggered this was saved. It therefore counted
        one short on the final activity, and a fully finished lesson sat in
        "in progress" forever.
        """
        totals = self.activities.aggregate(
            total=models.Count("id"),
            done=models.Count("id", filter=models.Q(completed_at__isnull=False)),
        )
        progress = (totals["done"] / totals["total"]) if totals["total"] else 0.0

        if progress >= 1.0:
            self.status = self.Status.COMPLETED
            self.completed_at = self.completed_at or timezone.now()
        elif progress > 0:
            self.status = self.Status.IN_PROGRESS
        else:
            self.status = self.Status.READY
        self.save(update_fields=["status", "completed_at"])
        return self.status


class LessonActivity(models.Model):
    """One thing to do inside a lesson.

    `route` and `params` tell the frontend where to send the learner rather than
    the activity carrying its own bespoke UI. That keeps new activity kinds from
    requiring a new screen each time.
    """

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="activities")
    position = models.PositiveSmallIntegerField(default=0)
    kind = models.CharField(max_length=20, help_text="review, listening, reading, writing, …")
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    minutes = models.PositiveSmallIntegerField(default=5)
    prompt = models.TextField(blank=True, help_text="Writing or speaking prompt, when needed.")
    target_expressions = models.JSONField(default=list, blank=True)
    route = models.CharField(
        max_length=64, blank=True, help_text="Frontend path that runs this activity."
    )
    params = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name_plural = "lesson activities"

    def __str__(self) -> str:
        return f"{self.kind}: {self.title}"

    def complete(self) -> None:
        if not self.completed_at:
            self.completed_at = timezone.now()
            self.save(update_fields=["completed_at"])
        self.lesson.refresh_status()
