"""Tests for lesson generation.

The recurring theme: the lesson must be correct and complete without any AI,
and AI must only ever improve it.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.ai.providers.base import AIOutputError, AIProvider, AIResult, AIUnavailable
from apps.lessons import services
from apps.lessons.models import Lesson
from apps.profiles.models import LearnerProfile
from apps.review.services import add_to_learning
from apps.skills.models import Passage
from apps.vocabulary.models import Expression

User = get_user_model()
PASSWORD = "pw-for-tests-123"


class StubProvider(AIProvider):
    """Returns a well-formed lesson."""

    name = "stub"

    def __init__(self, payload=None):
        self.payload = payload or (
            '{"title": "Dealing with problems at work",'
            ' "theme": "Everything today is about explaining a problem clearly.",'
            ' "encouragement": "Your listening has moved up this week.",'
            ' "activities": ['
            '  {"kind": "listening", "title": "Hear the problem", "instructions": "Listen twice.",'
            '   "prompt": "", "target_expressions": ["deal with"]},'
            '  {"kind": "writing", "title": "Explain what happened", "instructions": "Write it up.",'
            '   "prompt": "Describe a problem you solved at work.", "target_expressions": []}'
            ']}'
        )

    def generate(self, prompt, **kwargs):
        return AIResult(text=self.payload, model="stub", tier="medium", duration_ms=1)

    def chat(self, messages, **kwargs):
        return self.generate("")

    def health(self):
        return {"reachable": True}


class LearnerContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ctx", password=PASSWORD)

    def test_context_reports_real_learner_state(self):
        profile = LearnerProfile.objects.get(user=self.user)
        profile.interests = ["technology", "work"]
        profile.save()

        context = services.learner_context(self.user)
        self.assertEqual(context["interests"], ["technology", "work"])
        self.assertEqual(context["target_level"], profile.target_level)
        self.assertIn("plan", context)
        self.assertGreater(context["total_minutes"], 0)

    def test_context_counts_due_vocabulary(self):
        expression = Expression.objects.create(text="deal with", meaning="handle")
        add_to_learning(self.user, expression)
        self.assertEqual(services.learner_context(self.user)["due_count"], 0)  # new, not due yet

    def test_weak_skills_only_appear_once_measured(self):
        """A brand-new learner has no measured weaknesses, and the context must
        not invent any."""
        self.assertEqual(services.learner_context(self.user)["weak_skills"], [])

    def test_measured_weakness_reaches_the_context(self):
        from apps.profiles.services import record_practice

        for _ in range(4):
            record_practice(self.user, "listening", -40)
        self.assertIn("listening", services.learner_context(self.user)["weak_skills"])

    def test_recent_writing_mistakes_are_surfaced(self):
        from apps.skills.models import SkillAttempt

        SkillAttempt.objects.create(
            user=self.user,
            activity="writing",
            skill="writing",
            detail={"issues": [{"category": "preposition"}, {"category": "article"}]},
        )
        context = services.learner_context(self.user)
        self.assertIn("preposition", context["recent_mistakes"])
        self.assertIn("article", context["recent_mistakes"])


class TemplateLessonTests(TestCase):
    """The lesson must be complete and useful with no model running at all."""

    def setUp(self):
        self.user = User.objects.create_user(username="tmpl", password=PASSWORD)
        Passage.objects.create(title="A passage", text="One thing. Then another.", level="B1")

    def _lesson(self):
        return services.generate_lesson(self.user, use_ai=False)

    def test_a_lesson_is_produced_without_ai(self):
        lesson = self._lesson()
        self.assertEqual(lesson.origin, Lesson.Origin.TEMPLATE)
        self.assertGreater(lesson.activities.count(), 0)

    def test_every_activity_has_instructions_a_learner_can_follow(self):
        for activity in self._lesson().activities.all():
            with self.subTest(kind=activity.kind):
                self.assertTrue(activity.instructions.strip())
                self.assertTrue(activity.title.strip())

    def test_every_activity_knows_where_it_sends_the_learner(self):
        for activity in self._lesson().activities.all():
            with self.subTest(kind=activity.kind):
                self.assertTrue(activity.route.startswith("/"))

    def test_activity_minutes_match_the_plan(self):
        lesson = self._lesson()
        planned = {block["skill"]: block["minutes"] for block in lesson.context["plan"]}
        for activity in lesson.activities.exclude(kind="drill"):
            with self.subTest(kind=activity.kind):
                self.assertEqual(activity.minutes, planned[activity.kind])

    def test_reading_and_listening_activities_point_at_a_real_passage(self):
        lesson = self._lesson()
        for activity in lesson.activities.filter(kind__in=["reading", "listening"]):
            with self.subTest(kind=activity.kind):
                self.assertIn("passage_id", activity.params)

    def test_the_drill_is_added_when_it_fits_the_day(self):
        self.assertTrue(self._lesson().activities.filter(kind="drill").exists())

    def test_the_writing_activity_carries_a_prompt(self):
        writing = self._lesson().activities.filter(kind="writing").first()
        self.assertTrue(writing.prompt)

    def test_the_context_used_is_stored_for_auditing(self):
        self.assertIn("plan", self._lesson().context)


class AIEnrichmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ai", password=PASSWORD)
        Passage.objects.create(title="P", text="One thing. Then another.", level="B1")

    def test_ai_text_replaces_the_template_wording(self):
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=StubProvider()):
            lesson = services.generate_lesson(self.user)
        self.assertEqual(lesson.origin, Lesson.Origin.AI)
        self.assertEqual(lesson.title, "Dealing with problems at work")
        self.assertTrue(lesson.theme)
        listening = lesson.activities.filter(kind="listening").first()
        self.assertEqual(listening.title, "Hear the problem")
        self.assertEqual(listening.target_expressions, ["deal with"])

    def test_the_ai_cannot_change_the_time_allocation(self):
        """Only text is taken from the model. Minutes and routing stay
        authoritative, so a hallucination cannot rewrite the schedule."""
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=StubProvider()):
            lesson = services.generate_lesson(self.user)
        planned = {block["skill"]: block["minutes"] for block in lesson.context["plan"]}
        for activity in lesson.activities.exclude(kind="drill"):
            with self.subTest(kind=activity.kind):
                self.assertEqual(activity.minutes, planned[activity.kind])
                self.assertTrue(activity.route.startswith("/"))

    def test_a_partial_ai_response_improves_only_what_it_covered(self):
        """The stub returns two activities for a six-block plan. The rest must
        keep their template wording rather than being dropped or blanked."""
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=StubProvider()):
            lesson = services.generate_lesson(self.user)
        for activity in lesson.activities.all():
            with self.subTest(kind=activity.kind):
                self.assertTrue(activity.title.strip())
                self.assertTrue(activity.instructions.strip())

    def test_malformed_ai_output_falls_back_to_the_template(self):
        broken = StubProvider(payload="I'm afraid I can't do that, Dave.")
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=broken):
            lesson = services.generate_lesson(self.user)
        self.assertEqual(lesson.origin, Lesson.Origin.TEMPLATE)
        self.assertGreater(lesson.activities.count(), 0)

    def test_an_unavailable_model_falls_back_to_the_template(self):
        with mock.patch(
            "apps.ai.registry.get_ai_provider", side_effect=AIUnavailable("ollama down")
        ):
            lesson = services.generate_lesson(self.user)
        self.assertEqual(lesson.origin, Lesson.Origin.TEMPLATE)
        self.assertGreater(lesson.activities.count(), 0)

    def test_generation_is_cached_so_the_model_runs_once(self):
        provider = StubProvider()
        calls = []
        original = provider.generate

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        provider.generate = counting
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=provider):
            services.generate_lesson(self.user)
            other = User.objects.create_user(username="twin", password=PASSWORD)
            services.generate_lesson(other)
        self.assertEqual(len(calls), 1, "identical learner context should hit the cache")


class LessonLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="life", password=PASSWORD)

    def test_asking_twice_returns_the_same_lesson(self):
        first = services.generate_lesson(self.user, use_ai=False)
        second = services.generate_lesson(self.user, use_ai=False)
        self.assertEqual(first.id, second.id)
        self.assertEqual(Lesson.objects.count(), 1)

    def test_regenerating_replaces_it_deliberately(self):
        first = services.generate_lesson(self.user, use_ai=False)
        second = services.regenerate(self.user, use_ai=False)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(Lesson.objects.count(), 1)

    def test_completing_activities_advances_the_status(self):
        lesson = services.generate_lesson(self.user, use_ai=False)
        self.assertEqual(lesson.status, Lesson.Status.READY)

        activities = list(lesson.activities.all())
        activities[0].complete()
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, Lesson.Status.IN_PROGRESS)

        for activity in activities[1:]:
            activity.complete()
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, Lesson.Status.COMPLETED)
        self.assertIsNotNone(lesson.completed_at)

    def test_completing_twice_does_not_move_the_timestamp(self):
        lesson = services.generate_lesson(self.user, use_ai=False)
        activity = lesson.activities.first()
        activity.complete()
        first = activity.completed_at
        activity.complete()
        activity.refresh_from_db()
        self.assertEqual(activity.completed_at, first)

    def test_progress_is_a_fraction_of_activities_done(self):
        lesson = services.generate_lesson(self.user, use_ai=False)
        total = lesson.activities.count()
        lesson.activities.first().complete()
        lesson.refresh_from_db()
        self.assertAlmostEqual(lesson.progress, 1 / total)

    def test_lessons_are_one_per_learner_per_day(self):
        other = User.objects.create_user(username="life2", password=PASSWORD)
        services.generate_lesson(self.user, use_ai=False)
        services.generate_lesson(other, use_ai=False)
        self.assertEqual(Lesson.objects.filter(date=timezone.localdate()).count(), 2)
