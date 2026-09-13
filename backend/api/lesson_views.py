"""Lesson and conversation endpoints."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.prompts import SCENARIO_HINTS
from apps.conversation import services as conversation_services
from apps.conversation.models import ConversationMessage, ConversationSession
from apps.lessons import services as lesson_services
from apps.lessons.models import Lesson, LessonActivity
from apps.profiles.constants import CEFR


class LessonActivitySerializer(serializers.ModelSerializer):
    is_complete = serializers.SerializerMethodField()

    class Meta:
        model = LessonActivity
        fields = [
            "id", "position", "kind", "title", "instructions", "minutes",
            "prompt", "target_expressions", "route", "params",
            "completed_at", "is_complete",
        ]
        read_only_fields = fields

    def get_is_complete(self, activity) -> bool:
        return activity.completed_at is not None


class LessonSerializer(serializers.ModelSerializer):
    activities = LessonActivitySerializer(many=True, read_only=True)
    progress = serializers.FloatField(read_only=True)

    class Meta:
        model = Lesson
        fields = [
            "id", "date", "title", "theme", "encouragement", "total_minutes",
            "focus_skills", "status", "origin", "progress", "activities",
            "created_at", "completed_at",
        ]
        read_only_fields = fields


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LessonSerializer

    def get_queryset(self):
        # Newest first, with id as the tiebreak: lessons renew on completion,
        # so several can share a date and date alone gives an unstable order.
        return (
            Lesson.objects.filter(user=self.request.user)
            .order_by("-date", "-id")
            .prefetch_related("activities")
        )

    @action(detail=False, methods=["get", "post"])
    def today(self, request):
        """Today's lesson, created on first request and stable thereafter."""
        minutes = request.query_params.get("minutes") or request.data.get("minutes")
        use_ai = str(request.query_params.get("use_ai", "true")).lower() != "false"
        lesson = lesson_services.generate_lesson(
            request.user, minutes=int(minutes) if minutes else None, use_ai=use_ai
        )
        return Response(self.get_serializer(lesson).data)

    @action(detail=False, methods=["post"])
    def regenerate(self, request):
        """Deliberately discard today's lesson and build another."""
        minutes = request.data.get("minutes")
        use_ai = str(request.data.get("use_ai", "true")).lower() != "false"
        lesson = lesson_services.regenerate(
            request.user, minutes=int(minutes) if minutes else None, use_ai=use_ai
        )
        return Response(self.get_serializer(lesson).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="activities/(?P<activity_id>[^/.]+)/complete")
    def complete_activity(self, request, pk=None, activity_id=None):
        lesson = self.get_object()
        activity = get_object_or_404(lesson.activities, pk=activity_id)
        activity.complete()
        lesson.refresh_from_db()
        return Response(self.get_serializer(lesson).data)


class LearnerContextView(APIView):
    """The structured learner state a lesson is generated from.

    Exposed so the learner can see exactly what the system believes about them,
    rather than the personalisation being a black box.
    """

    def get(self, request):
        return Response(lesson_services.learner_context(request.user))


# --- Conversation ----------------------------------------------------------
class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = fields


class ConversationSessionSerializer(serializers.ModelSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)
    turn_count = serializers.SerializerMethodField()

    class Meta:
        model = ConversationSession
        fields = [
            "id", "scenario", "level", "status", "started_at", "ended_at",
            "feedback", "messages", "turn_count", "targets",
        ]
        read_only_fields = fields

    def get_turn_count(self, session) -> int:
        return len(session.learner_turns)


class StartConversationSerializer(serializers.Serializer):
    scenario = serializers.CharField(max_length=40, required=False, default="casual")
    targets = serializers.ListField(
        child=serializers.CharField(max_length=120), required=False, default=list, max_length=20
    )
    level = serializers.ChoiceField(
        choices=CEFR.choices, required=False, allow_blank=True, default=""
    )


class SendMessageSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=2000)


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSessionSerializer

    def get_queryset(self):
        return ConversationSession.objects.filter(user=self.request.user).prefetch_related(
            "messages"
        )

    @action(detail=False, methods=["get"])
    def scenarios(self, request):
        return Response(
            {
                "scenarios": [{"key": key, "description": text} for key, text in SCENARIO_HINTS.items()],
                "levels": [choice.value for choice in CEFR],
                # What the app would choose for this learner. The page cannot
                # work it out itself -- it depends on what they have already
                # practised -- and it names the situation before starting one.
                "suggested": conversation_services.next_scenario(request.user),
            }
        )

    @action(detail=False, methods=["get"])
    def prep(self, request):
        """The language to learn before this situation, at the learner's speaking level."""
        from apps.skills import topic_language

        scenario = request.query_params.get("scenario") or conversation_services.next_scenario(request.user)
        progress = request.user.skill_progress.filter(skill="speaking").first()
        level = progress.level if progress else request.user.learner_profile.overall_level
        situation = f"{scenario.replace('_', ' ')}: {SCENARIO_HINTS.get(scenario, '')}"
        data = topic_language.build(kind="conversation", topic=situation, level=level)
        if data.get("is_fallback"):
            data = topic_language._conversation_fallback(scenario, level)
        data["scenario"] = scenario
        return Response(data)

    @action(detail=False, methods=["post"])
    def start(self, request):
        payload = StartConversationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        session = conversation_services.start(request.user, **payload.validated_data)
        return Response(self.get_serializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def say(self, request, pk=None):
        session = self.get_object()
        if session.status == ConversationSession.Status.ENDED:
            return Response(
                {"error": {"code": "conversation_ended", "message": "This conversation has ended."}},
                status=status.HTTP_409_CONFLICT,
            )
        payload = SendMessageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        message = conversation_services.reply(session, payload.validated_data["text"])
        return Response(
            {
                "reply": ConversationMessageSerializer(message).data,
                "session": self.get_serializer(session).data,
            }
        )

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        session = self.get_object()
        feedback = conversation_services.end(session)
        session.refresh_from_db()
        return Response({"feedback": feedback, "session": self.get_serializer(session).data})
