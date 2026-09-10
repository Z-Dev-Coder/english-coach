"""What to say, and in what order, before the learner has to say it.

A speaking prompt on its own is not a task a B1 learner can act on. "Walk me
through a typical day" is perfectly clear and still leaves the hardest
questions unanswered: how do I start, what order do I put things in, and which
words do I need. Given only a prompt and a record button, a learner either
freezes or produces three flat sentences -- and neither is practice.

So every speaking task gets scaffolding, in the order it is actually needed:

  phrases  the functional language for this kind of answer, at this level
  frame    the moves a good answer makes, in order, with an example of each
  target   the expressions the lesson wants used

None of it is generated. Functional language for opening, sequencing, giving
examples and closing is a small, stable, well-documented set that a model would
only paraphrase -- less predictably, and at a cost on every speaking step. It
is the same scaffolding a teacher writes on the board, and the point is that it
is the *same* every time: a learner who meets "the thing is..." in four
different lessons starts using it.

The scaffolding is meant to be outgrown. Higher levels get fewer, less
hand-holding phrases, because a C1 speaker being told to say "First..." is
being taught to sound like a textbook.
"""
from __future__ import annotations

import re

# The kind of answer a prompt is asking for. Detected from the prompt itself,
# because the lesson generator writes prompts freely and tagging every one by
# hand would go stale the first time a prompt changed.
TASK_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("narrate", ("tell me about a time", "what happened", "describe a time", "last time",
                 "recently", "yesterday", "what did you do")),
    ("opinion", ("do you think", "what do you think", "agree", "opinion", "prefer",
                 "better", "should", "why do you")),
    ("compare", ("compare", "difference between", "versus", "vs", "or")),
    ("explain", ("how do you", "explain", "how does", "why does", "what is the")),
    ("describe", ("describe", "walk me through", "talk about", "tell me about", "what is your")),
]

# Functional language, by move and by level band. Kept short on purpose: three
# usable phrases get used, twelve get skimmed.
PHRASES: dict[str, dict[str, list[str]]] = {
    "open": {
        "low": ["Well, ...", "For me, ...", "I'd say ..."],
        "mid": ["Off the top of my head, ...", "The main thing is ...", "To be honest, ..."],
        "high": ["I suppose the honest answer is ...", "It depends, but broadly ..."],
    },
    "sequence": {
        "low": ["First, ...", "Then ...", "After that, ...", "Finally, ..."],
        "mid": ["To start with, ...", "Once that's done, ...", "By the end, ..."],
        "high": ["Early on, ...", "From there, ...", "Eventually, ..."],
    },
    "example": {
        "low": ["For example, ...", "Like when ..."],
        "mid": ["A good example is ...", "Say, for instance, ..."],
        "high": ["A case in point would be ...", "To give you a sense of it, ..."],
    },
    "reason": {
        "low": ["because ...", "so ..."],
        "mid": ["The reason is ...", "which means ..."],
        "high": ["largely because ...", "which is partly why ..."],
    },
    "contrast": {
        "low": ["But ...", "On the other hand, ..."],
        "mid": ["That said, ...", "Whereas ..."],
        "high": ["Having said that, ...", "If anything, ..."],
    },
    "close": {
        "low": ["So that's about it.", "That's my day, really."],
        "mid": ["So on the whole, ...", "That's roughly how it goes."],
        "high": ["So all things considered, ...", "That's the short version, anyway."],
    },
    "buy_time": {
        "low": ["Let me think.", "Hmm, good question."],
        "mid": ["That's a good question, actually.", "How can I put this ..."],
        "high": ["I've not thought about that before, but ...", "Let me put it this way ..."],
    },
}

# The moves a good answer of each kind makes, in order. `hint` says what to do;
# `phrases` names which bank to draw the examples from.
FRAMES: dict[str, list[dict]] = {
    "describe": [
        {"move": "Start simply", "hint": "One sentence saying what it is. Don't build up to it.", "phrases": "open"},
        {"move": "Go through it in order", "hint": "Two or three parts, in a sequence a listener can follow.", "phrases": "sequence"},
        {"move": "Add one detail", "hint": "A specific example makes it sound real rather than rehearsed.", "phrases": "example"},
        {"move": "Round it off", "hint": "Signal you've finished, so the other person knows it's their turn.", "phrases": "close"},
    ],
    "narrate": [
        {"move": "Set the scene", "hint": "When it was and where you were. One sentence.", "phrases": "open"},
        {"move": "Tell it in order", "hint": "What happened, step by step. Past tense throughout.", "phrases": "sequence"},
        {"move": "Say why it mattered", "hint": "The point of the story — what it changed or how you felt.", "phrases": "reason"},
        {"move": "Land it", "hint": "Stories need an ending, not just a stop.", "phrases": "close"},
    ],
    "opinion": [
        {"move": "Say what you think", "hint": "Answer first, reasons after. Don't save your view for the end.", "phrases": "open"},
        {"move": "Give your reason", "hint": "One reason, properly explained, beats three listed.", "phrases": "reason"},
        {"move": "Back it up", "hint": "An example from your own life is the strongest thing you have.", "phrases": "example"},
        {"move": "Acknowledge the other side", "hint": "This is what makes an opinion sound considered.", "phrases": "contrast"},
    ],
    "compare": [
        {"move": "Name both", "hint": "Say what you're comparing before you compare it.", "phrases": "open"},
        {"move": "One clear difference", "hint": "Pick the difference that matters most, not the most obvious.", "phrases": "contrast"},
        {"move": "Give an example of each", "hint": "Concrete beats abstract every time.", "phrases": "example"},
        {"move": "Say which you'd pick", "hint": "A comparison without a preference sounds unfinished.", "phrases": "close"},
    ],
    "explain": [
        {"move": "One-line summary", "hint": "If you can't say it in a sentence, start with the rough version.", "phrases": "open"},
        {"move": "Break it into steps", "hint": "Two or three, in order. Explaining is sequencing.", "phrases": "sequence"},
        {"move": "Give an example", "hint": "The example is usually what makes it land.", "phrases": "example"},
        {"move": "Check they followed", "hint": "Real explanations end with a check, not a full stop.", "phrases": "close"},
    ],
}

LOW_LEVELS = {"A1", "A2"}
HIGH_LEVELS = {"C1", "C2"}


def _band(level: str) -> str:
    level = (level or "B1").upper()
    if level in LOW_LEVELS:
        return "low"
    if level in HIGH_LEVELS:
        return "high"
    return "mid"


def detect_task(prompt: str) -> str:
    """Which kind of answer this prompt is asking for.

    Ordered rather than scored: "tell me about a time you..." is a story, not a
    description, and the narrate patterns are checked first so it is read that
    way. Anything unrecognised falls back to describe, which is the most
    generally useful frame.
    """
    text = (prompt or "").lower()
    if not text.strip():
        return "describe"
    for task, patterns in TASK_PATTERNS:
        for pattern in patterns:
            # Word-boundary matching, so "or" in "work" does not make every
            # prompt a comparison.
            if re.search(rf"\b{re.escape(pattern)}\b", text):
                return task
    return "describe"


def build_support(*, prompt: str, level: str = "B1", expressions: list[str] | None = None) -> dict:
    """Everything the learner needs before they open their mouth."""
    task = detect_task(prompt)
    band = _band(level)

    # Higher levels get less scaffolding: a C1 speaker being told to say
    # "First..." is being taught to sound like a textbook.
    per_move = 2 if band == "high" else 3

    frame = [
        {
            "move": step["move"],
            "hint": step["hint"],
            "phrases": PHRASES[step["phrases"]][band][:per_move],
        }
        for step in FRAMES[task]
    ]

    return {
        "task": task,
        "level": (level or "B1").upper(),
        "frame": frame,
        # Always offered: running out of words mid-answer is the moment a
        # learner gives up, and the fix is a phrase, not more vocabulary.
        "stalling_phrases": PHRASES["buy_time"][band],
        "target_expressions": list(expressions or []),
    }
