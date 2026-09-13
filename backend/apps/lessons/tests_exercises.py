"""Choose-the-answer exercises get parsed and an answer key the learner can check against."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.ai.providers.base import AIError
from apps.lessons import services
from apps.lessons.exercises import apply_key, parse_choice_items

PROMPT = (
    "1. I need to drop ___ the post office to send a parcel. (by / off / in) "
    "2. Can you pick ___ some milk on your way home? (up / out / over) "
    "3. I'm running ___ of time to get to the bank. (out / off / over)"
)
KEY = {
    "answers": [
        {"answer": "off", "explanation": "drop off = leave something somewhere"},
        {"answer": "up", "explanation": "pick up = collect or buy"},
        {"answer": "out", "explanation": "run out of = have none left"},
    ]
}


class ParseTests(SimpleTestCase):
    def test_parses_numbered_items_with_options(self):
        items = parse_choice_items(PROMPT)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["options"], ["by", "off", "in"])
        self.assertIn("___", items[0]["sentence"])
        self.assertNotIn("(by", items[0]["sentence"])

    def test_prose_without_options_is_not_an_exercise(self):
        self.assertEqual(parse_choice_items("Describe your morning. Use linking words."), [])

    def test_a_half_parseable_exercise_is_rejected(self):
        # Rendering some items as choices and dropping the rest would be worse.
        broken = "1. I need to drop ___ the parcel. (by / off) 2. Tell me about your day."
        self.assertEqual(parse_choice_items(broken), [])


class KeyTests(SimpleTestCase):
    def test_answers_are_attached(self):
        keyed = apply_key(parse_choice_items(PROMPT), KEY)
        self.assertEqual([item["answer"] for item in keyed], ["off", "up", "out"])

    def test_a_two_part_explanation_is_not_cut_off(self):
        # Seen live: a 240-character cap ended explanations mid-word, losing
        # the "why the other options are wrong" half.
        long = ("'Drop by' means to visit a place quickly, which fits going to the post office to send "
                "a parcel. 'Drop off' means to leave something or someone somewhere, and 'drop in' means "
                "to visit someone informally, so neither fits with 'the post office' in this sentence.")
        key = {"answers": [{"answer": "off", "explanation": long}, *KEY["answers"][1:]]}
        keyed = apply_key(parse_choice_items(PROMPT), key)
        self.assertEqual(keyed[0]["explanation"], long)

    def test_an_answer_that_is_not_an_option_voids_the_key(self):
        # A key able to mark the correct choice wrong is worse than no key.
        bad = {"answers": [*KEY["answers"][:2], {"answer": "away", "explanation": ""}]}
        self.assertEqual(apply_key(parse_choice_items(PROMPT), bad), [])

    def test_a_key_of_the_wrong_length_is_rejected(self):
        self.assertEqual(apply_key(parse_choice_items(PROMPT), {"answers": KEY["answers"][:1]}), [])


class EndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ex", password="exercise12345")
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(self.user)
        self.lesson = services.generate_lesson(self.user, use_ai=False)
        self.activity = self.lesson.activities.first()
        self.activity.prompt = PROMPT
        self.activity.save()
        self.url = f"/api/lessons/{self.lesson.id}/activities/{self.activity.id}/exercise/"

    def test_key_is_generated_once_and_stored(self):
        with mock.patch("apps.ai.services.cached", return_value=KEY) as cached:
            first = self.client.get(self.url).data
            second = self.client.get(self.url).data
        self.assertEqual([item["answer"] for item in first["items"]], ["off", "up", "out"])
        self.assertEqual(first, second)
        self.assertEqual(cached.call_count, 1, "the stored key should be reused")

    def test_without_a_model_items_come_back_unkeyed(self):
        with mock.patch("apps.ai.services.cached", side_effect=AIError("offline")):
            data = self.client.get(self.url).data
        self.assertFalse(data["checkable"])
        self.assertEqual(len(data["items"]), 3)

    def test_another_learners_lesson_is_not_reachable(self):
        other = get_user_model().objects.create_user(username="ex2", password="exercise12345")
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(other)
        self.assertEqual(client.get(self.url).status_code, 404)
