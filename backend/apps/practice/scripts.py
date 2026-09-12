"""Speaking script generation.

Design note: this deliberately has a working template path that needs no AI at
all. The learner should always be able to get a usable practice script, whether
or not Ollama is running, and the portable prompt they hand to ChatGPT/Gemini is
pure string assembly. AI enrichment (`generate_ai_script`) is a bonus layer, not
a dependency.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from apps.ai.prompts import NATURAL_ENGLISH_RULES, SCENARIO_HINTS
from apps.profiles.constants import cefr_index

# Level-appropriate speaking behaviour, used both to shape the built-in scripts
# and to instruct whichever assistant the learner practises with.
LEVEL_GUIDANCE = {
    "A1": {
        "sentence": "very short sentences (3-6 words)",
        "partner": "speak slowly, use the 500 most common words, and ask one simple question at a time",
        "turns": 6,
    },
    "A2": {
        "sentence": "short, simple sentences",
        "partner": "keep vocabulary basic, ask short follow-up questions, and rephrase if they hesitate",
        "turns": 8,
    },
    "B1": {
        "sentence": "everyday sentences with some linking words",
        "partner": "speak at a natural but unhurried pace and use common everyday phrasing",
        "turns": 10,
    },
    "B2": {
        "sentence": "longer sentences with opinions and reasons",
        "partner": "speak at natural speed, use idioms occasionally, and push them to justify opinions",
        "turns": 12,
    },
    "C1": {
        "sentence": "fluent, nuanced sentences",
        "partner": "speak fully naturally, use idiomatic and colloquial language, and challenge their reasoning",
        "turns": 14,
    },
    "C2": {
        "sentence": "precise, native-like sentences",
        "partner": "speak exactly as you would to a native speaker, including fast speech and cultural references",
        "turns": 14,
    },
}


@dataclass
class ScriptTemplate:
    scenario: str
    title: str
    setting: str
    goal: str
    expressions: dict[str, list[str]]  # keyed by the lowest CEFR level it suits
    opener: str
    # A worked opening, alternating Partner and You. Its job is to show the
    # learner what their own turns can sound like -- the half a roleplay prompt
    # never supplies -- so it always includes at least two "You" lines.
    sample_exchange: list[tuple[str, str]] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


# A small, hand-written starter set. Natural modern English, not textbook lines.
TEMPLATES: list[ScriptTemplate] = [
    ScriptTemplate(
        scenario="casual",
        title="Catching up with a friend",
        setting="You bump into a friend you have not seen for a few months. Your partner plays the friend.",
        goal="Talk about what you have been doing lately and ask about their life.",
        expressions={
            "A1": ["How are you?", "I'm good", "See you soon"],
            "B1": ["What have you been up to?", "Not much, actually", "We should catch up properly"],
            "B2": ["It's been ages!", "I've been meaning to call you", "Let's grab a coffee sometime"],
        },
        opener="Hey! I haven't seen you in ages. What have you been up to?",
        sample_exchange=[
            ("Partner", "Hey! I haven't seen you in ages. What have you been up to?"),
            ("You", "Not much, actually. Just work mostly. What about you?"),
            ("Partner", "Same here, honestly. Still at the same place?"),
            ("You", "Yeah, still there. It's been busy, but I can't complain."),
            ("Partner", "That's good. Are you still living over by the park?"),
            ("You", "No, we moved in the summer. We're a bit further out now."),
            ("Partner", "Oh nice, how's that? Bit quieter?"),
            ("You", "Much quieter, yeah. The commute's longer, but it's worth it."),
            ("Partner", "I can imagine. We should catch up properly sometime."),
            ("You", "Definitely. Are you free next weekend at all?"),
            ("Partner", "Saturday could work. I'll message you."),
            ("You", "Great, do that. It was really good to see you."),
        ],
        questions=[
            "What has changed in your life in the last six months?",
            "What are you looking forward to?",
        ],
    ),
    ScriptTemplate(
        scenario="job_interview",
        title="Interview: tell me about yourself",
        setting="You are in a job interview for a role you actually want. Your partner plays the interviewer.",
        goal="Introduce yourself, describe your experience, and explain why you want the job.",
        expressions={
            "A2": ["I work as a...", "I am good at...", "I want to learn..."],
            "B1": ["I've been working in... for three years", "I'm responsible for...", "I'd say my strength is..."],
            "B2": ["What drew me to this role is...", "I'd like to take on more responsibility", "That's a fair point"],
        },
        opener="Thanks for coming in. So, tell me a bit about yourself.",
        sample_exchange=[
            ("Partner", "Thanks for coming in. So, tell me a bit about yourself."),
            ("You", "Thanks for having me. I've been working in this field for about three years."),
            ("Partner", "And what does your current role involve?"),
            ("You", "I'm responsible for the day-to-day side of things, and I manage a small team."),
            ("Partner", "What made you apply for this role?"),
            ("You", "I'm looking for something with more responsibility, and this looked like a good fit."),
            ("Partner", "What would you say your main strength is?"),
            ("You", "I'd say I'm good at staying calm when things go wrong. That comes up a lot."),
            ("Partner", "Can you give me an example?"),
            ("You", "Sure. We lost a supplier last year, and I sorted out a replacement in a week."),
            ("Partner", "That's useful to hear. Do you have any questions for me?"),
            ("You", "Yes — could you tell me what the first few months would look like?"),
        ],
        questions=[
            "What is a problem you solved at work recently?",
            "Where do you want to be in three years?",
        ],
    ),
    ScriptTemplate(
        scenario="workplace",
        title="Explaining a problem at work",
        setting="Something went wrong on a project. Your partner plays a colleague who needs an update.",
        goal="Explain what happened, what you did about it, and what you need from them.",
        expressions={
            "A2": ["There is a problem", "I fixed it", "Can you help me?"],
            "B1": ["I had to deal with...", "It turned out that...", "Could you take a look at...?"],
            "B2": ["We ran into an issue with...", "I'll keep you posted", "Let me walk you through it"],
        },
        opener="Hey, I heard something came up with the deployment. What's the situation?",
        sample_exchange=[
            ("Partner", "Hey, I heard something came up with the deployment. What's the situation?"),
            ("You", "Yeah, we ran into a problem this morning. The build keeps failing."),
            ("Partner", "Do we know why?"),
            ("You", "Not yet. I'm still looking into it, but I'll let you know as soon as I do."),
            ("Partner", "Okay. How long do you think it'll take?"),
            ("You", "Hard to say. Give me a couple of hours and I'll have a better idea."),
            ("Partner", "Is it going to affect the release on Friday?"),
            ("You", "It might, to be honest. I'd rather flag that now than promise you otherwise."),
            ("Partner", "Appreciate that. Anything you need from me?"),
            ("You", "If you could let the client know there may be a delay, that would help."),
            ("Partner", "Will do. Keep me posted."),
            ("You", "Of course. I'll message you this afternoon either way."),
        ],
        questions=["What would you do differently next time?", "Who else needs to know about this?"],
    ),
    ScriptTemplate(
        scenario="restaurant",
        title="Ordering and sending something back",
        setting="You are eating out. Your partner plays the server. Something is wrong with your order.",
        goal="Order politely, then handle a problem without being rude.",
        expressions={
            "A1": ["I would like...", "Thank you", "The bill, please"],
            "B1": ["Could I get the...?", "Actually, I ordered the...", "No rush"],
            "B2": ["I don't want to make a fuss, but...", "Would it be possible to...?", "That's much better, thanks"],
        },
        opener="Hi there, are you ready to order, or do you need another minute?",
        sample_exchange=[
            ("Partner", "Hi there, are you ready to order, or do you need another minute?"),
            ("You", "I think we're ready, thanks. Could I have the chicken, please?"),
            ("Partner", "Of course. And anything to drink with that?"),
            ("You", "Just some water, please. Sorry — is the chicken spicy at all?"),
            ("Partner", "It has a bit of a kick, yes. I can ask them to go easy on it."),
            ("You", "That would be great, thank you."),
            ("Partner", "No problem. I'll get that ordered for you."),
            ("You", "Sorry, one more thing — does it come with anything on the side?"),
            ("Partner", "It comes with rice, but I can swap that for salad if you'd prefer."),
            ("You", "Salad would be lovely, actually. Thanks for sorting that."),
            ("Partner", "Not at all. It shouldn't be more than fifteen minutes."),
            ("You", "That's fine, we're not in a rush."),
        ],
        questions=["How do you complain politely in your own language?", "What would you order here?"],
    ),
    ScriptTemplate(
        scenario="phone_call",
        title="Sorting something out over the phone",
        setting="You call a company about a bill that looks wrong. Your partner plays the agent.",
        goal="Explain the problem clearly without visual cues, and get it resolved.",
        expressions={
            "A2": ["I have a problem with...", "Can you check it?", "Thank you for your help"],
            "B1": ["I'm calling about...", "Sorry, could you repeat that?", "Let me just check"],
            "B2": ["I've been charged twice", "Could you bear with me a second?", "Just so I'm clear..."],
        },
        opener="Thanks for calling, you're speaking with Sam. How can I help today?",
        sample_exchange=[
            ("Partner", "Thanks for calling, you're speaking with Sam. How can I help today?"),
            ("You", "Hi Sam. I'm calling about my last bill — I think there's been a mistake."),
            ("Partner", "I'm sorry to hear that. Can I take your account number?"),
            ("You", "Sure, one second. Sorry, could you say that again? The line isn't great."),
            ("Partner", "No problem — your account number, whenever you're ready."),
            ("You", "Right, it's 4-4-0-2-1-9. Shall I read that back?"),
            ("Partner", "That's got it, thank you. I can see the bill here. What seems to be wrong?"),
            ("You", "I've been charged twice for the same month, as far as I can tell."),
            ("Partner", "You're right, actually. I'll get that refunded for you."),
            ("You", "That's a relief. How long does the refund usually take?"),
            ("Partner", "Three to five working days."),
            ("You", "Perfect. Thanks very much for your help, Sam."),
        ],
        questions=["What is hardest about English phone calls?", "How would you ask someone to slow down?"],
    ),
    ScriptTemplate(
        scenario="small_talk",
        title="Small talk before a meeting",
        setting="You are waiting for a meeting to start with someone you barely know.",
        goal="Keep a light conversation going for a few minutes without awkward silences.",
        expressions={
            "A2": ["Nice weather today", "How was your weekend?", "Where are you from?"],
            "B1": ["Did you have a good weekend?", "Same here", "How's your week going?"],
            "B2": ["Busy week?", "I know what you mean", "Anyway, we should probably get started"],
        },
        opener="Morning! Looks like we're a bit early. Busy week for you?",
        sample_exchange=[
            ("Partner", "Morning! Looks like we're a bit early. Busy week for you?"),
            ("You", "Morning! Yeah, it's been pretty full on. How about you?"),
            ("Partner", "Same, honestly. Did you get anywhere nice at the weekend?"),
            ("You", "Not really, I just stayed home. It was quite nice, actually."),
            ("Partner", "Sometimes that's exactly what you need."),
            ("You", "That's what I thought. Did you do anything?"),
            ("Partner", "We took the kids out on Sunday. Cost me a fortune, mind."),
            ("You", "Ha, I can imagine. Were they happy though?"),
            ("Partner", "Worth it for that, yeah. Anyway — have you seen the agenda for this?"),
            ("You", "I had a quick look. It's mostly the budget, isn't it?"),
            ("Partner", "That's the one. Should be short, hopefully."),
            ("You", "Fingers crossed. Shall we go in?"),
        ],
        questions=["What small talk topics are safe at work?", "How do you end small talk politely?"],
    ),
]


def _expressions_for(template: ScriptTemplate, level: str) -> list[str]:
    """Pick the expression set closest to, but not above, the learner's level."""
    target = cefr_index(level)
    best_key, best_index = None, -1
    for key in template.expressions:
        index = cefr_index(key)
        if index <= target and index > best_index:
            best_key, best_index = key, index
    if best_key is None:  # learner is below every set; use the easiest available
        best_key = min(template.expressions, key=cefr_index)
    return template.expressions[best_key]


def build_portable_prompt(
    *,
    title: str,
    setting: str,
    goal: str,
    level: str,
    expressions: list[str],
    questions: list[str],
    sample_exchange: list[tuple[str, str]] | None = None,
) -> str:
    """Render a self-contained roleplay prompt for ChatGPT, Gemini or similar.

    Written as instructions to *that* assistant, so it works standing alone with
    no context from this app.
    """
    guidance = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["B1"])
    expression_list = "\n".join(f"- {e}" for e in expressions) or "- (none specified)"
    question_list = "\n".join(f"- {q}" for q in questions) or "- (none specified)"

    # The learner's own lines. Without these the prompt describes a situation
    # and leaves the hardest part -- producing the first sentence -- entirely
    # to someone who is practising precisely because that is hard.
    if sample_exchange:
        script_block = "\n".join(f"{who}: {text}" for who, text in sample_exchange)
        script_section = f"""THE SCRIPT I HAVE PRACTISED
I have read this through out loud, both parts. Start us here, then let the
conversation go its own way -- do not stick to it once we are past the opening,
and do not read my lines for me.

{script_block}

"""
    else:
        script_section = ""

    return f"""You are my English speaking partner. We are going to do a roleplay.

MY LEVEL: CEFR {level}
Speak so that I can follow: {guidance["partner"]}. Expect me to reply in {guidance["sentence"]}.

THE SITUATION
{setting}

MY GOAL
{goal}

{script_section}EXPRESSIONS I AM PRACTISING
Try to create natural openings for me to use these. Do not list them for me.
{expression_list}

HOW TO RUN THIS
1. Start the roleplay immediately, in character, with one short line. No preamble.
2. Stay in character for about {guidance["turns"]} exchanges.
3. Keep your turns to 1-3 sentences, like a real person.
4. Do NOT correct my English during the roleplay, even if I make mistakes.
5. If I go silent or get stuck, nudge me with a question instead of explaining.
6. When I type "FEEDBACK", stop the roleplay and give me:
   - 3 things I did well
   - my most important mistakes, each as: what I said, the natural version, and why
   - 3 more natural expressions I could have used
   - one thing to focus on next time

QUESTIONS TO WORK IN IF IT FITS
{question_list}

STYLE
{NATURAL_ENGLISH_RULES}

Begin now with your first line, in character."""


# Below this it is an opening, not something to read aloud as a script.
MIN_SCRIPT_LINES = 4


def normalize_lines(raw) -> list[dict]:
    """Coerce a model's idea of a script into ours, or reject it.

    Returns an empty list when what came back cannot be practised -- too few
    lines, or only one person speaking. The caller substitutes a written
    script rather than storing a fragment.
    """
    if not isinstance(raw, list):
        return []

    collected: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        collected.append((str(item.get("speaker") or "").strip().lower(), text[:400]))

    if not collected:
        return []

    labels = [label for label, _ in collected]
    explicit = any(label.startswith("partner") for label in labels) and any(
        label in {"you", "learner", "me"} for label in labels
    )

    if explicit:
        role = lambda label: "Partner" if label.startswith("partner") else "You"  # noqa: E731
    else:
        # Two labels in a two-person script are the two roles, whatever the
        # model decided to call them. The one that speaks first is the partner,
        # because every script here opens with them.
        order: list[str] = []
        for label in labels:
            if label not in order:
                order.append(label)
        first = order[0] if order else ""
        role = lambda label: "Partner" if label == first else "You"  # noqa: E731

    lines = [{"speaker": role(label), "text": text} for label, text in collected]

    if len(lines) < MIN_SCRIPT_LINES:
        return []
    if len({line["speaker"] for line in lines}) < 2:
        return []
    return lines


def generate_template_script(*, scenario: str | None, level: str, rng: random.Random | None = None) -> dict:
    """Build a script from the built-in templates. Never fails, never needs AI."""
    rng = rng or random.Random()
    pool = [t for t in TEMPLATES if scenario in (None, "", t.scenario)] or TEMPLATES
    template = rng.choice(pool)
    expressions = _expressions_for(template, level)

    return {
        "scenario": template.scenario,
        "level": level,
        "title": template.title,
        "setting": template.setting,
        "goal": template.goal,
        "target_expressions": expressions,
        # Both sides, so the page shows the learner their own turns rather
        # than only what will be said to them.
        "lines": [
            {"speaker": who, "text": text}
            for who, text in (template.sample_exchange or [("Partner", template.opener)])
        ],
        "follow_up_questions": template.questions,
        "portable_prompt": build_portable_prompt(
            title=template.title,
            setting=template.setting,
            goal=template.goal,
            level=level,
            expressions=expressions,
            sample_exchange=template.sample_exchange,
            questions=template.questions,
        ),
        "source": "template",
    }


AI_SCRIPT_SCHEMA = {
    "type": "object",
    "required": ["title", "setting", "goal", "target_expressions", "lines"],
    "properties": {
        "title": {"type": "string"},
        "setting": {"type": "string"},
        "goal": {"type": "string"},
        "target_expressions": {"type": "array", "items": {"type": "string"}},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["speaker", "text"],
                "properties": {"speaker": {"type": "string"}, "text": {"type": "string"}},
            },
        },
        "follow_up_questions": {"type": "array", "items": {"type": "string"}},
    },
}


def generate_ai_script(provider, *, scenario: str, level: str, topic: str = "", weak_points: list[str] | None = None) -> dict:
    """AI-generated variant. Falls back to a template on any AI failure."""
    from apps.ai.providers.base import AIError, TIER_MEDIUM

    hint = SCENARIO_HINTS.get(scenario, SCENARIO_HINTS["casual"])
    guidance = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["B1"])
    focus = ", ".join(weak_points or []) or "general fluency"
    topic_line = f"Make it about: {topic}.\n" if topic else ""

    prompt = f"""Create an English speaking-practice roleplay for a CEFR {level} learner.

Situation type: {hint}
{topic_line}The learner is currently weak at: {focus}.
Their replies will be {guidance["sentence"]}.

{NATURAL_ENGLISH_RULES}

Return JSON with:
- title: a short name for this roleplay
- setting: 1-2 sentences describing the situation and who plays whom
- goal: what the learner should achieve
- target_expressions: 3-5 natural expressions to practise, suitable for {level}
- lines: a 4-6 turn sample exchange, alternating "Partner" and "You"
- follow_up_questions: 2 questions to extend the conversation
"""
    try:
        data = provider.generate_json(prompt, schema=AI_SCRIPT_SCHEMA, tier=TIER_MEDIUM, temperature=0.8)
    except AIError:
        return generate_template_script(scenario=scenario, level=level)

    expressions = [str(e) for e in data.get("target_expressions", [])]
    questions = [str(q) for q in data.get("follow_up_questions", [])]
    lines = normalize_lines(data.get("lines"))
    if not lines:
        # Whatever came back is not something the learner can practise. Their
        # own hand-written exchange for this situation is better than a
        # one-sided fragment, so borrow it.
        template = next((item for item in TEMPLATES if item.scenario == scenario), None)
        if template and template.sample_exchange:
            lines = [
                {"speaker": who, "text": text} for who, text in template.sample_exchange
            ]
    return {
        "scenario": scenario,
        "level": level,
        "title": data["title"],
        "setting": data["setting"],
        "goal": data["goal"],
        "target_expressions": expressions,
        "lines": lines,
        "follow_up_questions": questions,
        "portable_prompt": build_portable_prompt(
            title=data["title"],
            setting=data["setting"],
            goal=data["goal"],
            level=level,
            expressions=expressions,
            questions=questions,
            sample_exchange=[(line["speaker"], line["text"]) for line in lines],
        ),
        "source": "ai",
    }
