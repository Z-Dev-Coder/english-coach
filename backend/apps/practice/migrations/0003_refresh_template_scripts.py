"""Bring saved template scripts up to the current written version.

Migration 0002 repaired one-line scripts by giving them the template exchange
as it stood then -- twelve turns of six to seventeen words each. The written
scripts have since been rewritten to train extended turns, so those repaired
rows are stale again, and a learner opening one practises the version the
rewrite was meant to remove.

Only scripts the app itself wrote are refreshed. A script generated for this
learner is theirs, may have been practised, and is not ours to replace --
`source` is what separates the two.

This is idempotent: a row already matching the current exchange is skipped, so
re-running costs nothing and re-applying after a future rewrite picks up only
what changed.
"""
from django.db import migrations


def refresh(apps, schema_editor):
    from apps.practice.scripts import TEMPLATES, build_portable_prompt

    exchanges = {
        template.scenario: template.sample_exchange
        for template in TEMPLATES
        if template.sample_exchange
    }
    if not exchanges:
        return

    SpeakingScript = apps.get_model("practice", "SpeakingScript")

    for script in SpeakingScript.objects.filter(source="template").iterator():
        exchange = exchanges.get(script.scenario)
        if not exchange:
            continue

        wanted = [{"speaker": who, "text": text} for who, text in exchange]
        if script.lines == wanted:
            continue

        script.lines = wanted
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
    """Nothing to undo: the previous content was a worse version of this one."""


class Migration(migrations.Migration):
    dependencies = [("practice", "0002_backfill_full_scripts")]
    operations = [migrations.RunPython(refresh, noop)]
