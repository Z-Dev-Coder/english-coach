"""Listening and Talk teach topic language first, and Talk checks it was used."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ai.providers.base import AIError
from apps.profiles.models import SkillProgress
from apps.skills import topic_language
from apps.skills.models import Passage

LESSON = {
    "vocabulary": [{"text": "commute", "meaning": "journey to work", "example": "My commute is long."}],
    "expressions": [{"text": "run late", "meaning": "be late", "example": "I'm running late."}],
    "tips": ["'running late' links: runnin-late."],
    "questions": ["Why is the speaker stressed?"],
}


class BuildTests(TestCase):
    def test_model_output_is_cleaned(self):
        with mock.patch("apps.ai.services.cached", return_value=LESSON):
            result = topic_language.build(kind="listening", text="Some text.", level="B1")
        self.assertFalse(result["is_fallback"])
        self.assertEqual(result["expressions"][0]["text"], "run late")

    def test_listening_without_a_model_invents_nothing(self):
        with mock.patch("apps.ai.services.cached", side_effect=AIError("offline")):
            result = topic_language.build(kind="listening", text="Some text.", level="B1")
        self.assertTrue(result["is_fallback"])
        self.assertEqual(result["vocabulary"], [])
        self.assertEqual(result["expressions"], [])

    def test_conversation_without_a_model_uses_the_written_script_phrases(self):
        with mock.patch("apps.ai.services.cached", side_effect=AIError("offline")):
            result = topic_language.build(kind="conversation", topic="job_interview", level="B1")
        self.assertTrue(result["expressions"], "fell back to nothing for a known situation")


class EndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tl", password="topic12345")
        for skill, level in (("listening", "A2"), ("speaking", "B2")):
            progress, _ = SkillProgress.objects.get_or_create(user=self.user, skill=skill)
            progress.level = level
            progress.save()
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(self.user)

    def test_passage_lesson_uses_the_listening_level(self):
        passage = Passage.objects.create(title="T", text="A sentence here. Another one.", level="A2")
        seen = {}

        def fake(**kwargs):
            seen.update(kwargs)
            return LESSON

        with mock.patch("apps.skills.topic_language.build", side_effect=fake):
            response = self.client.get(f"/api/skills/passages/{passage.id}/lesson/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["level"], "A2")
        self.assertEqual(seen["kind"], "listening")

    def test_conversation_prep_uses_the_speaking_level(self):
        seen = {}

        def fake(**kwargs):
            seen.update(kwargs)
            return {**LESSON, "is_fallback": False}

        with mock.patch("apps.skills.topic_language.build", side_effect=fake):
            response = self.client.get("/api/conversations/prep/", {"scenario": "restaurant"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["level"], "B2")
        self.assertEqual(response.data["scenario"], "restaurant")

    def test_conversation_review_reports_used_targets(self):
        from apps.conversation import services as conversation_services

        with mock.patch("apps.conversation.services.get_ai_provider") as provider:
            provider.return_value.chat.side_effect = AIError("offline")
            provider.return_value.generate_json.side_effect = AIError("offline")
            response = self.client.post(
                "/api/conversations/start/",
                {"scenario": "casual", "targets": ["run late", "catch up"]},
                format="json",
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["targets"], ["run late", "catch up"])
            session_id = response.data["id"]
            self.client.post(f"/api/conversations/{session_id}/say/", {"text": "Sorry, I was running late today."}, format="json")
            from apps.conversation.models import ConversationSession

            feedback = conversation_services.generate_feedback(ConversationSession.objects.get(id=session_id))

        self.assertEqual(feedback["targets"]["used"], ["run late"])
        self.assertEqual(feedback["targets"]["missing"], ["catch up"])
