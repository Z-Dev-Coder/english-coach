"""Real recorded content is fetched on demand, never from a fixed list (offline)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from apps.content import lle
from apps.skills import voa

STORY = " ".join(f"This is sentence number {n} of a real story." for n in range(14))


class StoryLinesTests(SimpleTestCase):
    def test_a_story_becomes_short_presenter_lines(self):
        lines = lle.story_lines(STORY)
        self.assertGreaterEqual(len(lines), 6)
        self.assertTrue(all(line["speaker"] == "Presenter" for line in lines))
        self.assertTrue(all(len(line["text"]) < 200 for line in lines))

    def test_levels_above_a2_use_real_stories(self):
        with mock.patch("apps.content.lle.import_story", return_value="story") as story:
            self.assertEqual(lle.import_next("C1"), "story")
        story.assert_called_once()

    def test_c2_borrows_the_c1_programme(self):
        self.assertTrue(voa.categories_for("C2"))
        self.assertEqual(voa.categories_for("C2"), voa.categories_for("C1"))


class TopUpTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="topup", password="topup12345")

    @override_settings(LIVE_CONTENT_FETCH=False)
    def test_no_network_when_live_fetch_is_off(self):
        with mock.patch("threading.Thread") as thread:
            voa.top_up_if_needed(self.user, "B1")
        thread.assert_not_called()

    @override_settings(LIVE_CONTENT_FETCH=True)
    def test_fetches_in_background_when_learner_has_run_out(self):
        with mock.patch("threading.Thread") as thread:
            voa.top_up_if_needed(self.user, "B1")
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()
