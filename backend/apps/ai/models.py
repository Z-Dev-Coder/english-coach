from django.conf import settings
from django.db import models


class AIRequestLog(models.Model):
    """Audit trail for AI calls: cost/latency visibility and prompt debugging.

    Kept deliberately small (no full prompt bodies by default) so the table does
    not balloon; set store_prompt=True on the call sites you are debugging.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_requests",
    )
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=128)
    tier = models.CharField(max_length=16)
    task = models.CharField(max_length=64, help_text="e.g. explain, evaluate_writing, lesson")
    duration_ms = models.PositiveIntegerField(default=0)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    prompt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["task", "-created_at"])]

    def __str__(self) -> str:
        status = "ok" if self.success else "fail"
        return f"{self.task}/{self.model} {self.duration_ms}ms {status}"


class AICache(models.Model):
    """Content-addressed cache for expensive generations.

    The key is a hash of (task, model, inputs) so identical requests -- same
    article, same difficulty, same objective -- reuse the stored result instead
    of re-running the model (master prompt sections 33-34).
    """

    key = models.CharField(max_length=64, unique=True, db_index=True)
    task = models.CharField(max_length=64)
    model = models.CharField(max_length=128)
    payload = models.JSONField()
    hits = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.task}:{self.key[:12]} ({self.hits} hits)"
