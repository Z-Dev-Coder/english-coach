from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("content", "0002_scene_sceneprogress")]

    operations = [
        migrations.AddField(
            model_name="scene",
            name="audio_url",
            field=models.URLField(blank=True, max_length=500, help_text="Real human recording of the scene."),
        ),
        migrations.AddField(
            model_name="scene",
            name="audio_credit",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="scene",
            name="source_url",
            field=models.URLField(blank=True, max_length=500, help_text="Page the scene came from."),
        ),
        migrations.AlterField(
            model_name="scene",
            name="source",
            field=models.CharField(
                choices=[("seed", "Hand-written"), ("ai", "Generated"), ("voa", "Real recording (VOA)")],
                default="seed",
                max_length=8,
            ),
        ),
    ]
