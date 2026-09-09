"""Prompt templates and the JSON schemas their output must satisfy.

Prompts live here rather than inline in services so they can be reviewed,
diffed and tuned as a unit. Every prompt that requests structured output has a
matching schema in this module, and callers always pass both together.

House style for all learner-facing English (master prompt sections 50-51):
modern, natural, conversational, register-aware. Textbook English is a bug.
"""
from __future__ import annotations

from .providers.base import wrap_untrusted

NATURAL_ENGLISH_RULES = (
    "Write natural, modern, conversational English of the kind people actually say today. "
    "Avoid stiff textbook sentences, avoid over-formal phrasing unless the register calls for it, "
    "and avoid rare vocabulary that does not serve the learning point."
)


# --- Explain an expression -------------------------------------------------
EXPLANATION_SCHEMA = {
    "type": "object",
    "required": ["expression", "meaning", "examples", "register"],
    "properties": {
        "expression": {"type": "string"},
        "meaning": {"type": "string"},
        "register": {"type": "string"},
        "part_of_speech": {"type": "string"},
        "cefr_level": {"type": "string"},
        "examples": {"type": "array", "items": {"type": "string"}},
        "collocations": {"type": "array", "items": {"type": "string"}},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "common_mistake": {"type": "string"},
    },
}


def explain_expression(expression: str, *, level: str = "B1", english_only: bool = False) -> str:
    audience = (
        "Explain in simple English only."
        if english_only
        else "Explain in simple English; the learner may still need short, plain wording."
    )
    return f"""Explain this English expression for a {level} learner.

Expression: {expression}

{audience}
{NATURAL_ENGLISH_RULES}

Return JSON with these keys:
- expression: the expression, in its natural dictionary form
- meaning: one clear sentence
- register: one of formal, neutral, casual, slang, professional, academic
- part_of_speech: e.g. phrasal verb, idiom, collocation, noun
- cefr_level: A1, A2, B1, B2, C1 or C2
- examples: 3 short sentences someone would really say
- collocations: up to 4 words that commonly appear with it
- synonyms: up to 3 natural alternatives
- common_mistake: one mistake learners typically make with it, or an empty string
"""


# --- Vocabulary extraction -------------------------------------------------
VOCABULARY_SCHEMA = {
    "type": "object",
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["expression", "meaning", "example"],
                "properties": {
                    "expression": {"type": "string"},
                    "meaning": {"type": "string"},
                    "example": {"type": "string"},
                    "kind": {"type": "string"},
                    "cefr_level": {"type": "string"},
                    "register": {"type": "string"},
                },
            },
        }
    },
}


def extract_vocabulary(text: str, *, level: str = "B1", limit: int = 8) -> str:
    return f"""From the content below, pick up to {limit} expressions worth teaching a {level} learner.

Strongly prefer multi-word items: phrasal verbs, collocations, idioms, and fixed
expressions. Only include a single word when that word alone is genuinely useful.

{wrap_untrusted(text)}

Return JSON: {{"items": [{{"expression", "meaning", "example", "kind", "cefr_level", "register"}}]}}
where "kind" is one of: word, phrase, idiom, phrasal_verb, collocation, pattern.
The "example" must be a natural sentence, not copied verbatim from the content.
"""


# --- Writing evaluation ----------------------------------------------------
WRITING_FEEDBACK_SCHEMA = {
    "type": "object",
    "required": ["issues", "natural_version", "strengths"],
    "properties": {
        "estimated_level": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "natural_version": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["original", "correction", "explanation", "category"],
                "properties": {
                    "original": {"type": "string"},
                    "correction": {"type": "string"},
                    "explanation": {"type": "string"},
                    "category": {"type": "string"},
                },
            },
        },
        "practice_prompt": {"type": "string"},
    },
}


def evaluate_writing(text: str, *, level: str = "B1", task: str = "") -> str:
    task_line = f"The learner was asked to: {task}\n" if task else ""
    return f"""You are an experienced English teacher giving feedback to a {level} learner.
{task_line}
Learner's writing:
{wrap_untrusted(text)}

Do not silently rewrite their work. Explain every change so they learn from it.
{NATURAL_ENGLISH_RULES}

Return JSON with:
- estimated_level: the CEFR level this writing suggests
- strengths: 1-3 specific things they did well
- issues: each with original (the exact wrong phrase), correction, explanation
  (one sentence, why), and category (one of: grammar, vocabulary, word_choice,
  preposition, article, word_order, naturalness, collocation, spelling)
- natural_version: the whole text rewritten as a native speaker would say it,
  keeping the learner's own meaning and voice
- practice_prompt: one short exercise targeting their most important issue
"""


# --- Summarisation ---------------------------------------------------------
def summarize(text: str, *, level: str = "B1", sentences: int = 3) -> str:
    return f"""Summarise the content below in {sentences} sentences at CEFR {level} level.
{NATURAL_ENGLISH_RULES}
Reply with the summary only, no preamble.

{wrap_untrusted(text)}
"""


# --- Conversation ----------------------------------------------------------
SCENARIO_HINTS = {
    "casual": "a relaxed chat between friends",
    "job_interview": "a job interview; you are the interviewer",
    "restaurant": "ordering at a restaurant; you are the server",
    "hotel": "checking into a hotel; you are the receptionist",
    "shopping": "shopping in a store; you are a shop assistant",
    "travel": "travelling: airports, directions, tickets",
    "workplace": "a workplace conversation with a colleague",
    "phone_call": "a phone call; you cannot see each other",
    "doctor": "a medical appointment; you are the doctor",
    "customer_service": "a customer service call; you are the agent",
    "small_talk": "friendly small talk before a meeting starts",
    "debate": "a friendly debate where you take the opposing view",
    "presentation": "a Q&A after the learner presents something",
}


def conversation_system(*, scenario: str = "casual", level: str = "B1") -> str:
    hint = SCENARIO_HINTS.get(scenario, SCENARIO_HINTS["casual"])
    return f"""You are a friendly native English speaker in this situation: {hint}.

You are talking with a CEFR {level} English learner.
{NATURAL_ENGLISH_RULES}

Rules:
- Stay in character; never mention that you are an AI or a teacher.
- Keep replies to 1-3 sentences, like a real person in a real conversation.
- Do NOT correct the learner's mistakes mid-conversation. Feedback comes later.
- Ask a natural follow-up question most turns so the conversation keeps moving.
- Match their level: be understandable, but do not sound like a textbook.
"""
