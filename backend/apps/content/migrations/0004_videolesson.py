import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0003_scene_audio"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VideoLesson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("video_id", models.CharField(max_length=20, unique=True)),
                ("title", models.CharField(max_length=300)),
                ("channel", models.CharField(max_length=120)),
                ("level", models.CharField(
                    choices=[("A1", "A1"), ("A2", "A2"), ("B1", "B1"), ("B2", "B2"), ("C1", "C1"), ("C2", "C2")],
                    default="B1", max_length=2,
                )),
                ("kind", models.CharField(blank=True, help_text="Conversation, street interviews, talk…", max_length=40)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("summary", models.TextField(blank=True)),
                ("expressions", models.JSONField(blank=True, default=list, help_text="[{expression, meaning, example}]")),
                ("listen_for", models.JSONField(blank=True, default=list, help_text="[{time, note}] moments worth catching.")),
                ("questions", models.JSONField(blank=True, default=list)),
                ("speaking_prompt", models.TextField(blank=True)),
                ("prepared_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["level", "id"]},
        ),
        migrations.CreateModel(
            name="VideoProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="video_progress", to=settings.AUTH_USER_MODEL,
                )),
                ("video", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="progress", to="content.videolesson",
                )),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("user", "video"), name="uniq_video_progress")],
            },
        ),
    ]
