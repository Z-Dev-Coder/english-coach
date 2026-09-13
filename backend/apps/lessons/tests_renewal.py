"""Lessons renew on completion, not on the calendar.

The old rule was one lesson per learner per day, looked up by today's date.
That assumed the learner studies every day: miss two, and each morning minted a
fresh lesson and abandoned the half-finished one -- so a plan was lost by not
opening the app, which punishes exactly the weeks when someone most needs to
pick up where they left off.
"""
import datetime as dt
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.lessons import services
from apps.lessons.models import Lesson
from apps.skills.models import Passage


class RenewalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="renew", password="renewal12345"
        )
        for index in range(4):
            Passage.objects.create(
                title=f"Passage {index}", text="A sentence. Another one.", level="B1", owner=None
            )

    def _finish(self, lesson):
        for activity in lesson.activities.all():
            activity.complete()
        lesson.refresh_from_db()
        return lesson

    def test_an_unfinished_lesson_survives_a_week_away(self):
        """The whole point. Time off should cost momentum, not progress."""
        today = timezone.now().date()
        first = services.generate_lesson(self.user, date=today, use_ai=False)
        first.activities.first().complete()

        later = services.generate_lesson(
            self.user, date=today + dt.timedelta(days=7), use_ai=False
        )
        self.assertEqual(first.id, later.id, "a week away replaced the unfinished plan")

    def test_progress_is_still_there_when_they_come_back(self):
        today = timezone.now().date()
        lesson = services.generate_lesson(self.user, date=today, use_ai=False)
        done = lesson.activities.first()
        done.complete()

        later = services.generate_lesson(
            self.user, date=today + dt.timedelta(days=12), use_ai=False
        )
        self.assertIsNotNone(later.activities.get(id=done.id).completed_at)

    def test_finishing_it_is_what_produces_the_next_one(self):
        today = timezone.now().date()
        first = self._finish(services.generate_lesson(self.user, date=today, use_ai=False))
        self.assertEqual(first.status, Lesson.Status.COMPLETED)

        second = services.generate_lesson(self.user, date=today, use_ai=False)
        self.assertNotEqual(first.id, second.id, "completing it did not produce a new lesson")

    def test_the_same_day_is_not_a_barrier_once_it_is_finished(self):
        # The old unique(user, date) constraint would have refused this. A
        # learner who finishes early should be able to keep going.
        today = timezone.now().date()
        self._finish(services.generate_lesson(self.user, date=today, use_ai=False))
        second = services.generate_lesson(self.user, date=today, use_ai=False)
        self.assertEqual(second.status, Lesson.Status.READY)

    def test_asking_twice_returns_the_same_lesson(self):
        # Refreshing the page must never swap the material out.
        first = services.generate_lesson(self.user, use_ai=False)
        second = services.generate_lesson(self.user, use_ai=False)
        self.assertEqual(first.id, second.id)

    def test_only_one_unfinished_lesson_can_exist(self):
        services.generate_lesson(self.user, use_ai=False)
        unfinished = Lesson.objects.filter(user=self.user).exclude(
            status__in=[Lesson.Status.COMPLETED, Lesson.Status.ABANDONED]
        )
        self.assertEqual(unfinished.count(), 1)

    def test_a_retired_lesson_does_not_block_the_next_one(self):
        first = services.generate_lesson(self.user, use_ai=False)
        second = services.regenerate(self.user, use_ai=False)
        first.refresh_from_db()

        self.assertEqual(first.status, Lesson.Status.ABANDONED)
        self.assertEqual(services.current_lesson(self.user).id, second.id)

    def test_a_retired_lesson_still_counts_as_material_already_seen(self):
        """Retired rather than deleted, so rotation is not reset by a re-roll.

        Deleting the row would let the replacement hand back the very passage
        the discarded lesson had just used -- the loop this was meant to end.
        """
        first = services.generate_lesson(self.user, use_ai=False)
        used = {
            activity.params.get("passage_id")
            for activity in first.activities.filter(kind__in=["listening", "reading"])
            if activity.params.get("passage_id")
        }
        if not used:
            self.skipTest("this plan had no passage work to compare")

        second = services.regenerate(self.user, use_ai=False)
        replacement = {
            activity.params.get("passage_id")
            for activity in second.activities.filter(kind__in=["listening", "reading"])
            if activity.params.get("passage_id")
        }
        self.assertFalse(used & replacement, "the replacement reused the discarded passage")


class StatusFromPrefetchTests(TestCase):
    """A finished lesson must register as finished even when prefetched.

    The viewset loads lessons with `prefetch_related("activities")`, and Django
    populates each child's forward FK cache with that same parent. So the last
    activity's `self.lesson.activities.all()` returned the list captured
    *before* it was saved, counted one short, and left a fully completed lesson
    sitting in "in progress" forever -- which, now that renewal is driven by
    completion, meant the next lesson could never be built.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prefetch", password="prefetch12345"
        )

    def test_completing_the_last_activity_through_a_prefetched_lesson(self):
        services.generate_lesson(self.user, use_ai=False)

        # Exactly how the viewset loads it.
        lesson = Lesson.objects.prefetch_related("activities").get(user=self.user)
        for activity in lesson.activities.all():
            activity.complete()

        lesson.refresh_from_db()
        self.assertEqual(lesson.status, Lesson.Status.COMPLETED)
        self.assertIsNotNone(lesson.completed_at)

    def test_and_the_next_lesson_can_then_be_built(self):
        first = services.generate_lesson(self.user, use_ai=False)
        prefetched = Lesson.objects.prefetch_related("activities").get(id=first.id)
        for activity in prefetched.activities.all():
            activity.complete()

        second = services.generate_lesson(self.user, use_ai=False)
        self.assertNotEqual(first.id, second.id)


class EnrichmentCacheTests(TestCase):
    """Consecutive lessons must not be served each other's words.

    The AI cache was keyed entirely on the learner's context -- level, weak
    skills, mistakes, interests, plan shape. All of that is deliberately
    slow-moving, so two lessons in a row hashed identically and the second was
    handed the first one's title, theme and prompts, undoing the rotation of
    the material underneath.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cachekey", password="cachekey12345"
        )

    def test_the_cache_key_changes_between_lessons(self):
        from apps.lessons import services as lesson_services

        seen = []

        def fake_cached(kind, payload, build):
            seen.append(payload.get("sequence"))
            return {"title": "T", "theme": "", "encouragement": "", "activities": []}

        with mock.patch("apps.ai.services.cached", side_effect=fake_cached):
            first = lesson_services.generate_lesson(self.user, use_ai=True)
            for activity in first.activities.all():
                activity.complete()
            lesson_services.generate_lesson(self.user, use_ai=True)

        self.assertEqual(len(seen), 2)
        self.assertNotEqual(seen[0], seen[1], "both lessons shared one cache key")


class LessonHistoryEndpointTests(TestCase):
    """The history list: every lesson, newest first, only the learner's own."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.user = get_user_model().objects.create_user(username="hist", password="history12345")
        self.other = get_user_model().objects.create_user(username="other", password="history12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_lists_finished_and_current_lessons_newest_first(self):
        first = services.generate_lesson(self.user, use_ai=False)
        for activity in first.activities.all():
            activity.complete()
        second = services.generate_lesson(self.user, use_ai=False)

        response = self.client.get("/api/lessons/")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.data]
        # Same date, so the id tiebreak is what makes this deterministic.
        self.assertEqual(ids, [second.id, first.id])

    def test_never_shows_another_learners_lessons(self):
        theirs = services.generate_lesson(self.other, use_ai=False)
        self.assertNotIn(theirs.id, [item["id"] for item in self.client.get("/api/lessons/").data])
        self.assertEqual(self.client.get(f"/api/lessons/{theirs.id}/").status_code, 404)
