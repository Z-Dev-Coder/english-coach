"""Speaking scaffolding: task detection, frames and levelled phrases.

Tests the teaching claims rather than exact wording, so the phrase bank can be
rewritten without rewriting the suite. What must hold: a story is treated as a
story, every frame gives the learner an ordered set of moves with usable
language, and higher levels get less hand-holding.
"""
from django.test import SimpleTestCase

from apps.skills.speaking_support import FRAMES, build_support, detect_task


class TaskDetectionTests(SimpleTestCase):
    def test_it_reads_a_story_prompt_as_a_story(self):
        # "Tell me about a time you..." is a narrative, not a description, and
        # the two need different moves in a different order.
        for prompt in [
            "Tell me about a time you had to complain about something.",
            "What happened the last time you were late?",
            "Describe a time when a plan fell through.",
        ]:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_task(prompt), "narrate")

    def test_it_reads_an_opinion_prompt_as_an_opinion(self):
        for prompt in [
            "Do you think working from home is better?",
            "What do you think about that idea?",
        ]:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_task(prompt), "opinion")

    def test_a_plain_prompt_is_a_description(self):
        self.assertEqual(detect_task("Walk me through a typical day in your life."), "describe")

    def test_a_stray_or_does_not_make_everything_a_comparison(self):
        # Substring matching would find "or" inside "morning" and route half
        # the prompts in the app to the wrong frame.
        self.assertNotEqual(detect_task("Describe your morning routine."), "compare")

    def test_an_unknown_prompt_still_gets_a_frame(self):
        # Prompts are written freely by the lesson generator, so falling back
        # matters more than being clever.
        for prompt in ["", "   ", "Blorp?"]:
            with self.subTest(prompt=prompt):
                self.assertIn(detect_task(prompt), FRAMES)


class SupportTests(SimpleTestCase):
    PROMPT = "Walk me through a typical day in your life."

    def test_every_move_comes_with_language_to_use(self):
        # A move the learner cannot phrase is not help, it is a instruction to
        # perform something they already could not do.
        support = build_support(prompt=self.PROMPT, level="B1")
        self.assertGreater(len(support["frame"]), 2)
        for step in support["frame"]:
            with self.subTest(move=step["move"]):
                self.assertTrue(step["hint"])
                self.assertTrue(step["phrases"], "a move with no usable phrases")

    def test_higher_levels_get_less_scaffolding(self):
        # A C1 speaker told to say "First..." is being taught to sound like a
        # textbook.
        low = build_support(prompt=self.PROMPT, level="A2")
        high = build_support(prompt=self.PROMPT, level="C1")
        low_count = sum(len(step["phrases"]) for step in low["frame"])
        high_count = sum(len(step["phrases"]) for step in high["frame"])
        self.assertGreater(low_count, high_count)

    def test_the_language_differs_by_level(self):
        low = build_support(prompt=self.PROMPT, level="A1")["frame"][0]["phrases"]
        high = build_support(prompt=self.PROMPT, level="C2")["frame"][0]["phrases"]
        self.assertNotEqual(set(low), set(high))

    def test_stalling_phrases_are_always_offered(self):
        # Running out of words mid-answer is where a learner gives up, and the
        # fix is a phrase rather than more vocabulary.
        for level in ["A1", "B1", "C2"]:
            with self.subTest(level=level):
                self.assertTrue(build_support(prompt=self.PROMPT, level=level)["stalling_phrases"])

    def test_target_expressions_are_carried_through(self):
        support = build_support(
            prompt=self.PROMPT, level="B1", expressions=["first", "after that"]
        )
        self.assertEqual(support["target_expressions"], ["first", "after that"])

    def test_an_unknown_level_falls_back_rather_than_failing(self):
        self.assertTrue(build_support(prompt=self.PROMPT, level="ZZ")["frame"])

    def test_a_story_and_a_description_get_different_moves(self):
        story = build_support(prompt="Tell me about a time you got lost.", level="B1")
        describe = build_support(prompt=self.PROMPT, level="B1")
        self.assertNotEqual(
            [step["move"] for step in story["frame"]],
            [step["move"] for step in describe["frame"]],
        )
