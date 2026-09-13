from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("content", "0005_video_dynamic")]

    operations = [
        migrations.AddField(
            model_name="scene",
            name="word_timings",
            field=models.JSONField(
                blank=True, default=list, help_text="[[word_index, seconds]] over the lines joined by spaces."
            ),
        ),
    ]
