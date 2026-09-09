"""A starter set of genuinely useful expressions.

Chosen for how often they come up in real spoken English rather than for
textbook tidiness, and weighted toward multi-word items — phrasal verbs,
collocations and fixed expressions are where intermediate learners gain the most
ground, and where learner English most often sounds unnatural.

Every example sentence is something a person would actually say.
"""

from .models import Kind

# (text, kind, cefr, register, meaning, [examples], common_mistake)
SEED_EXPRESSIONS = [
    (
        "figure out", Kind.PHRASAL_VERB, "B1", "neutral",
        "To understand something or solve it by thinking it through.",
        [
            "I still can't figure out why the build keeps failing.",
            "Give me a minute to figure this out.",
            "We'll figure something out.",
        ],
        "",
    ),
    (
        "deal with", Kind.PHRASAL_VERB, "B1", "neutral",
        "To handle a problem, task or person.",
        [
            "I had to deal with an internet problem at work today.",
            "I'll deal with it in the morning.",
            "She's really good at dealing with difficult customers.",
        ],
        "Not 'deal to' or 'deal about'.",
    ),
    (
        "end up", Kind.PHRASAL_VERB, "B1", "neutral",
        "To finally be in a situation, often unexpectedly.",
        [
            "We ended up staying an extra night.",
            "If you keep skipping practice, you'll end up starting over.",
            "I ended up doing it myself.",
        ],
        "Followed by -ing, not the infinitive: 'ended up staying', not 'ended up to stay'.",
    ),
    (
        "run into", Kind.PHRASAL_VERB, "B1", "casual",
        "To meet someone by chance, or to hit a problem unexpectedly.",
        [
            "I ran into an old colleague at the station.",
            "We ran into a few issues with the deployment.",
            "Let me know if you run into trouble.",
        ],
        "",
    ),
    (
        "look forward to", Kind.PHRASAL_VERB, "B1", "neutral",
        "To feel happy about something that is going to happen.",
        [
            "I'm really looking forward to the weekend.",
            "Looking forward to hearing from you.",
            "She's looking forward to starting the new job.",
        ],
        "Followed by -ing, not the infinitive: 'looking forward to seeing you'.",
    ),
    (
        "get the hang of", Kind.IDIOM, "B2", "casual",
        "To learn how to do something after some practice.",
        [
            "It took me a week to get the hang of the new system.",
            "You'll get the hang of it.",
            "I'm slowly getting the hang of cooking properly.",
        ],
        "",
    ),
    (
        "What have you been up to?", Kind.PHRASE, "B1", "casual",
        "A natural way to ask what someone has been doing recently.",
        [
            "Hey! Long time. What have you been up to?",
            "So what have you been up to lately?",
        ],
        "",
    ),
    (
        "to be honest", Kind.PHRASE, "B1", "casual",
        "Used before saying what you really think.",
        [
            "To be honest, I'd rather stay in.",
            "It wasn't great, to be honest.",
        ],
        "",
    ),
    (
        "I'd say", Kind.PATTERN, "B1", "casual",
        "A softer way to give an opinion or estimate.",
        [
            "I'd say it'll take about two hours.",
            "I'd say that's the best option we have.",
        ],
        "",
    ),
    (
        "make a decision", Kind.COLLOCATION, "B1", "neutral",
        "To decide something. English uses 'make', not 'take'.",
        [
            "We need to make a decision by Friday.",
            "He made the decision to leave.",
        ],
        "Not 'take a decision' in everyday English, and never 'do a decision'.",
    ),
    (
        "pay attention", Kind.COLLOCATION, "A2", "neutral",
        "To watch or listen carefully.",
        [
            "Sorry, I wasn't paying attention.",
            "Pay attention to how she pronounces it.",
        ],
        "Followed by 'to', not 'on' or 'at'.",
    ),
    (
        "take my time", Kind.COLLOCATION, "B1", "casual",
        "To do something slowly and carefully, without rushing.",
        [
            "I'd rather take my time and get it right.",
            "Take your time, there's no rush.",
        ],
        "",
    ),
    (
        "keep you posted", Kind.IDIOM, "B2", "professional",
        "To keep someone updated about a situation.",
        [
            "I'll keep you posted.",
            "Keep me posted on how it goes.",
        ],
        "",
    ),
    (
        "let me walk you through it", Kind.PHRASE, "B2", "professional",
        "An offer to explain something step by step.",
        [
            "It looks complicated, but let me walk you through it.",
            "Can you walk me through what happened?",
        ],
        "",
    ),
    (
        "come up with", Kind.PHRASAL_VERB, "B1", "neutral",
        "To think of an idea, plan or solution.",
        [
            "Who came up with that name?",
            "We need to come up with something better.",
        ],
        "",
    ),
    (
        "It turned out that", Kind.PATTERN, "B2", "neutral",
        "Used to introduce something you discovered later.",
        [
            "It turned out that the file was corrupted the whole time.",
            "It turned out to be much easier than I expected.",
        ],
        "",
    ),
    (
        "I'm not sure I follow", Kind.PHRASE, "B2", "professional",
        "A polite way of saying you do not understand.",
        [
            "Sorry, I'm not sure I follow. Could you go over that again?",
        ],
        "",
    ),
    (
        "no rush", Kind.PHRASE, "B1", "casual",
        "Telling someone they do not need to hurry.",
        [
            "Whenever you get a chance, no rush.",
            "No rush, but I'd like it by Friday.",
        ],
        "",
    ),
    (
        "It's been ages", Kind.IDIOM, "B2", "casual",
        "A long time has passed since you last saw someone.",
        [
            "It's been ages! How are you?",
            "I haven't been there in ages.",
        ],
        "",
    ),
    (
        "I'm exhausted", Kind.PHRASE, "B1", "neutral",
        "A natural way to say you are extremely tired.",
        [
            "I'm exhausted. I need an early night.",
            "You look exhausted, are you okay?",
        ],
        "More natural than 'I am very tired'. Casual: 'I'm beat.'",
    ),
    (
        "grab something to eat", Kind.COLLOCATION, "B1", "casual",
        "To get food quickly and informally.",
        [
            "Want to grab something to eat after work?",
            "I'll grab something on the way.",
        ],
        "",
    ),
    (
        "give me a hand", Kind.IDIOM, "B1", "casual",
        "To help someone.",
        [
            "Could you give me a hand with this?",
            "Thanks for giving me a hand earlier.",
        ],
        "",
    ),
    (
        "sort it out", Kind.PHRASAL_VERB, "B2", "casual",
        "To fix a problem or put something in order.",
        [
            "Don't worry, we'll sort it out.",
            "I need to sort out my schedule.",
        ],
        "",
    ),
    (
        "make sense", Kind.COLLOCATION, "B1", "neutral",
        "To be understandable or logical.",
        [
            "That makes sense now.",
            "Does that make sense, or should I explain it differently?",
        ],
        "Not 'make a sense'. And people say 'it makes sense', not 'it has sense'.",
    ),
    (
        "I've been meaning to", Kind.PATTERN, "B2", "casual",
        "Something you have intended to do for a while but have not done yet.",
        [
            "I've been meaning to call you.",
            "I've been meaning to sort out my desk for weeks.",
        ],
        "",
    ),
    (
        "as far as I know", Kind.PHRASE, "B2", "neutral",
        "Used when you believe something is true but are not certain.",
        [
            "As far as I know, the meeting is still on.",
        ],
        "",
    ),
    (
        "a bit of a nightmare", Kind.IDIOM, "B2", "casual",
        "Something that was difficult or annoying.",
        [
            "The commute this morning was a bit of a nightmare.",
        ],
        "",
    ),
    (
        "get back to you", Kind.PHRASE, "B1", "professional",
        "To reply to someone later with an answer.",
        [
            "Let me check and I'll get back to you.",
            "Sorry for the delay getting back to you.",
        ],
        "",
    ),
    (
        "on second thought", Kind.PHRASE, "B2", "neutral",
        "Used when you change your mind.",
        [
            "On second thought, let's just take a taxi.",
        ],
        "",
    ),
    (
        "look into", Kind.PHRASAL_VERB, "B2", "professional",
        "To investigate or examine something.",
        [
            "I'll look into it and let you know.",
            "Could you look into why the report is late?",
        ],
        "",
    ),
]
