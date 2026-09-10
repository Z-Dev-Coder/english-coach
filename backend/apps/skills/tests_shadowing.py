"""The shadowing guide: chunking, stress and intonation.

Tests the teaching claims rather than exact string output, so the chunking rule
can be tuned without rewriting the suite. What must stay true is that a lower
level gets shorter chunks, that beats land on content words, and that pitch
rises mid-sentence and falls at the end.
"""
from django.test import SimpleTestCase

from apps.skills.shadowing import (
    WORDS_PER_CHUNK,
    build_guide,
    intonation_for,
    stressed_indices,
)

SENTENCE = "The hardest part of learning something new isn't the difficult bit in the middle."


class ChunkingTests(SimpleTestCase):
    def test_lower_levels_get_shorter_chunks(self):
        # The whole point of chunking: succeed at a phrase rather than fail at
        # a sentence. An A2 learner cannot hold what a C1 learner can.
        a2 = build_guide(SENTENCE, level="A2")
        c1 = build_guide(SENTENCE, level="C1")
        self.assertGreater(a2["chunk_count"], c1["chunk_count"])

    def test_no_chunk_exceeds_the_level_budget(self):
        for level, limit in WORDS_PER_CHUNK.items():
            guide = build_guide(SENTENCE, level=level)
            for chunk in guide["chunks"]:
                with self.subTest(level=level, chunk=chunk["text"]):
                    self.assertLessEqual(len(chunk["text"].split()), limit)

    def test_it_breaks_at_a_conjunction_when_it_can(self):
        # A speaker draws breath before "because", not three words earlier.
        guide = build_guide(
            "I stayed at home because the weather was completely terrible.", level="A2"
        )
        starts = [chunk["text"].split()[0].lower() for chunk in guide["chunks"]]
        self.assertIn("because", starts)

    def test_it_never_strands_a_single_word(self):
        """A one-word chunk teaches a pause where a speaker would not take one.

        Observed live: "English speakers rarely say what they" / "mean" -- the
        verb alone in its own chunk, which is the opposite of chunking.
        """
        text = "English speakers rarely say what they mean in a conversation."
        for level in ["A1", "A2", "B1", "B2"]:
            guide = build_guide(text, level=level)
            for chunk in guide["chunks"][1:]:
                with self.subTest(level=level, chunk=chunk["text"]):
                    self.assertGreater(
                        len(chunk["text"].split()), 1, "a chunk was left with one word"
                    )

    def test_every_chunk_belongs_to_a_sentence(self):
        guide = build_guide("First one. Second one here.", level="B1")
        self.assertEqual({chunk["sentence"] for chunk in guide["chunks"]}, {0, 1})

    def test_empty_input_is_an_empty_guide_not_an_error(self):
        for value in ["", "   ", None]:
            with self.subTest(value=value):
                self.assertEqual(build_guide(value)["chunks"], [])

    def test_an_unknown_level_falls_back_rather_than_failing(self):
        guide = build_guide(SENTENCE, level="ZZ")
        self.assertEqual(guide["words_per_chunk"], WORDS_PER_CHUNK["B1"])


class StressTests(SimpleTestCase):
    def test_beats_land_on_content_words(self):
        chunk = "the hardest part of learning"
        words = chunk.split()
        marked = {words[i] for i in stressed_indices(chunk)}
        self.assertIn("hardest", marked)
        self.assertIn("learning", marked)
        # Reducing these is most of what makes a learner sound fluent, and it
        # is invisible in the spelling.
        self.assertNotIn("the", marked)
        self.assertNotIn("of", marked)

    def test_a_chunk_of_only_function_words_still_gets_a_beat(self):
        # Otherwise "and then it was" is displayed with nothing to hit, which
        # invites reading it flat.
        self.assertTrue(stressed_indices("and then it was"))

    def test_no_words_means_no_beats(self):
        self.assertEqual(stressed_indices("..."), [])


class IntonationTests(SimpleTestCase):
    def test_mid_sentence_rises_and_the_end_falls(self):
        self.assertEqual(intonation_for("in the middle", is_final=False), "rise")
        self.assertEqual(intonation_for("in the middle.", is_final=True), "fall")

    def test_yes_no_questions_rise(self):
        self.assertEqual(intonation_for("Are you coming?", is_final=True), "rise")

    def test_wh_questions_fall(self):
        # Getting this one backwards is among the most audible non-native
        # patterns there is, so it is worth encoding rather than guessing.
        for question in ["What time is it?", "Where are you going?", "How was it?"]:
            with self.subTest(question=question):
                self.assertEqual(intonation_for(question, is_final=True), "fall")

    def test_the_last_chunk_of_a_statement_falls(self):
        guide = build_guide(SENTENCE, level="B1")
        self.assertEqual(guide["chunks"][-1]["intonation"], "fall")
        for chunk in guide["chunks"][:-1]:
            self.assertEqual(chunk["intonation"], "rise")
