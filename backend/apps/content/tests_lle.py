"""Parsing Let's Learn English lesson pages into real-voice scenes (offline)."""
from django.test import SimpleTestCase

from apps.content import lle

PAGE = """
<h1>Let's Learn English Level 2 Lesson 2: The Interview</h1>
<a href="https://voa-audio.voanews.eu/vle/2017/x.mp3">mp3</a>
<a href="/a/lets-learn-english-level-2-lesson-3/4027340.html">next</a>
<div class="wsw">
<p>Anna: Ms. Weaver is giving new assignments out.</p>
<p>Professor Bot: Look for phrasal verbs while you watch.</p>
<p>Ms. Weaver: I want you to go back to hosting.</p>
<p>Anna: That sounds great.</p>
<p>Ms. Weaver: You're also a team player.</p>
<p>Anna: That sounds even better!</p>
<p>Ms. Weaver: Someone who is very different from you.</p>
<p>Anna: What do you mean?</p>
<p>Words in this Story</p>
<p>assignment: n. a job given to someone</p>
</div>
"""


class ParseLessonTests(SimpleTestCase):
    def test_extracts_speakers_lines_and_audio(self):
        parsed = lle.parse_lesson(PAGE)
        self.assertEqual(parsed["audio_url"], "https://voa-audio.voanews.eu/vle/2017/x.mp3")
        self.assertEqual(parsed["lines"][0], {"speaker": "Anna", "text": "Ms. Weaver is giving new assignments out."})
        self.assertEqual(parsed["lines"][1]["speaker"], "Ms. Weaver")

    def test_narrator_and_glossary_are_left_out(self):
        speakers = {line["speaker"] for line in lle.parse_lesson(PAGE)["lines"]}
        self.assertNotIn("Professor Bot", speakers)
        self.assertNotIn("assignment", speakers)

    def test_follows_link_to_next_lesson(self):
        self.assertEqual(
            lle.next_lesson_url(PAGE, 2, 2),
            f"{lle.BASE}/a/lets-learn-english-level-2-lesson-3/4027340.html",
        )

    def test_page_without_dialogue_is_skipped(self):
        self.assertEqual(lle.parse_lesson(PAGE.split('<div class="wsw">')[0]), {})
