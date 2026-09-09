"""Settings-level regression tests."""
import os
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from config.settings import PROJECT_ROOT, _database_config


class DatabasePathTests(SimpleTestCase):
    """A relative sqlite:// URL must not resolve against the current directory.

    Regression test for a real bug: `DATABASE_URL=sqlite:///db.sqlite3` created a
    *separate database per launch directory*. The server (started from the repo
    root) and management commands (run from backend/) used different files, so
    seeded data and user accounts appeared to vanish.

    These exercise the resolver directly rather than `settings.DATABASES`,
    because the test runner substitutes its own database name at runtime.
    """

    def _resolve(self, url):
        with mock.patch.dict(os.environ, {"DATABASE_URL": url}):
            return _database_config()

    def test_relative_sqlite_path_is_anchored_to_the_project_root(self):
        config = self._resolve("sqlite:///db.sqlite3")
        self.assertTrue(Path(config["NAME"]).is_absolute())
        self.assertEqual(Path(config["NAME"]), PROJECT_ROOT / "db.sqlite3")

    def test_a_nested_relative_path_is_also_anchored(self):
        config = self._resolve("sqlite:///data/app.sqlite3")
        self.assertEqual(Path(config["NAME"]), PROJECT_ROOT / "data" / "app.sqlite3")

    def test_an_absolute_sqlite_path_is_left_alone(self):
        absolute = Path("D:/somewhere/else/custom.sqlite3")
        config = self._resolve(f"sqlite:///{absolute}")
        self.assertEqual(Path(config["NAME"]), absolute)

    def test_in_memory_databases_are_not_turned_into_files(self):
        config = self._resolve("sqlite://:memory:")
        self.assertIn(config["NAME"], ("", ":memory:"))

    def test_postgres_urls_are_passed_through_untouched(self):
        config = self._resolve("postgres://user:pw@localhost:5432/english_coach")
        self.assertIn("postgresql", config["ENGINE"])
        self.assertEqual(config["NAME"], "english_coach")
        self.assertEqual(config["HOST"], "localhost")
        self.assertEqual(config["PORT"], 5432)

    def test_the_default_when_no_url_is_set_is_absolute(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            self.assertTrue(Path(_database_config()["NAME"]).is_absolute())


class SecuritySettingsTests(SimpleTestCase):
    def test_authentication_is_required_by_default(self):
        """A new endpoint must be private unless it opts out explicitly."""
        self.assertIn(
            "rest_framework.permissions.IsAuthenticated",
            settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"],
        )

    def test_errors_go_through_the_friendly_handler(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["EXCEPTION_HANDLER"],
            "api.exceptions.friendly_exception_handler",
        )

    def test_throttling_is_configured(self):
        self.assertIn("anon", settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
