from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LearnerProfile, default_skill_rows


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def bootstrap_learner(sender, instance, created, **kwargs):
    """Every user gets a profile and a full set of skill rows immediately.

    Done via a signal rather than in the registration view so that users created
    by fixtures, the admin, or `createsuperuser` are equally usable.
    """
    if not created:
        return
    LearnerProfile.objects.get_or_create(user=instance)
    default_skill_rows(instance)
