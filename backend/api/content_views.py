"""Real-world content and mistake-bank endpoints."""
from __future__ import annotations

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.content import services as content_services
from apps.content.models import Article, ContentSource
from apps.mistakes import services as mistake_services
from apps.mistakes.models import Mistake


class ArticleSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    has_material = serializers.BooleanField(read_only=True)

    class Meta:
        model = Article
        fields = [
            "id", "title", "url", "summary", "author", "topic", "published_at",
            "source_name", "status", "level", "adapted_text", "vocabulary",
            "phrases", "questions", "speaking_prompt", "writing_prompt",
            "has_material", "preparation_error",
        ]
        read_only_fields = fields


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    """Real-world stories.

    Articles are shared rather than per-learner: the same story is the same
    story. Nothing here is user-specific except which ones get surfaced.
    """

    serializer_class = ArticleSerializer

    def get_queryset(self):
        queryset = Article.objects.select_related("source")
        topic = self.request.query_params.get("topic")
        if topic:
            queryset = queryset.filter(topic=topic)
        query = self.request.query_params.get("search")
        if query:
            return content_services.search(query, topic=topic or "")
        return queryset

    @action(detail=False, methods=["get"])
    def today(self, request):
        """A handful of current stories, biased toward the learner's interests."""
        prepare_count = int(request.query_params.get("prepare", 0) or 0)
        articles = content_services.today_in_english(
            request.user,
            limit=int(request.query_params.get("limit", 6) or 6),
            prepare_count=min(prepare_count, 3),
        )
        return Response(
            {
                "articles": ArticleSerializer(articles, many=True).data,
                # order_by() must be cleared before distinct(): the model's
                # default ordering is added to the SELECT, which makes DISTINCT
                # compare (topic, name) and return the same topic repeatedly.
                "topics": sorted(
                    ContentSource.objects.filter(is_active=True)
                    .order_by()
                    .values_list("topic", flat=True)
                    .distinct()
                ),
            }
        )

    @action(detail=True, methods=["post"])
    def prepare(self, request, pk=None):
        """Generate learning material for one story, at the learner's reading level.

        It used to default to B1 whenever the page sent no level -- which it
        never did -- so every story was adapted at B1 regardless of the learner.
        """
        from apps.content.scenes import learner_level

        article = self.get_object()
        level = request.data.get("level") or learner_level(request.user, "reading")
        if article.is_prepared and article.level == level:
            return Response(ArticleSerializer(article).data)
        prepared = content_services.prepare(article, level=level)
        return Response(ArticleSerializer(prepared).data)


class IngestView(APIView):
    """Trigger a fetch by hand.

    Normally run from the command line or a scheduler; exposed so the learner
    can pull fresh stories without leaving the app.
    """

    def post(self, request):
        results = content_services.ingest_all(topic=request.data.get("topic", ""))
        return Response(
            {
                "results": results,
                "added": sum(item["added"] for item in results),
            }
        )


class DialogueSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=20, max_length=4000)
    level = serializers.CharField(max_length=2, required=False, allow_blank=True, default="")


class DialogueStudyView(APIView):
    """Study a short dialogue excerpt the learner supplies.

    Deliberately user-supplied only: the app does not scrape or redistribute
    subtitles. The learner pastes a few lines from what they are watching.
    """

    def post(self, request):
        payload = DialogueSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        result = content_services.study_dialogue(
            request.user,
            payload.validated_data["text"],
            level=payload.validated_data["level"],
        )
        return Response(result)


# --- Mistake bank ----------------------------------------------------------
class MistakeSerializer(serializers.ModelSerializer):
    is_persistent = serializers.BooleanField(read_only=True)

    class Meta:
        model = Mistake
        fields = [
            "id", "category", "incorrect", "correct", "explanation",
            "occurrences", "times_avoided", "status", "is_persistent",
            "first_seen_at", "last_seen_at",
        ]
        read_only_fields = fields


class MistakeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MistakeSerializer

    def get_queryset(self):
        queryset = Mistake.objects.filter(user=self.request.user)
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=False, methods=["get"])
    def summary(self, request):
        mistake_services.refresh_statuses(request.user)
        return Response(mistake_services.summary(request.user))

    @action(detail=False, methods=["get"])
    def practice(self, request):
        """The mistakes worth working on today, as tasks rather than a list."""
        return Response({"items": mistake_services.practice_items(request.user)})

    @action(detail=True, methods=["post"])
    def avoided(self, request, pk=None):
        """The learner got this right when they could have got it wrong."""
        mistake = mistake_services.mark_avoided(request.user, int(pk))
        if not mistake:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(MistakeSerializer(mistake).data)


class SceneSummarySerializer(serializers.ModelSerializer):
    class Meta:
        from apps.content.models import Scene

        model = Scene
        fields = ["id", "slug", "title", "genre", "level", "setting", "source", "audio_url"]


class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.content.models import Scene

        model = Scene
        fields = [
            "id", "slug", "title", "genre", "level", "setting", "lines",
            "expressions", "questions", "source", "audio_url", "audio_credit",
        ]


class SceneViewSet(viewsets.ReadOnlyModelViewSet):
    """Movies & TV lessons: original scenes at the learner's listening level."""

    serializer_class = SceneSerializer

    def get_queryset(self):
        from apps.content.models import Scene

        return Scene.objects.all()

    def _with_done(self, scene, done):
        data = SceneSerializer(scene).data
        data["done"] = scene.id in done
        return data

    def list(self, request):
        from apps.content import scenes

        level, items = scenes.scenes_for(request.user)
        done = scenes.done_ids(request.user)
        return Response(
            {
                "level": level,
                "scenes": [
                    {**SceneSummarySerializer(scene).data, "done": scene.id in done}
                    for scene in items
                ],
            }
        )

    def retrieve(self, request, pk=None):
        from apps.content import scenes

        return Response(self._with_done(self.get_object(), scenes.done_ids(request.user)))

    @action(detail=False, methods=["get"])
    def next(self, request):
        from apps.content import scenes

        use_ai = str(request.query_params.get("use_ai", "true")).lower() != "false"
        scene = scenes.next_scene(request.user, use_ai=use_ai)
        if scene is None:
            return Response({"detail": "No scenes available."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self._with_done(scene, scenes.done_ids(request.user)))

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        from apps.content import scenes

        scenes.complete_scene(request.user, self.get_object())
        return Response({"done": True})
