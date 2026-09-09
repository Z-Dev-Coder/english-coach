"""Tests for skill activities: scoring, recording, and profile effects."""
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.ai.providers.base import AIError, AIProvider, AIResult, AIUnavailable
from apps.profiles.constants import Skill
from apps.profiles.models import SkillProgress
from apps.skills import services
from apps.skills.models import ActivityType, Passage, SkillAttempt

User = get_user_model()
PASSWORD = "pw-for-tests-123"


class ScoreMappingTests(TestCase):
    def test_perfect_accuracy_gains_the_maximum(self):
        self.assertAlmostEqual(services.accuracy_to_delta(1.0), services.MAX_GAIN)

    def test_zero_accuracy_loses_the_maximum(self):
        self.assertAlmostEqual(services.accuracy_to_delta(0.0), services.MAX_LOSS)

    def test_the_pivot_is_neutral(self):
        self.assertAlmostEqual(services.accuracy_to_delta(0.7), 0.0)

    def test_a_mediocre_score_is_not_treated_as_progress(self):
        """A flat linear map would call 65% an improvement. It is not."""
        self.assertLess(services.accuracy_to_delta(0.65), 0)

    def test_being_wrong_costs_more_than_being_right_gains(self):
        self.assertGreater(abs(services.MAX_LOSS), services.MAX_GAIN)


class PassageTests(TestCase):
    def test_word_count_and_readability_are_cached_on_save(self):
        passage = Passage.objects.create(title="T", text="The cat sat. It was warm.")
        self.assertEqual(passage.word_count, 6)
        self.assertIsNotNone(passage.reading_ease)

    def test_sentences_are_split(self):
        passage = Passage.objects.create(title="T", text="One thing. Then another!")
        self.assertEqual(passage.sentences(), ["One thing.", "Then another!"])

    def test_learner_passages_estimate_their_own_level(self):
        user = User.objects.create_user(username="p", password=PASSWORD)
        passage = services.create_passage(user, title="", text="I like cats. They are nice. I have one.")
        self.assertEqual(passage.owner, user)
        self.assertTrue(passage.level)
        self.assertEqual(passage.source, Passage.Source.LEARNER)

    def test_a_pasted_passage_without_a_title_gets_one(self):
        user = User.objects.create_user(username="p2", password=PASSWORD)
        passage = services.create_passage(user, title="", text="Something interesting happened today.")
        self.assertTrue(passage.title)


class DictationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dict", password=PASSWORD)

    def test_a_perfect_dictation_raises_the_listening_score(self):
        before = SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score
        services.check_dictation(
            self.user, expected="I couldn't figure it out.", written="I couldn't figure it out."
        )
        after = SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score
        self.assertGreater(after, before)

    def test_a_bad_dictation_lowers_it(self):
        before = SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score
        services.check_dictation(self.user, expected="I couldn't figure it out.", written="banana")
        after = SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score
        self.assertLess(after, before)

    def test_the_word_diff_is_stored_for_the_learner_to_see(self):
        attempt = services.check_dictation(
            self.user, expected="I really like this", written="I very like this"
        )
        self.assertEqual(attempt.activity, ActivityType.DICTATION)
        wrong = [t for t in attempt.detail["tokens"] if t["op"] == "wrong"]
        self.assertEqual(wrong[0]["expected"], "really")
        self.assertEqual(wrong[0]["actual"], "very")

    def test_punctuation_differences_do_not_cost_marks(self):
        attempt = services.check_dictation(
            self.user, expected="Let's go, now!", written="lets go now"
        )
        self.assertTrue(attempt.detail["is_perfect"])

    def test_an_empty_answer_is_handled(self):
        attempt = services.check_dictation(self.user, expected="something", written="")
        self.assertEqual(attempt.accuracy, 0.0)


class ShadowingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="shad", password=PASSWORD)

    def test_shadowing_states_plainly_that_it_is_an_estimate(self):
        """Presenting recogniser agreement as a pronunciation score would be a
        false claim about what the software can measure."""
        attempt = services.check_shadowing(
            self.user, expected="I'll get back to you", transcript="I'll get back to you"
        )
        self.assertIn("estimate", attempt.detail["caveat"].lower())
        self.assertEqual(attempt.detail["measurement"], "speech-recognition-agreement")

    def test_shadowing_moves_pronunciation_not_listening(self):
        listening_before = SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score
        services.check_shadowing(self.user, expected="no rush", transcript="no rush")
        self.assertEqual(
            SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score,
            listening_before,
        )
        self.assertGreater(
            SkillProgress.objects.get(user=self.user, skill=Skill.PRONUNCIATION).score, 50
        )

    def test_recogniser_contraction_drift_is_not_punished(self):
        attempt = services.check_shadowing(
            self.user, expected="I won't be long", transcript="I will not be long"
        )
        self.assertTrue(attempt.detail["is_perfect"])


class WritingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="write", password=PASSWORD)

    def test_rule_checks_flag_writing_that_is_too_short(self):
        issues = services.basic_writing_checks("Too short.")
        self.assertTrue(any(issue["category"] == "length" for issue in issues))

    def test_rule_checks_flag_a_runaway_sentence(self):
        long_sentence = "I went to the shop and " + "then I bought something and " * 15 + "left."
        issues = services.basic_writing_checks(long_sentence)
        self.assertTrue(any(issue["category"] == "sentence_structure" for issue in issues))

    def test_rule_checks_flag_missing_capitalisation(self):
        issues = services.basic_writing_checks("i went to work today and it was fine " * 3)
        self.assertTrue(any(issue["category"] == "spelling" for issue in issues))

    def test_good_writing_passes_the_rule_checks(self):
        text = (
            "I had to deal with an internet problem at work today. "
            "It turned out that the router had simply been unplugged by the cleaners, "
            "which took me two hours to figure out. Next time I will check the obvious things first."
        )
        self.assertEqual(services.basic_writing_checks(text), [])

    def test_writing_is_recorded_even_when_the_ai_is_offline(self):
        with mock.patch(
            "apps.ai.registry.get_ai_provider",
            side_effect=AIUnavailable("ollama down"),
        ):
            attempt = services.evaluate_writing(self.user, text="Something I wrote today.")
        self.assertEqual(attempt.activity, ActivityType.WRITING)
        self.assertEqual(attempt.detail["source"], "rules")

    def test_the_writing_score_is_untouched_when_only_rules_ran(self):
        """Rule checks cannot judge whether writing is good. Inventing a score
        from them would move the profile on no evidence."""
        before = SkillProgress.objects.get(user=self.user, skill=Skill.WRITING).score
        with mock.patch(
            "apps.ai.registry.get_ai_provider", side_effect=AIUnavailable("down")
        ):
            attempt = services.evaluate_writing(self.user, text="A short thing.")
        self.assertIsNone(attempt.accuracy)
        self.assertEqual(
            SkillProgress.objects.get(user=self.user, skill=Skill.WRITING).score, before
        )

    def test_ai_feedback_is_used_when_available(self):
        feedback = {
            "estimated_level": "B2",
            "strengths": ["Clear structure"],
            "issues": [
                {
                    "original": "discussed about",
                    "correction": "discussed",
                    "explanation": "'Discuss' takes no preposition.",
                    "category": "preposition",
                }
            ],
            "natural_version": "We discussed the problem.",
            "practice_prompt": "Write three sentences using 'discuss'.",
        }
        provider = mock.Mock(spec=AIProvider)
        provider.evaluate_writing.return_value = feedback
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=provider):
            attempt = services.evaluate_writing(
                self.user, text="We discussed about the problem at length today. " * 4
            )
        self.assertEqual(attempt.detail["source"], "ai")
        self.assertEqual(attempt.detail["issues"][0]["category"], "preposition")
        self.assertIsNotNone(attempt.accuracy)

    def test_structural_notes_survive_alongside_ai_feedback(self):
        provider = mock.Mock(spec=AIProvider)
        provider.evaluate_writing.return_value = {
            "issues": [], "strengths": [], "natural_version": ""
        }
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=provider):
            attempt = services.evaluate_writing(self.user, text="tiny.")
        self.assertIn("structural_notes", attempt.detail)


class ReadingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="read", password=PASSWORD)
        self.passage = Passage.objects.create(
            title="T", text="One two three four five six seven eight nine ten."
        )

    def test_words_per_minute_is_computed(self):
        attempt = services.record_reading(self.user, passage=self.passage, seconds=30)
        self.assertEqual(attempt.detail["words_per_minute"], 20)

    def test_reading_fast_alone_does_not_raise_the_reading_score(self):
        """Speed is not comprehension. Counting it as progress would be exactly
        the activity-versus-improvement confusion the product avoids."""
        before = SkillProgress.objects.get(user=self.user, skill=Skill.READING).score
        services.record_reading(self.user, passage=self.passage, seconds=1)
        self.assertEqual(
            SkillProgress.objects.get(user=self.user, skill=Skill.READING).score, before
        )

    def test_comprehension_does_move_the_reading_score(self):
        before = SkillProgress.objects.get(user=self.user, skill=Skill.READING).score
        services.record_reading(
            self.user, passage=self.passage, seconds=60, comprehension=1.0
        )
        self.assertGreater(
            SkillProgress.objects.get(user=self.user, skill=Skill.READING).score, before
        )


class DrillTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="drill", password=PASSWORD)

    def test_a_sentence_is_always_available_even_with_no_content(self):
        drill = services.drill_sentence(self.user)
        self.assertTrue(drill["sentence"])
        self.assertEqual(drill["steps"][0], "listen")

    def test_the_drill_prefers_the_learners_own_vocabulary(self):
        from apps.review.services import add_to_learning
        from apps.vocabulary.models import ExampleSentence, Expression

        expression = Expression.objects.create(text="deal with", meaning="handle")
        ExampleSentence.objects.create(expression=expression, text="I had to deal with it.")
        add_to_learning(self.user, expression)

        drill = services.drill_sentence(self.user)
        self.assertEqual(drill["source"], "vocabulary")
        self.assertEqual(drill["expression"], "deal with")

    def test_the_drill_falls_back_to_a_passage(self):
        Passage.objects.create(title="P", text="I did not realise how hard it was.", level="B1")
        drill = services.drill_sentence(self.user)
        self.assertEqual(drill["source"], "passage")

    def test_one_drill_credits_listening_speaking_and_writing(self):
        sentence = "I did not realise how difficult it was."
        attempt = services.check_drill(
            self.user, sentence=sentence, spoken=sentence, written=sentence, variation="I did not realise how expensive it was."
        )
        self.assertEqual(attempt.activity, ActivityType.DRILL)
        for skill in (Skill.LISTENING, Skill.SPEAKING, Skill.WRITING):
            with self.subTest(skill=skill):
                self.assertGreater(
                    SkillProgress.objects.get(user=self.user, skill=skill).score, 50
                )

    def test_skipping_the_spoken_step_does_not_credit_speaking(self):
        sentence = "No rush at all."
        services.check_drill(self.user, sentence=sentence, written=sentence)
        self.assertEqual(
            SkillProgress.objects.get(user=self.user, skill=Skill.SPEAKING).score, 50
        )
        self.assertGreater(
            SkillProgress.objects.get(user=self.user, skill=Skill.LISTENING).score, 50
        )

    def test_the_learners_variation_is_kept(self):
        attempt = services.check_drill(
            self.user, sentence="I was tired.", written="I was tired.", variation="I was exhausted."
        )
        self.assertEqual(attempt.detail["variation"], "I was exhausted.")
        self.assertEqual(attempt.detail["variation_words"], 3)

    def test_a_spoken_drill_carries_the_estimate_caveat(self):
        attempt = services.check_drill(self.user, sentence="No rush.", spoken="no rush")
        self.assertIn("estimate", attempt.detail["caveat"].lower())


class SummaryTests(TestCase):
    def test_summary_groups_attempts_by_skill(self):
        user = User.objects.create_user(username="sum", password=PASSWORD)
        services.check_dictation(user, expected="one two", written="one two")
        services.check_dictation(user, expected="three four", written="three")
        summary = services.skill_summary(user)
        self.assertEqual(summary[Skill.LISTENING]["attempts"], 2)
        self.assertIsNotNone(summary[Skill.LISTENING]["mean_accuracy"])

    def test_summary_is_empty_for_a_new_learner(self):
        user = User.objects.create_user(username="sum2", password=PASSWORD)
        self.assertEqual(services.skill_summary(user), {})


class SeedPassageTests(TestCase):
    def test_seeding_is_idempotent(self):
        call_command("seed_passages", stdout=StringIO())
        first = Passage.objects.count()
        self.assertGreater(first, 0)
        call_command("seed_passages", stdout=StringIO())
        self.assertEqual(Passage.objects.count(), first)

    def test_seed_passages_are_shared_not_owned(self):
        call_command("seed_passages", stdout=StringIO())
        self.assertFalse(Passage.objects.filter(source=Passage.Source.SEED, owner__isnull=False).exists())

    def test_seed_passages_span_several_levels(self):
        call_command("seed_passages", stdout=StringIO())
        levels = set(Passage.objects.values_list("level", flat=True))
        self.assertGreaterEqual(len(levels), 3)
