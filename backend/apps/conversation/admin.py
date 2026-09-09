from django.contrib import admin

from .models import ConversationMessage, ConversationSession


class MessageInline(admin.TabularInline):
    model = ConversationMessage
    extra = 0
    readonly_fields = ("role", "content", "created_at")


@admin.register(ConversationSession)
class ConversationSessionAdmin(admin.ModelAdmin):
    list_display = ("scenario", "user", "level", "status", "started_at")
    list_filter = ("scenario", "status")
    inlines = [MessageInline]
