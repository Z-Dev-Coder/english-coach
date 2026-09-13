"""Repair lessons generated while the model pasted its text into the prompt.

Before the passage got its own field, the model wrote reading and listening
steps as `Text: "..." Questions: 1. ... 2. ...` (or `Audio transcript: "..."`)
inside `prompt`, while the step's passage_id pointed at an unrelated library
passage. The home card showed one text and the runner opened another.

For each such step this pulls the quoted text out into a Passage owned by the
learner, points the step at it, and keeps only the questions in params. Steps
whose prompt does not match the pattern are left alone rather than guessed at.
"""
import re

from django.db import migrations

QUOTED = re.compile(r'^\s*[A-Za-z ]{2,30}:\s*"(?P<text>.+?)"\s*(?P<rest>.*)$', re.S)
QUESTION = re.compile(r"\d+\.\s*(.+?)(?=\s*\d+\.\s|$)", re.S)


def split(apps, schema_editor):
    Activity = apps.get_model("lessons", "LessonActivity")
    Passage = apps.get_model("skills", "Passage")

    steps = Activity.objects.filter(kind__in=["reading", "listening"]).select_related("lesson")
    for step in steps.iterator():
        match = QUOTED.match(step.prompt or "")
        if not match or len(match.group("text").split()) < 15:
            continue

        rest = match.group("rest")
        rest = re.sub(r"^\s*questions?\s*:\s*", "", rest, flags=re.I)
        questions = [q.strip() for q in QUESTION.findall(rest) if q.strip()]

        lesson = step.lesson
        passage = Passage.objects.create(
            title=(step.title or lesson.title)[:200],
            text=match.group("text").strip(),
            level=(lesson.context or {}).get("overall_level", "B1"),
            topic=(lesson.theme or "")[:40],
            source="ai",
            owner_id=lesson.user_id,
        )
        params = dict(step.params or {})
        params["passage_id"] = passage.id
        params.setdefault("tab", step.kind)
        if questions:
            params["questions"] = questions[:6]
        step.params = params
        step.prompt = ""
        step.save(update_fields=["params", "prompt"])


class Migration(migrations.Migration):
    dependencies = [
        ("lessons", "0002_remove_lesson_uniq_lesson_per_day_and_more"),
        ("skills", "0001_initial"),
    ]
    operations = [migrations.RunPython(split, migrations.RunPython.noop)]
