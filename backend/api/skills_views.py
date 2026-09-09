"""Skill activity endpoints. Thin: validate, delegate to apps.skills.services."""
from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles.constants import CEFR
from apps.skills import services
from apps.skills.models import ActivityType, Passage, SkillAttempt


class PassageSerializer(serializers.ModelSerializer):
    sentences = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Passage
        fields = [
            "id", "title", "text", "level", "topic", "source", "source_url",
            "word_count", "reading_ease", "sentences", "is_mine", "created_at",
        ]
        read_only_fields = fields

    def get_sentences(self, passage) -> list[str]:
        return passage.sentences()

    def get_is_mine(self, passage) -> bool:
        return passage.owner_id is not None


class SkillAttemptSerializer(serializers.ModelSerializer):
    passage_title = serializers.CharField(source="passage.title", read_only=True, default="")

    class Meta:
        model = SkillAttempt
        fields = [
            "id", "activity", "skill", "prompt", "response", "accuracy",
            "score_delta", "duration_ms", "detail", "passage", "passage_title",
            "created_at",
        ]
        read_only_fields = fields


class AddPassageSerializer(serializers.Serializer):
    # Optional fields carry explicit defaults: without them DRF omits the key
    # from validated_data entirely, and the service call fails on a missing
    # keyword argument rather than using its own default.
    title = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    text = serializers.CharField(min_length=20)
    level = serializers.ChoiceField(
        choices=CEFR.choices, required=False, allow_blank=True, default=""
    )
    topic = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")


class PassageViewSet(viewsets.ReadOnlyModelViewSet):
    """Shared passages plus the learner's own. Never another learner's."""

    serializer_class = PassageSerializer

    def get_queryset(self):
        queryset = Passage.objects.filter(Q(owner__isnull=True) | Q(owner=self.request.user))
        level = self.request.query_params.get("level")
        if level:
            queryset = queryset.filter(level=level)
        topic = self.request.query_params.get("topic")
        if topic:
            queryset = queryset.filter(topic=topic)
        return queryset

    @action(detail=False, methods=["post"])
    def add(self, request):
        payload = AddPassageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        passage = services.create_passage(request.user, **payload.validated_data)
        return Response(PassageSerializer(passage).data, status=status.HTTP_201_CREATED)


class DictationSerializer(serializers.Serializer):
    expected = serializers.CharField()
    written = serializers.CharField(allow_blank=True)
    passage_id = serializers.IntegerField(required=False, allow_null=True)
    duration_ms = serializers.IntegerField(required=False, default=0, min_value=0)


class ShadowingSerializer(serializers.Serializer):
    expected = serializers.CharField()
    transcript = serializers.CharField(allow_blank=True)
    passage_id = serializers.IntegerField(required=False, allow_null=True)
    duration_ms = serializers.IntegerField(required=False, default=0, min_value=0)


class WritingSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1)
    task = serializers.CharField(required=False, allow_blank=True, default="")
    level = serializers.CharField(max_length=2, required=False, allow_blank=True, default="")
    duration_ms = serializers.IntegerField(required=False, default=0, min_value=0)


class ReadingSerializer(serializers.Serializer):
    passage_id = serializers.IntegerField()
    seconds = serializers.IntegerField(min_value=1)
    comprehension = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=1)


class DrillSerializer(serializers.Serializer):
    sentence = serializers.CharField()
    spoken = serializers.CharField(required=False, allow_blank=True, default="")
    written = serializers.CharField(required=False, allow_blank=True, default="")
    variation = serializers.CharField(required=False, allow_blank=True, default="")
    duration_ms = serializers.IntegerField(required=False, default=0, min_value=0)


def _passage_for(request, passage_id):
    if not passage_id:
        return None
    return Passage.objects.filter(
        Q(pk=passage_id) & (Q(owner__isnull=True) | Q(owner=request.user))
    ).first()


class DictationView(APIView):
    def post(self, request):
        payload = DictationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        attempt = services.check_dictation(
            request.user,
            expected=data["expected"],
            written=data["written"],
            passage=_passage_for(request, data.get("passage_id")),
            duration_ms=data["duration_ms"],
        )
        return Response(SkillAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class ShadowingView(APIView):
    def post(self, request):
        payload = ShadowingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        attempt = services.check_shadowing(
            request.user,
            expected=data["expected"],
            transcript=data["transcript"],
            passage=_passage_for(request, data.get("passage_id")),
            duration_ms=data["duration_ms"],
        )
        return Response(SkillAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class WritingView(APIView):
    def post(self, request):
        payload = WritingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        attempt = services.evaluate_writing(
            request.user,
            text=data["text"],
            task=data["task"],
            level=data["level"],
            duration_ms=data["duration_ms"],
        )
        return Response(SkillAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class ReadingView(APIView):
    def post(self, request):
        payload = ReadingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        passage = get_object_or_404(
            Passage.objects.filter(Q(owner__isnull=True) | Q(owner=request.user)),
            pk=data["passage_id"],
        )
        attempt = services.record_reading(
            request.user,
            passage=passage,
            seconds=data["seconds"],
            comprehension=data.get("comprehension"),
        )
        return Response(SkillAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class DrillView(APIView):
    """GET a sentence to drill, POST the result of drilling it."""

    def get(self, request):
        return Response(services.drill_sentence(request.user, level=request.query_params.get("level", "")))

    def post(self, request):
        payload = DrillSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        attempt = services.check_drill(request.user, **payload.validated_data)
        return Response(SkillAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class AttemptListView(APIView):
    def get(self, request):
        queryset = SkillAttempt.objects.filter(user=request.user).select_related("passage")
        activity = request.query_params.get("activity")
        if activity in dict(ActivityType.choices):
            queryset = queryset.filter(activity=activity)
        return Response(SkillAttemptSerializer(queryset[:50], many=True).data)


class SkillSummaryView(APIView):
    def get(self, request):
        return Response(services.skill_summary(request.user))
