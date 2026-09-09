"""Wipe a learner's history without destroying the account or the shared library.

Useful after testing, or whenever the profile has been trained on data that was
not really the learner's — a demo, a stress test, someone else borrowing the
laptop. Skill scores, review schedules and the mistake bank are all evidence,
and evidence gathered from the wrong person makes every later decision wrong.

What is kept: the account, the profile's own settings (goals, interests), the
shared Expression library, and passages and articles, since none of those are
personal history.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.profiles.constants import ALL_SKILLS
from apps.profiles.models import SkillProgress, StudySession


class Command(BaseCommand):
    help = "Reset one learner's progress, keeping their account and the shared content."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="Username to reset.")
        parser.add_argument(
            "--keep-vocabulary",
            action="store_true",
            help="Keep tracked words but clear their review history and schedule.",
        )
        parser.add_argument(
            "--keep-ai-log",
            action="store_true",
            help="Keep the AI request log, so cost history survives the reset.",
        )
        parser.add_argument(
            "--yes", action="store_true", help="Skip the confirmation prompt."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist as exc:
            raise CommandError(f"No user named {options['user']!r}.") from exc

        from apps.ai.models import AICache, AIRequestLog
        from apps.conversation.models import ConversationSession
        from apps.lessons.models import Lesson
        from apps.mistakes.models import Mistake
        from apps.practice.models import SpeakingScript
        from apps.review.models import Review
        from apps.skills.models import SkillAttempt
        from apps.vocabulary.models import VocabularyProgress

        counts = {
            "skill attempts": SkillAttempt.objects.filter(user=user).count(),
            "reviews": Review.objects.filter(user=user).count(),
            "mistakes": Mistake.objects.filter(user=user).count(),
            "conversations": ConversationSession.objects.filter(user=user).count(),
            "lessons": Lesson.objects.filter(user=user).count(),
            "study sessions": StudySession.objects.filter(user=user).count(),
            "speaking scripts": SpeakingScript.objects.filter(user=user).count(),
            "tracked words": VocabularyProgress.objects.filter(user=user).count(),
        }

        self.stdout.write(f"\nAbout to reset {user.get_username()}:")
        for label, count in counts.items():
            if label == "tracked words" and options["keep_vocabulary"]:
                self.stdout.write(f"  {count:>5}  {label} (kept, schedule reset)")
            else:
                self.stdout.write(f"  {count:>5}  {label}")
        self.stdout.write("  all skill scores back to their starting values")

        if not options["yes"]:
            answer = input("\nType the username again to confirm: ").strip()
            if answer != user.get_username():
                raise CommandError("Cancelled — nothing was changed.")

        # Review rows point at VocabularyProgress, so they go first either way.
        Review.objects.filter(user=user).delete()
        SkillAttempt.objects.filter(user=user).delete()
        Mistake.objects.filter(user=user).delete()  # cascades to occurrences
        ConversationSession.objects.filter(user=user).delete()  # cascades to messages
        Lesson.objects.filter(user=user).delete()  # cascades to activities
        StudySession.objects.filter(user=user).delete()
        SpeakingScript.objects.filter(user=user).delete()

        if options["keep_vocabulary"]:
            # Back to "never seen": no stability, no schedule, due immediately.
            from django.utils import timezone

            from apps.vocabulary.models import MasteryState

            VocabularyProgress.objects.filter(user=user).update(
                stability=None,
                difficulty=None,
                due_at=timezone.now(),
                state=MasteryState.NEW,
                reps=0,
                lapses=0,
                successful_productions=0,
                last_reviewed_at=None,
                last_interval_days=0,
            )
        else:
            VocabularyProgress.objects.filter(user=user).delete()

        # Skill scores are the most contaminated thing here: they are an average
        # over attempts that were not the learner's.
        SkillProgress.objects.filter(user=user).delete()
        SkillProgress.objects.bulk_create(
            [SkillProgress(user=user, skill=skill) for skill in ALL_SKILLS]
        )

        if not options["keep_ai_log"]:
            AIRequestLog.objects.filter(user=user).delete()
            AIRequestLog.objects.filter(user__isnull=True).delete()
            AICache.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {user.get_username()} starts clean — the shared expression "
                "library, passages and articles were left alone."
            )
        )
