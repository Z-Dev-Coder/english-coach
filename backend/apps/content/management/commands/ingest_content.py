"""Fetch the configured feeds. Safe to run on a schedule; ingestion is idempotent."""
from django.core.management.base import BaseCommand

from apps.content.models import Article, ContentSource
from apps.content.seed_data import SEED_SOURCES
from apps.content.services import ingest_all, prepare


class Command(BaseCommand):
    help = "Fetch RSS sources and optionally prepare learning material."

    def add_arguments(self, parser):
        parser.add_argument("--topic", default="", help="Only fetch sources in this topic.")
        parser.add_argument(
            "--seed", action="store_true", help="Create the built-in sources first."
        )
        parser.add_argument(
            "--prepare",
            type=int,
            default=0,
            help="Generate learning material for N of the newest articles (slow: needs the model).",
        )
        parser.add_argument("--level", default="B1", help="CEFR level to write material at.")

    def handle(self, *args, **options):
        if options["seed"]:
            created = 0
            for entry in SEED_SOURCES:
                _source, was_created = ContentSource.objects.update_or_create(
                    feed_url=entry["feed_url"],
                    defaults={
                        "name": entry["name"],
                        "homepage": entry["homepage"],
                        "topic": entry["topic"],
                    },
                )
                created += was_created
            self.stdout.write(self.style.SUCCESS(f"Sources: {created} created."))

        for result in ingest_all(topic=options["topic"]):
            if result["ok"]:
                self.stdout.write(
                    f"  {result['source']}: +{result['added']} new, {result['skipped']} already had"
                )
            else:
                self.stdout.write(self.style.WARNING(f"  {result['source']}: {result['error']}"))

        count = options["prepare"]
        if not count:
            return

        pending = Article.objects.filter(status=Article.Status.FETCHED)[:count]
        self.stdout.write(f"Preparing material for {len(pending)} articles…")
        for article in pending:
            prepared = prepare(article, level=options["level"])
            mark = "ok" if prepared.is_prepared else f"failed ({prepared.preparation_error[:60]})"
            self.stdout.write(f"  {article.title[:60]}… {mark}")
