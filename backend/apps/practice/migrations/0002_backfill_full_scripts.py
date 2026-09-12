"""Give scripts saved before the full-exchange change their missing lines.

Every script created before this carried a single opening line, because that
was all a template held. They are still rendered under "read it out loud, both
parts" -- a heading that is simply false when there is only one part, and a
learner opening one of those sees the old, broken version of the feature with
no way to tell it apart from the new one.

Regenerating on read would hide the problem rather than fix it, so the rows are
repaired here. A script is judged inadequate if it has fewer than four lines or
only one speaker: either way it is an opening, not something to practise.

The portable prompt is rebuilt at the same time, since it embeds the script.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    # The templates and prompt builder are ordinary Python, not models, so they
    # are safe to import directly -- there is no historical version of them.
    from apps.practice.scripts import TEMPLATES, build_portable_prompt

    exchanges = {
        template.scenario: template.sample_exchange
        for template in TEMPLATES
        if template.sample_exchange
    }
    if not exchanges:
        return

    SpeakingScript = apps.get_model("practice", "SpeakingScript")

    for script in SpeakingScript.objects.all().iterator():
        lines = script.lines or []
        speakers = {line.get("speaker") for line in lines if isinstance(line, dict)}
        if len(lines) >= 4 and len(speakers) > 1:
            continue

        exchange = exchanges.get(script.scenario)
        if not exchange:
            # A scenario we no longer have a template for. Leaving it alone is
            # better than replacing its content with another situation's.
            continue

        script.lines = [{"speaker": who, "text": text} for who, text in exchange]
        script.portable_prompt = build_portable_prompt(
            title=script.title,
            setting=script.setting,
            goal=script.goal,
            level=script.level,
            expressions=script.target_expressions or [],
            questions=script.follow_up_questions or [],
            sample_exchange=list(exchange),
        )
        script.save(update_fields=["lines", "portable_prompt"])


def noop(apps, schema_editor):
    """Nothing to undo.

    The previous state was one line where there are now twelve; restoring that
    would be discarding content to recreate a defect.
    """


class Migration(migrations.Migration):
    dependencies = [("practice", "0001_initial")]
    operations = [migrations.RunPython(backfill, noop)]
