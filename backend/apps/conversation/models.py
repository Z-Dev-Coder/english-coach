from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.profiles.constants import CEFR


class ConversationSession(models.Model):
    """One roleplay conversation, plus the feedback given afterwards.

    Feedback is stored on the session rather than generated on demand: it is
    expensive to produce, and the learner should be able to come back to it.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    scenario = models.CharField(max_length=40, default="casual")
    level = models.CharField(max_length=2, choices=CEFR.choices, default=CEFR.B1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    feedback = models.JSONField(
        default=dict, blank=True, help_text="Structured review, produced after the conversation ends."
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "-started_at"])]

    def __str__(self) -> str:
        return f"{self.scenario} with {self.user} ({self.started_at:%Y-%m-%d})"

    @property
    def learner_turns(self) -> list[str]:
        return [
            message.content
            for message in self.messages.filter(role=ConversationMessage.Role.LEARNER)
        ]

    def end(self) -> None:
        self.status = self.Status.ENDED
        self.ended_at = timezone.now()
        self.save(update_fields=["status", "ended_at"])


class ConversationMessage(models.Model):
    """One turn. Stored in full so feedback can quote what was actually said."""

    class Role(models.TextChoices):
        LEARNER = "learner", "Learner"
        PARTNER = "partner", "Conversation partner"

    session = models.ForeignKey(
        ConversationSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}"
