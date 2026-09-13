"""Writing lessons: topic language first, then checking the learner used it."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.profiles.models import SkillProgress
from apps.skills import writing_support
from apps.skills.writing_support import used_items


class UsedItemsTests(SimpleTestCase):
    def test_a_phrasal_verb_split_by_its_object_still_counts(self):
        # "put the meeting off" is correct use of "put off"; a strict string
        # match would mark it missing and punish exactly what was taught.
        self.assertEqual(used_items("Could we put the meeting off?", ["put off"]), ["put off"])

    def test_inflected_forms_count(self):
        text = "I picked up the report and I've been dealing with the issues."
        self.assertEqual(used_items(text, ["pick up", "deal with"]), ["pick up", "deal with"])

    def test_a_pattern_with_a_gap_counts(self):
        text = "I was wondering if you could send me the slides."
        self.assertEqual(
            used_items(text, ["I was wondering if you could ..."]),
            ["I was wondering if you could ..."],
        )

    def test_words_far_apart_do_not_count(self):
        text = "Please put your coat on the chair and then we can talk about the day off."
        self.assertEqual(used_items(text, ["put off"]), [])

    def test_missing_items_are_not_reported_as_used(self):
        self.assertEqual(used_items("Hello there.", ["as far as I know", "let me know"]), [])


class BuildLessonTests(TestCase):
    def test_a_model_lesson_is_cleaned_and_returned(self):
        data = {
            "genre": "email",
            "vocabulary": [{"text": "reschedule", "meaning": "change the time", "example": "Can we reschedule?"}],
            "phrasal_verbs": [{"text": "put off", "meaning": "delay", "example": "Let's put it off."}],
            "expressions": [{"text": "sorry for the short notice", "meaning": "apology", "example": "x"}],
            "sentence_patterns": [{"pattern": "Would it be possible to ...", "use": "polite", "example": "y"}],
            "plan": [{"part": "Opening", "what_to_write": "Say why.", "starter": "I'm writing to"}],
            "model_text": "Hi Sam, ...",
            "style_tips": ["Be polite."],
            "word_target": 90,
        }
        with mock.patch("apps.ai.services.cached", return_value=data):
            lesson = writing_support.build_lesson(task="Postpone a meeting", level="B1")
        self.assertFalse(lesson["is_fallback"])
        self.assertEqual(lesson["phrasal_verbs"][0]["text"], "put off")
        self.assertEqual(lesson["word_target"], 90)

    def test_without_a_model_it_falls_back_honestly(self):
        from apps.ai.providers.base import AIError

        with mock.patch("apps.ai.services.cached", side_effect=AIError("offline")):
            lesson = writing_support.build_lesson(task="Postpone a meeting", level="B1")
        self.assertTrue(lesson["is_fallback"])
        # Topic lists stay empty rather than invented.
        self.assertEqual(lesson["vocabulary"], [])
        self.assertTrue(lesson["plan"])


class WritingEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="wl", password="writing12345")
        progress, _ = SkillProgress.objects.get_or_create(user=self.user, skill="writing")
        progress.level = "A2"
        progress.save()
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(self.user)

    def test_lesson_uses_the_writing_level(self):
        seen = {}

        def fake(*, task, level):
            seen["level"] = level
            return {"plan": [], "level": level}

        with mock.patch("apps.skills.writing_support.build_lesson", side_effect=fake):
            self.client.get("/api/skills/writing-lesson/", {"task": "Postpone a meeting"})
        self.assertEqual(seen["level"], "A2")

    def test_submission_reports_used_and_missing_targets(self):
        from apps.ai.providers.base import AIError

        with mock.patch("apps.ai.registry.get_ai_provider") as provider:
            provider.return_value.evaluate_writing.side_effect = AIError("offline")
            response = self.client.post(
                "/api/skills/writing/",
                {
                    "text": "Hi Sam, could we put the meeting off until Friday? Let me know.",
                    "task": "Postpone a meeting",
                    "targets": ["put off", "let me know", "reschedule"],
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        targets = response.data["detail"]["targets"]
        self.assertEqual(targets["used"], ["put off", "let me know"])
        self.assertEqual(targets["missing"], ["reschedule"])
