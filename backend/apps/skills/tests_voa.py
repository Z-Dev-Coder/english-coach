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

    def test_page_without_audio_is_skipped(self):
        self.assertEqual(voa.parse_article(PAGE.replace(".mp3", ".txt")), {})

    def test_article_links_are_unique_and_absolute(self):
        listing = '<a href="/a/one/1.html"></a><a href="/a/one/1.html"></a><a href="/a/two/2.html"></a>'
        self.assertEqual(
            voa.article_links(listing),
            [f"{voa.BASE}/a/one/1.html", f"{voa.BASE}/a/two/2.html"],
        )
