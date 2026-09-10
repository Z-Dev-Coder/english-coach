"""Vocabulary and review endpoints. Thin: they delegate to apps.review.services."""
from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.review import services
from apps.review.models import Review
from apps.vocabulary import lookup
from apps.vocabulary.models import ExampleSentence, Expression, MasteryState, VocabularyProgress

from .review_serializers import (
    AddExpressionSerializer,
    AddExtractedSerializer,
    AnswerSerializer,
    QueueItemSerializer,
    ReviewLogSerializer,
    VocabularyProgressSerializer,
)


class VocabularyViewSet(viewsets.ReadOnlyModelViewSet):
    """The learner's own vocabulary, with its scheduling state."""

    serializer_class = VocabularyProgressSerializer

    def get_queryset(self):
        queryset = (
            VocabularyProgress.objects.filter(user=self.request.user)
            .select_related("expression")
            .prefetch_related("expression__examples")
        )
        state = self.request.query_params.get("state")
        if state in dict(MasteryState.choices):
            queryset = queryset.filter(state=state)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(expression__normalized__icontains=search.lower())
                | Q(expression__meaning__icontains=search)
            )
        return queryset

    @action(detail=False, methods=["post"])
    def add(self, request):
        """Add an expression the learner met somewhere and start scheduling it."""
        payload = AddExpressionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        from apps.vocabulary.models import normalize

        expression, created = Expression.objects.get_or_create(
            normalized=normalize(data["text"]),
            kind=data["kind"],
            defaults={
                "text": data["text"],
                "meaning": data["meaning"],
                "cefr_level": data.get("cefr_level") or "B1",
                "register": data.get("register") or "neutral",
                "source": Expression.Source.LEARNER,
            },
        )
        if created and data.get("example"):
            ExampleSentence.objects.create(expression=expression, text=data["example"])

        progress = services.add_to_learning(request.user, expression)
        return Response(
            VocabularyProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


    @action(detail=False, methods=["post"], url_path="add-extracted")
    def add_extracted(self, request):
        """Add vocabulary lifted from an article or a dialogue to the queue.

        This is what turns reading into remembering: without it, extracted
        vocabulary is something the learner looked at once.
        """
        payload = AddExtractedSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        progress = services.add_extracted(
            request.user,
            data["items"],
            source=data["source"],
            source_url=data["source_url"],
        )
        return Response(
            {
                "added": len(progress),
                "items": VocabularyProgressSerializer(progress, many=True).data,
                "due_now": services.due_count(request.user),
            },
            status=status.HTTP_201_CREATED,
        )


class ReviewQueueView(APIView):
    """GET /api/review/queue/ — what to study right now."""

    def get(self, request):
        limit = request.query_params.get("limit")
        minutes = request.query_params.get("minutes")
        items = services.build_queue(
            request.user,
            limit=int(limit) if limit else None,
            minutes=int(minutes) if minutes else None,
        )
        return Response(
            {
                "count": len(items),
                "due_now": services.due_count(request.user),
                "items": QueueItemSerializer(items, many=True).data,
            }
        )


class ReviewAnswerView(APIView):
    """POST /api/review/answer/ — grade one card and reschedule it."""

    def post(self, request):
        payload = AnswerSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        progress = get_object_or_404(
            VocabularyProgress, pk=data["progress_id"], user=request.user
        )
        log = services.answer(
            progress,
            data["rating"],
            exercise=data["exercise"],
            duration_ms=data["duration_ms"],
        )
        return Response(
            {
                "review": ReviewLogSerializer(log).data,
                "progress": VocabularyProgressSerializer(progress).data,
                "next_due_in_days": log.scheduled_days,
                "remaining": services.due_count(request.user),
            }
        )


class ReviewStatsView(APIView):
    def get(self, request):
        return Response(
            {
                **services.stats(request.user),
                "forecast": services.forecast(request.user),
            }
        )


class ReviewHistoryView(APIView):
    def get(self, request):
        logs = (
            Review.objects.filter(user=request.user)
            .select_related("progress__expression")[:50]
        )
        return Response(ReviewLogSerializer(logs, many=True).data)


class DefineView(APIView):
    """Define a single word, for the hover-a-word popover in reading content.

    GET rather than POST: it is a pure read, and being cacheable by the browser
    matters for something triggered by pointer movement.

    Missing words are a 200 with `found: false`, not a 404. The client asks
    about whatever token the pointer happened to land on -- a name, a number,
    a typo in the learner's own writing -- and none of those are error
    conditions worth logging or retrying.
    """

    def get(self, request):
        word = request.query_params.get("word", "")
        if not word:
            return Response(
                {"detail": "A `word` query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(lookup.look_up(word))
