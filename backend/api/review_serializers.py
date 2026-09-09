"""Serializers for vocabulary and review.

Kept in their own module rather than growing `serializers.py` indefinitely; the
API package stays organised by domain as later phases add more.
"""
from rest_framework import serializers

from apps.review.models import ExerciseType, Review
from apps.vocabulary.models import ExampleSentence, Expression, Kind, VocabularyProgress


class ExampleSentenceSerializer(serializers.ModelSerializer):
    cloze = serializers.CharField(read_only=True)

    class Meta:
        model = ExampleSentence
        fields = ["id", "text", "translation", "cloze"]


class ExpressionSerializer(serializers.ModelSerializer):
    examples = ExampleSentenceSerializer(many=True, read_only=True)
    is_multi_word = serializers.BooleanField(read_only=True)

    class Meta:
        model = Expression
        fields = [
            "id",
            "text",
            "kind",
            "meaning",
            "part_of_speech",
            "register",
            "cefr_level",
            "topic",
            "pronunciation",
            "collocations",
            "synonyms",
            "antonyms",
            "common_mistake",
            "source",
            "source_url",
            "examples",
            "is_multi_word",
        ]
        read_only_fields = ["id", "source", "examples", "is_multi_word"]


class VocabularyProgressSerializer(serializers.ModelSerializer):
    expression = ExpressionSerializer(read_only=True)
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = VocabularyProgress
        fields = [
            "id",
            "expression",
            "state",
            "stability",
            "difficulty",
            "due_at",
            "reps",
            "lapses",
            "successful_productions",
            "last_reviewed_at",
            "last_interval_days",
            "success_rate",
        ]
        read_only_fields = fields


class QueueItemSerializer(serializers.Serializer):
    """One card in the review queue: the item plus how to test it."""

    progress = VocabularyProgressSerializer()
    exercise = serializers.CharField()
    prompt = serializers.SerializerMethodField()

    def get_prompt(self, item) -> dict:
        """The exact text to show, decided server-side.

        The frontend should not have to know the pedagogy — it renders whatever
        the engine says this exercise needs.
        """
        expression = item.progress.expression
        example = expression.examples.first()

        if item.exercise == ExerciseType.MEET:
            return {
                "instruction": "A new expression. Read it, then say it out loud.",
                "front": expression.text,
                "support": expression.meaning,
            }
        if item.exercise == ExerciseType.RECALL:
            return {
                "instruction": "What does this mean?",
                "front": expression.text,
                "support": "",
            }
        if item.exercise == ExerciseType.PRODUCE:
            return {
                "instruction": "Which expression means this?",
                "front": expression.meaning,
                "support": "",
            }
        if item.exercise == ExerciseType.CLOZE:
            return {
                "instruction": "Fill the gap.",
                "front": example.cloze() if example else expression.meaning,
                "support": expression.meaning,
            }
        return {
            "instruction": "Use it in a sentence about your own life.",
            "front": expression.text,
            "support": expression.meaning,
        }


class AnswerSerializer(serializers.Serializer):
    progress_id = serializers.IntegerField()
    rating = serializers.ChoiceField(choices=[1, 2, 3, 4])
    exercise = serializers.ChoiceField(
        choices=ExerciseType.choices, required=False, default=ExerciseType.RECALL
    )
    duration_ms = serializers.IntegerField(required=False, default=0, min_value=0)


class ReviewLogSerializer(serializers.ModelSerializer):
    expression = serializers.CharField(source="progress.expression.text", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "expression",
            "rating",
            "exercise",
            "scheduled_days",
            "retrievability",
            "reviewed_at",
        ]
        read_only_fields = fields


class AddExpressionSerializer(serializers.Serializer):
    """Adding an expression the learner met in the wild."""

    text = serializers.CharField(max_length=200)
    meaning = serializers.CharField()
    kind = serializers.ChoiceField(choices=Kind.choices, required=False, default=Kind.PHRASE)
    cefr_level = serializers.CharField(max_length=2, required=False, allow_blank=True)
    register = serializers.CharField(max_length=20, required=False, allow_blank=True)
    example = serializers.CharField(required=False, allow_blank=True)


class AddExtractedSerializer(serializers.Serializer):
    """A batch of expressions pulled out of content the learner just studied."""

    items = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=20)
    source = serializers.ChoiceField(
        choices=["content", "ai", "learner"], required=False, default="content"
    )
    source_url = serializers.CharField(required=False, allow_blank=True, default="", max_length=800)
