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

# Where a learner actually meets each pattern, so the frame is tied to a real
# moment rather than to an exercise.
SITUATIONS: dict[str, str] = {
    "describe": "Use this pattern when someone asks what something is like — your job, your routine, "
                "your town — at work small talk, in an interview, or meeting new people.",
    "narrate": "Use this pattern when you tell someone what happened — a weekend, a problem at work, "
               "a trip — the most common long turn in everyday conversation.",
    "opinion": "Use this pattern when someone asks what you think — in meetings, discussions with "
               "friends, or speaking exams. Say your view first, then support it.",
    "compare": "Use this pattern when you weigh two options — choosing a place, a product, a way of "
               "doing things — and need to explain which you'd pick.",
    "explain": "Use this pattern when you tell someone how something works or how to do it — giving "
               "directions, training a colleague, explaining a process.",
}

# How and when to use each functional phrase, in plain words.
PHRASE_NOTES: dict[str, str] = {
    "Well, ...": "A soft start that gives you a second to think. Very natural before any answer.",
    "For me, ...": "Shows you're giving your own experience, not a fact about everyone.",
    "I'd say ...": "A relaxed way to give an answer or estimate without sounding too certain.",
    "Off the top of my head, ...": "Means 'without thinking carefully first' — good for quick, honest answers.",
    "The main thing is ...": "Puts the most important point first, so the listener knows what matters.",
    "To be honest, ...": "Signals a sincere or slightly surprising answer. Don't use it in every sentence.",
    "I suppose the honest answer is ...": "Thoughtful opening before an answer that isn't simple.",
    "It depends, but broadly ...": "Admits there are exceptions, then gives the general answer.",
    "First, ...": "Starts the first step. Pause slightly after it.",
    "Then ...": "Moves to the next step. Unstressed and quick in speech.",
    "After that, ...": "Like 'then', but gives you a moment to think of the next step.",
    "Finally, ...": "Tells the listener this is the last step.",
    "To start with, ...": "A more natural spoken 'first' — for the beginning of a sequence or story.",
    "Once that's done, ...": "Means 'after finishing that step' — great for routines and processes.",
    "By the end, ...": "Jumps to the result or last part of a story or day.",
    "Early on, ...": "Refers to the beginning of a period or story.",
    "From there, ...": "Moves the story or process forward from the last point.",
    "Eventually, ...": "After a long time or several steps — often with a result.",
    "For example, ...": "Introduces one specific case that proves your point.",
    "Like when ...": "Casual way to start a short example from your life.",
    "A good example is ...": "Introduces a clear, chosen example.",
    "Say, for instance, ...": "Offers an example as a possibility — 'imagine this case'.",
    "A case in point would be ...": "A precise example that proves exactly what you said.",
    "To give you a sense of it, ...": "Introduces a detail that helps the listener picture it.",
    "because ...": "Gives the reason. Keep the part after it short when speaking.",
    "so ...": "Gives the result: cause, so result.",
    "The reason is ...": "Puts the reason in focus — say it, pause, then explain.",
    "which means ...": "Adds the consequence of what you just said, in one breath.",
    "largely because ...": "The main reason, while suggesting there are others.",
    "which is partly why ...": "Links a fact to one of the reasons for a result.",
    "But ...": "Introduces a contrast. Simple and completely natural in speech.",
    "On the other hand, ...": "Presents the opposite side of the same question.",
    "That said, ...": "Means 'even so' — adds a point that limits what you just said.",
    "Whereas ...": "Directly contrasts two things in one sentence.",
    "Having said that, ...": "Like 'that said', slightly more careful and formal.",
    "If anything, ...": "Suggests the truth is actually the opposite, or even stronger.",
    "So that's about it.": "Clearly tells the listener you've finished.",
    "That's my day, really.": "Casual ending for describing a routine.",
    "So on the whole, ...": "Sums up everything into one general conclusion.",
    "That's roughly how it goes.": "Ends a description of a routine or process.",
    "So all things considered, ...": "Conclusion after weighing different points.",
    "That's the short version, anyway.": "Ends a long answer and admits there's more to say.",
}

# Conjunctions and linkers that join ideas into longer turns, per task and level.
_C = lambda word, use, example: {"word": word, "use": use, "example": example}  # noqa: E731
CONNECTORS: dict[str, dict[str, list[dict]]] = {
    "describe": {
        "low": [
            _C("and", "adds another fact to the same sentence", "I get up at seven and I have a quick breakfast."),
            _C("but", "adds a contrast", "It's a small town, but it has a great market."),
            _C("because", "gives a reason", "I take the bus because it's cheaper."),
            _C("when", "says at what time something happens", "When I get home, I cook dinner."),
        ],
        "mid": [
            _C("while", "two things happening at the same time", "I listen to podcasts while I'm cooking."),
            _C("which", "adds information about the thing you just mentioned", "I work in an office, which is ten minutes from home."),
            _C("although", "a contrast inside one sentence", "Although it's busy, I really enjoy it."),
            _C("so", "a result", "The traffic is bad, so I usually leave early."),
            _C("as soon as", "immediately after", "As soon as I arrive, I check my emails."),
        ],
        "high": [
            _C("whereas", "contrasts two parts of the description", "Mornings are hectic, whereas evenings are fairly calm."),
            _C("which is why", "links a fact to its result", "It's near the station, which is why I chose it."),
            _C("even though", "strong contrast", "Even though it's small, it never feels crowded."),
            _C("not to mention", "adds an extra, stronger point", "It's convenient, not to mention cheap."),
        ],
    },
    "narrate": {
        "low": [
            _C("and then", "moves the story to the next event", "I missed the bus, and then it started to rain."),
            _C("when", "the moment something happened", "When I got there, the shop was closed."),
            _C("so", "the result of an event", "I was late, so I took a taxi."),
            _C("because", "why something happened", "I was tired because I didn't sleep well."),
        ],
        "mid": [
            _C("while", "something happened during another action", "While I was waiting, my phone died."),
            _C("as soon as", "immediately after", "As soon as I saw her, I knew something was wrong."),
            _C("before / after", "the order of two events", "Before I left, I checked the address twice."),
            _C("although", "a surprising contrast", "Although we were late, they still let us in."),
            _C("in the end", "the final result after a problem", "In the end, we found a different place."),
        ],
        "high": [
            _C("by the time", "one event was already finished when another happened", "By the time we arrived, everyone had left."),
            _C("which meant (that)", "the consequence of an event", "The train was cancelled, which meant I had to drive."),
            _C("no sooner ... than", "one thing happened right after another", "No sooner had I sat down than the phone rang."),
            _C("it turned out (that)", "a surprising discovery", "It turned out that I'd gone to the wrong station."),
        ],
    },
    "opinion": {
        "low": [
            _C("because", "gives the reason for your view", "I prefer trains because they're relaxing."),
            _C("but", "the other side", "It's expensive, but it's worth it."),
            _C("so", "your conclusion", "It saves time, so I think it's better."),
            _C("also", "adds another reason", "It's also better for the environment."),
        ],
        "mid": [
            _C("although", "admits a point against your view", "Although it costs more, I think it's worth it."),
            _C("as long as", "a condition for your view", "It's fine as long as you don't do it every day."),
            _C("on top of that", "adds a second reason", "On top of that, it's much quicker."),
            _C("that's why", "links reasons to your opinion", "That's why I'd always choose it."),
            _C("whereas", "contrasts two views or options", "Some people love it, whereas I find it stressful."),
        ],
        "high": [
            _C("even if", "your view stays true in a difficult case", "Even if it were cheaper, I wouldn't choose it."),
            _C("provided that", "a formal condition", "It works well, provided that people follow the rules."),
            _C("given that", "a known fact supporting your view", "Given that most people work from home, it makes sense."),
            _C("which is not to say", "limits your point to avoid overstatement", "Which is not to say it's perfect."),
        ],
    },
    "compare": {
        "low": [
            _C("but", "a difference", "The city is exciting, but the country is quiet."),
            _C("and", "a similarity", "Both are cheap and easy to find."),
            _C("more ... than", "comparing one quality", "The train is more comfortable than the bus."),
            _C("because", "why you prefer one", "I like the first one because it's closer."),
        ],
        "mid": [
            _C("whereas", "contrasts the two directly", "Cafés are noisy, whereas libraries are quiet."),
            _C("while", "contrast (like whereas)", "While one is cheap, the other is faster."),
            _C("both ... and", "what they share", "Both the gym and the park are close by."),
            _C("unlike", "a difference with a noun", "Unlike the bus, the train is always on time."),
            _C("so overall", "your final choice", "So overall, I'd go for the train."),
        ],
        "high": [
            _C("in contrast", "a strong difference at the start of a sentence", "In contrast, the second option is flexible."),
            _C("by comparison", "shows how one looks next to the other", "By comparison, the old system was slow."),
            _C("the former / the latter", "refers back to the first / second option", "The latter is cheaper, but the former lasts longer."),
            _C("on balance", "the conclusion after weighing both", "On balance, I'd choose the first."),
        ],
    },
    "explain": {
        "low": [
            _C("first / then", "the order of steps", "First you open the app, then you choose a seat."),
            _C("and", "joins two actions in one step", "You press the button and wait."),
            _C("if", "a condition", "If it doesn't work, try again."),
            _C("so", "the result of a step", "It saves your card, so it's quicker next time."),
        ],
        "mid": [
            _C("once", "after completing a step", "Once you've paid, you'll get a code."),
            _C("unless", "except if", "It won't start unless you plug it in."),
            _C("so that", "the purpose of a step", "Save it first so that you don't lose it."),
            _C("which", "adds information about a step", "You get a code, which you show at the door."),
            _C("otherwise", "what happens if you don't", "Keep the receipt, otherwise you can't return it."),
        ],
        "high": [
            _C("the idea being that", "the purpose behind a design", "It checks twice, the idea being that errors are caught early."),
            _C("in which case", "what to do in a specific situation", "It might freeze, in which case just restart it."),
            _C("as a result", "the effect of the process", "As a result, the whole thing takes minutes."),
            _C("assuming (that)", "a condition you expect is true", "Assuming you have the app, it's very simple."),
        ],
    },
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

    for step in frame:
        step["phrase_notes"] = [
            {"phrase": phrase, "use": PHRASE_NOTES.get(phrase, "")} for phrase in step["phrases"]
        ]

    return {
        "task": task,
        "level": (level or "B1").upper(),
        "situation": SITUATIONS[task],
        "pattern": " → ".join(step["move"] for step in FRAMES[task]),
        "frame": frame,
        "connectors": CONNECTORS[task][band],
        # Always offered: running out of words mid-answer is the moment a
        # learner gives up, and the fix is a phrase, not more vocabulary.
        "stalling_phrases": PHRASES["buy_time"][band],
        "target_expressions": list(expressions or []),
    }


# Connectives a learner has by A2. Their dictionary entries are actively
# misleading here -- "then: that time" is the noun sense and nothing to do with
# sequencing -- so they get a usage note instead of a definition.
USAGE_NOTES = {
    "first": "Opens the first step. Say it, then pause slightly before the step itself.",
    "firstly": "Same as 'first', slightly more formal. Fine in a presentation, stiff in conversation.",
    "then": "Joins one step to the next. Unstressed in speech — it almost disappears.",
    "after that": "Like 'then', but buys you a moment to think. Useful when you need one.",
    "next": "Moves to the following step. Interchangeable with 'then' in most answers.",
    "finally": "Signals the last step, so the listener knows you are finishing.",
    "in the end": "Not the same as 'finally' — this one means after some difficulty.",
    "also": "Adds something related. Put it after the subject: 'I also...', not 'Also I...'.",
    "however": "Written English. In speech, 'but' or 'that said' sounds far more natural.",
    "so": "Introduces a result, and in speech also just fills a gap while you think.",
    "because": "Gives the reason. In speech the clause after it is usually short.",
}


def usage_note(expression: str) -> str:
    """A note on how to use this, for words a definition would not help with."""
    return USAGE_NOTES.get((expression or "").strip().lower(), "")


def fallback_answer(*, prompt: str, level: str, task: str | None = None) -> dict:
    """A skeleton to fill in, for when the model is unavailable.

    Deliberately not a fake answer. Inventing one without a model would mean
    writing something generic enough to fit any prompt, which is precisely the
    failure being fixed. A labelled skeleton is honest about being a scaffold
    and is still usable -- the learner has the moves and the language for each.
    """
    task = task or detect_task(prompt)
    band = _band(level)
    lines = []
    for step in FRAMES[task]:
        opener = PHRASES[step["phrases"]][band][0]
        lines.append(f"{opener} ({step['move'].lower()} — {step['hint']})")
    return {
        "answer": "\n".join(lines),
        "notes": [],
        "is_skeleton": True,
    }
