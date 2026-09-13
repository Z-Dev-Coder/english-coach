"""Skill activity services: score an attempt, record it, move the profile.

Everything here works without AI. Writing feedback uses the local model when it
is available and falls back to rule-based checks when it is not, so no activity
is ever blocked by Ollama being off.
"""
from __future__ import annotations

import random
from dataclasses import asdict

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.profiles.constants import Skill
from apps.profiles.services import record_practice

from .models import ACTIVITY_SKILL, DRILL_SKILLS, ActivityType, Passage, SkillAttempt
from .similarity import Comparison, compare, estimate_level, split_sentences, tokenize

# How far a single attempt can move a skill score before the profile's own
# damping is applied. Full marks is worth noticeably less than a bad attempt
# costs, because confidently wrong is more informative than confidently right.
MAX_GAIN = 12.0
MAX_LOSS = -15.0


def accuracy_to_delta(accuracy: float) -> float:
    """Map 0..1 accuracy onto a score change.

    Centred at 0.7: below that the learner is losing ground on this material,
    above it they are gaining. A flat linear map from 0..1 would mean a
    perfectly reasonable 65% still counted as progress.
    """
    pivot = 0.7
    if accuracy >= pivot:
        return MAX_GAIN * (accuracy - pivot) / (1 - pivot)
    return MAX_LOSS * (pivot - accuracy) / pivot


def _serialize(comparison: Comparison) -> dict:
    return {
        "accuracy": comparison.accuracy,
        "percentage": comparison.percentage,
        "summary": comparison.summary(),
        "is_perfect": comparison.is_perfect,
        "expected_words": comparison.expected_words,
        "correct_words": comparison.correct_words,
        "tokens": [asdict(token) for token in comparison.tokens],
    }


def record(
    user,
    *,
    activity: str,
    prompt: str = "",
    response: str = "",
    accuracy: float | None = None,
    detail: dict | None = None,
    passage: Passage | None = None,
    duration_ms: int = 0,
    skills: tuple[str, ...] | None = None,
) -> SkillAttempt:
    """Persist an attempt and move the relevant skill score(s).

    `skills` overrides the default mapping, which the drill uses to credit
    listening, speaking and writing from a single attempt.
    """
    targets = skills or (ACTIVITY_SKILL.get(activity, Skill.VOCABULARY),)
    delta = accuracy_to_delta(accuracy) if accuracy is not None else 0.0

    attempt = SkillAttempt.objects.create(
        user=user,
        activity=activity,
        skill=targets[0],
        passage=passage,
        prompt=prompt,
        response=response,
        accuracy=accuracy,
        score_delta=delta,
        duration_ms=duration_ms,
        detail=detail or {},
    )

    if accuracy is not None:
        for skill in targets:
            record_practice(user, skill, delta)

    return attempt


# --- Listening: dictation --------------------------------------------------
def check_dictation(user, *, expected: str, written: str, passage=None, duration_ms=0) -> SkillAttempt:
    """The learner heard a sentence and typed it. Score the words, not the commas."""
    comparison = compare(expected, written)
    return record(
        user,
        activity=ActivityType.DICTATION,
        prompt=expected,
        response=written,
        accuracy=comparison.accuracy,
        detail=_serialize(comparison),
        passage=passage,
        duration_ms=duration_ms,
    )


# --- Pronunciation: shadowing ----------------------------------------------
def check_shadowing(user, *, expected: str, transcript: str, passage=None, duration_ms=0) -> SkillAttempt:
    """The learner repeated a sentence aloud; the browser transcribed it.

    Important honesty constraint (master prompt section 15): this measures what
    the speech recogniser *heard*, which is a proxy for intelligibility, not a
    phonetic assessment. The detail payload says so explicitly and the UI
    repeats it, because presenting this as a pronunciation score would be a
    false claim about what the software can do.
    """
    comparison = compare(expected, transcript)
    detail = _serialize(comparison)
    detail["measurement"] = "speech-recognition-agreement"
    detail["caveat"] = (
        "This is an estimate. It reflects how much of your speech the browser "
        "recognised, not a phonetic analysis, and accents affect it."
    )
    return record(
        user,
        activity=ActivityType.SHADOWING,
        prompt=expected,
        response=transcript,
        accuracy=comparison.accuracy,
        detail=detail,
        passage=passage,
        duration_ms=duration_ms,
    )


# --- Writing ---------------------------------------------------------------
# Rule-based checks used when the local model is unavailable. Not a grammar
# checker: they catch structural problems a learner can act on without AI.
def basic_writing_checks(text: str, *, minimum_words: int = 30) -> list[dict]:
    issues: list[dict] = []
    words = tokenize(text, expand_contractions=False)
    sentences = split_sentences(text)

    if len(words) < minimum_words:
        issues.append(
            {
                "category": "length",
                "explanation": (
                    f"You wrote {len(words)} words. Aim for at least {minimum_words} "
                    "so there is enough to give you useful feedback on."
                ),
            }
        )

    if sentences:
        longest = max(sentences, key=lambda s: len(s.split()))
        if len(longest.split()) > 40:
            issues.append(
                {
                    "category": "sentence_structure",
                    "original": longest[:120],
                    "explanation": "This sentence runs very long. Splitting it in two usually reads better.",
                }
            )

        lengths = [len(s.split()) for s in sentences]
        if len(sentences) >= 3 and max(lengths) - min(lengths) <= 2:
            issues.append(
                {
                    "category": "sentence_structure",
                    "explanation": "Your sentences are all a similar length. Varying them makes writing sound more natural.",
                }
            )

    if text and text == text.lower():
        issues.append(
            {
                "category": "spelling",
                "explanation": "Nothing is capitalised. Sentences and the word 'I' need capital letters.",
            }
        )

    return issues


def evaluate_writing(
    user,
    *,
    text: str,
    task: str = "",
    level: str = "",
    duration_ms: int = 0,
    targets: list[str] | None = None,
) -> SkillAttempt:
    """Evaluate a piece of writing, with AI when available.

    Accuracy is intentionally left unscored (None) when only the rule-based path
    ran: rule checks cannot judge whether writing is *good*, and inventing a
    number from them would push the learner's writing score around on no
    evidence.
    """
    from apps.ai.providers.base import AIError
    from apps.ai.registry import get_ai_provider

    # The learner's writing level, not a fixed B1: feedback pitched at the
    # wrong level either drowns a beginner or flatters an advanced writer.
    if not level:
        from apps.profiles.models import LearnerProfile, SkillProgress

        progress = SkillProgress.objects.filter(user=user, skill="writing").first()
        level = progress.level if progress else LearnerProfile.objects.get(user=user).overall_level
    detail: dict = {"source": "rules", "issues": basic_writing_checks(text)}
    accuracy = None

    try:
        feedback = get_ai_provider().evaluate_writing(text, level=level, task=task)
        detail = {
            "source": "ai",
            "estimated_level": feedback.get("estimated_level", ""),
            "strengths": feedback.get("strengths", []),
            "issues": feedback.get("issues", []),
            "natural_version": feedback.get("natural_version", ""),
            "practice_prompt": feedback.get("practice_prompt", ""),
            # Keep the rule findings: they catch structural things the model
            # tends to overlook, like every sentence being the same length.
            "structural_notes": basic_writing_checks(text),
        }
        # Fewer issues per 100 words means better writing. Capped so that a
        # single short flawless paragraph does not imply mastery.
        word_count = max(1, len(tokenize(text, expand_contractions=False)))
        issues_per_100 = len(detail["issues"]) * 100 / word_count
        accuracy = max(0.0, min(1.0, 1 - issues_per_100 / 12))
    except AIError as exc:
        detail["ai_unavailable"] = str(exc)

    if targets:
        from apps.skills.writing_support import used_items

        used = used_items(text, targets)
        detail["targets"] = {
            "used": used,
            "missing": [item for item in targets if item not in used],
        }

    attempt = record(
        user,
        activity=ActivityType.WRITING,
        prompt=task,
        response=text,
        accuracy=accuracy,
        detail=detail,
        duration_ms=duration_ms,
    )

    # Every correction the system produces goes through the mistake bank, so
    # one-off notes accumulate into a picture of what this learner keeps
    # getting wrong. Imported here to keep skills independent of mistakes.
    from apps.mistakes.services import record_from_feedback

    record_from_feedback(
        user,
        detail.get("issues", []),
        origin="writing",
        context=text[:500],
    )
    return attempt


# --- Reading ---------------------------------------------------------------
def record_reading(user, *, passage: Passage, seconds: int, comprehension: float | None = None) -> SkillAttempt:
    """Log a completed read, with words-per-minute and optional comprehension.

    Speed alone is not comprehension, so when no comprehension score is given
    the attempt is recorded but the reading score is left untouched. Counting
    "I scrolled past this quickly" as progress would be exactly the
    activity-versus-improvement confusion the product is meant to avoid.
    """
    minutes = max(seconds, 1) / 60
    wpm = round(passage.word_count / minutes)
    return record(
        user,
        activity=ActivityType.READING,
        prompt=passage.title,
        accuracy=comprehension,
        detail={"words_per_minute": wpm, "word_count": passage.word_count, "seconds": seconds},
        passage=passage,
        duration_ms=seconds * 1000,
    )


# --- Listen, speak, write drill (master prompt section 14) ------------------
DRILL_STEPS = ("listen", "repeat", "write", "change", "personalise")


def drill_sentence(user, *, level: str = "", rng: random.Random | None = None) -> dict:
    """Pick one sentence for the Listen-Speak-Write drill.

    Prefers sentences from the learner's own vocabulary examples, so the drill
    reinforces material they are already scheduled to review, and falls back to
    passages at their level.
    """
    rng = rng or random.Random()
    from apps.vocabulary.models import ExampleSentence

    examples = list(
        ExampleSentence.objects.filter(
            expression__learner_progress__user=user
        ).select_related("expression")[:60]
    )
    if examples:
        example = rng.choice(examples)
        return {
            "sentence": example.text,
            "source": "vocabulary",
            "expression": example.expression.text,
            "meaning": example.expression.meaning,
            "steps": list(DRILL_STEPS),
        }

    passages = Passage.objects.filter(Q(owner=user) | Q(owner__isnull=True))
    if level:
        passages = passages.filter(level=level)
    passage = passages.order_by("?").first()
    sentences = passage.sentences() if passage else []
    if not sentences:
        return {
            "sentence": "I did not realise how difficult it would be.",
            "source": "fallback",
            "expression": "",
            "meaning": "",
            "steps": list(DRILL_STEPS),
        }
    return {
        "sentence": rng.choice(sentences),
        "source": "passage",
        "passage_id": passage.id,
        "expression": "",
        "meaning": "",
        "steps": list(DRILL_STEPS),
    }


def check_drill(
    user, *, sentence: str, spoken: str = "", written: str = "", variation: str = "", duration_ms: int = 0
) -> SkillAttempt:
    """Score one pass through the drill.

    Listening (what they typed), speaking (what was recognised) and writing
    (their own variation) are scored together, because the whole point of the
    exercise is that they are the same sentence seen from three sides.
    """
    written_result = compare(sentence, written) if written else None
    spoken_result = compare(sentence, spoken) if spoken else None

    scores = [r.accuracy for r in (written_result, spoken_result) if r is not None]
    accuracy = sum(scores) / len(scores) if scores else None

    detail = {
        "sentence": sentence,
        "written": _serialize(written_result) if written_result else None,
        "spoken": _serialize(spoken_result) if spoken_result else None,
        "variation": variation,
        # A learner who changed the sentence and kept it grammatical has done
        # the productive half of the exercise; length is a crude but honest
        # proxy for "they actually wrote something".
        "variation_words": len(tokenize(variation)) if variation else 0,
    }
    if spoken_result is not None:
        detail["caveat"] = (
            "Speaking accuracy is an estimate from browser speech recognition, "
            "not a phonetic analysis."
        )

    credited = DRILL_SKILLS if spoken else (Skill.LISTENING, Skill.WRITING)
    return record(
        user,
        activity=ActivityType.DRILL,
        prompt=sentence,
        response=written or spoken,
        accuracy=accuracy,
        detail=detail,
        duration_ms=duration_ms,
        skills=credited,
    )


# --- Analytics -------------------------------------------------------------
def skill_summary(user, days: int = 30) -> dict:
    """Recent activity per skill, for the progress view."""
    since = timezone.now() - timezone.timedelta(days=days)
    rows = (
        SkillAttempt.objects.filter(user=user, created_at__gte=since)
        .values("skill")
        .annotate(attempts=Count("id"), mean_accuracy=Avg("accuracy"))
    )
    return {
        row["skill"]: {
            "attempts": row["attempts"],
            "mean_accuracy": round(row["mean_accuracy"], 3) if row["mean_accuracy"] else None,
        }
        for row in rows
    }


def create_passage(user, *, title: str, text: str, level: str = "", topic: str = "") -> Passage:
    """Store text the learner pasted in. Private to them."""
    return Passage.objects.create(
        title=title or (text.strip().split("\n")[0][:80] or "Untitled"),
        text=text,
        level=level or estimate_level(text),
        topic=topic,
        source=Passage.Source.LEARNER,
        owner=user,
    )


def speaking_model_answer(*, prompt: str, level: str, expressions: list[str], moves: list[str]) -> dict:
    """One worked answer to a speaking prompt, for the learner to adapt.

    This is the one part of the speaking scaffolding that goes to a model. The
    frames and functional language are fixed sets that a model would only
    paraphrase, but a model *answer* has to be about the actual prompt, so
    there is nothing to look it up in.

    Cached on the prompt and level, so a given prompt costs one call ever --
    and every learner who meets it afterwards pays nothing. That is what keeps
    a per-prompt generation inside the project's zero-recurring-cost rule.

    Falls back to a labelled skeleton rather than an invented answer. Writing
    one without a model would mean something generic enough to fit any prompt,
    which is exactly the "too generic" failure this exists to fix.
    """
    from apps.ai import prompts as ai_prompts
    from apps.ai.providers.base import TIER_MEDIUM, AIError
    from apps.ai.registry import get_ai_provider
    from apps.ai.services import cached
    from apps.skills.speaking_support import fallback_answer

    if not prompt:
        return fallback_answer(prompt=prompt, level=level)

    try:
        provider = get_ai_provider()
        data = cached(
            "speaking_model_answer",
            {"prompt": prompt, "level": level, "expressions": sorted(expressions)},
            lambda: provider.generate_json(
                ai_prompts.speaking_model_answer(
                    prompt=prompt, level=level, expressions=expressions, moves=moves
                ),
                schema=ai_prompts.MODEL_ANSWER_SCHEMA,
                tier=TIER_MEDIUM,
                temperature=0.7,
            ),
        )
    except AIError:
        return fallback_answer(prompt=prompt, level=level)

    answer = str(data.get("answer") or "").strip()
    if not answer:
        return fallback_answer(prompt=prompt, level=level)

    notes = []
    for note in data.get("notes") or []:
        if not isinstance(note, dict):
            continue
        quote = str(note.get("quote") or "").strip()
        why = str(note.get("why") or "").strip()
        if quote and why:
            notes.append({"quote": quote[:120], "why": why[:240]})

    glossed = []
    for item in data.get("expressions") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        meaning = str(item.get("meaning") or "").strip()
        if text and meaning:
            glossed.append(
                {
                    "text": text[:120],
                    "meaning": meaning[:240],
                    "example": str(item.get("example") or "").strip()[:200],
                }
            )

    return {
        "answer": answer,
        "notes": notes[:4],
        "expressions": glossed,
        "is_skeleton": False,
    }
