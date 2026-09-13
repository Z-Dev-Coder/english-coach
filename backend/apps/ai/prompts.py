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


# --- Lesson generation -----------------------------------------------------
LESSON_SCHEMA = {
    "type": "object",
    "required": ["title", "theme", "activities"],
    "properties": {
        "title": {"type": "string"},
        "theme": {"type": "string"},
        "encouragement": {"type": "string"},
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "title", "instructions"],
                "properties": {
                    "kind": {"type": "string"},
                    "title": {"type": "string"},
                    "instructions": {"type": "string"},
                    "prompt": {"type": "string"},
                    "target_expressions": {"type": "array", "items": {"type": "string"}},
                    "passage": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "text": {"type": "string"},
                        },
                    },
                    "questions": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def generate_lesson(context: dict) -> str:
    """Ask for today's lesson, given the learner's actual state.

    The context is assembled from the database by LessonGenerator, never by the
    model: what the learner is weak at and what is due are facts, not something
    to be invented.
    """
    weak = ", ".join(context.get("weak_skills") or []) or "nothing in particular yet"
    mistakes = ", ".join(context.get("recent_mistakes") or []) or "none recorded yet"
    interests = ", ".join(context.get("interests") or []) or "general everyday life"
    blocks = "\n".join(
        f"- {block['skill']}: {block['minutes']} minutes" for block in context.get("plan", [])
    )

    return f"""Design today's English lesson for one specific learner.

LEARNER
Overall level: {context.get('overall_level', 'B1')}
Target level: {context.get('target_level', 'C1')}
Weakest skills: {weak}
Recent mistakes to work on: {mistakes}
Interests: {interests}
Vocabulary due for review today: {context.get('due_count', 0)}
Time available: {context.get('total_minutes', 30)} minutes

TIME ALREADY ALLOCATED (do not change these)
{blocks}

Write ONE activity for each block above, in the same order, using the same
"kind" value as the block's skill. Tie them together with a single theme drawn
from the learner's interests, so the lesson feels like one session rather than
six unrelated exercises.

{NATURAL_ENGLISH_RULES}

Return JSON:
- title: a short, specific name for today's lesson
- theme: the thread connecting the activities, in one sentence
- encouragement: one honest, non-patronising sentence about their progress
- activities: one object per block, each with
    kind (matching the block's skill),
    title (short),
    instructions (what the learner should actually do, 1-2 sentences),
    prompt (the writing/speaking prompt or discussion question, if the activity needs one),
    target_expressions (up to 4 expressions to work in, or an empty list)

For "reading" and "listening" activities, write an ORIGINAL text for the
lesson's theme and put it in `passage`: a `title` and a `text` of 120-200 words,
at the learner's level, using the target expressions naturally. Put 3-5
comprehension questions in `questions`. Do NOT put the text or the questions in
`prompt` -- leave `prompt` empty for these two kinds. If both kinds are in the
plan, write one passage on the reading activity; the listening activity will
use the same text.

For target_expressions, give language that belongs to THIS topic and that a
learner at this level would not already produce unprompted: collocations,
phrasal verbs, idioms and fixed phrases. For a lesson about a daily routine
that means things like "grab a coffee", "get going", "wind down", "have a
lie-in".

Do NOT give connectives or sequencing words -- "first", "then", "after that",
"finally", "also", "however". Learners have those by A2, they carry no topic,
and listing them wastes the four slots that could have taught something.
"""


# --- Conversation feedback -------------------------------------------------
CONVERSATION_FEEDBACK_SCHEMA = {
    "type": "object",
    "required": ["summary", "did_well", "corrections"],
    "properties": {
        "summary": {"type": "string"},
        "estimated_level": {"type": "string"},
        "did_well": {"type": "array", "items": {"type": "string"}},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["original", "natural", "explanation"],
                "properties": {
                    "original": {"type": "string"},
                    "natural": {"type": "string"},
                    "explanation": {"type": "string"},
                    "category": {"type": "string"},
                },
            },
        },
        "useful_expressions": {"type": "array", "items": {"type": "string"}},
        "focus_next_time": {"type": "string"},
    },
}


def conversation_feedback(turns: list[str], *, scenario: str = "casual", level: str = "B1") -> str:
    """Review what the learner said, after the conversation rather than during it.

    Only the learner's own turns are sent: the assistant's replies are not under
    review, and excluding them keeps the model from critiquing its own output.
    """
    said = "\n".join(f"{index + 1}. {turn}" for index, turn in enumerate(turns))
    return f"""You are an English teacher reviewing what a CEFR {level} learner said
during a {scenario.replace('_', ' ')} conversation.

WHAT THE LEARNER SAID
{said}

Judge only their English, not the conversation topic. Be specific and kind:
point at real phrases, not general advice. Do not invent mistakes — if
something was already natural, leave it alone.

{NATURAL_ENGLISH_RULES}

Return JSON:
- summary: one sentence on how the conversation went
- estimated_level: the CEFR level this speech suggests
- did_well: 2-3 specific things they got right, quoting them
- corrections: each with original (their exact words), natural (how a native
  speaker would say it), explanation (one sentence, why), and category (one of:
  grammar, vocabulary, word_choice, preposition, article, word_order,
  naturalness, collocation, fluency)
- useful_expressions: up to 4 expressions that would have fitted this conversation
- focus_next_time: one specific thing to work on
"""


# --- Real-world content ----------------------------------------------------
ARTICLE_MATERIAL_SCHEMA = {
    "type": "object",
    "required": ["adapted_text", "vocabulary", "questions"],
    "properties": {
        "adapted_text": {"type": "string"},
        "level": {"type": "string"},
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["expression", "meaning"],
                "properties": {
                    "expression": {"type": "string"},
                    "meaning": {"type": "string"},
                    "example": {"type": "string"},
                    "kind": {"type": "string"},
                },
            },
        },
        "phrases": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "speaking_prompt": {"type": "string"},
        "writing_prompt": {"type": "string"},
    },
}


def article_material(title: str, summary: str, *, level: str = "B1") -> str:
    """Turn a news summary into learning material.

    The adapted text must be *written*, not copied: we are producing a study aid
    about a story, not redistributing someone's article. The prompt says so
    explicitly, and the source summary is fenced as untrusted content.
    """
    return f"""Create English learning material about this news story for a CEFR {level} learner.

HEADLINE: {title}

{wrap_untrusted(summary)}

Write your OWN short retelling of the story in your own words. Do not copy
sentences from the source. If the summary is too thin to retell, write about the
topic generally rather than inventing specific facts, figures or quotations.

{NATURAL_ENGLISH_RULES}

Return JSON:
- adapted_text: your retelling, 4-6 sentences at {level} level
- level: the CEFR level you actually wrote at
- vocabulary: 4-6 useful expressions from this topic, each with expression,
  meaning, example (your own sentence) and kind (word, phrase, idiom,
  phrasal_verb, collocation)
- phrases: 2-3 natural phrases someone would use when discussing this topic
- questions: 3 comprehension questions about your retelling
- speaking_prompt: one question inviting the learner's own opinion
- writing_prompt: one short writing task connected to the topic
"""


# --- Dialogue study (movies, TV, real conversations) -----------------------
DIALOGUE_SCHEMA = {
    "type": "object",
    "required": ["expressions"],
    "properties": {
        "summary": {"type": "string"},
        "register": {"type": "string"},
        "expressions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["expression", "meaning"],
                "properties": {
                    "expression": {"type": "string"},
                    "meaning": {"type": "string"},
                    "register": {"type": "string"},
                    "literal_trap": {"type": "string"},
                    "example": {"type": "string"},
                    "alternatives": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "roleplay_prompt": {"type": "string"},
    },
}


def dialogue_study(text: str, *, level: str = "B1") -> str:
    """Mine a short dialogue excerpt for natural spoken English.

    Aimed at exactly what makes film and TV dialogue hard: expressions whose
    meaning is nothing like the sum of their words.
    """
    return f"""A CEFR {level} learner is studying this short piece of English dialogue,
from a film, show or real conversation they came across.

{wrap_untrusted(text)}

Focus on the spoken English that a learner would not produce themselves:
idioms, phrasal verbs, fixed expressions, and anything whose meaning is not
obvious from the individual words.

{NATURAL_ENGLISH_RULES}

Return JSON:
- summary: one sentence on what is happening and the tone
- register: the overall register (casual, slang, professional, neutral, formal)
- expressions: 3-6 items, each with expression, meaning, register,
  literal_trap (what a learner might wrongly think it means, or an empty
  string), example (your own sentence) and alternatives (up to 2 other ways to
  say it)
- roleplay_prompt: a short scenario where the learner could use these naturally
"""


# --- Speaking model answer -------------------------------------------------

MODEL_ANSWER_SCHEMA = {
    "type": "object",
    "required": ["answer"],
    "properties": {
        "answer": {"type": "string"},
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["quote", "why"],
                "properties": {
                    "quote": {"type": "string"},
                    "why": {"type": "string"},
                },
            },
        },
        "expressions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "meaning"],
                "properties": {
                    "text": {"type": "string"},
                    "meaning": {"type": "string"},
                    "example": {"type": "string"},
                },
            },
        },
    },
}


def speaking_model_answer(*, prompt: str, level: str, expressions: list[str], moves: list[str]) -> str:
    """Ask for one worked answer the learner can read aloud and then adapt.

    Deliberately a *model*, not a script to memorise, and the instruction says
    so: an answer built from someone else's life is not something a learner can
    reuse, and reciting it teaches nothing about producing their own.
    """
    expression_list = "\n".join(f"- {e}" for e in expressions) or "- (none specified)"
    move_list = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(moves)) or "(no fixed structure)"

    return f"""Write ONE model answer to this speaking prompt, for an English learner at CEFR {level}.

THE PROMPT
{prompt}

THE STRUCTURE THE ANSWER SHOULD FOLLOW
{move_list}

EXPRESSIONS TO WORK IN NATURALLY
{expression_list}

RULES
- Write it as one person speaking out loud, not as an essay. Contractions,
  false starts and everyday phrasing are right; formal written English is not.
- 6 to 10 sentences. Long enough to model a real answer, short enough to say
  in a minute.
- Pitch the vocabulary and grammar at {level}. An answer the learner cannot
  produce is a demonstration of failure, not a model.
- Invent ordinary, unremarkable specifics. A model answer full of drama is
  harder to adapt to a normal life.
- Use every expression above at least once, where it genuinely fits. Do not
  force one in.

{NATURAL_ENGLISH_RULES}

Return JSON:
- answer: the full answer as one string, with line breaks between the moves
- notes: 2-4 objects, each with `quote` (a short phrase lifted verbatim from
  your answer) and `why` (one sentence on what that phrase is doing -- the
  move it performs or the effect it has). These teach the learner what to
  copy, so point at technique, not at vocabulary they can already see.
- expressions: one object per expression above, each with `text` (exactly as
  given), `meaning` (what it means *in the sense this lesson is using*, in one
  short plain sentence a learner at this level would understand) and `example`
  (one short sentence using it, which may be lifted from your answer).

  The meaning matters more than it looks. A dictionary gives the first listed
  sense: asked about "to unwind" it explains separating a ball of yarn, which
  is correct and useless here. Gloss the sense you actually used.
"""


# --- Speaking roleplay script ----------------------------------------------

ROLEPLAY_SCRIPT_SCHEMA = {
    "type": "object",
    "required": ["lines"],
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["speaker", "text"],
                "properties": {
                    "speaker": {"type": "string"},
                    "text": {"type": "string"},
                    "note": {"type": "string"},
                },
            },
        },
    },
}


def speaking_dialogue(*, title: str, setting: str, goal: str, level: str, expressions: list[str]) -> str:
    """Ask for a complete two-person script the learner can read aloud.

    Every "You" line has to be a line they could actually say. A model answer
    written above their level demonstrates failure rather than teaching
    anything, and a script they cannot read aloud is not a script.
    """
    expression_list = "\n".join(f"- {e}" for e in expressions) or "- (none specified)"

    return f"""Write a complete roleplay script for an English learner at CEFR {level} to practise out loud.

THE SITUATION
{setting}

THE LEARNER'S GOAL
{goal}

EXPRESSIONS TO WORK IN NATURALLY
{expression_list}

RULES
- 10 to 14 lines, alternating, starting with Partner.
- Label every line either "Partner" or "You". "You" is the learner.
- Every "You" line must be one this learner could actually say at {level}.
  A line above their level teaches them they cannot do it.
- At least THREE of the "You" turns must be extended answers of 40 to 80 words:
  several sentences that develop a point, give a reason and add a detail. Being
  able to hold the floor is the skill that does not arrive on its own, and a
  script of one-line replies rehearses the opposite of it.
- To earn those long turns, the Partner must ask open questions -- "what's it
  actually like?", "how did you handle that?" -- not questions answerable with
  yes or a single fact. Padding a short answer sounds wrong; being asked
  something open does not.
- Keep some short turns too. A conversation of nothing but speeches is not a
  conversation.
- Real spoken English: contractions, short answers, the odd hesitation. Not
  written dialogue and not a textbook exchange where both sides speak in full
  correct sentences nobody uses.
- The conversation must actually reach the learner's goal by the end, not
  stop halfway.
- Work the expressions into the "You" lines, where they genuinely fit.

{NATURAL_ENGLISH_RULES}

Return JSON:
- lines: the script in order, each with `speaker` ("Partner" or "You"), `text`,
  and optionally `note` -- one short phrase on what that line is *doing*
  (deflecting, buying time, asking for repetition). Put a note only on the two
  or three lines where the technique is worth naming.
"""


# --- Movies & TV scene lessons ---------------------------------------------

SCENE_SCHEMA = {
    "type": "object",
    "required": ["title", "lines", "expressions"],
    "properties": {
        "title": {"type": "string"},
        "genre": {"type": "string"},
        "setting": {"type": "string"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["speaker", "text"],
                "properties": {"speaker": {"type": "string"}, "text": {"type": "string"}},
            },
        },
        "expressions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["expression", "meaning"],
                "properties": {
                    "expression": {"type": "string"},
                    "meaning": {"type": "string"},
                    "literal_trap": {"type": "string"},
                    "example": {"type": "string"},
                },
            },
        },
        "questions": {"type": "array", "items": {"type": "string"}},
    },
}


def scene_lesson(*, level: str, genre: str, avoid_titles: list[str]) -> str:
    """Ask for an ORIGINAL screen-style scene -- never a real script."""
    avoid = "\n".join(f"- {t}" for t in avoid_titles[:20]) or "- (none yet)"
    return f"""Write an ORIGINAL short scene in the style of a {genre} film or TV show, as a
listening and vocabulary lesson for an English learner at CEFR {level}.

Do NOT reproduce or imitate the dialogue of any real film or TV show. Invent the
characters, situation and lines yourself.

RULES
- 9 to 12 lines between 2 or 3 named characters, with a one-sentence `setting`.
- Sound like people on screen: interruptions, short replies, idioms, phrasal
  verbs, and spoken forms learners hear but textbooks avoid.
- Pitch grammar and general vocabulary at {level}; the expressions are the
  stretch.
- Pick 5 to 7 expressions actually used in the lines. For each give `meaning`
  (plain words a {level} learner understands), `literal_trap` (why the words
  mislead, or "" if they don't) and `example` (a new sentence, not from the scene).
- 3 comprehension `questions` about what happens.
- A title that is different from these:
{avoid}

{NATURAL_ENGLISH_RULES}

Return JSON with: title, genre, setting, lines (speaker, text), expressions, questions.
"""


# --- Writing lessons ---------------------------------------------------------

_ITEM = {
    "type": "object",
    "required": ["text", "meaning"],
    "properties": {
        "text": {"type": "string"},
        "meaning": {"type": "string"},
        "example": {"type": "string"},
    },
}

WRITING_LESSON_SCHEMA = {
    "type": "object",
    "required": ["vocabulary", "expressions", "plan", "model_text"],
    "properties": {
        "genre": {"type": "string"},
        "vocabulary": {"type": "array", "items": _ITEM},
        "phrasal_verbs": {"type": "array", "items": _ITEM},
        "expressions": {"type": "array", "items": _ITEM},
        "sentence_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pattern", "example"],
                "properties": {
                    "pattern": {"type": "string"},
                    "use": {"type": "string"},
                    "example": {"type": "string"},
                },
            },
        },
        "plan": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["part", "what_to_write"],
                "properties": {
                    "part": {"type": "string"},
                    "what_to_write": {"type": "string"},
                    "starter": {"type": "string"},
                },
            },
        },
        "model_text": {"type": "string"},
        "style_tips": {"type": "array", "items": {"type": "string"}},
        "word_target": {"type": "integer"},
    },
}


def writing_lesson(*, task: str, level: str) -> str:
    """Ask for the language and structure a learner needs to write this task."""
    return f"""You are an English writing mentor. Prepare a lesson so a learner at CEFR {level}
can write this task well, using language they would not produce on their own.

THE TASK
{task}

Give the language for THIS topic and THIS kind of text -- not general advice.

RULES
- vocabulary: 6 topic words or collocations a {level} learner is ready to learn.
- phrasal_verbs: 3-4 phrasal verbs that fit this topic naturally.
- expressions: 4-5 fixed phrases or idioms suited to this kind of text and its
  register (an email to a colleague and a story to a friend need different ones).
- For each of those three lists give `text`, `meaning` (plain words a {level}
  learner understands) and `example` (a sentence on this topic).
- sentence_patterns: 3 structures worth using here, each with `pattern` (e.g.
  "I was wondering if you could ..."), `use` (when to use it) and `example`.
- plan: 3-5 parts of the text in order, each with `part`, `what_to_write`
  (specific to this task) and `starter` (a sentence opening to begin that part).
- model_text: a model answer at {level}, the right length for the task, that
  uses at least half of the vocabulary, phrasal verbs and expressions above.
- style_tips: 2-3 points about tone, register or layout for this kind of text.
- word_target: a sensible length in words for a {level} learner.
- genre: the kind of text (email, story, opinion, review, message, ...).

{NATURAL_ENGLISH_RULES}

Return JSON with exactly those fields.
"""
