"""Tests for the FSRS scheduler.

These are pure-function tests: no database, no Django. They assert the
*properties* the algorithm must hold rather than hard-coded outputs, so the
suite stays meaningful if the weights are ever retuned.
"""
from django.test import SimpleTestCase

from apps.review.fsrs import (
    DECAY,
    FACTOR,
    MAX_INTERVAL_DAYS,
    MIN_STABILITY,
    MemoryState,
    Rating,
    initial_difficulty,
    initial_stability,
    interval_for,
    next_difficulty,
    retrievability,
    review,
    stability_after_lapse,
    stability_after_success,
)


class ForgettingCurveTests(SimpleTestCase):
    def test_recall_is_certain_immediately_after_review(self):
        self.assertEqual(retrievability(0, 10), 1.0)

    def test_recall_decays_with_time(self):
        early = retrievability(1, 10)
        late = retrievability(30, 10)
        self.assertGreater(early, late)
        self.assertGreater(early, 0.9)
        self.assertLess(late, 0.8)

    def test_the_curve_has_a_heavy_tail(self):
        """FSRS uses a power law, not an exponential decay. At three times the
        stability an item is still recalled about three quarters of the time,
        which is why intervals can grow as aggressively as they do."""
        self.assertAlmostEqual(retrievability(30, 10), 0.766, places=2)
        # Exponential decay would have fallen far lower by the same point.
        self.assertGreater(retrievability(30, 10), 0.5)
        # It keeps falling over the long run, but slowly: even at a hundred
        # times the stability an item is recalled about one time in five.
        self.assertAlmostEqual(retrievability(1000, 10), 0.202, places=2)

    def test_recall_is_90_percent_after_exactly_one_stability(self):
        # This is the definition of stability, so it is worth pinning down.
        self.assertAlmostEqual(retrievability(10, 10), 0.9, places=6)

    def test_more_stable_items_are_remembered_longer(self):
        self.assertGreater(retrievability(30, 100), retrievability(30, 10))

    def test_new_items_do_not_divide_by_zero(self):
        self.assertEqual(retrievability(5, 0), 1.0)


class IntervalTests(SimpleTestCase):
    def test_interval_equals_stability_at_default_retention(self):
        for stability in (1, 7, 30, 365):
            with self.subTest(stability=stability):
                self.assertEqual(interval_for(stability), stability)

    def test_higher_desired_retention_shortens_intervals(self):
        self.assertLess(interval_for(100, 0.95), interval_for(100, 0.9))
        self.assertGreater(interval_for(100, 0.8), interval_for(100, 0.9))

    def test_interval_is_never_below_one_day(self):
        self.assertGreaterEqual(interval_for(0.01), 1)

    def test_interval_is_capped(self):
        self.assertLessEqual(interval_for(10_000_000), MAX_INTERVAL_DAYS)

    def test_factor_and_decay_are_consistent(self):
        self.assertAlmostEqual(FACTOR, 0.9 ** (1 / DECAY) - 1, places=9)


class FirstReviewTests(SimpleTestCase):
    def test_better_grades_give_longer_first_intervals(self):
        intervals = [
            review(MemoryState(), rating, elapsed_days=0).interval_days
            for rating in (Rating.AGAIN, Rating.HARD, Rating.GOOD, Rating.EASY)
        ]
        self.assertEqual(intervals, sorted(intervals))
        self.assertLess(intervals[0], intervals[-1])

    def test_again_on_a_new_item_schedules_it_for_tomorrow(self):
        self.assertEqual(review(MemoryState(), Rating.AGAIN, 0).interval_days, 1)

    def test_better_grades_give_lower_difficulty(self):
        self.assertGreater(
            initial_difficulty(Rating.AGAIN), initial_difficulty(Rating.EASY)
        )

    def test_initial_values_are_in_range(self):
        for rating in Rating:
            with self.subTest(rating=rating):
                self.assertGreaterEqual(initial_stability(rating), MIN_STABILITY)
                self.assertTrue(1.0 <= initial_difficulty(rating) <= 10.0)


class DifficultyTests(SimpleTestCase):
    def test_failing_makes_an_item_harder_and_easy_makes_it_easier(self):
        self.assertGreater(next_difficulty(5.0, Rating.AGAIN), 5.0)
        self.assertLess(next_difficulty(5.0, Rating.EASY), 5.0)

    def test_difficulty_stays_within_bounds_under_repeated_failure(self):
        difficulty = 5.0
        for _ in range(100):
            difficulty = next_difficulty(difficulty, Rating.AGAIN)
        self.assertLessEqual(difficulty, 10.0)

    def test_difficulty_stays_within_bounds_under_repeated_success(self):
        difficulty = 5.0
        for _ in range(100):
            difficulty = next_difficulty(difficulty, Rating.EASY)
        self.assertGreaterEqual(difficulty, 1.0)


class StabilityTests(SimpleTestCase):
    def test_success_always_increases_stability(self):
        for rating in (Rating.HARD, Rating.GOOD, Rating.EASY):
            with self.subTest(rating=rating):
                self.assertGreater(
                    stability_after_success(10, 5, 0.9, rating), 10
                )

    def test_easy_grows_faster_than_good_which_grows_faster_than_hard(self):
        hard = stability_after_success(10, 5, 0.9, Rating.HARD)
        good = stability_after_success(10, 5, 0.9, Rating.GOOD)
        easy = stability_after_success(10, 5, 0.9, Rating.EASY)
        self.assertLess(hard, good)
        self.assertLess(good, easy)

    def test_recalling_a_nearly_forgotten_item_teaches_more(self):
        """The retrieval-practice effect: a hard-won recall is worth more than
        an easy one, so low retrievability must yield larger growth."""
        nearly_forgotten = stability_after_success(10, 5, 0.3, Rating.GOOD)
        still_fresh = stability_after_success(10, 5, 0.99, Rating.GOOD)
        self.assertGreater(nearly_forgotten, still_fresh)

    def test_easier_items_grow_faster_than_difficult_ones(self):
        self.assertGreater(
            stability_after_success(10, 2, 0.9, Rating.GOOD),
            stability_after_success(10, 9, 0.9, Rating.GOOD),
        )

    def test_forgetting_never_lengthens_the_schedule(self):
        for stability in (0.5, 1, 10, 100, 1000):
            with self.subTest(stability=stability):
                self.assertLessEqual(
                    stability_after_lapse(stability, 5, 0.9), stability
                )

    def test_stability_never_goes_below_the_floor(self):
        self.assertGreaterEqual(stability_after_lapse(0.01, 10, 0.1), MIN_STABILITY)


class ReviewTests(SimpleTestCase):
    def _mature(self):
        """An item reviewed successfully a few times."""
        state = MemoryState()
        interval = 0
        for _ in range(4):
            result = review(state, Rating.GOOD, elapsed_days=interval)
            state, interval = result.state, result.interval_days
        return state, interval

    def test_repeated_success_produces_expanding_intervals(self):
        state = MemoryState()
        intervals = []
        elapsed = 0
        for _ in range(6):
            result = review(state, Rating.GOOD, elapsed_days=elapsed)
            state, elapsed = result.state, result.interval_days
            intervals.append(elapsed)
        self.assertEqual(intervals, sorted(intervals))
        self.assertGreater(intervals[-1], intervals[0])

    def test_forgetting_a_mature_item_collapses_its_interval(self):
        state, interval = self._mature()
        lapsed = review(state, Rating.AGAIN, elapsed_days=interval)
        self.assertLess(lapsed.interval_days, interval)
        self.assertLess(lapsed.state.stability, state.stability)

    def test_forgetting_also_raises_difficulty(self):
        state, interval = self._mature()
        lapsed = review(state, Rating.AGAIN, elapsed_days=interval)
        self.assertGreater(lapsed.state.difficulty, state.difficulty)

    def test_reviewing_late_is_used_as_information(self):
        """Two identical items, one reviewed on time and one very late. The late
        recall was harder, so it must earn more stability."""
        state, interval = self._mature()
        on_time = review(state, Rating.GOOD, elapsed_days=interval)
        late = review(state, Rating.GOOD, elapsed_days=interval * 4)
        self.assertGreater(late.state.stability, on_time.state.stability)

    def test_same_day_repetition_does_not_inflate_the_schedule(self):
        state, interval = self._mature()
        normal = review(state, Rating.GOOD, elapsed_days=interval)
        same_day = review(state, Rating.GOOD, elapsed_days=0)
        self.assertLess(same_day.state.stability, normal.state.stability)

    def test_result_reports_retrievability_at_review_time(self):
        state, interval = self._mature()
        result = review(state, Rating.GOOD, elapsed_days=interval)
        self.assertAlmostEqual(result.retrievability_at_review, 0.9, places=1)

    def test_integer_ratings_are_accepted(self):
        # The API layer passes plain ints from JSON.
        self.assertEqual(
            review(MemoryState(), 3, 0).interval_days,
            review(MemoryState(), Rating.GOOD, 0).interval_days,
        )

    def test_a_long_history_stays_numerically_sane(self):
        state = MemoryState()
        elapsed = 0
        for index in range(60):
            rating = Rating.AGAIN if index % 7 == 0 else Rating.GOOD
            result = review(state, rating, elapsed_days=elapsed)
            state, elapsed = result.state, result.interval_days
            self.assertTrue(1 <= elapsed <= MAX_INTERVAL_DAYS)
            self.assertTrue(1.0 <= state.difficulty <= 10.0)
            self.assertGreater(state.stability, 0)
