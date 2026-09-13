"""Phrase-to-meaning matching exercises: parsed, keyed, checkable."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.lessons import services
from apps.lessons.exercises import apply_matching_key, parse_matching

PROMPT = (
    "Phrases: drop off, pick up, run out of, pop into, run into, check out. "
    "Meanings: a) to leave something somewhere; b) to collect something; "
    "c) to have none left; d) to go into a place quickly; e) to meet by chance; "
    "f) to look at or try something new."
)
KEY = {"answers": [{"letter": l, "explanation": "x"} for l in "abcdef"]}


class ParseMatchingTests(SimpleTestCase):
    def test_parses_phrases_and_lettered_meanings(self):
        parsed = parse_matching(PROMPT)
        self.assertEqual(parsed["phrases"][0], "drop off")
        self.assertEqual(len(parsed["phrases"]), 6)
        self.assertEqual(parsed["meanings"][2], {"letter": "c", "text": "to have none left"})
        self.assertEqual(len(parsed["meanings"]), 6)

    def test_mismatched_counts_stay_text(self):
        self.assertEqual(parse_matching("Phrases: a, b, c. Meanings: a) one; b) two."), {})

    def test_prose_is_not_a_matching_exercise(self):
        self.assertEqual(parse_matching("Describe your day using the phrases you know."), {})


class MatchingKeyTests(SimpleTestCase):
    def test_key_is_applied(self):
        keyed = apply_matching_key(parse_matching(PROMPT), KEY)
        self.assertEqual([p["answer"] for p in keyed["pairs"]], list("abcdef"))

    def test_a_meaning_used_twice_voids_the_key(self):
        bad = {"answers": [{"letter": "a", "explanation": ""}] * 6}
        self.assertEqual(apply_matching_key(parse_matching(PROMPT), bad), {})

    def test_an_unknown_letter_voids_the_key(self):
        bad = {"answers": [*KEY["answers"][:5], {"letter": "z", "explanation": ""}]}
        self.assertEqual(apply_matching_key(parse_matching(PROMPT), bad), {})


class MatchingEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mt", password="matching12345")
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(self.user)
        lesson = services.generate_lesson(self.user, use_ai=False)
        activity = lesson.activities.first()
        activity.prompt = PROMPT
        activity.params = {}
        activity.save()
        self.url = f"/api/lessons/{lesson.id}/activities/{activity.id}/exercise/"

    def test_returns_a_keyed_matching_exercise_and_stores_it(self):
        with mock.patch("apps.ai.services.cached", return_value=KEY) as cached:
            first = self.client.get(self.url).data
            second = self.client.get(self.url).data
        self.assertEqual(first["type"], "matching")
        self.assertTrue(first["checkable"])
        self.assertEqual(len(first["pairs"]), 6)
        self.assertEqual(first, second)
        self.assertEqual(cached.call_count, 1)
