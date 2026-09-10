"""API contract tests for the skill activities."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.ai.providers.base import AIUnavailable
from apps.profiles.constants import Skill
from apps.profiles.models import SkillProgress
from apps.skills.models import Passage

User = get_user_model()
PASSWORD = "pw-for-tests-123"


class PassageAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password=PASSWORD)
        self.client.force_authenticate(self.user)
        self.shared = Passage.objects.create(title="Shared", text="A shared passage. It is short.")

    def _rows(self, response):
        return response.data["results"] if "results" in response.data else response.data

    def test_shared_passages_are_listed(self):
        response = self.client.get("/api/skills/passages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self._rows(response)), 1)

    def test_passages_include_split_sentences_for_dictation(self):
        row = self._rows(self.client.get("/api/skills/passages/"))[0]
        self.assertEqual(row["sentences"], ["A shared passage.", "It is short."])
        self.assertGreater(row["word_count"], 0)

    def test_a_learner_can_paste_their_own_text(self):
        response = self.client.post(
            "/api/skills/passages/add/",
            {"text": "Something I found online today and want to study properly."},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_mine"])
        self.assertTrue(response.data["level"])

    def test_pasted_text_must_be_long_enough_to_be_useful(self):
        response = self.client.post("/api/skills/passages/add/", {"text": "short"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_another_learners_passage_is_invisible(self):
        other = User.objects.create_user(username="other", password=PASSWORD)
        Passage.objects.create(title="Theirs", text="Private text here.", owner=other)
        titles = [row["title"] for row in self._rows(self.client.get("/api/skills/passages/"))]
        self.assertNotIn("Theirs", titles)

    def test_passages_can_be_filtered_by_level(self):
        Passage.objects.create(title="Hard", text="Complex prose.", level="C1")
        rows = self._rows(self.client.get("/api/skills/passages/", {"level": "C1"}))
        self.assertEqual([row["title"] for row in rows], ["Hard"])

    def test_authentication_is_required(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/skills/passages/").status_code, 401)


class DictationAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dicto", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_a_correct_dictation_returns_a_perfect_diff(self):
        response = self.client.post(
            reverse("dictation"),
            {"expected": "I can't figure it out.", "written": "I cant figure it out"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["detail"]["is_perfect"])
        self.assertEqual(response.data["skill"], Skill.LISTENING)

    def test_mistakes_are_returned_word_by_word(self):
        response = self.client.post(
            reverse("dictation"),
            {"expected": "I really like this", "written": "I very like this"},
            format="json",
        )
        tokens = response.data["detail"]["tokens"]
        self.assertEqual([t["op"] for t in tokens], ["correct", "wrong", "correct", "correct"])

    def test_a_missing_field_is_rejected(self):
        self.assertEqual(
            self.client.post(reverse("dictation"), {"written": "x"}, format="json").status_code, 400
        )

    def test_it_moves_the_listening_score(self):
        before = SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score
        self.client.post(
            reverse("dictation"), {"expected": "no rush", "written": "no rush"}, format="json"
        )
        self.assertGreater(
            SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score, before
        )


class ShadowingAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shadow", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_the_response_carries_the_estimate_caveat(self):
        response = self.client.post(
            reverse("shadowing"),
            {"expected": "keep me posted", "transcript": "keep me posted"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("estimate", response.data["detail"]["caveat"].lower())

    def test_it_scores_pronunciation(self):
        response = self.client.post(
            reverse("shadowing"), {"expected": "no rush", "transcript": "no rush"}, format="json"
        )
        self.assertEqual(response.data["skill"], Skill.PRONUNCIATION)


class WritingAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="writer", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_writing_works_with_the_ai_offline(self):
        with mock.patch(
            "apps.ai.registry.get_ai_provider", side_effect=AIUnavailable("ollama down")
        ):
            response = self.client.post(
                reverse("writing"),
                {"text": "Today I went to work and fixed a problem.", "task": "Describe your day"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["detail"]["source"], "rules")

    def test_empty_writing_is_rejected(self):
        self.assertEqual(
            self.client.post(reverse("writing"), {"text": ""}, format="json").status_code, 400
        )


class ReadingAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rdr", password=PASSWORD)
        self.client.force_authenticate(self.user)
        self.passage = Passage.objects.create(title="P", text="One two three four five.")

    def test_reading_records_words_per_minute(self):
        response = self.client.post(
            reverse("reading"), {"passage_id": self.passage.id, "seconds": 30}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["detail"]["words_per_minute"], 10)

    def test_reading_a_missing_passage_is_a_clean_404(self):
        response = self.client.post(
            reverse("reading"), {"passage_id": 999999, "seconds": 10}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_record_against_another_learners_passage(self):
        other = User.objects.create_user(username="other2", password=PASSWORD)
        theirs = Passage.objects.create(title="T", text="Private.", owner=other)
        response = self.client.post(
            reverse("reading"), {"passage_id": theirs.id, "seconds": 10}, format="json"
        )
        self.assertEqual(response.status_code, 404)


class DrillAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="driller", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_get_returns_a_sentence_and_the_steps(self):
        response = self.client.get(reverse("drill"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["sentence"])
        self.assertEqual(
            response.data["steps"], ["listen", "repeat", "write", "change", "personalise"]
        )

    def test_posting_a_full_drill_scores_three_skills(self):
        sentence = "I did not realise how difficult it was."
        response = self.client.post(
            reverse("drill"),
            {
                "sentence": sentence,
                "spoken": sentence,
                "written": sentence,
                "variation": "I did not realise how expensive it was.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        for skill in (Skill.LISTENING, Skill.SPEAKING, Skill.WRITING):
            with self.subTest(skill=skill):
                self.assertGreater(
                    SkillProgress.objects.get(user=self.user, skill=skill).score, 50
                )

    def test_a_partial_drill_is_accepted(self):
        response = self.client.post(
            reverse("drill"), {"sentence": "No rush.", "written": "No rush."}, format="json"
        )
        self.assertEqual(response.status_code, 201)


class AttemptsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hist", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_attempts_are_listed_newest_first_and_scoped_to_the_user(self):
        self.client.post(
            reverse("dictation"), {"expected": "one", "written": "one"}, format="json"
        )
        other = User.objects.create_user(username="other3", password=PASSWORD)
        self.client.force_authenticate(other)
        self.client.post(
            reverse("dictation"), {"expected": "two", "written": "two"}, format="json"
        )
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("attempts"))
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["prompt"], "one")

    def test_attempts_can_be_filtered_by_activity(self):
        self.client.post(
            reverse("dictation"), {"expected": "one", "written": "one"}, format="json"
        )
        self.assertEqual(len(self.client.get(reverse("attempts"), {"activity": "writing"}).data), 0)
        self.assertEqual(
            len(self.client.get(reverse("attempts"), {"activity": "dictation"}).data), 1
        )

    def test_summary_reports_per_skill_activity(self):
        self.client.post(
            reverse("dictation"), {"expected": "one two", "written": "one two"}, format="json"
        )
        response = self.client.get(reverse("skill-summary"))
        self.assertEqual(response.data[Skill.LISTENING]["attempts"], 1)


class ShadowingGuideEndpointTests(APITestCase):
    """The guide endpoint. The chunking rules are tested in apps.skills."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="shadow", password="shadowing12345"
        )
        self.client.force_authenticate(self.user)

    def test_it_returns_chunks_for_supplied_text(self):
        response = self.client.get(
            "/api/skills/shadowing/guide/",
            {"text": "The hardest part is the beginning, not the middle.", "level": "A2"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data["chunks"]), 1)
        chunk = response.data["chunks"][0]
        for key in ("text", "words", "stress", "intonation", "pause_ms"):
            self.assertIn(key, chunk)

    def test_it_defaults_to_the_learners_own_level(self):
        # Chunk length is the entire point of the guide, so defaulting to a
        # fixed level would hand a beginner a C1-sized phrase.
        response = self.client.get(
            "/api/skills/shadowing/guide/", {"text": "A short sentence here."}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["level"])

    def test_no_text_is_a_400_rather_than_an_empty_guide(self):
        response = self.client.get("/api/skills/shadowing/guide/")
        self.assertEqual(response.status_code, 400)

    def test_it_requires_authentication(self):
        self.client.force_authenticate(None)
        response = self.client.get("/api/skills/shadowing/guide/", {"text": "Hello there."})
        self.assertEqual(response.status_code, 401)
