"""Pre-fetch real dialogue scenes from VOA's "Let's Learn English".

    python manage.py import_lle --count 5

Optional: the app already fetches the next lesson on its own whenever a
learner has finished every scene at their level. This only warms the library.
"""
from django.core.management.base import BaseCommand

from apps.content import lle


class Command(BaseCommand):
    help = "Fetch the next real-voice dialogue scenes for each level."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=5, help="Lessons per level.")
        parser.add_argument("--no-ai", action="store_true")

    def handle(self, *args, count, no_ai, **options):
        added = 0
        for _, level, _ in lle.SERIES:
            for _ in range(count):
                scene = lle.import_next(level, use_ai=not no_ai)
                if scene is None:
                    break
                added += 1
                self.stdout.write(f"+ [{level}] {scene.title} ({len(scene.lines)} lines)")
        self.stdout.write(self.style.SUCCESS(f"Imported {added} real-voice scenes."))
