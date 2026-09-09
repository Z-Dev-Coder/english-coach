from django.contrib import admin

from .models import SpeakingScript


@admin.register(SpeakingScript)
class SpeakingScriptAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "scenario", "level", "source", "created_at")
    list_filter = ("scenario", "level", "source")
