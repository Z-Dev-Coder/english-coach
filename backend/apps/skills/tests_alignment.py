"""Matching heard words to the transcript, without running the speech model."""
from django.test import SimpleTestCase, override_settings
from unittest import mock

from apps.skills import alignment

TEXT = "One dollar and eighty-seven cents. That was all.\nAnd sixty cents of it."


class MatchTests(SimpleTestCase):
    def test_programme_intro_not_in_text_is_skipped(self):
        heard = [("We", 0.5), ("present", 0.9), ("a", 1.2), ("story.", 1.4),
                 ("One", 15.4), ("dollar", 15.8), ("and", 16.1), ("eighty-seven", 16.4),
                 ("cents.", 17.0), ("That", 18.3), ("was", 18.5), ("all.", 18.8)]
        timings = dict(alignment.match(TEXT, heard))
        self.assertEqual(timings[0], 15.4)   # "One" starts at 15.4s, not 0
        self.assertEqual(timings[5], 18.3)   # "That"

    def test_misheard_words_leave_gaps_but_keep_order(self):
        heard = [("One", 1.0), ("dolor", 1.3), ("and", 1.6), ("cents", 2.0), ("That", 3.0)]
        timings = alignment.match(TEXT, heard)
        starts = [start for _, start in timings]
        self.assertEqual(starts, sorted(starts))
        self.assertNotIn(1, dict(timings))

    def test_char_timings_point_at_word_starts_in_any_whitespace_form(self):
        word_timings = [[0, 15.4], [5, 18.3]]
        collapsed = " ".join(TEXT.split())
        for text in (TEXT, collapsed):
            offsets = alignment.char_timings(text, word_timings)
            self.assertEqual(text[offsets[1][0]:offsets[1][0] + 4], "That")

    def test_recording_that_is_not_this_text_gets_no_timings(self):
        with mock.patch.object(alignment, "transcribe", return_value=[("completely", 1.0), ("different", 2.0)]):
            self.assertEqual(alignment.timings_for("http://x/a.mp3", TEXT), [])

    @override_settings(LIVE_CONTENT_FETCH=False)
    def test_no_background_alignment_when_live_fetch_is_off(self):
        passage = mock.Mock(audio_url="http://x/a.mp3", spec=["audio_url"])
        with mock.patch("threading.Thread") as thread:
            alignment.align_in_background(passage)
        thread.assert_not_called()
