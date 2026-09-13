"""Watch on YouTube: one video at a time, found from channel feeds when needed (offline)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.content import videos
from apps.content.models import VideoLesson, VideoProgress
from apps.profiles.models import SkillProgress

FEED_XML = """<feed>
<entry><yt:videoId>short00001</yt:videoId><link rel="alternate" href="https://www.youtube.com/shorts/short00001"/>
<media:group><media:title>Quick slang quiz #shorts</media:title><media:description>x</media:description></media:group></entry>
<entry><yt:videoId>video000001</yt:videoId><link rel="alternate" href="https://www.youtube.com/watch?v=video000001"/>
<media:group><media:title>Talking about lunch &amp; food</media:title><media:description>Beth and Neil talk about lunch.</media:description></media:group></entry>
<entry><yt:videoId>video000002</yt:videoId><link rel="alternate" href="https://www.youtube.com/watch?v=video000002"/>
<media:group><media:title>Talking about transport</media:title><media:description>Buses and trains.</media:description></media:group></entry>
</feed>"""

PREP = {
    "summary": "Two presenters talk about lunch.",
    "expressions": [
        {"expression": "grab a bite", "meaning": "eat something quickly", "example": "Let's grab a bite."},
        {"expression": "packed lunch", "meaning": "food you bring from home", "example": "I bring a packed lunch."},
        {"expression": "skip a meal", "meaning": "not eat a meal", "example": "I skipped breakfast."},
    ],
    "listen_for": ["Notice how they agree."],
    "questions": ["What do they usually eat?", "Do you agree with them?"],
    "speaking_prompt": "What did you have for lunch yesterday?",
}


class ParseFeedTests(TestCase):
    def test_shorts_are_skipped_and_entities_decoded(self):
        items = videos.parse_feed(FEED_XML)
        self.assertEqual([item["video_id"] for item in items], ["video000001", "video000002"])
        self.assertEqual(items[0]["title"], "Talking about lunch & food")


class DynamicVideoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="yt", password="youtube12345")
        SkillProgress.objects.update_or_create(user=self.user, skill="listening", defaults={"level": "A2"})
        provider = mock.Mock()
        provider.generate_json.return_value = PREP
        self.patches = [
            mock.patch("apps.content.videos._fetch", return_value=FEED_XML),
            mock.patch("apps.ai.registry.get_ai_provider", return_value=provider),
        ]
        for patch in self.patches:
            patch.start()
        self.provider = provider

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_nothing_exists_until_a_learner_needs_it(self):
        self.assertEqual(VideoLesson.objects.count(), 0)
        video = videos.next_video(self.user)
        self.assertEqual(VideoLesson.objects.count(), 1)
        self.assertEqual(video.expressions[0]["expression"], "grab a bite")

    def test_the_same_video_until_it_is_finished(self):
        first = videos.next_video(self.user)
        self.assertEqual(videos.next_video(self.user).id, first.id)
        self.assertEqual(self.provider.generate_json.call_count, 1)

    def test_finishing_gives_a_new_video(self):
        first = videos.next_video(self.user)
        videos.complete(self.user, first)
        second = videos.next_video(self.user)
        self.assertNotEqual(second.id, first.id)
        self.assertEqual(VideoProgress.objects.filter(user=self.user, completed_at__isnull=True).count(), 1)

    def test_a_prepared_video_is_reused_for_another_learner(self):
        videos.next_video(self.user)
        other = get_user_model().objects.create_user(username="yt2", password="youtube12345")
        SkillProgress.objects.update_or_create(user=other, skill="listening", defaults={"level": "A2"})
        videos.next_video(other)
        self.assertEqual(self.provider.generate_json.call_count, 1)

    def test_api_next_and_complete(self):
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(self.user)
        data = client.get("/api/content/videos/next/").data
        self.assertTrue(data["url"].startswith("https://www.youtube.com/watch?v="))
        self.assertEqual(client.post(f"/api/content/videos/{data['id']}/complete/").status_code, 200)
        self.assertEqual(len(client.get("/api/content/videos/").data["videos"]), 1)
        self.assertNotEqual(client.get("/api/content/videos/next/").data["id"], data["id"])

    def test_feeds_unreachable_is_reported_not_crashed(self):
        cache.clear()
        with mock.patch("apps.content.videos._fetch", side_effect=OSError("offline")):
            client = APIClient(HTTP_HOST="localhost")
            client.force_authenticate(self.user)
            self.assertEqual(client.get("/api/content/videos/next/").status_code, 503)
