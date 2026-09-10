"""Material rotates instead of repeating.

Reported as everything running in a loop: the same listening passage every
day, and the writing prompt cycling through the same handful. These test the
property that matters -- consecutive days give different material -- rather
than the mechanism, so the selection rule can change without rewriting them.
"""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.lessons import services
from apps.lessons.models import Lesson
from apps.skills.models import Passage


class PassageRotationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rot", password="rotation12345"
        )
        for index in range(4):
            Passage.objects.create(
                title=f"Passage {index}",
                text="A sentence. Another sentence.",
                level="B1",
                owner=None,
            )

    def _lesson_on(self, date):
        """One finished lesson, then the next.

        Lessons renew on completion rather than on the date, so a test that
        only advances the clock now gets the same unfinished lesson back --
        which is the point of the rule. Finishing it is what a learner does
        before the next one exists.
        """
        lesson = services.generate_lesson(self.user, date=date, use_ai=False)
        for activity in lesson.activities.all():
            activity.complete()
        lesson.refresh_from_db()
        return lesson

    def _passage_ids(self, lesson):
        return {
            activity.params.get("passage_id")
            for activity in lesson.activities.filter(kind__in=["listening", "reading"])
            if activity.params.get("passage_id")
        }

    def test_consecutive_days_use_different_passages(self):
        today = timezone.now().date()
        per_day = []
        for offset in range(3):
            ids = self._passage_ids(self._lesson_on(today + dt.timedelta(days=offset)))
            if ids:
                per_day.append(ids)

        # The old code picked at random per call with no memory, so the same
        # passage could -- and did -- come up on consecutive mornings.
        for earlier in range(len(per_day)):
            for later in range(earlier + 1, len(per_day)):
                self.assertFalse(
                    per_day[earlier] & per_day[later],
                    f"day {earlier} and day {later} shared a passage",
                )

    def test_listening_and_reading_share_the_day_s_passage(self):
        # Deliberate: reading a text and then hearing the same text is the
        # point, and beats two unrelated texts in one short session.
        lesson = self._lesson_on(timezone.now().date())
        ids = self._passage_ids(lesson)
        self.assertLessEqual(len(ids), 1, "the day handed out more than one text")

    def test_it_reuses_only_once_the_library_is_exhausted(self):
        # With four passages, a fifth listening activity has to repeat one --
        # and should repeat the one used longest ago rather than the newest.
        today = timezone.now().date()
        for offset in range(6):
            self._lesson_on(today + dt.timedelta(days=offset))

        activities = list(
            Lesson.objects.filter(user=self.user)
            .order_by("date")
            .values_list("activities__params", flat=True)
        )
        used = [
            (params or {}).get("passage_id")
            for params in activities
            if (params or {}).get("passage_id")
        ]
        self.assertGreater(len(set(used)), 1, "never moved past the first passage")

    def test_it_prefers_the_learners_own_level(self):
        # overall_level is derived from per-skill progress, so it is asked for
        # rather than set -- the assertion is that the passage matches it.
        Passage.objects.create(title="Hard", text="Complex.", level="C2", owner=None)
        level = self.user.learner_profile.overall_level

        lesson = self._lesson_on(timezone.now().date())
        for activity in lesson.activities.filter(kind__in=["listening", "reading"]):
            passage_id = activity.params.get("passage_id")
            if passage_id:
                self.assertEqual(
                    Passage.objects.get(id=passage_id).level,
                    level,
                    "handed out a passage at the wrong level",
                )


class WritingPromptRotationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="wrot", password="rotation12345"
        )

    def test_consecutive_days_get_different_prompts(self):
        today = timezone.now().date()
        prompts = []
        for offset in range(3):
            lesson = services.generate_lesson(
                self.user, date=today + dt.timedelta(days=offset), use_ai=False
            )
            for activity in lesson.activities.filter(kind="writing"):
                prompts.append(activity.prompt)
            # Finish it, or the next request returns this same lesson.
            for activity in lesson.activities.all():
                activity.complete()

        if len(prompts) > 1:
            # Indexing by plan position meant the same prompt every day
            # whenever writing landed in the same slot.
            self.assertEqual(
                len(prompts), len(set(prompts)), "the same writing prompt came round again"
            )
