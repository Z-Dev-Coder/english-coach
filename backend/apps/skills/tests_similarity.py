"""Tests for text comparison and readability. Pure functions, no database."""
from django.test import SimpleTestCase

from apps.skills.similarity import (
    Op,
    compare,
    count_syllables,
    estimate_level,
    flesch_reading_ease,
    normalize,
    similarity,
    split_sentences,
    tokenize,
)


class NormalizeTests(SimpleTestCase):
    def test_case_and_punctuation_are_ignored(self):
        self.assertEqual(normalize("Hello, World!"), "hello world")

    def test_extra_whitespace_collapses(self):
        self.assertEqual(normalize("  too   many   spaces "), "too many spaces")

    def test_accents_are_stripped(self):
        self.assertEqual(normalize("café"), "cafe")

    def test_contractions_expand_so_both_forms_match(self):
        self.assertEqual(normalize("I didn't"), normalize("I did not"))
        self.assertEqual(normalize("it's fine"), normalize("it is fine"))

    def test_empty_input_is_safe(self):
        self.assertEqual(normalize(""), "")
        self.assertEqual(tokenize(""), [])


class CompareTests(SimpleTestCase):
    def test_identical_text_is_perfect(self):
        result = compare("I can't figure it out.", "I cant figure it out")
        self.assertTrue(result.is_perfect)
        self.assertEqual(result.percentage, 100)
        self.assertEqual(result.summary(), "Word perfect.")

    def test_punctuation_and_case_do_not_cost_marks(self):
        self.assertTrue(compare("Let's go, now!", "lets go now").is_perfect)

    def test_a_wrong_word_is_reported_with_what_was_said(self):
        result = compare("I really like this movie", "I very like this movie")
        wrong = [t for t in result.tokens if t.op == Op.WRONG]
        self.assertEqual(len(wrong), 1)
        self.assertEqual(wrong[0].expected, "really")
        self.assertEqual(wrong[0].actual, "very")

    def test_a_missing_word_is_identified(self):
        result = compare("I had to deal with it", "I had to deal it")
        missing = [t for t in result.tokens if t.op == Op.MISSING]
        self.assertEqual([t.expected for t in missing], ["with"])

    def test_an_extra_word_is_identified(self):
        result = compare("I went home", "I went back home")
        extra = [t for t in result.tokens if t.op == Op.EXTRA]
        self.assertEqual([t.actual for t in extra], ["back"])

    def test_one_dropped_word_does_not_invalidate_the_rest(self):
        """A naive position-by-position comparison would mark everything after a
        dropped word as wrong. That is both incorrect and demoralising."""
        result = compare(
            "I did not realise how difficult it was",
            "I did realise how difficult it was",
        )
        self.assertGreater(result.accuracy, 0.8)
        self.assertEqual(len(result.mistakes), 1)

    def test_completely_wrong_scores_zero(self):
        self.assertEqual(compare("hello there", "completely different words").accuracy, 0.0)

    def test_empty_attempt_scores_zero_without_crashing(self):
        result = compare("something expected", "")
        self.assertEqual(result.accuracy, 0.0)
        self.assertEqual(result.expected_words, 2)

    def test_empty_expectation_is_handled(self):
        self.assertTrue(compare("", "").is_perfect)
        self.assertEqual(compare("", "unexpected words").accuracy, 0.0)

    def test_accuracy_is_the_fraction_of_expected_words_recovered(self):
        result = compare("one two three four", "one two three")
        self.assertEqual(result.correct_words, 3)
        self.assertEqual(result.expected_words, 4)
        self.assertAlmostEqual(result.accuracy, 0.75)

    def test_summary_describes_the_kind_of_mistake(self):
        self.assertIn("missed", compare("a b c", "a c").summary().lower())
        self.assertIn("extra", compare("a c", "a b c").summary().lower())

    def test_speech_recognition_contraction_drift_is_forgiven(self):
        """Browser speech recognition expands contractions unpredictably; the
        learner said the sentence correctly either way."""
        self.assertTrue(compare("I won't be long", "I will not be long").is_perfect)


class SimilarityTests(SimpleTestCase):
    def test_identical_strings(self):
        self.assertEqual(similarity("hello", "hello"), 1.0)

    def test_near_miss_inside_a_word_scores_high(self):
        self.assertGreater(similarity("I realised", "I realise"), 0.85)

    def test_unrelated_strings_score_low(self):
        self.assertLess(similarity("hello there", "xyzzy"), 0.4)

    def test_two_empty_strings_match(self):
        self.assertEqual(similarity("", ""), 1.0)


class ReadabilityTests(SimpleTestCase):
    def test_syllable_counting(self):
        for word, expected in (("cat", 1), ("water", 2), ("beautiful", 3), ("the", 1)):
            with self.subTest(word=word):
                self.assertEqual(count_syllables(word), expected)

    def test_silent_e_is_not_counted(self):
        self.assertEqual(count_syllables("make"), 1)

    def test_empty_word_has_no_syllables(self):
        self.assertEqual(count_syllables(""), 0)

    def test_simple_text_is_easier_than_complex_text(self):
        simple = "The cat sat on the mat. It was warm."
        complex_text = (
            "Notwithstanding the aforementioned considerations, the committee "
            "determined that implementation remained fundamentally impracticable."
        )
        self.assertGreater(flesch_reading_ease(simple), flesch_reading_ease(complex_text))

    def test_level_estimate_ranks_texts_sensibly(self):
        from apps.profiles.constants import cefr_index

        easy = estimate_level("I like cats. They are nice. I have one.")
        hard = estimate_level(
            "The epistemological ramifications of such methodological "
            "presuppositions necessitate considerable philosophical scrutiny."
        )
        self.assertLess(cefr_index(easy), cefr_index(hard))

    def test_empty_text_does_not_divide_by_zero(self):
        self.assertEqual(flesch_reading_ease(""), 100.0)
        self.assertEqual(estimate_level(""), "A1")


class SentenceSplitTests(SimpleTestCase):
    def test_splits_on_terminal_punctuation(self):
        self.assertEqual(
            split_sentences("One thing. Then another! And a third?"),
            ["One thing.", "Then another!", "And a third?"],
        )

    def test_single_sentence_without_punctuation(self):
        self.assertEqual(split_sentences("just one"), ["just one"])

    def test_empty_text_returns_nothing(self):
        self.assertEqual(split_sentences("   "), [])
