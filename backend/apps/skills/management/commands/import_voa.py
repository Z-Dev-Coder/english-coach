"""Import real recorded passages from VOA Learning English.

    python manage.py import_voa --per-category 6

Idempotent: a page already imported (same source_url) is skipped.
"""
from django.core.management.base import BaseCommand

from apps.skills import voa
from apps.skills.models import Passage


class Command(BaseCommand):
    help = "Import real-voice listening passages (audio + transcript) from VOA Learning English."

    def add_arguments(self, parser):
        parser.add_argument("--per-category", type=int, default=6)

    def handle(self, *args, per_category, **options):
        added = 0
        for category, (topic, level) in voa.CATEGORIES.items():
            try:
                links = voa.article_links(voa.fetch(f"{voa.BASE}/z/{category}"))
            except Exception as exc:  # network trouble on one category shouldn't stop the rest
                self.stderr.write(f"category {category}: {exc}")
                continue
            taken = 0
            for url in links:
                if taken >= per_category:
                    break
                if Passage.objects.filter(source_url=url).exists():
                    taken += 1
                    continue
                try:
                    parsed = voa.parse_article(voa.fetch(url))
                except Exception as exc:
                    self.stderr.write(f"{url}: {exc}")
                    continue
                if not parsed:
                    continue
                Passage.objects.create(
                    title=parsed["title"],
                    text=parsed["text"],
                    level=level,
                    topic=topic,
                    source=Passage.Source.FEED,
                    source_url=url,
                    audio_url=parsed["audio_url"],
                    audio_credit=voa.CREDIT,
                    word_count=len(parsed["text"].split()),
                )
                taken += 1
                added += 1
                self.stdout.write(f"+ [{level}] {parsed['title']}")
        self.stdout.write(self.style.SUCCESS(f"Imported {added} real-voice passages."))
