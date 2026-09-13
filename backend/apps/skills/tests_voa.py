"""Parsing VOA Learning English pages into real-voice passages (offline)."""
from django.test import SimpleTestCase

from apps.skills import voa

SENTENCE = "The town is in the middle of good farmland and many people visit it every year. "
PAGE = f"""
<h1 class="title">American Places: Gettysburg</h1>
<script>var x = "https://voa-audio.voanews.eu/vle/2025/a_hq.mp3";</script>
<a href="https://voa-audio.voanews.eu/vle/2025/a.mp3">Direct link</a>
<div class="wsw">
<p>No media source currently available</p>
<p>{SENTENCE * 4}</p>
<p>{SENTENCE * 3}</p>
<p>I'm Jill Robbins.</p>
<p>_____________________________</p>
<p>Words in This Story</p>
<p><i>farmland</i> - n. land used for farming</p>
</div>
"""


class ParseArticleTests(SimpleTestCase):
    def test_extracts_title_audio_and_transcript(self):
        parsed = voa.parse_article(PAGE)
        self.assertEqual(parsed["title"], "American Places: Gettysburg")
        self.assertEqual(parsed["audio_url"], "https://voa-audio.voanews.eu/vle/2025/a.mp3")
        self.assertIn("good farmland", parsed["text"])

    def test_player_chrome_sign_off_and_glossary_are_dropped(self):
        text = voa.parse_article(PAGE)["text"]
        self.assertNotIn("No media source", text)
        self.assertNotIn("Jill Robbins", text)
        self.assertNotIn("land used for farming", text)

    def test_curly_apostrophe_sign_off_and_credit_line_are_dropped(self):
        page = PAGE.replace("I'm Jill Robbins.", "I’m John Russell.</p><p>John Russell adapted it for VOA Learning English.")
        text = voa.parse_article(page)["text"]
        self.assertNotIn("John Russell", text)

    def test_wire_service_stories_are_not_imported(self):
        page = PAGE.replace("<p>I'm Jill", "<p>The Associated Press reported this story.</p><p>I'm Jill")
        self.assertEqual(voa.parse_article(page), {})

    def test_underline_between_introduction_and_story_does_not_end_the_transcript(self):
        # American Stories: intro, a line of underscores, then the whole story.
        page = PAGE.replace(
            f"<p>{SENTENCE * 3}</p>",
            "<p>________________</p><p>The whole story continues here after the break.</p>" + f"<p>{SENTENCE * 3}</p>",
        )
        text = voa.parse_article(page)["text"]
        self.assertIn("The whole story continues here", text)
        self.assertNotIn("____", text)
        self.assertNotIn("land used for farming", text)

    def test_american_stories_layout_keeps_story_and_drops_quiz_teachers_and_glossary(self):
        page = f"""
<h1>American Stories: How the Animals Lost Their Tails</h1>
<a href="https://voa-audio.voanews.eu/vle/2023/story.mp3">mp3</a>
<div class="wsw">
<p>Introduction:</p><p>{SENTENCE * 2}</p>
<p>________________________________________________</p>
<p>{SENTENCE * 5}</p><p>The animals got their tails back in the end.</p>
<p>Mario Ritter, Jr. adapted this public domain story by Carl Sandburg for VOA Learning English.</p>
<h2>Quiz - How the Animals Lost Their Tails</h2>
<h2>For Teachers</h2><p>Download the document below for lesson ideas.</p>
<h2>Words in This Story</h2><p>gavel - n. a small hammer</p>
<p>We want to hear from you.</p>
</div>"""
        text = voa.parse_article(page)["text"]
        self.assertIn("got their tails back in the end", text)
        for dropped in ("Mario Ritter", "lesson ideas", "small hammer", "hear from you", "____"):
            self.assertNotIn(dropped, text)

    def test_editors_note_mentioning_voa_at_the_top_does_not_end_the_transcript(self):
        page = PAGE.replace(
            "<p>No media source currently available</p>",
            "<p>No media source currently available</p>"
            "<p>Editor's Note: We are pleased to share this holiday story, adapted for VOA Learning English.</p>",
        )
        parsed = voa.parse_article(page)
        self.assertTrue(parsed)
        self.assertIn("good farmland", parsed["text"])
        self.assertNotIn("Editor's Note", parsed["text"])

    def test_page_without_audio_is_skipped(self):
        self.assertEqual(voa.parse_article(PAGE.replace(".mp3", ".txt")), {})

    def test_article_links_are_unique_and_absolute(self):
        listing = '<a href="/a/one/1.html"></a><a href="/a/one/1.html"></a><a href="/a/two/2.html"></a>'
        self.assertEqual(
            voa.article_links(listing),
            [f"{voa.BASE}/a/one/1.html", f"{voa.BASE}/a/two/2.html"],
        )
