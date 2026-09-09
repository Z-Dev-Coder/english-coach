from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("progress", "rating", "exercise", "scheduled_days", "reviewed_at")
    list_filter = ("rating", "exercise")
