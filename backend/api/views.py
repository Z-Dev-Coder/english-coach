"""API views. Deliberately thin: parse, delegate to a service, serialize."""
from __future__ import annotations

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.services import ai_health
from apps.practice.models import SpeakingScript
from apps.practice.services import create_speaking_script
from apps.practice.scripts import SCENARIO_HINTS
from apps.profiles.constants import ALL_SKILLS, CEFR
from apps.profiles.models import LearnerProfile, StudySession
from apps.profiles.services import build_daily_plan, dashboard_payload

from .serializers import (
    LearnerProfileSerializer,
    RegisterSerializer,
    SpeakingScriptRequestSerializer,
    SpeakingScriptSerializer,
    StudySessionSerializer,
)


class RegisterView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "username": user.get_username()}, status=status.HTTP_201_CREATED
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth import authenticate

        user = authenticate(
            request,
            username=request.data.get("username"),
            password=request.data.get("password"),
        )
        if user is None:
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Wrong username or password."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.get_username()})


class ProfileView(RetrieveUpdateAPIView):
    serializer_class = LearnerProfileSerializer

    def get_object(self):
        return LearnerProfile.objects.get(user=self.request.user)


class DashboardView(APIView):
    def get(self, request):
        return Response(dashboard_payload(request.user))


class TodayLessonView(APIView):
    """Today's plan. In Phase 1 this is the time allocation; Phase 4 attaches
    generated activities to each block without changing this contract."""

    def get(self, request):
        minutes = request.query_params.get("minutes")
        plan = build_daily_plan(request.user, minutes=int(minutes) if minutes else None)
        return Response(
            {
                "date": timezone.localdate(),
                "total_minutes": sum(b.minutes for b in plan),
                "blocks": [
                    {"skill": b.skill, "minutes": b.minutes, "reason": b.reason} for b in plan
                ],
            }
        )


class StudySessionViewSet(viewsets.ModelViewSet):
    serializer_class = StudySessionSerializer

    def get_queryset(self):
        return StudySession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        session = self.get_object()
        session.complete()
        return Response(self.get_serializer(session).data)


class SpeakingScriptViewSet(viewsets.ReadOnlyModelViewSet):
    """Speaking Script Studio.

    GET  /api/practice/speaking-scripts/         previously generated scripts
    POST /api/practice/speaking-scripts/generate/ create a new one
    POST /api/practice/speaking-scripts/{id}/practiced/  mark as practised
    """

    serializer_class = SpeakingScriptSerializer

    def get_queryset(self):
        return SpeakingScript.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def scenarios(self, request):
        return Response(
            {
                "scenarios": [{"key": k, "description": v} for k, v in SCENARIO_HINTS.items()],
                "levels": [c.value for c in CEFR],
            }
        )

    @action(detail=False, methods=["post"])
    def generate(self, request):
        payload = SpeakingScriptRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        script = create_speaking_script(request.user, **payload.validated_data)
        return Response(self.get_serializer(script).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def practiced(self, request, pk=None):
        script = self.get_object()
        script.times_practiced += 1
        script.save(update_fields=["times_practiced"])
        return Response(self.get_serializer(script).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_status(request):
    """Whether the local AI is usable, and what to run if it is not."""
    return Response(ai_health())


@api_view(["GET"])
@permission_classes([AllowAny])
def meta(request):
    """Static vocabulary the frontend needs to render forms without hard-coding."""
    return Response(
        {
            "skills": ALL_SKILLS,
            "levels": [{"value": c.value, "label": c.label} for c in CEFR],
            "scenarios": sorted(SCENARIO_HINTS),
        }
    )
