from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.profiles.models import LearnerProfile, StudySession

User = get_user_model()
PASSWORD = "pw-for-tests-123"


class AuthTests(APITestCase):
    def test_register_creates_user_profile_and_token(self):
        response = self.client.post(
            reverse("register"),
            {"username": "newbie", "password": PASSWORD, "native_language": "Burmese"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("token", response.data)
        user = User.objects.get(username="newbie")
        self.assertTrue(LearnerProfile.objects.filter(user=user).exists())

    def test_weak_password_is_rejected_with_a_readable_error(self):
        response = self.client.post(reverse("register"), {"username": "weak", "password": "123"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    def test_login_returns_token(self):
        User.objects.create_user(username="known", password=PASSWORD)
        response = self.client.post(
            reverse("login"), {"username": "known", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_bad_login_is_401_not_500(self):
        User.objects.create_user(username="known", password=PASSWORD)
        response = self.client.post(reverse("login"), {"username": "known", "password": "wrong"})
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoints_require_authentication(self):
        for name in ("dashboard", "profile", "today-lesson"):
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 401)


class AuthenticatedAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_dashboard_shape(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        for key in ("learner", "streak_days", "plan", "skills", "weak_areas"):
            self.assertIn(key, response.data)

    def test_today_lesson_blocks_sum_to_the_requested_minutes(self):
        response = self.client.get(reverse("today-lesson"), {"minutes": 45})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_minutes"], 45)
        self.assertEqual(sum(b["minutes"] for b in response.data["blocks"]), 45)

    def test_every_plan_block_explains_itself(self):
        response = self.client.get(reverse("today-lesson"))
        self.assertTrue(all(b["reason"] for b in response.data["blocks"]))

    def test_profile_update_persists(self):
        response = self.client.patch(
            reverse("profile"),
            {"daily_minutes": 45, "interests": ["technology", "movies"], "priority_skills": ["speaking"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        profile = LearnerProfile.objects.get(user=self.user)
        self.assertEqual(profile.daily_minutes, 45)
        self.assertEqual(profile.priority_skills, ["speaking"])

    def test_profile_rejects_unknown_skill_names(self):
        response = self.client.patch(
            reverse("profile"), {"priority_skills": ["telepathy"]}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_profile_rejects_invalid_weekdays(self):
        response = self.client.patch(
            reverse("profile"), {"preferred_study_days": [0, 9]}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_session_lifecycle(self):
        created = self.client.post("/api/sessions/", {"planned_minutes": 30}, format="json")
        self.assertEqual(created.status_code, 201)
        session_id = created.data["id"]
        completed = self.client.post(f"/api/sessions/{session_id}/complete/")
        self.assertEqual(completed.data["status"], StudySession.Status.COMPLETED)

    def test_sessions_are_scoped_to_the_requesting_user(self):
        other = User.objects.create_user(username="other", password=PASSWORD)
        StudySession.objects.create(user=other)
        response = self.client.get("/api/sessions/")
        self.assertEqual(len(response.data["results"] if "results" in response.data else response.data), 0)


class SpeakingScriptAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="speaker", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_generate_returns_a_pasteable_prompt(self):
        response = self.client.post(
            "/api/practice/speaking-scripts/generate/",
            {"scenario": "job_interview", "level": "B1"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("portable_prompt", response.data)
        self.assertIn("CEFR B1", response.data["portable_prompt"])
        self.assertEqual(response.data["scenario"], "job_interview")

    def test_invalid_level_is_rejected(self):
        response = self.client.post(
            "/api/practice/speaking-scripts/generate/", {"level": "Z9"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_scenarios_endpoint_lists_options(self):
        response = self.client.get("/api/practice/speaking-scripts/scenarios/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["scenarios"])
        self.assertIn("B1", response.data["levels"])

    def test_marking_as_practiced_increments_the_counter(self):
        created = self.client.post("/api/practice/speaking-scripts/generate/", {}, format="json")
        response = self.client.post(
            f"/api/practice/speaking-scripts/{created.data['id']}/practiced/"
        )
        self.assertEqual(response.data["times_practiced"], 1)

    def test_scripts_are_private_to_their_owner(self):
        created = self.client.post("/api/practice/speaking-scripts/generate/", {}, format="json")
        self.client.force_authenticate(User.objects.create_user(username="nosy", password=PASSWORD))
        response = self.client.get(f"/api/practice/speaking-scripts/{created.data['id']}/")
        self.assertEqual(response.status_code, 404)


class AIStatusTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="status", password=PASSWORD)
        self.client.force_authenticate(self.user)

    @mock.patch("api.views.ai_health", return_value={"reachable": False, "setup_hint": "run ollama"})
    def test_status_reports_unreachable_without_erroring(self, _health):
        response = self.client.get(reverse("ai-status"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["reachable"])


class ErrorEnvelopeTests(APITestCase):
    def test_ai_unavailable_becomes_503_with_a_helpful_message(self):
        from apps.ai.providers.base import AIUnavailable
        from api.exceptions import friendly_exception_handler

        response = friendly_exception_handler(AIUnavailable("ollama down"), {})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"]["code"], "ai_unavailable")
        self.assertIn("keep studying", response.data["error"]["message"])

    def test_unhandled_exceptions_are_not_swallowed(self):
        from api.exceptions import friendly_exception_handler

        self.assertIsNone(friendly_exception_handler(ZeroDivisionError(), {}))
