"""Movies & TV lessons: at the learner's level, never repeated before they run out."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.content import scenes
from apps.content.models import Scene, SceneProgress
from apps.content.scene_seeds import SEED_SCENES
from apps.profiles.models import SkillProgress


class SeedScriptTests(TestCase):
    def test_every_seed_scene_is_a_usable_lesson(self):
        for seed in SEED_SCENES:
            with self.subTest(slug=seed["slug"]):
                self.assertGreaterEqual(len(seed["lines"]), 8)
                self.assertGreaterEqual(len({who for who, _ in seed["lines"]}), 2)
                self.assertGreaterEqual(len(seed["expressions"]), 5)
                self.assertGreaterEqual(len(seed["questions"]), 3)
                text = " ".join(line for _, line in seed["lines"]).lower()
                for item in seed["expressions"]:
                    # An expression that isn't in the scene can't be learned from it.
                    first_word = item["expression"].lower().strip(" .!?'").split()[0]
                    self.assertIn(first_word, text, f"{item['expression']!r} not used in the scene")


class SceneSelectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sc", password="scenes12345")

    def _set_listening(self, level):
        progress, _ = SkillProgress.objects.get_or_create(user=self.user, skill="listening")
        progress.level = level
        progress.save()

    def test_scenes_follow_the_listening_level(self):
        self._set_listening("B2")
        level, items = scenes.scenes_for(self.user)
        self.assertEqual(level, "B2")
        self.assertTrue(items)
        self.assertTrue(all(scene.level == "B2" for scene in items))

    def test_a_level_without_scenes_uses_the_nearest_one(self):
        self._set_listening("C2")
        _, items = scenes.scenes_for(self.user)
        self.assertTrue(items, "a C2 learner got nothing at all")
        self.assertTrue(all(scene.level == "B2" for scene in items))

    def test_next_scene_skips_finished_ones(self):
        self._set_listening("A2")
        first = scenes.next_scene(self.user, use_ai=False)
        scenes.complete_scene(self.user, first)
        second = scenes.next_scene(self.user, use_ai=False)
        self.assertNotEqual(first.id, second.id)

    def test_when_all_are_done_a_new_one_is_generated(self):
        self._set_listening("A2")
        for scene in Scene.objects.none():
            pass
        scenes.ensure_seed_scenes()
        for scene in Scene.objects.filter(level="A2"):
            scenes.complete_scene(self.user, scene)

        fresh = Scene(slug="ai-a2-test", title="Brand New", level="A2", source=Scene.Source.AI)
        with mock.patch("apps.content.lle.import_next", return_value=None), \
                mock.patch("apps.content.scenes.generate_scene", return_value=fresh) as generate:
            result = scenes.next_scene(self.user, use_ai=True)
        generate.assert_called_once()
        self.assertEqual(result.title, "Brand New")

    def test_when_all_are_done_a_real_recorded_lesson_is_fetched_first(self):
        self._set_listening("A2")
        scenes.ensure_seed_scenes()
        for scene in Scene.objects.filter(level="A2"):
            scenes.complete_scene(self.user, scene)

        real = Scene(slug="lle-2-9", title="Real One", level="A2", source=Scene.Source.VOA)
        with mock.patch("apps.content.lle.import_next", return_value=real), \
                mock.patch("apps.content.scenes.generate_scene") as generate:
            result = scenes.next_scene(self.user, use_ai=True)
        generate.assert_not_called()
        self.assertEqual(result.title, "Real One")

    def test_without_a_model_the_oldest_finished_scene_comes_round(self):
        self._set_listening("A2")
        scenes.ensure_seed_scenes()
        a2 = list(Scene.objects.filter(level="A2").order_by("id"))
        for scene in a2:
            scenes.complete_scene(self.user, scene)
        oldest = a2[0]
        SceneProgress.objects.filter(user=self.user, scene=oldest).update(
            completed_at="2020-01-01T00:00:00Z"
        )
        self.assertEqual(scenes.next_scene(self.user, use_ai=False).id, oldest.id)

    def test_seeding_is_idempotent(self):
        scenes.ensure_seed_scenes()
        scenes.ensure_seed_scenes()
        self.assertEqual(Scene.objects.filter(source=Scene.Source.SEED).count(), len(SEED_SCENES))


class SceneEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sce", password="scenes12345")
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(self.user)

    def test_next_complete_and_list(self):
        with mock.patch("apps.content.scenes.generate_scene", return_value=None):
            scene = self.client.get("/api/content/scenes/next/").data
            self.assertTrue(scene["lines"])
            self.assertFalse(scene["done"])

            self.assertEqual(self.client.post(f"/api/content/scenes/{scene['id']}/complete/").status_code, 200)
            listed = self.client.get("/api/content/scenes/").data
            done = {item["id"]: item["done"] for item in listed["scenes"]}
            self.assertTrue(done[scene["id"]])
            self.assertNotEqual(self.client.get("/api/content/scenes/next/").data["id"], scene["id"])


class ArticleLevelTests(TestCase):
    """Articles are adapted at the learner's reading level, not always B1."""

    def setUp(self):
        from apps.content.models import Article, ContentSource

        self.user = get_user_model().objects.create_user(username="art", password="article12345")
        progress, _ = SkillProgress.objects.get_or_create(user=self.user, skill="reading")
        progress.level = "B2"
        progress.save()
        source = ContentSource.objects.create(name="S", feed_url="https://example.com/feed")
        self.article = Article.objects.create(
            source=source, guid="g1", url="https://example.com/a", title="T", summary="x" * 200
        )
        self.client = APIClient(HTTP_HOST="localhost")
        self.client.force_authenticate(self.user)

    def test_prepare_uses_the_reading_level(self):
        seen = {}

        def fake_prepare(article, *, level):
            seen["level"] = level
            article.level = level
            article.status = article.Status.PREPARED
            article.save()
            return article

        with mock.patch("apps.content.services.prepare", side_effect=fake_prepare):
            self.client.post(f"/api/articles/{self.article.id}/prepare/", {}, format="json")
        self.assertEqual(seen["level"], "B2")

    def test_an_article_prepared_at_another_level_is_redone(self):
        self.article.status = self.article.Status.PREPARED
        self.article.level = "B1"
        self.article.save()
        with mock.patch("apps.content.services.prepare", side_effect=lambda a, level: a) as prepare:
            self.client.post(f"/api/articles/{self.article.id}/prepare/", {}, format="json")
        prepare.assert_called_once()
