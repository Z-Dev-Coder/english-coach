"""Skill activity endpoints. Thin: validate, delegate to apps.skills.services."""
from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles.constants import CEFR
from apps.skills import services, shadowing, speaking_support, writing_support
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
    targets = serializers.ListField(
        child=serializers.CharField(max_length=120), required=False, default=list, max_length=30
    )
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


class WritingLessonView(APIView):
    """The language, plan and model text for a writing task, at the learner's level."""

    def get(self, request):
        task = request.query_params.get("task", "")[:600]
        level = request.query_params.get("level") or ""
        if not level:
            progress = request.user.skill_progress.filter(skill="writing").first()
            level = progress.level if progress else request.user.learner_profile.overall_level
        return Response(writing_support.build_lesson(task=task, level=level))


class SpeakingSupportView(APIView):
    """What to say and in what order, before the learner has to say it.

    GET: it is a pure function of the prompt and the level, and nothing is
    recorded by asking how to approach a question.

    The target expressions come back with their meanings attached rather than
    as bare chips. A chip reading "after that" tells a learner nothing they
    could not guess; what they need is what it means, and a sentence using it.
    """

    def get(self, request):
        prompt = request.query_params.get("prompt", "")
        expressions = [
            value
            for value in request.query_params.getlist("expression")
            if value and len(value) < 200
        ][:8]

        level = request.query_params.get("level") or ""
        if not level:
            progress = request.user.skill_progress.filter(skill="speaking").first()
            level = progress.level if progress else request.user.learner_profile.overall_level

        support = speaking_support.build_support(
            prompt=prompt, level=level, expressions=expressions
        )
        support["target_expressions"] = _resolve_expressions(expressions)

        # The worked answer. Asked for separately because it is the slow part:
        # everything above is a lookup, this may be a model call on the first
        # learner to meet this prompt.
        if request.query_params.get("with_answer") == "1":
            answer = services.speaking_model_answer(
                prompt=prompt,
                level=level,
                expressions=[item["text"] for item in support["target_expressions"]],
                moves=[step["move"] for step in support["frame"]],
            )
            support["model_answer"] = answer
            # The model wrote the answer using these expressions, so it knows
            # which sense the lesson meant -- which a general dictionary cannot.
            _apply_glosses(support["target_expressions"], answer.get("expressions") or [])
        return Response(support)


def _apply_glosses(resolved, glosses):
    """Overlay the model's lesson-specific meanings on the resolved list.

    Only where it actually supplied one: a dictionary sense for an ordinary
    word is perfectly good, and losing it because the model skipped an entry
    would be a step backwards.
    """
    by_text = {str(item.get("text", "")).strip().lower(): item for item in glosses}
    for entry in resolved:
        gloss = by_text.get(entry["text"].strip().lower())
        if not gloss:
            continue
        entry["meaning"] = gloss["meaning"]
        if gloss.get("example"):
            entry["example"] = gloss["example"]


def _resolve_expressions(texts):
    """Attach our own meaning and example to each expression we know.

    One query for all of them, not one each: this runs on every speaking step,
    and eight round trips for eight chips is how a page quietly gets slow.

    An expression we do not teach still comes back, just without a meaning.
    The lesson generator writes these freely, so an unknown one is the normal
    case rather than an error -- and a chip with no meaning is still better
    than dropping the phrase the lesson asked the learner to practise.
    """
    from apps.vocabulary.models import Expression, normalize

    if not texts:
        return []

    wanted = {normalize(text): text for text in texts}
    known = {
        expression.normalized: expression
        for expression in Expression.objects.filter(
            normalized__in=list(wanted)
        ).prefetch_related("examples")
    }

    from apps.vocabulary import lookup as dictionary_lookup

    resolved = []
    for key, original in wanted.items():
        expression = known.get(key)
        if expression is None:
            # Not one we teach. The lesson generator writes these freely, so
            # this is the common case -- fall through to the dictionary rather
            # than showing a bare phrase nobody has explained.
            # A connective's dictionary entry is worse than nothing here:
            # "then: that time" is the noun sense and says nothing about
            # sequencing. Where we have a usage note, it wins.
            note = speaking_support.usage_note(original)
            if note:
                resolved.append({"text": original, "meaning": note, "example": ""})
                continue

            found = dictionary_lookup.look_up(original)
            senses = (found.get("entries") or [{}])[0].get("senses") or [{}]
            # "to unwind" is a verb by construction, but a dictionary lists
            # the noun first and the learner is shown "any mechanism that
            # unwinds something" -- true, and not what the lesson meant.
            wants_verb = original.strip().lower().startswith("to ")
            sense = next(
                (s for s in senses if wants_verb and s.get("part_of_speech") == "verb"),
                senses[0],
            )
            resolved.append(
                {
                    "text": original,
                    "meaning": sense.get("definition", ""),
                    "example": sense.get("example", ""),
                }
            )
            continue
        example = expression.examples.all()[:1]
        resolved.append(
            {
                "text": expression.text,
                "meaning": expression.meaning,
                "example": example[0].text if example else "",
                "register": expression.register,
            }
        )
    return resolved


class ShadowingGuideView(APIView):
    """How to shadow a passage: chunk boundaries, stress and intonation.

    GET, because it is a pure function of the text and the level -- nothing is
    recorded by asking how to say something. Level defaults to the learner's
    own speaking level rather than a fixed value, since chunk length is the
    whole point of the guide.
    """

    def get(self, request):
        passage = _passage_for(request, request.query_params.get("passage_id"))
        text = request.query_params.get("text") or (passage.text if passage else "")
        if not text:
            return Response(
                {"detail": "Pass `text`, or a `passage_id` you have access to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        level = request.query_params.get("level") or ""
        if not level:
            progress = request.user.skill_progress.filter(skill="speaking").first()
            level = progress.level if progress else request.user.learner_profile.overall_level

        guide = shadowing.build_guide(text, level=level)
        if passage is not None:
            guide["passage"] = {"id": passage.id, "title": passage.title}
        return Response(guide)


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
            targets=data.get("targets") or [],
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
