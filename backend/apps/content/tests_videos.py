"""Watch on YouTube lessons: picked at the learner's level, prepared from a transcript."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.content import videos
from apps.content.models import VideoLesson
from apps.profiles.models import SkillProgress

PREP = {
    "summary": "Two friends talk about lunch.",
    "expressions": [
        {"expression": "grab a bite", "meaning": "eat something quickly", "example": "Let's grab a bite."},
        {"expression": "packed lunch", "meaning": "food you bring from home", "example": "I bring a packed lunch."},
        {"expression": "on the go", "meaning": "while moving", "example": "I eat on the go."},
    ],
    "listen_for": [{"time": "0:45", "note": "How Beth disagrees politely."}],
    "questions": ["What does Neil eat?", "Why does Beth skip lunch?"],
    "speaking_prompt": "What did you have for lunch yesterday?",
}


class VideoLessonTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="yt", password="youtube12345")
        SkillProgress.objects.update_or_create(user=self.user, skill="listening", defaults={"level": "A2"})
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(self.user)

    def test_library_videos_at_the_learners_level(self):
        level, items = videos.videos_for(self.user)
        self.assertEqual(level, "A2")
        self.assertTrue(items)
        self.assertTrue(all(video.level == "A2" for video in items))

    def test_finishing_a_video_moves_to_the_next(self):
        first = videos.next_video(self.user)
        videos.complete(self.user, first)
        self.assertNotEqual(videos.next_video(self.user).id, first.id)

    def test_prepare_writes_notes_without_storing_the_transcript(self):
        videos.ensure_library()
        video = VideoLesson.objects.filter(level="A2").first()
        provider = mock.Mock()
        provider.generate_json.return_value = PREP
        with mock.patch("apps.ai.registry.get_ai_provider", return_value=provider):
            self.assertTrue(videos.prepare(video, "[0:01] SECRET TRANSCRIPT LINE"))
        video.refresh_from_db()
        self.assertEqual(video.expressions[0]["expression"], "grab a bite")
        self.assertIsNotNone(video.prepared_at)
        stored = " ".join(str(getattr(video, f.name)) for f in VideoLesson._meta.fields)
        self.assertNotIn("SECRET TRANSCRIPT LINE", stored)

    def test_api_links_to_youtube(self):
        data = self.client.get("/api/content/videos/next/").data
        self.assertTrue(data["url"].startswith("https://www.youtube.com/watch?v="))
        self.assertEqual(self.client.post(f"/api/content/videos/{data['id']}/complete/").status_code, 200)

    def test_notes_shipped_with_the_library_are_applied(self):
        videos.ensure_library()
        prepared = VideoLesson.objects.exclude(prepared_at=None)
        self.assertTrue(prepared.exists())
        for video in prepared:
            self.assertGreaterEqual(len(video.expressions), 3)
            self.assertGreaterEqual(len(video.questions), 2)
            self.assertTrue(all(":" in moment["time"] for moment in video.listen_for))

    def test_prepared_videos_come_first(self):
        _, items = videos.videos_for(self.user)
        self.assertIsNotNone(items[0].prepared_at)

    def test_timed_text_skips_music_markers(self):
        text = videos.timed_text([
            {"text": "[Music]", "start_ms": "0"},
            {"text": "Hello everyone.", "start_ms": "65000"},
        ])
        self.assertEqual(text, "[1:05] Hello everyone.")
