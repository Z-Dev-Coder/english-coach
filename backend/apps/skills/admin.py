from django.contrib import admin

from .models import Passage, SkillAttempt


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "topic", "word_count", "reading_ease", "source", "owner")
    list_filter = ("level", "topic", "source")
    search_fields = ("title", "text")


@admin.register(SkillAttempt)
class SkillAttemptAdmin(admin.ModelAdmin):
    list_display = ("activity", "skill", "user", "accuracy", "created_at")
    list_filter = ("activity", "skill")
