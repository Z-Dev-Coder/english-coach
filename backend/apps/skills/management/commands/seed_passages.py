"""Load the built-in reading and listening passages. Idempotent."""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.skills.models import Passage
from apps.skills.seed_data import SEED_PASSAGES


class Command(BaseCommand):
    help = "Load the built-in passages used for reading, listening and dictation."

    @transaction.atomic
    def handle(self, *args, **options):
        created = updated = 0
        for entry in SEED_PASSAGES:
            _passage, was_created = Passage.objects.update_or_create(
                title=entry["title"],
                owner=None,
                defaults={
                    "text": entry["text"],
                    "level": entry["level"],
                    "topic": entry["topic"],
                    "source": Passage.Source.SEED,
                },
            )
            created += was_created
            updated += not was_created
        self.stdout.write(
            self.style.SUCCESS(f"Passages: {created} created, {updated} updated.")
        )
