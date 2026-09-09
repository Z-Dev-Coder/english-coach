from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user, swapped in from day one so multi-user support stays possible.

    The app is single-learner today, but replacing AUTH_USER_MODEL later is a
    painful migration; doing it now costs nothing.
    """

    native_language = models.CharField(
        max_length=64,
        blank=True,
        help_text="Used to decide how much native-language support to show (see immersion levels).",
    )
    timezone = models.CharField(max_length=64, default="UTC")

    def __str__(self) -> str:
        return self.get_username()
