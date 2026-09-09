from django.contrib import admin

from .models import ExampleSentence, Expression, VocabularyProgress


class ExampleInline(admin.TabularInline):
    model = ExampleSentence
    extra = 1


@admin.register(Expression)
class ExpressionAdmin(admin.ModelAdmin):
    list_display = ("text", "kind", "cefr_level", "register", "source")
    list_filter = ("kind", "cefr_level", "register", "source")
    search_fields = ("text", "meaning")
    inlines = [ExampleInline]


@admin.register(VocabularyProgress)
class VocabularyProgressAdmin(admin.ModelAdmin):
    list_display = ("expression", "user", "state", "stability", "due_at", "reps", "lapses")
    list_filter = ("state",)
