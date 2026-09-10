"""Conversation tutor: talk first, feedback afterwards.

The central pedagogical rule (master prompt section 13/21) is that corrections
do not interrupt the conversation. Being stopped every sentence destroys
fluency practice, which is the whole point of the activity. So `reply()` never
corrects, and all correction happens in `generate_feedback()` once the learner
has finished.
"""
from __future__ import annotations

from apps.ai import prompts
from apps.ai.providers.base import TIER_LARGE, TIER_MEDIUM, AIError, AIUnavailable
from apps.ai.registry import get_ai_provider
from apps.profiles.constants import Skill
from apps.profiles.models import SkillProgress
from apps.profiles.services import record_practice

from .models import ConversationMessage, ConversationSession

# How many turns of history to send. Enough for the model to stay coherent,
# short enough to keep a small local model fast and inside its context window.
HISTORY_TURNS = 12

# Openers used when the model is unavailable, so a conversation can still start.
# Each is a real question that invites more than a yes or no.
FALLBACK_OPENERS = {
    "casual": "Hey! I haven't seen you in ages. What have you been up to?",
    "job_interview": "Thanks for coming in. So, tell me a bit about yourself.",
    "restaurant": "Hi there, are you ready to order, or do you need another minute?",
    "hotel": "Good evening! Do you have a reservation with us?",
    "shopping": "Hi, are you looking for anything in particular today?",
    "travel": "Morning. Where are you heading today?",
    "workplace": "Morning! Did you get a chance to look at that email I sent?",
    "phone_call": "Thanks for calling, you're speaking with Sam. How can I help?",
    "doctor": "Come in, take a seat. What seems to be the problem?",
    "customer_service": "Thanks for holding. Can you tell me what happened?",
    "small_talk": "Morning! Looks like we're a bit early. Busy week for you?",
    "debate": "So you think that's the right call? I'm not so sure. Convince me.",
    "presentation": "Thanks, that was interesting. Can I ask about your first point?",
}


def _speaking_level(user) -> str:
    """Pitch the conversation at the learner's speaking level, not their best."""
    progress = SkillProgress.objects.filter(user=user, skill=Skill.SPEAKING).first()
    return progress.level if progress else "B1"


# Matches the speaking-script rotation.
SCENARIO_WINDOW = 12


def next_scenario(user) -> str:
    """The situation this learner has gone longest without practising.

    Replaces defaulting to "casual" every time, which meant the same
    conversation for anyone who did not go looking through the dropdown.
    """
    from apps.ai.prompts import SCENARIO_HINTS

    available = list(SCENARIO_HINTS)
    if not available:
        return "casual"

    recent = list(
        ConversationSession.objects.filter(user=user)
        .order_by("-started_at")
        .values_list("scenario", flat=True)[:SCENARIO_WINDOW]
    )
    unused = [scenario for scenario in available if scenario not in recent]
    if unused:
        return unused[0]
    return max(available, key=lambda scenario: recent.index(scenario))


def start(user, *, scenario: str = "", level: str = "") -> ConversationSession:
    """Open a session and have the partner speak first.

    The partner opens deliberately: facing an empty box is the hardest moment
    in speaking practice, and a concrete question to answer removes it.
    """
    session = ConversationSession.objects.create(
        user=user,
        scenario=scenario or next_scenario(user),
        level=level or _speaking_level(user),
    )

    opener = FALLBACK_OPENERS.get(session.scenario, FALLBACK_OPENERS["casual"])
    try:
        system = prompts.conversation_system(scenario=session.scenario, level=session.level)
        generated = get_ai_provider().chat(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": "Start the conversation with one short line, in character.",
                },
            ],
            tier=TIER_MEDIUM,
        )
        if generated.text.strip():
            opener = generated.text.strip()
    except AIError:
        pass  # The scripted opener is a perfectly good conversation starter.

    ConversationMessage.objects.create(
        session=session, role=ConversationMessage.Role.PARTNER, content=opener
    )
    return session


def _history(session: ConversationSession) -> list[dict]:
    messages = list(session.messages.all())[-HISTORY_TURNS:]
    return [
        {
            "role": "user" if message.role == ConversationMessage.Role.LEARNER else "assistant",
            "content": message.content,
        }
        for message in messages
    ]


def reply(session: ConversationSession, text: str) -> ConversationMessage:
    """Record the learner's turn and answer it, in character and uncorrected."""
    ConversationMessage.objects.create(
        session=session, role=ConversationMessage.Role.LEARNER, content=text
    )

    system = prompts.conversation_system(scenario=session.scenario, level=session.level)
    result = get_ai_provider().chat(
        [{"role": "system", "content": system}, *_history(session)], tier=TIER_MEDIUM
    )
    content = result.text.strip()
    if not content:
        raise AIUnavailable("The conversation partner did not respond. Try sending that again.")

    return ConversationMessage.objects.create(
        session=session, role=ConversationMessage.Role.PARTNER, content=content
    )


def generate_feedback(session: ConversationSession) -> dict:
    """Review the learner's turns once the conversation is over.

    Only the learner's own turns are analysed. Sending the partner's replies too
    would invite the model to critique its own output, which is noise.
    """
    turns = session.learner_turns
    if not turns:
        return {
            "summary": "You ended the conversation before saying anything, so there is nothing to review yet.",
            "did_well": [],
            "corrections": [],
            "useful_expressions": [],
            "focus_next_time": "Try answering the opening question, even in one short sentence.",
            "available": True,
        }

    try:
        feedback = get_ai_provider().generate_json(
            prompts.conversation_feedback(turns, scenario=session.scenario, level=session.level),
            schema=prompts.CONVERSATION_FEEDBACK_SCHEMA,
            # Large tier: the review feeds the mistake bank, so vagueness here
            # is expensive. The conversation turns themselves stay on medium —
            # they are the high-volume part and precision matters far less.
            tier=TIER_LARGE,
            temperature=0.4,
        )
        feedback["available"] = True
    except AIError as exc:
        # A conversation that happened is still worth crediting, and the learner
        # should be told why the review is missing rather than shown an error.
        feedback = {
            "summary": f"You spoke {len(turns)} times. The review could not run this time.",
            "did_well": [],
            "corrections": [],
            "useful_expressions": [],
            "focus_next_time": "",
            "available": False,
            "error": str(exc),
        }

    session.feedback = feedback
    session.save(update_fields=["feedback"])

    from apps.mistakes.services import record_from_feedback

    record_from_feedback(
        session.user,
        feedback.get("corrections", []),
        origin="conversation",
        context=" ".join(turns)[:500],
    )
    return feedback


def end(session: ConversationSession) -> dict:
    """Close the session, credit the practice, and produce the review.

    Scoring is based on how much the learner actually said. Fluency is built by
    producing language, and a conversation of ten real turns is worth more than
    two. It is deliberately generous: this is participation credit, not an
    assessment of correctness, which the feedback covers separately.
    """
    session.end()
    feedback = generate_feedback(session)

    turns = session.learner_turns
    if turns:
        words = sum(len(turn.split()) for turn in turns)
        # Roughly: a short exchange is neutral, a substantial one is progress.
        delta = min(10.0, len(turns) * 0.8 + words / 40)
        record_practice(session.user, Skill.SPEAKING, delta)
        record_practice(session.user, Skill.FLUENCY, delta)

    return feedback
