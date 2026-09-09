from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    name = "apps.profiles"
    label = "profiles"

    def ready(self):
        from . import signals  # noqa: F401
