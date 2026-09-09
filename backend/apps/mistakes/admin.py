from django.contrib import admin

from .models import Mistake, MistakeOccurrence


class OccurrenceInline(admin.TabularInline):
    model = MistakeOccurrence
    extra = 0
    readonly_fields = ("origin", "context", "created_at")


@admin.register(Mistake)
class MistakeAdmin(admin.ModelAdmin):
    list_display = ("incorrect", "correct", "category", "occurrences", "status", "last_seen_at")
    list_filter = ("category", "status")
    search_fields = ("incorrect", "correct")
    inlines = [OccurrenceInline]
