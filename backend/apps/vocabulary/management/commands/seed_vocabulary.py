"""Load the built-in starter expressions.

Idempotent: safe to run repeatedly. Existing expressions are updated rather than
duplicated, and a learner's review history is never touched.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.review.services import add_to_learning
from apps.vocabulary.models import ExampleSentence, Expression, normalize
from apps.vocabulary.seed_data import SEED_EXPRESSIONS


class Command(BaseCommand):
    help = "Load the built-in starter vocabulary, optionally assigning it to a learner."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            help="Username to add the expressions to. Omit to only load the shared set.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        created = updated = 0

        for text, kind, level, register, meaning, examples, mistake in SEED_EXPRESSIONS:
            expression, was_created = Expression.objects.update_or_create(
                normalized=normalize(text),
                kind=kind,
                defaults={
                    "text": text,
                    "meaning": meaning,
                    "cefr_level": level,
                    "register": register,
                    "common_mistake": mistake,
                    "source": Expression.Source.SEED,
                },
            )
            created += was_created
            updated += not was_created

            # Replace examples wholesale so edits to the seed file take effect.
            expression.examples.all().delete()
            ExampleSentence.objects.bulk_create(
                [
                    ExampleSentence(expression=expression, text=sentence, position=position)
                    for position, sentence in enumerate(examples)
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(f"Expressions: {created} created, {updated} updated.")
        )

        username = options.get("user")
        if not username:
            return

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"No user named {username!r}."))
            return

        before = user.vocabulary.count()
        for expression in Expression.objects.filter(source=Expression.Source.SEED):
            add_to_learning(user, expression)
        added = user.vocabulary.count() - before
        self.stdout.write(
            self.style.SUCCESS(f"Added {added} new expressions to {username}'s queue.")
        )
