from django.contrib import admin

from .models import Article, ContentSource


@admin.register(ContentSource)
class ContentSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "topic", "is_active", "article_count", "last_fetched_at")
    list_filter = ("topic", "is_active")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "topic", "status", "level", "published_at")
    list_filter = ("status", "topic", "level")
    search_fields = ("title", "summary")
