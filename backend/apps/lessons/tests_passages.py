"""Reading and listening steps use one text, written for the lesson.

The step used to show two: a passage the model pasted into `prompt`, and a
library passage picked by rotation that the runner actually opened. With six
library passages the same few also kept repeating.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.lessons import services
from apps.skills.models import Passage


def fake_enrichment(texts):
    """A cached() stand-in returning a lesson whose reading step has a passage."""
    calls = iter(texts)

    def fake(kind, payload, build):
        title, text = next(calls)
        return {
            "title": title,
            "theme": "Errands",
            "activities": [
                {
                    "kind": kind_name,
                    "title": f"{kind_name} step",
                    "instructions": "Do it.",
                    "prompt": "Text: pasted copy that must not survive. Questions: 1. x?",
                    "passage": {"title": title, "text": text},
                    "questions": ["What did they drop off?", "Who did they run into?"],
                }
                for kind_name in ("review", "reading", "listening", "writing", "speaking")
            ],
        }

    return fake


class LessonPassageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lp", password="passages12345")
        Passage.objects.create(title="Library", text="A library text. Another.", level="B1")

    def _lesson(self, title, text):
        with mock.patch("apps.ai.services.cached", side_effect=fake_enrichment([(title, text)])):
            return services.generate_lesson(self.user, use_ai=True)

    def test_the_step_points_at_the_lessons_own_passage(self):
        lesson = self._lesson("A Neighbourhood Update", "I dropped off my dry cleaning. Then I popped into the bakery.")
        steps = list(lesson.activities.filter(kind__in=["reading", "listening"]))
        self.assertTrue(steps, "plan had no reading or listening step")

        ids = {step.params.get("passage_id") for step in steps}
        self.assertEqual(len(ids), 1, "reading and listening should share one text")
        passage = Passage.objects.get(id=ids.pop())
        self.assertEqual(passage.title, "A Neighbourhood Update")
        self.assertEqual(passage.owner, self.user)
        self.assertEqual(passage.source, Passage.Source.AI)

    def test_the_prompt_no_longer_carries_a_second_copy(self):
        lesson = self._lesson("Errands", "Some text here. And more.")
        for step in lesson.activities.filter(kind__in=["reading", "listening"]):
            self.assertNotIn("pasted copy", step.prompt)
            self.assertEqual(step.params.get("questions")[0], "What did they drop off?")

    def test_consecutive_lessons_get_different_texts(self):
        first = self._lesson("One", "First text. Here.")
        for activity in first.activities.all():
            activity.complete()
        second = self._lesson("Two", "Second text. Here.")

        def ids(lesson):
            return {a.params.get("passage_id") for a in lesson.activities.filter(kind__in=["reading", "listening"])}

        self.assertFalse(ids(first) & ids(second), "a new lesson reused the previous text")

    def test_without_a_model_the_library_is_the_fallback(self):
        lesson = services.generate_lesson(self.user, use_ai=False)
        for step in lesson.activities.filter(kind__in=["reading", "listening"]):
            self.assertEqual(Passage.objects.get(id=step.params["passage_id"]).title, "Library")
