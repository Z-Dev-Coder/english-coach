from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("skills", "0002_passage_audio")]

    operations = [
        migrations.AddField(
            model_name="passage",
            name="word_timings",
            field=models.JSONField(
                blank=True, default=list,
                help_text="[[word_index, seconds]] from the recording (apps.skills.alignment).",
            ),
        ),
    ]
