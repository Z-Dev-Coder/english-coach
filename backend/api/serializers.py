from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.practice.models import SpeakingScript
from apps.profiles.constants import ALL_SKILLS, CEFR, SCHEDULABLE_SKILLS
from apps.profiles.models import LearnerProfile, SkillProgress, StudySession

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["username", "email", "password", "native_language"]

    def validate_password(self, value: str) -> str:
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        # create_user hashes the password; the profile/skill rows are created by
        # the post_save signal in apps.profiles.signals.
        return User.objects.create_user(**validated_data)


class SkillProgressSerializer(serializers.ModelSerializer):
    is_weak = serializers.BooleanField(read_only=True)

    class Meta:
        model = SkillProgress
        fields = ["skill", "level", "score", "confidence", "attempts", "last_practiced_at", "is_weak"]
        read_only_fields = fields


class LearnerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    overall_level = serializers.CharField(read_only=True)
    skills = SkillProgressSerializer(source="user.skill_progress", many=True, read_only=True)

    class Meta:
        model = LearnerProfile
        fields = [
            "username",
            "overall_level",
            "target_level",
            "daily_minutes",
            "weekly_goal_sessions",
            "immersion_level",
            "interests",
            "priority_skills",
            "preferred_study_days",
            "preferred_study_time",
            "skills",
        ]

    def validate_priority_skills(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Expected a list of skill names.")
        unknown = [s for s in value if s not in ALL_SKILLS]
        if unknown:
            raise serializers.ValidationError(
                f"Unknown skills: {', '.join(unknown)}. Valid: {', '.join(SCHEDULABLE_SKILLS)}."
            )
        return value

    def validate_interests(self, value):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise serializers.ValidationError("Expected a list of topic strings.")
        return value[:20]

    def validate_preferred_study_days(self, value):
        if not isinstance(value, list) or not all(isinstance(v, int) and 1 <= v <= 7 for v in value):
            raise serializers.ValidationError("Expected ISO weekday numbers, 1 (Mon) to 7 (Sun).")
        return sorted(set(value))


class StudySessionSerializer(serializers.ModelSerializer):
    active_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = StudySession
        fields = [
            "id",
            "started_at",
            "ended_at",
            "status",
            "planned_minutes",
            "active_seconds",
            "active_minutes",
            "skill_breakdown",
            "notes",
        ]
        read_only_fields = ["id", "started_at", "ended_at", "status", "active_minutes"]


class SpeakingScriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeakingScript
        fields = [
            "id",
            "scenario",
            "level",
            "title",
            "setting",
            "goal",
            "target_expressions",
            "lines",
            "follow_up_questions",
            "portable_prompt",
            "source",
            "times_practiced",
            "created_at",
        ]
        read_only_fields = fields


class SpeakingScriptRequestSerializer(serializers.Serializer):
    scenario = serializers.CharField(required=False, allow_blank=True, max_length=40)
    level = serializers.ChoiceField(choices=CEFR.choices, required=False, allow_blank=True)
    topic = serializers.CharField(required=False, allow_blank=True, max_length=200)
    use_ai = serializers.BooleanField(required=False, default=False)
