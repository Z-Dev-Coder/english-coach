import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.profiles.constants import ALL_SKILLS, SCHEDULABLE_SKILLS, cefr_shift
from apps.profiles.models import LearnerProfile, SkillProgress, StudySession
from apps.profiles.services import (
    build_daily_plan,
    current_streak,
    dashboard_payload,
    record_practice,
    skill_weights,
    weekly_minutes,
)

User = get_user_model()


class BootstrapTests(TestCase):
    def test_new_user_gets_profile_and_all_skill_rows(self):
        user = User.objects.create_user(username="lena", password="pw-for-tests-123")
        self.assertTrue(LearnerProfile.objects.filter(user=user).exists())
        self.assertEqual(
            sorted(user.skill_progress.values_list("skill", flat=True)), sorted(ALL_SKILLS)
        )

    def test_bootstrap_is_idempotent_on_resave(self):
        user = User.objects.create_user(username="lena", password="pw-for-tests-123")
        user.email = "lena@example.com"
        user.save()
        self.assertEqual(user.skill_progress.count(), len(ALL_SKILLS))


class PlannerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pat", password="pw-for-tests-123")

    def test_plan_minutes_sum_exactly_to_requested_total(self):
        for total in (10, 15, 30, 45, 60, 90):
            with self.subTest(total=total):
                plan = build_daily_plan(self.user, minutes=total)
                self.assertEqual(sum(b.minutes for b in plan), total)

    def test_plan_never_contains_empty_blocks(self):
        plan = build_daily_plan(self.user, minutes=30)
        self.assertTrue(all(b.minutes > 0 for b in plan))

    def test_review_always_present_even_on_a_tiny_day(self):
        plan = build_daily_plan(self.user, minutes=5)
        self.assertEqual(plan[0].skill, "review")
        self.assertGreaterEqual(plan[0].minutes, 3)

    def test_weak_skill_receives_more_time_than_strong_skill(self):
        self.user.skill_progress.filter(skill="listening").update(score=20)
        self.user.skill_progress.filter(skill="reading").update(score=95)
        minutes = {b.skill: b.minutes for b in build_daily_plan(self.user, minutes=60)}
        self.assertGreater(minutes["listening"], minutes["reading"])

    def test_no_skill_is_dropped_entirely_so_interleaving_survives(self):
        # Even with one catastrophically weak skill, the others keep a share.
        self.user.skill_progress.filter(skill="listening").update(score=0)
        minutes = {b.skill: b.minutes for b in build_daily_plan(self.user, minutes=60)}
        for skill in SCHEDULABLE_SKILLS:
            self.assertGreater(minutes.get(skill, 0), 0, f"{skill} was dropped from the plan")

    def test_explicit_priority_raises_a_skills_weight(self):
        before = skill_weights(self.user)["writing"]
        profile = LearnerProfile.objects.get(user=self.user)
        profile.priority_skills = ["writing"]
        profile.save()
        self.assertGreater(skill_weights(self.user)["writing"], before)

    def test_recently_practiced_skill_loses_weight_to_a_stale_one(self):
        now = timezone.now()
        self.user.skill_progress.filter(skill="speaking").update(last_practiced_at=now)
        self.user.skill_progress.filter(skill="writing").update(
            last_practiced_at=now - dt.timedelta(days=30)
        )
        weights = skill_weights(self.user, now=now)
        self.assertGreater(weights["writing"], weights["speaking"])

    def test_plan_uses_profile_daily_minutes_by_default(self):
        profile = LearnerProfile.objects.get(user=self.user)
        profile.daily_minutes = 45
        profile.save()
        self.assertEqual(sum(b.minutes for b in build_daily_plan(self.user)), 45)


class WeaknessTests(TestCase):
    """A skill is only "weak" once there is evidence for it."""

    def setUp(self):
        self.user = User.objects.create_user(username="fresh", password="pw-for-tests-123")

    def test_new_learner_has_no_weak_skills(self):
        self.assertTrue(all(not sp.is_weak for sp in self.user.skill_progress.all()))
        self.assertTrue(all(sp.is_unassessed for sp in self.user.skill_progress.all()))

    def test_new_learner_plan_says_baseline_not_weakness(self):
        reasons = " ".join(b.reason for b in build_daily_plan(self.user, minutes=30))
        self.assertIn("sets your baseline", reasons)
        self.assertNotIn("weakest areas", reasons)

    def test_low_score_with_evidence_is_weak(self):
        record_practice(self.user, "listening", -60)
        sp = SkillProgress.objects.get(user=self.user, skill="listening")
        self.assertTrue(sp.is_weak)
        self.assertFalse(sp.is_unassessed)

    def test_measured_weakness_is_named_in_the_plan(self):
        for _ in range(5):
            record_practice(self.user, "listening", -40)
        reasons = " ".join(b.reason for b in build_daily_plan(self.user, minutes=30))
        self.assertIn("weakest areas", reasons)


class StreakTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sam", password="pw-for-tests-123")
        self.today = timezone.localdate()

    def _session(self, days_ago: int, status=StudySession.Status.COMPLETED):
        started = timezone.now() - dt.timedelta(days=days_ago)
        return StudySession.objects.create(
            user=self.user, started_at=started, status=status, active_seconds=600
        )

    def test_no_sessions_means_no_streak(self):
        self.assertEqual(current_streak(self.user, self.today), 0)

    def test_consecutive_days_counted(self):
        for days_ago in (0, 1, 2):
            self._session(days_ago)
        self.assertEqual(current_streak(self.user, self.today), 3)

    def test_streak_survives_a_day_that_is_not_over_yet(self):
        # Studied yesterday and the day before, nothing yet today.
        self._session(1)
        self._session(2)
        self.assertEqual(current_streak(self.user, self.today), 2)

    def test_gap_breaks_the_streak(self):
        self._session(0)
        self._session(3)
        self.assertEqual(current_streak(self.user, self.today), 1)

    def test_abandoned_sessions_do_not_count(self):
        self._session(0, status=StudySession.Status.ABANDONED)
        self.assertEqual(current_streak(self.user, self.today), 0)

    def test_weekly_minutes_sums_active_time_only(self):
        self._session(0)
        self._session(0)
        self.assertEqual(weekly_minutes(self.user, self.today), 20)


class ProgressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="max", password="pw-for-tests-123")

    def test_practice_is_damped_not_applied_raw(self):
        sp = record_practice(self.user, "writing", score_delta=50)
        self.assertLess(sp.score, 100)
        self.assertAlmostEqual(sp.score, 50 + 50 * 0.3, places=5)

    def test_score_is_clamped_to_range(self):
        for _ in range(50):
            record_practice(self.user, "writing", score_delta=100)
        self.assertLessEqual(SkillProgress.objects.get(user=self.user, skill="writing").score, 100)
        for _ in range(100):
            record_practice(self.user, "writing", score_delta=-100)
        self.assertGreaterEqual(SkillProgress.objects.get(user=self.user, skill="writing").score, 0)

    def test_confidence_grows_with_attempts_but_never_exceeds_one(self):
        first = record_practice(self.user, "reading", 1).confidence
        for _ in range(30):
            record_practice(self.user, "reading", 1)
        latest = SkillProgress.objects.get(user=self.user, skill="reading")
        self.assertGreater(latest.confidence, first)
        self.assertLessEqual(latest.confidence, 1.0)

    def test_level_tracks_score(self):
        SkillProgress.objects.filter(user=self.user, skill="grammar").update(score=10)
        self.assertEqual(record_practice(self.user, "grammar", -5).level, "A1")
        SkillProgress.objects.filter(user=self.user, skill="grammar").update(score=95)
        self.assertEqual(record_practice(self.user, "grammar", 5).level, "C2")

    def test_skills_are_tracked_independently(self):
        record_practice(self.user, "listening", 40)
        listening = SkillProgress.objects.get(user=self.user, skill="listening")
        speaking = SkillProgress.objects.get(user=self.user, skill="speaking")
        self.assertNotEqual(listening.score, speaking.score)


class CEFRTests(TestCase):
    def test_shift_clamps_at_both_ends(self):
        self.assertEqual(cefr_shift("A1", -5), "A1")
        self.assertEqual(cefr_shift("C2", 5), "C2")
        self.assertEqual(cefr_shift("B1", 1), "B2")

    def test_unknown_level_falls_back_to_b1(self):
        self.assertEqual(cefr_shift("nonsense", 0), "B1")


class DashboardPayloadTests(TestCase):
    def test_payload_has_everything_the_home_screen_needs(self):
        user = User.objects.create_user(username="dash", password="pw-for-tests-123")
        payload = dashboard_payload(user)
        for key in ("learner", "streak_days", "plan", "skills", "weak_areas", "focus"):
            self.assertIn(key, payload)
        self.assertEqual(len(payload["skills"]), len(ALL_SKILLS))
        self.assertLessEqual(len(payload["focus"]), 2)


class ResetLearnerTests(TestCase):
    """Contaminated history makes every later decision wrong, so a clean reset
    has to be complete — and has to leave the shared library alone."""

    def setUp(self):
        from io import StringIO

        self.out = StringIO()
        self.user = User.objects.create_user(username="dirty", password="pw-for-tests-123")
        self.other = User.objects.create_user(username="clean", password="pw-for-tests-123")

    def _make_history(self, user):
        from apps.conversation.models import ConversationMessage, ConversationSession
        from apps.lessons.services import generate_lesson
        from apps.mistakes.services import record
        from apps.review.services import add_to_learning, answer
        from apps.skills.services import check_dictation
        from apps.vocabulary.models import Expression

        expression = Expression.objects.create(text=f"deal with {user.id}", meaning="handle")
        progress = add_to_learning(user, expression)
        answer(progress, 3)
        check_dictation(user, expected="one two", written="one three")
        record(user, incorrect="I discussed about it", correct="I discussed it")
        session = ConversationSession.objects.create(user=user)
        ConversationMessage.objects.create(session=session, role="learner", content="hi")
        generate_lesson(user, use_ai=False)
        StudySession.objects.create(user=user, active_seconds=600)
        record_practice(user, "writing", -40)

    def _reset(self, **kwargs):
        from django.core.management import call_command

        call_command("reset_learner", user="dirty", yes=True, stdout=self.out, **kwargs)

    def test_all_personal_history_is_removed(self):
        from apps.conversation.models import ConversationSession
        from apps.lessons.models import Lesson
        from apps.mistakes.models import Mistake
        from apps.review.models import Review
        from apps.skills.models import SkillAttempt
        from apps.vocabulary.models import VocabularyProgress

        self._make_history(self.user)
        self._reset()

        for model in (Review, SkillAttempt, Mistake, Lesson, StudySession, VocabularyProgress):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.filter(user=self.user).count(), 0)
        self.assertEqual(ConversationSession.objects.filter(user=self.user).count(), 0)

    def test_skill_scores_return_to_their_starting_values(self):
        self._make_history(self.user)
        self.assertLess(
            SkillProgress.objects.get(user=self.user, skill="writing").score, 50
        )
        self._reset()
        rows = SkillProgress.objects.filter(user=self.user)
        self.assertEqual(rows.count(), len(ALL_SKILLS))
        for row in rows:
            with self.subTest(skill=row.skill):
                self.assertEqual(row.score, 50.0)
                self.assertEqual(row.attempts, 0)
                self.assertEqual(row.confidence, 0.0)

    def test_another_learner_is_untouched(self):
        from apps.review.models import Review

        self._make_history(self.user)
        self._make_history(self.other)
        self._reset()
        self.assertGreater(Review.objects.filter(user=self.other).count(), 0)
        self.assertGreater(self.other.vocabulary.count(), 0)

    def test_the_shared_library_survives(self):
        """Expressions, passages and articles are not personal history."""
        from apps.skills.models import Passage
        from apps.vocabulary.models import Expression

        Passage.objects.create(title="Shared", text="A shared passage.")
        self._make_history(self.user)
        expressions = Expression.objects.count()
        self._reset()
        self.assertEqual(Expression.objects.count(), expressions)
        self.assertEqual(Passage.objects.filter(owner__isnull=True).count(), 1)

    def test_the_account_and_its_settings_survive(self):
        profile = LearnerProfile.objects.get(user=self.user)
        profile.interests = ["technology"]
        profile.daily_minutes = 45
        profile.save()

        self._make_history(self.user)
        self._reset()

        self.assertTrue(User.objects.filter(username="dirty").exists())
        profile.refresh_from_db()
        self.assertEqual(profile.interests, ["technology"])
        self.assertEqual(profile.daily_minutes, 45)

    def test_keep_vocabulary_retains_the_words_but_clears_the_schedule(self):
        from apps.vocabulary.models import MasteryState, VocabularyProgress

        self._make_history(self.user)
        self._reset(keep_vocabulary=True)

        rows = VocabularyProgress.objects.filter(user=self.user)
        self.assertGreater(rows.count(), 0)
        for row in rows:
            with self.subTest(word=row.expression_id):
                self.assertEqual(row.state, MasteryState.NEW)
                self.assertIsNone(row.stability)
                self.assertEqual(row.reps, 0)

    def test_an_unknown_user_is_a_clean_error(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("reset_learner", user="nobody", yes=True, stdout=self.out)
