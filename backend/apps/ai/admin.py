from django.contrib import admin

from .models import AICache, AIRequestLog


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = ("task", "model", "duration_ms", "success", "created_at")
    list_filter = ("task", "success", "model")


@admin.register(AICache)
class AICacheAdmin(admin.ModelAdmin):
    list_display = ("task", "model", "hits", "last_used_at")
    list_filter = ("task",)
