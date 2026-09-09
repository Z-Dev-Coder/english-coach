from django.conf import settings
from django.db import models

from apps.profiles.constants import CEFR


class SpeakingScript(models.Model):
    """A level-appropriate speaking practice script.

    Two things live on this model:

    1. The script itself (roleplay setup, target expressions, lines, questions),
       which the learner can practise against here.
    2. `portable_prompt` -- the same script rendered as a self-contained block of
       text the learner can paste into ChatGPT, Gemini, or any other assistant to
       run the roleplay there. That makes the feature useful even away from this
       app, and costs nothing to produce.
    """

    class Source(models.TextChoices):
        TEMPLATE = "template", "Built-in template"
        AI = "ai", "AI generated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="speaking_scripts"
    )
    scenario = models.CharField(max_length=40)
    level = models.CharField(max_length=2, choices=CEFR.choices, default=CEFR.B1)
    title = models.CharField(max_length=200)
    setting = models.TextField(help_text="The situation, and who each side is playing.")
    goal = models.TextField(blank=True, help_text="What the learner should achieve in the roleplay.")
    target_expressions = models.JSONField(
        default=list, blank=True, help_text="Expressions the learner should try to use."
    )
    lines = models.JSONField(
        default=list,
        blank=True,
        help_text='Sample exchange: [{"speaker": "Partner"|"You", "text": "..."}]',
    )
    follow_up_questions = models.JSONField(default=list, blank=True)
    portable_prompt = models.TextField(
        help_text="Copy-paste block for practising this script with ChatGPT, Gemini, etc."
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.TEMPLATE)
    times_practiced = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.level})"
