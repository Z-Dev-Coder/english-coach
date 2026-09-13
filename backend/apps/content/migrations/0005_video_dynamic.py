import django.utils.timezone
from django.db import migrations, models


def clear_static_library(apps, schema_editor):
    # Videos used to come from a fixed list; they are now found per learner.
    apps.get_model("content", "VideoLesson").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("content", "0004_videolesson")]

    operations = [
        migrations.RunPython(clear_static_library, migrations.RunPython.noop),
        migrations.AddField(
            model_name="videolesson",
            name="description",
            field=models.TextField(blank=True, help_text="The channel's own description, from its feed."),
        ),
        migrations.AlterField(
            model_name="videolesson",
            name="listen_for",
            field=models.JSONField(blank=True, default=list, help_text="Short tasks to do while watching."),
        ),
        migrations.AddField(
            model_name="videoprogress",
            name="assigned_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="videoprogress",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
