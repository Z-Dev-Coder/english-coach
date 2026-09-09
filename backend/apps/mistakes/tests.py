"""Tests for the mistake bank."""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.mistakes import services
from apps.mistakes.models import (
    Category,
    Mistake,
    MistakeOccurrence,
    build_key,
    normalize_category,
)

User = get_user_model()
PASSWORD = "pw-for-tests-123"


class CategoryTests(TestCase):
    def test_known_categories_pass_through(self):
        self.assertEqual(normalize_category("preposition"), Category.PREPOSITION)

    def test_aliases_are_folded_in(self):
        """Otherwise the bank fragments into near-duplicate buckets that never
        accumulate enough evidence to act on."""
        self.assertEqual(normalize_category("verb_tense"), Category.GRAMMAR)
        self.assertEqual(normalize_category("Articles"), Category.ARTICLE)
        self.assertEqual(normalize_category("word choice"), Category.WORD_CHOICE)

    def test_an_unknown_category_defaults_to_grammar(self):
        self.assertEqual(normalize_category("something odd"), Category.GRAMMAR)
        self.assertEqual(normalize_category(""), Category.GRAMMAR)


class TrackabilityTests(TestCase):
    def test_a_real_correction_is_tracked(self):
        self.assertTrue(services.is_trackable("discussed about", "discussed"))

    def test_identical_text_is_not_a_mistake(self):
        self.assertFalse(services.is_trackable("the same", "the same"))

    def test_punctuation_only_changes_are_ignored(self):
        """Small models produce a lot of comma advice; recording it would bury
        the genuine repeated errors."""
        self.assertFalse(services.is_trackable("Yes I did", "Yes, I did"))

    def test_case_only_changes_are_ignored(self):
        self.assertFalse(services.is_trackable("friday", "Friday"))

    def test_very_short_fragments_are_ignored(self):
        self.assertFalse(services.is_trackable("a", "an"))


class RecordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mist", password=PASSWORD)

    def test_a_correction_creates_a_mistake_with_one_occurrence(self):
        mistake = services.record(
            self.user,
            incorrect="I discussed about the problem",
            correct="I discussed the problem",
            category="preposition",
            explanation="'Discuss' takes no preposition.",
        )
        self.assertEqual(mistake.occurrences, 1)
        self.assertEqual(mistake.category, Category.PREPOSITION)
        self.assertEqual(mistake.occurrence_log.count(), 1)

    def test_the_same_mistake_increments_rather_than_duplicating(self):
        for _ in range(3):
            services.record(
                self.user, incorrect="I very like it", correct="I really like it"
            )
        self.assertEqual(Mistake.objects.count(), 1)
        mistake = Mistake.objects.get()
        self.assertEqual(mistake.occurrences, 3)
        self.assertEqual(mistake.occurrence_log.count(), 3)

    def test_matching_ignores_case_and_punctuation(self):
        services.record(self.user, incorrect="I very like it.", correct="I really like it.")
        services.record(self.user, incorrect="i VERY like it", correct="i really like it")
        self.assertEqual(Mistake.objects.count(), 1)

    def test_untrackable_corrections_return_nothing(self):
        self.assertIsNone(services.record(self.user, incorrect="Yes", correct="Yes,"))
        self.assertEqual(Mistake.objects.count(), 0)

    def test_different_learners_keep_separate_banks(self):
        other = User.objects.create_user(username="mist2", password=PASSWORD)
        services.record(self.user, incorrect="I very like it", correct="I really like it")
        services.record(other, incorrect="I very like it", correct="I really like it")
        self.assertEqual(Mistake.objects.count(), 2)

    def test_the_occurrence_records_where_it_happened(self):
        services.record(
            self.user,
            incorrect="I very like it",
            correct="I really like it",
            origin=MistakeOccurrence.Origin.CONVERSATION,
            context="I very like it, actually.",
        )
        occurrence = MistakeOccurrence.objects.get()
        self.assertEqual(occurrence.origin, "conversation")
        self.assertIn("actually", occurrence.context)

    def test_an_explanation_is_filled_in_if_it_was_missing(self):
        services.record(self.user, incorrect="I very like it", correct="I really like it")
        services.record(
            self.user,
            incorrect="I very like it",
            correct="I really like it",
            explanation="'Very' does not modify verbs.",
        )
        self.assertIn("does not modify", Mistake.objects.get().explanation)

    def test_keys_are_stable_across_formatting(self):
        self.assertEqual(build_key("Discussed  About", "discussed"), build_key("discussed about", "Discussed"))


class FeedbackIngestionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fb", password=PASSWORD)

    def test_writing_feedback_shape_is_accepted(self):
        recorded = services.record_from_feedback(
            self.user,
            [
                {
                    "original": "I discussed about it",
                    "correction": "I discussed it",
                    "category": "preposition",
                    "explanation": "No preposition.",
                }
            ],
            origin="writing",
        )
        self.assertEqual(len(recorded), 1)

    def test_conversation_feedback_shape_is_accepted(self):
        """Writing uses `correction`, conversation uses `natural`."""
        recorded = services.record_from_feedback(
            self.user,
            [{"original": "I very like it", "natural": "I really like it", "category": "word_choice"}],
            origin="conversation",
        )
        self.assertEqual(len(recorded), 1)
        self.assertEqual(Mistake.objects.get().correct, "I really like it")

    def test_malformed_entries_are_skipped_without_raising(self):
        recorded = services.record_from_feedback(
            self.user, ["not a dict", {}, {"original": "x"}, None], origin="writing"
        )
        self.assertEqual(recorded, [])

    def test_an_empty_list_is_fine(self):
        self.assertEqual(services.record_from_feedback(self.user, [], origin="writing"), [])
        self.assertEqual(services.record_from_feedback(self.user, None, origin="writing"), [])


class StatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="st", password=PASSWORD)

    def _old_mistake(self, days_ago, occurrences=2):
        mistake = services.record(
            self.user, incorrect="I discussed about it", correct="I discussed it"
        )
        Mistake.objects.filter(pk=mistake.pk).update(
            last_seen_at=timezone.now() - dt.timedelta(days=days_ago), occurrences=occurrences
        )
        return Mistake.objects.get(pk=mistake.pk)

    def test_a_stale_mistake_becomes_improving(self):
        self._old_mistake(days_ago=30)
        services.refresh_statuses(self.user)
        self.assertEqual(Mistake.objects.get().status, Mistake.Status.IMPROVING)

    def test_a_recent_mistake_stays_active(self):
        self._old_mistake(days_ago=2)
        services.refresh_statuses(self.user)
        self.assertEqual(Mistake.objects.get().status, Mistake.Status.ACTIVE)

    def test_making_it_again_reactivates_it(self):
        """Silence is weak evidence of improvement; a repeat is strong evidence
        against it."""
        self._old_mistake(days_ago=30)
        services.refresh_statuses(self.user)
        services.record(self.user, incorrect="I discussed about it", correct="I discussed it")
        self.assertEqual(Mistake.objects.get().status, Mistake.Status.ACTIVE)

    def test_avoiding_it_repeatedly_marks_it_improving(self):
        mistake = self._old_mistake(days_ago=1)
        for _ in range(3):
            services.mark_avoided(self.user, mistake.id)
        mistake.refresh_from_db()
        self.assertEqual(mistake.times_avoided, 3)
        self.assertEqual(mistake.status, Mistake.Status.IMPROVING)

    def test_avoiding_another_learners_mistake_does_nothing(self):
        mistake = self._old_mistake(days_ago=1)
        other = User.objects.create_user(username="nosy", password=PASSWORD)
        self.assertIsNone(services.mark_avoided(other, mistake.id))


class SurfacingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="surf", password=PASSWORD)

    def test_only_repeated_mistakes_are_persistent(self):
        services.record(self.user, incorrect="a one off mistake", correct="a one-time slip")
        for _ in range(2):
            services.record(self.user, incorrect="I very like it", correct="I really like it")

        persistent = services.persistent(self.user)
        self.assertEqual(len(persistent), 1)
        self.assertEqual(persistent[0].correct, "I really like it")

    def test_the_most_frequent_come_first(self):
        for _ in range(2):
            services.record(self.user, incorrect="I very like it", correct="I really like it")
        for _ in range(5):
            services.record(self.user, incorrect="I discussed about it", correct="I discussed it")
        self.assertEqual(services.persistent(self.user)[0].occurrences, 5)

    def test_weak_categories_reflect_the_bank(self):
        for index in range(3):
            services.record(
                self.user,
                incorrect=f"a preposition slip {index}",
                correct=f"a preposition fix {index}",
                category="preposition",
            )
        services.record(
            self.user, incorrect="an article slip", correct="an article fix", category="article"
        )
        self.assertEqual(services.weak_categories(self.user)[0], Category.PREPOSITION)

    def test_practice_items_turn_mistakes_into_tasks(self):
        for _ in range(2):
            services.record(
                self.user,
                incorrect="I discussed about it",
                correct="I discussed it",
                context="I discussed about it with my team.",
            )
        items = services.practice_items(self.user)
        self.assertEqual(len(items), 1)
        self.assertIn("discussed it", items[0]["task"])
        self.assertIn("my team", items[0]["context"])

    def test_summary_counts_by_status_and_category(self):
        services.record(self.user, incorrect="I very like it", correct="I really like it")
        summary = services.summary(self.user)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["active"], 1)
        self.assertIn("categories", summary)

    def test_summary_is_safe_for_a_learner_with_no_mistakes(self):
        summary = services.summary(self.user)
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["by_category"], {})


class IntegrationTests(TestCase):
    """The bank must actually be fed by the activities that produce corrections."""

    def setUp(self):
        self.user = User.objects.create_user(username="int", password=PASSWORD)

    def test_ai_writing_feedback_populates_the_bank(self):
        from unittest import mock

        from apps.ai.providers.base import AIProvider
        from apps.skills.services import evaluate_writing

        provider = mock.Mock(spec=AIProvider)
        provider.evaluate_writing.return_value = {
            "issues": [
                {
                    "original": "I discussed about the problem",
                    "correction": "I discussed the problem",
                    "explanation": "No preposition after 'discuss'.",
                    "category": "preposition",
                }
            ],
            "strengths": [],
            "natural_version": "",
        }
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=provider):
            evaluate_writing(self.user, text="I discussed about the problem with my team today.")

        mistake = Mistake.objects.get()
        self.assertEqual(mistake.category, Category.PREPOSITION)
        self.assertEqual(mistake.occurrence_log.first().origin, "writing")

    def test_repeated_mistakes_reach_the_lesson_generator(self):
        from apps.lessons.services import learner_context

        for _ in range(2):
            services.record(
                self.user,
                incorrect="I discussed about it",
                correct="I discussed it",
                category="preposition",
            )
        context = learner_context(self.user)
        self.assertIn("preposition", context["recent_mistakes"])
        self.assertEqual(context["repeated_mistakes"][0]["times"], 2)
