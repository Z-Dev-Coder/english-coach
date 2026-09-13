from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("skills", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="passage",
            name="audio_url",
            field=models.URLField(blank=True, max_length=500, help_text="A real human recording of this text."),
        ),
        migrations.AddField(
            model_name="passage",
            name="audio_credit",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
