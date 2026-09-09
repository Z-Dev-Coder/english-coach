"""API contract tests for vocabulary and review."""
import datetime as dt

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.review import services
from apps.review.models import ExerciseType
from apps.vocabulary.models import ExampleSentence, Expression, Kind, MasteryState, VocabularyProgress

User = get_user_model()
PASSWORD = "pw-for-tests-123"


def make_expression(text="figure out", example="I can't figure it out.", **kwargs):
    expression = Expression.objects.create(
        text=text,
        kind=kwargs.pop("kind", Kind.PHRASAL_VERB),
        meaning=kwargs.pop("meaning", "to understand something"),
        **kwargs,
    )
    if example:
        ExampleSentence.objects.create(expression=expression, text=example)
    return expression


class ReviewQueueAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_queue_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("review-queue")).status_code, 401)

    def test_empty_queue_is_a_valid_response_not_an_error(self):
        response = self.client.get(reverse("review-queue"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["items"], [])

    def test_queue_items_carry_a_ready_made_prompt(self):
        services.add_to_learning(self.user, make_expression())
        item = self.client.get(reverse("review-queue")).data["items"][0]
        self.assertEqual(item["exercise"], ExerciseType.MEET)
        self.assertIn("instruction", item["prompt"])
        self.assertEqual(item["prompt"]["front"], "figure out")
        self.assertEqual(item["progress"]["expression"]["text"], "figure out")

    def test_cloze_prompt_hides_the_expression(self):
        progress = services.add_to_learning(
            self.user, make_expression("deal with", example="I had to deal with it.")
        )
        VocabularyProgress.objects.filter(pk=progress.pk).update(
            state=MasteryState.WEAK, reps=5, lapses=3, stability=2, difficulty=8,
            due_at=timezone.now() - dt.timedelta(days=1),
            last_reviewed_at=timezone.now() - dt.timedelta(days=3),
        )
        item = self.client.get(reverse("review-queue")).data["items"][0]
        self.assertEqual(item["exercise"], ExerciseType.CLOZE)
        self.assertIn("______", item["prompt"]["front"])
        self.assertNotIn("deal with", item["prompt"]["front"])

    def test_production_prompt_shows_the_meaning_not_the_answer(self):
        progress = services.add_to_learning(self.user, make_expression())
        VocabularyProgress.objects.filter(pk=progress.pk).update(
            state=MasteryState.REVIEW, reps=3, stability=20, difficulty=5,
            due_at=timezone.now() - dt.timedelta(days=1),
            last_reviewed_at=timezone.now() - dt.timedelta(days=21),
        )
        item = self.client.get(reverse("review-queue")).data["items"][0]
        self.assertEqual(item["exercise"], ExerciseType.PRODUCE)
        self.assertEqual(item["prompt"]["front"], "to understand something")

    def test_limit_is_respected(self):
        for index in range(10):
            services.add_to_learning(self.user, make_expression(f"phrase {index}"))
        self.assertLessEqual(len(self.client.get(reverse("review-queue"), {"limit": 3}).data["items"]), 3)

    def test_another_users_items_never_appear(self):
        other = User.objects.create_user(username="other", password=PASSWORD)
        services.add_to_learning(other, make_expression())
        self.assertEqual(self.client.get(reverse("review-queue")).data["count"], 0)


class AnswerAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="grader", password=PASSWORD)
        self.client.force_authenticate(self.user)
        self.progress = services.add_to_learning(self.user, make_expression())

    def test_answering_reschedules_and_reports_the_new_interval(self):
        response = self.client.post(
            reverse("review-answer"),
            {"progress_id": self.progress.id, "rating": 3, "exercise": "meet"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["next_due_in_days"], 1)
        self.assertEqual(response.data["progress"]["reps"], 1)
        self.assertEqual(response.data["progress"]["state"], MasteryState.LEARNING)

    def test_invalid_rating_is_rejected(self):
        response = self.client.post(
            reverse("review-answer"),
            {"progress_id": self.progress.id, "rating": 9},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_cannot_grade_another_users_item(self):
        other = User.objects.create_user(username="victim", password=PASSWORD)
        theirs = services.add_to_learning(other, make_expression("their phrase"))
        response = self.client.post(
            reverse("review-answer"), {"progress_id": theirs.id, "rating": 3}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_item_is_a_clean_404(self):
        response = self.client.post(
            reverse("review-answer"), {"progress_id": 999999, "rating": 3}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)


class VocabularyAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vocab", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_learner_can_add_an_expression_they_met(self):
        response = self.client.post(
            "/api/vocabulary/add/",
            {
                "text": "a bit of a nightmare",
                "meaning": "something difficult or annoying",
                "kind": "idiom",
                "example": "The commute was a bit of a nightmare.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["state"], MasteryState.NEW)
        self.assertEqual(len(response.data["expression"]["examples"]), 1)

    def test_adding_a_known_expression_reuses_it_rather_than_duplicating(self):
        make_expression("look into", meaning="to investigate")
        response = self.client.post(
            "/api/vocabulary/add/",
            {"text": "Look Into", "meaning": "to investigate", "kind": "phrasal_verb"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Expression.objects.filter(normalized="look into").count(), 1)

    def test_adding_requires_a_meaning(self):
        response = self.client.post("/api/vocabulary/add/", {"text": "x"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_list_can_be_filtered_by_state(self):
        services.add_to_learning(self.user, make_expression("one"))
        second = services.add_to_learning(self.user, make_expression("two"))
        services.answer(second, 3)
        response = self.client.get("/api/vocabulary/", {"state": "new"})
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 1)

    def test_list_can_be_searched(self):
        services.add_to_learning(self.user, make_expression("keep you posted"))
        services.add_to_learning(self.user, make_expression("no rush"))
        response = self.client.get("/api/vocabulary/", {"search": "POSTED"})
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 1)

    def test_vocabulary_is_private_to_its_owner(self):
        other = User.objects.create_user(username="nosy", password=PASSWORD)
        services.add_to_learning(other, make_expression())
        response = self.client.get("/api/vocabulary/")
        rows = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(rows), 0)


class ReviewStatsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="statsy", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_stats_include_a_forecast(self):
        response = self.client.get(reverse("review-stats"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["forecast"]), 7)
        self.assertIn("by_state", response.data)

    def test_history_lists_recent_reviews(self):
        progress = services.add_to_learning(self.user, make_expression())
        services.answer(progress, 3)
        response = self.client.get(reverse("review-history"))
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["expression"], "figure out")


class DashboardIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dash2", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_dashboard_now_reports_the_real_review_count(self):
        for index in range(3):
            services.add_to_learning(self.user, make_expression(f"item {index}"))
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("review", response.data)
        self.assertEqual(response.data["review"]["total_tracked"], 3)

    def test_dashboard_works_for_a_learner_with_no_vocabulary(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.data["review"]["due_now"], 0)
        self.assertIsNone(response.data["review"]["success_rate"])


class AddExtractedAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ext", password=PASSWORD)
        self.client.force_authenticate(self.user)

    def test_a_batch_from_an_article_lands_in_the_queue(self):
        response = self.client.post(
            "/api/vocabulary/add-extracted/",
            {
                "items": [
                    {"expression": "run into", "meaning": "meet by chance", "kind": "phrasal_verb"},
                    {"expression": "keep you posted", "meaning": "keep you updated"},
                ],
                "source": "content",
                "source_url": "https://example.com/story",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["added"], 2)
        self.assertEqual(len(self.client.get(reverse("review-queue")).data["items"]), 2)

    def test_an_empty_batch_is_rejected(self):
        response = self.client.post(
            "/api/vocabulary/add-extracted/", {"items": []}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_authentication_is_required(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            "/api/vocabulary/add-extracted/",
            {"items": [{"expression": "x", "meaning": "y"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_items_are_added_to_the_calling_user_only(self):
        other = User.objects.create_user(username="ext2", password=PASSWORD)
        self.client.post(
            "/api/vocabulary/add-extracted/",
            {"items": [{"expression": "look into", "meaning": "investigate"}]},
            format="json",
        )
        self.assertEqual(other.vocabulary.count(), 0)
        self.assertEqual(self.user.vocabulary.count(), 1)
