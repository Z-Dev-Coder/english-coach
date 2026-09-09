from django.contrib import admin

from .models import Lesson, LessonActivity


class ActivityInline(admin.TabularInline):
    model = LessonActivity
    extra = 0


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "date", "status", "origin", "total_minutes")
    list_filter = ("status", "origin")
    inlines = [ActivityInline]
