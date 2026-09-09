"""Tests for the review engine: queue construction, grading, and state changes."""
import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.review import services
from apps.review.fsrs import Rating
from apps.review.models import ExerciseType, Review
from apps.vocabulary.models import (
    ExampleSentence,
    Expression,
    Kind,
    MasteryState,
    VocabularyProgress,
    normalize,
)

User = get_user_model()
PASSWORD = "pw-for-tests-123"


def make_expression(text="figure out", kind=Kind.PHRASAL_VERB, example=None, **kwargs):
    expression = Expression.objects.create(
        text=text, kind=kind, meaning=kwargs.pop("meaning", "to understand something"), **kwargs
    )
    if example:
        ExampleSentence.objects.create(expression=expression, text=example)
    return expression


class ExpressionModelTests(TestCase):
    def test_normalization_is_case_and_space_insensitive(self):
        self.assertEqual(normalize("  Figure   Out "), "figure out")

    def test_same_text_and_kind_cannot_be_duplicated(self):
        make_expression("deal with")
        from django.db.utils import IntegrityError

        with self.assertRaises(IntegrityError):
            make_expression("  DEAL WITH  ")

    def test_same_text_may_exist_as_a_different_kind(self):
        make_expression("well", kind=Kind.WORD)
        make_expression("well", kind=Kind.PHRASE)  # must not raise
        self.assertEqual(Expression.objects.filter(normalized="well").count(), 2)

    def test_multi_word_detection(self):
        self.assertTrue(make_expression("look into").is_multi_word)
        self.assertFalse(make_expression("resilient", kind=Kind.WORD).is_multi_word)


class ClozeTests(TestCase):
    def test_the_expression_is_blanked_out(self):
        expression = make_expression("deal with", example="I had to deal with it today.")
        self.assertEqual(expression.examples.first().cloze(), "I had to ______ it today.")

    def test_matching_ignores_case(self):
        expression = make_expression("no rush", example="No rush, take your time.")
        self.assertEqual(expression.examples.first().cloze(), "______, take your time.")

    def test_a_sentence_without_the_exact_form_is_left_intact(self):
        """Better to show a full sentence than to blank the wrong words."""
        expression = make_expression("end up", example="She ended up staying.")
        self.assertEqual(expression.examples.first().cloze(), "She ended up staying.")


class SchedulingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rev", password=PASSWORD)
        self.progress = services.add_to_learning(self.user, make_expression())

    def test_new_items_start_due_and_unscheduled(self):
        self.assertEqual(self.progress.state, MasteryState.NEW)
        self.assertIsNone(self.progress.stability)
        self.assertEqual(self.progress.reps, 0)

    def test_answering_schedules_the_item_into_the_future(self):
        log = services.answer(self.progress, Rating.GOOD, exercise=ExerciseType.MEET)
        self.progress.refresh_from_db()
        self.assertGreater(self.progress.due_at, timezone.now())
        self.assertEqual(self.progress.reps, 1)
        self.assertIsNotNone(self.progress.stability)
        self.assertEqual(log.scheduled_days, self.progress.last_interval_days)

    def test_better_grades_buy_longer_intervals(self):
        user2 = User.objects.create_user(username="rev2", password=PASSWORD)
        other = services.add_to_learning(user2, make_expression("come up with"))
        good = services.answer(self.progress, Rating.GOOD)
        easy = services.answer(other, Rating.EASY)
        self.assertGreater(easy.scheduled_days, good.scheduled_days)

    def test_failing_records_a_lapse(self):
        services.answer(self.progress, Rating.GOOD)
        services.answer(self.progress, Rating.AGAIN)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.lapses, 1)
        self.assertEqual(self.progress.reps, 2)

    def test_productive_exercises_are_credited_separately_from_recognition(self):
        services.answer(self.progress, Rating.GOOD, exercise=ExerciseType.RECALL)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.successful_productions, 0)

        services.answer(self.progress, Rating.GOOD, exercise=ExerciseType.PRODUCE)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.successful_productions, 1)

    def test_a_failed_production_is_not_credited(self):
        services.answer(self.progress, Rating.AGAIN, exercise=ExerciseType.PRODUCE)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.successful_productions, 0)

    def test_every_review_is_logged_with_before_and_after_state(self):
        services.answer(self.progress, Rating.GOOD)
        log = Review.objects.get()
        self.assertEqual(log.state_before, MasteryState.NEW)
        self.assertIsNone(log.stability_before)
        self.assertIsNotNone(log.stability_after)
        self.assertEqual(log.user, self.user)

    def test_elapsed_time_is_measured_from_the_real_last_review(self):
        services.answer(self.progress, Rating.GOOD)
        self.progress.refresh_from_db()
        later = timezone.now() + dt.timedelta(days=10)
        log = services.answer(self.progress, Rating.GOOD, now=later)
        self.assertAlmostEqual(log.elapsed_days, 10, places=1)


class MasteryStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mast", password=PASSWORD)
        self.progress = services.add_to_learning(self.user, make_expression())

    def test_first_review_moves_an_item_out_of_new(self):
        services.answer(self.progress, Rating.GOOD)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.state, MasteryState.LEARNING)

    def test_repeated_failure_marks_an_item_weak(self):
        now = timezone.now()
        for index in range(4):
            services.answer(self.progress, Rating.AGAIN, now=now + dt.timedelta(days=index))
            self.progress.refresh_from_db()
        self.assertEqual(self.progress.state, MasteryState.WEAK)

    def test_weak_survives_a_single_good_answer(self):
        """An item you have forgotten four times is not fixed by one success."""
        now = timezone.now()
        for index in range(4):
            services.answer(self.progress, Rating.AGAIN, now=now + dt.timedelta(days=index))
            self.progress.refresh_from_db()
        services.answer(self.progress, Rating.GOOD, now=now + dt.timedelta(days=5))
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.state, MasteryState.WEAK)

    def test_high_stability_becomes_mastered(self):
        self.progress.reps = 10
        self.progress.stability = 400
        self.assertEqual(self.progress.recompute_state(), MasteryState.MASTERED)

    def test_success_rate_reflects_lapses(self):
        self.progress.reps, self.progress.lapses = 10, 2
        self.assertAlmostEqual(self.progress.success_rate, 0.8)


class QueueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="queue", password=PASSWORD)
        self.now = timezone.now()

    def _tracked(self, text, *, due_days_ago=None, state=MasteryState.REVIEW, reps=3):
        expression = make_expression(text, kind=Kind.PHRASE)
        progress = services.add_to_learning(self.user, expression)
        if due_days_ago is not None:
            VocabularyProgress.objects.filter(pk=progress.pk).update(
                due_at=self.now - dt.timedelta(days=due_days_ago),
                state=state,
                reps=reps,
                stability=10,
                difficulty=5,
                last_reviewed_at=self.now - dt.timedelta(days=due_days_ago + 10),
            )
            progress.refresh_from_db()
        return progress

    def test_empty_queue_when_nothing_is_tracked(self):
        self.assertEqual(services.build_queue(self.user, now=self.now), [])

    def test_new_items_appear_in_the_queue(self):
        self._tracked("figure out")
        queue = services.build_queue(self.user, now=self.now)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].exercise, ExerciseType.MEET)

    def test_items_due_in_the_future_are_excluded(self):
        progress = self._tracked("deal with", due_days_ago=-5)  # due in 5 days
        self.assertNotIn(progress.id, [item.progress.id for item in services.build_queue(self.user, now=self.now)])

    def test_most_overdue_items_come_first(self):
        slightly = self._tracked("no rush", due_days_ago=1)
        very = self._tracked("it's been ages", due_days_ago=30)
        queue = services.build_queue(self.user, now=self.now)
        self.assertEqual(queue[0].progress.id, very.id)
        self.assertEqual(queue[1].progress.id, slightly.id)

    def test_due_items_are_prioritised_over_new_ones(self):
        due = self._tracked("look into", due_days_ago=3)
        self._tracked("brand new")
        queue = services.build_queue(self.user, now=self.now)
        self.assertEqual(queue[0].progress.id, due.id)

    def test_new_items_are_capped_per_day(self):
        for index in range(20):
            self._tracked(f"expression {index}")
        queue = services.build_queue(self.user, limit=50, new_per_day=5, now=self.now)
        self.assertEqual(len(queue), 5)

    def test_queue_length_is_derived_from_available_minutes(self):
        for index in range(60):
            self._tracked(f"item {index}", due_days_ago=1)
        short = services.build_queue(self.user, minutes=2, now=self.now)
        longer = services.build_queue(self.user, minutes=10, now=self.now)
        self.assertLess(len(short), len(longer))

    def test_queue_is_scoped_to_the_user(self):
        other = User.objects.create_user(username="other", password=PASSWORD)
        services.add_to_learning(other, make_expression("their word"))
        self.assertEqual(services.build_queue(self.user, now=self.now), [])

    def test_new_items_are_interleaved_rather_than_dumped_at_the_end(self):
        for index in range(8):
            self._tracked(f"due {index}", due_days_ago=index + 1)
        self._tracked("a new one")
        queue = services.build_queue(self.user, limit=20, now=self.now)
        positions = [i for i, item in enumerate(queue) if item.exercise == ExerciseType.MEET]
        self.assertEqual(len(positions), 1)
        self.assertLess(positions[0], len(queue) - 1, "new item was left at the very end")


class ExerciseSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ex", password=PASSWORD)
        self.progress = services.add_to_learning(self.user, make_expression())

    def _with(self, state, reps=3):
        self.progress.state = state
        self.progress.reps = reps
        return services.choose_exercise(self.progress)

    def test_new_items_are_introduced_not_tested(self):
        self.assertEqual(self._with(MasteryState.NEW, reps=0), ExerciseType.MEET)

    def test_learning_items_are_tested_by_recall(self):
        self.assertEqual(self._with(MasteryState.LEARNING), ExerciseType.RECALL)

    def test_weak_items_are_pushed_to_production_not_recognition(self):
        self.assertEqual(self._with(MasteryState.WEAK), ExerciseType.CLOZE)

    def test_mastered_items_are_used_in_the_learners_own_sentence(self):
        self.assertEqual(self._with(MasteryState.MASTERED), ExerciseType.USE)

    def test_review_items_alternate_so_it_never_becomes_rote(self):
        self.assertNotEqual(
            self._with(MasteryState.REVIEW, reps=2), self._with(MasteryState.REVIEW, reps=3)
        )


class StatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="stats", password=PASSWORD)

    def test_empty_stats_are_safe(self):
        result = services.stats(self.user)
        self.assertEqual(result["total_tracked"], 0)
        self.assertIsNone(result["success_rate"])

    def test_success_rate_counts_only_failures_as_failures(self):
        progress = services.add_to_learning(self.user, make_expression())
        services.answer(progress, Rating.GOOD)
        services.answer(progress, Rating.HARD)
        services.answer(progress, Rating.AGAIN)
        self.assertAlmostEqual(services.stats(self.user)["success_rate"], 2 / 3, places=3)

    def test_forecast_covers_the_requested_window(self):
        rows = services.forecast(self.user, days=7)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0]["date"], timezone.localdate())

    def test_forecast_day_zero_includes_overdue_items(self):
        progress = services.add_to_learning(self.user, make_expression())
        VocabularyProgress.objects.filter(pk=progress.pk).update(
            due_at=timezone.now() - dt.timedelta(days=30), state=MasteryState.REVIEW, reps=2
        )
        self.assertEqual(services.forecast(self.user, days=3)[0]["count"], 1)


class AddToLearningTests(TestCase):
    def test_adding_the_same_expression_twice_is_idempotent(self):
        user = User.objects.create_user(username="idem", password=PASSWORD)
        expression = make_expression()
        first = services.add_to_learning(user, expression)
        second = services.add_to_learning(user, expression)
        self.assertEqual(first.id, second.id)
        self.assertEqual(VocabularyProgress.objects.count(), 1)


class SeedCommandTests(TestCase):
    def test_seeding_is_idempotent_and_assigns_to_a_user(self):
        from io import StringIO

        from django.core.management import call_command

        user = User.objects.create_user(username="seeded", password=PASSWORD)
        call_command("seed_vocabulary", user="seeded", stdout=StringIO())
        first_count = Expression.objects.count()
        self.assertGreater(first_count, 20)
        self.assertEqual(user.vocabulary.count(), first_count)

        call_command("seed_vocabulary", user="seeded", stdout=StringIO())
        self.assertEqual(Expression.objects.count(), first_count)
        self.assertEqual(user.vocabulary.count(), first_count)

    def test_seed_prefers_multi_word_expressions(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_vocabulary", stdout=StringIO())
        expressions = list(Expression.objects.all())
        multi_word = [e for e in expressions if e.is_multi_word]
        self.assertGreater(
            len(multi_word) / len(expressions),
            0.8,
            "the starter set should be overwhelmingly multi-word",
        )

    def test_every_seeded_expression_has_at_least_one_example(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_vocabulary", stdout=StringIO())
        for expression in Expression.objects.all():
            self.assertGreater(
                expression.examples.count(), 0, f"{expression.text} has no example sentence"
            )


class AddExtractedTests(TestCase):
    """Closing the loop: content produces vocabulary, vocabulary becomes review."""

    def setUp(self):
        self.user = User.objects.create_user(username="extract", password=PASSWORD)

    def test_extracted_items_enter_the_review_queue(self):
        added = services.add_extracted(
            self.user,
            [
                {
                    "expression": "run into",
                    "meaning": "to meet by chance",
                    "example": "I ran into an old colleague.",
                    "kind": "phrasal_verb",
                },
                {"expression": "a bit of a nightmare", "meaning": "difficult or annoying"},
            ],
        )
        self.assertEqual(len(added), 2)
        self.assertEqual(VocabularyProgress.objects.filter(user=self.user).count(), 2)
        queue = services.build_queue(self.user)
        self.assertEqual(len(queue), 2)

    def test_an_example_sentence_is_kept_for_gap_fill(self):
        services.add_extracted(
            self.user,
            [{"expression": "run into", "meaning": "meet by chance",
              "example": "I ran into an old colleague."}],
        )
        expression = Expression.objects.get(normalized="run into")
        self.assertEqual(expression.examples.count(), 1)

    def test_a_missing_kind_is_guessed_from_shape(self):
        services.add_extracted(
            self.user,
            [
                {"expression": "figure out", "meaning": "understand"},
                {"expression": "resilient", "meaning": "tough"},
            ],
        )
        self.assertEqual(Expression.objects.get(normalized="figure out").kind, Kind.PHRASE)
        self.assertEqual(Expression.objects.get(normalized="resilient").kind, Kind.WORD)

    def test_adding_the_same_item_twice_is_a_no_op(self):
        items = [{"expression": "deal with", "meaning": "handle"}]
        services.add_extracted(self.user, items)
        services.add_extracted(self.user, items)
        self.assertEqual(VocabularyProgress.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Expression.objects.filter(normalized="deal with").count(), 1)

    def test_an_expression_already_in_the_library_is_reused(self):
        existing = make_expression("deal with", kind=Kind.PHRASAL_VERB, meaning="handle")
        services.add_extracted(
            self.user, [{"expression": "Deal With", "meaning": "cope", "kind": "phrasal_verb"}]
        )
        self.assertEqual(Expression.objects.filter(normalized="deal with").count(), 1)
        self.assertEqual(
            VocabularyProgress.objects.get(user=self.user).expression_id, existing.id
        )

    def test_incomplete_items_are_skipped_rather_than_stored_empty(self):
        added = services.add_extracted(
            self.user,
            [
                {"expression": "", "meaning": "nothing"},
                {"expression": "orphan", "meaning": ""},
                "not a dict",
                {"expression": "keeps this", "meaning": "a real meaning"},
            ],
        )
        self.assertEqual(len(added), 1)

    def test_the_source_is_recorded_so_provenance_survives(self):
        services.add_extracted(
            self.user,
            [{"expression": "look into", "meaning": "investigate"}],
            source="content",
            source_url="https://example.com/story",
        )
        expression = Expression.objects.get(normalized="look into")
        self.assertEqual(expression.source, "content")
        self.assertIn("example.com", expression.source_url)

    def test_an_empty_batch_is_safe(self):
        self.assertEqual(services.add_extracted(self.user, []), [])
        self.assertEqual(services.add_extracted(self.user, None), [])
