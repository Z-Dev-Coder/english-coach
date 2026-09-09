# Architecture

Decisions, alternatives, and what each one costs later.

## 1. Per-skill proficiency instead of a global level

`SkillProgress` holds one row per (user, skill) with `score` (0-100), `level`
(CEFR) and `confidence` (0-1). `LearnerProfile.overall_level` is derived for
display only and is never used to pick difficulty for a specific skill.

**Why:** the whole product premise is personalising by weakness. A global level
makes that impossible — it averages away the exact signal we need.

**Alternative considered:** one `level` field on the profile. Simpler, but every
adaptive feature would then need a per-skill override anyway.

**Confidence matters.** A new learner starts at a neutral 50 across the board,
which is *below* the weakness threshold. Without a confidence gate the app would
tell a brand-new user that all eight of their skills are weak — wrong (nothing
has been measured) and demoralising. So `is_weak` requires `confidence > 0`, and
unmeasured skills get "this sets your baseline" in the plan instead.

## 2. AI provider abstraction

```
AIProvider (ABC)
├─ generate()  chat()  health()          <- providers implement these three
└─ generate_json() explain() summarize() <- shared, built on the primitives
   extract_vocabulary() evaluate_writing() conversational_response()
```

Business code calls `get_ai_provider()`. Nothing outside `apps/ai/providers/`
imports `requests` or knows Ollama exists.

**Why only three abstract methods:** every task helper is implemented once on
the base class, so a new provider inherits all learning features and behaves
identically. Providers may override for efficiency, but never must.

**Model tiers, not model names.** Callers ask for `TIER_SMALL` or `TIER_MEDIUM`.
Tiers resolve through `.env`, and a missing larger model falls back down the
chain rather than failing — so an unset `AI_MODEL_LARGE` breaks nothing.

## 3. Never trusting model JSON

`generate_json()` parses, validates against a schema, and on failure retries
once with the parse error fed back before raising `AIOutputError`.

Recovery is deliberately forgiving: small local models wrap JSON in prose or
code fences constantly. `extract_json()` tries the raw text, fenced blocks, and
the outermost `{...}`/`[...]` span before giving up.

**Schema validation is hand-rolled** (~30 lines) rather than pulling in
`jsonschema`, because we use exactly four constructs: `type`, `required`,
`properties`, `items`. If that grows, swap the library in behind
`validate_schema()` — one function, no call-site changes.

## 4. Prompt injection from external content

Every externally sourced string (articles, RSS, subtitles) goes through
`wrap_untrusted()`, which fences it and instructs the model to treat it as data.
The wrapper also strips the fence markers from *inside* the content, so hostile
text cannot close the fence and escape into instruction position.

This matters most in Phase 5, when RSS ingestion starts. Building it in now
costs nothing; retrofitting it after content flows would mean auditing every
prompt.

## 5. Planner as a pure function

`build_daily_plan()` reads the database and returns time blocks. No AI, no
network. Weights are named constants with documented rationale:

| Constant | Value | Role |
|---|---|---|
| `BASE_SHARE` | 1.0 | Floor, so no skill is ever dropped (preserves interleaving) |
| `WEAKNESS_WEIGHT` | 2.5 | How hard a low score pulls minutes in |
| `PRIORITY_WEIGHT` | 1.0 | The learner's explicit choice |
| `STALENESS_WEIGHT` | 0.8 | Neglected skills resurface |
| `REVIEW_SHARE` | 0.17 | ~5 of 30 minutes, floored at 3 |

Allocation uses largest-remainder, so blocks sum to exactly the requested
minutes — no drift, no zero-minute cards.

**Why a floor at all:** pure weakness-chasing would drop strong skills entirely,
which contradicts interleaving. Every skill keeps a share.

## 6. Score updates are damped

`record_practice()` applies only 30% of the raw delta and grows confidence as
`attempts / (attempts + 10)`. One unusually good or bad session should not
rewrite the learner's profile. This is the difference between a progress
estimate and a mood ring.

## 7. Caching by content hash

`cached(task, inputs, producer)` keys on `sha256(task + model + inputs)`. Same
article, same difficulty, same objective → the stored lesson, not a new
generation. Local inference is free in money but expensive in seconds.

## 8. Service layer

Business logic lives in `apps/*/services.py`. Views parse, delegate, serialize.
This is what makes the planner and the scoring rules testable without HTTP —
and it is why the test suite runs in under a second.

## 9. Database: SQLite now, Postgres by env var

Postgres was not installed on the target machine. `DATABASE_URL` drives the
connection, defaulting to SQLite. Every model avoids backend-specific features,
so the switch is a one-line `.env` change plus `migrate`.

**Tradeoff:** SQLite will not survive concurrent writes at scale. For a
single-learner app it is irrelevant, and the escape hatch costs one line.

## 9a. Relative SQLite paths are anchored to the project root

`DATABASE_URL=sqlite:///db.sqlite3` is a *relative* path, so SQLite opens it
against the process working directory. The server (launched from the repo root)
and management commands (run from `backend/`) therefore used **different
database files** — which presents as vanished accounts and seeded data that is
not there.

`_database_config()` in settings resolves relative SQLite paths against
`PROJECT_ROOT`, making the database a property of the project rather than of the
shell. Absolute paths, in-memory databases and Postgres URLs pass through
untouched. Covered by regression tests in `config/tests.py`.

## 10. Custom User from day one

`AUTH_USER_MODEL = "accounts.User"` even though the app is single-learner.
Swapping the user model later is one of Django's genuinely painful migrations;
doing it now costs nothing and keeps multi-user viable.

## 10a. Token authentication

DRF token auth, with three properties that are easy to get wrong:

- **Logout revokes.** `POST /api/auth/logout/` deletes the token server-side.
  Without it, signing out only forgets the token locally while it stays valid
  forever — anyone holding it keeps access.
- **Login rotates.** Each login issues a fresh token and deletes the previous
  one, so signing out on one device cannot be undone by a stale token on
  another.
- **The client verifies before trusting.** The frontend restores a token from
  `localStorage` on boot and calls `/api/auth/me/` before rendering the app.
  Otherwise a revoked token produces a shell where every request fails. Any 401
  from any endpoint clears the token centrally in `lib/api.js` and returns the
  learner to the login screen.

## 11. FSRS scheduling

`apps/review/fsrs.py` implements FSRS-5 as pure functions over a frozen
dataclass: no Django, no database, no clock. Two numbers model each item —
`stability` (days until recall falls to 90%) and `difficulty` (1-10) — updated
after every review from the grade and the *real* elapsed time.

**Why implement rather than depend:** the algorithm is ~120 lines, and vendoring
it pins the behaviour and keeps the dependency surface small. The weights are
the published FSRS-5 defaults; optimising them per learner needs a few hundred
reviews of history, which is why `Review` logs before/after state in full.

**Why FSRS over SM-2:** SM-2 applies fixed multipliers. FSRS uses a memory model
fitted to millions of real reviews, so it exploits things SM-2 throws away —
most importantly that reviewing *late* and still recalling is evidence of
stronger memory, and that a hard-won recall teaches more than an easy one.

Two invariants are enforced beyond the raw formulas, because the maths alone can
violate them at the edges: forgetting never lengthens an interval, and repeating
an item the same day cannot inflate its schedule.

## 12. One attempt table, not four

`SkillAttempt` holds every activity rather than having separate
ListeningAttempt / ReadingAttempt / WritingAttempt / SpeakingAttempt models.

They share every column that matters — who, what, how well, how long — and
differ only in a payload that is genuinely activity-specific (word diffs,
feedback issues, transcripts), which lives in `detail`. Four near-identical
tables would turn the cross-skill queries analytics actually needs ("accuracy by
skill", "attempts this week") into four-way unions for no benefit.

`detail` stays disciplined because exactly one service function writes each
shape, rather than it being a junk drawer any view can add to.

## 13. Honesty about what can be measured

Three places where the easy implementation would overstate what the software
knows, and the code deliberately does not:

- **Pronunciation.** Shadowing compares the expected sentence with what the
  browser's speech recogniser heard. That is a proxy for intelligibility, not a
  phonetic analysis, and accents affect it. The stored payload carries an
  explicit `measurement` and `caveat` field and the UI repeats them.
- **Reading.** Recording that a passage was read quickly does not move the
  reading score. Speed is not comprehension, and counting it as progress would
  be exactly the activity-versus-improvement confusion the product exists to
  avoid. Only an actual comprehension score moves it.
- **Writing without AI.** Rule-based checks catch structure — length, runaway
  sentences, missing capitals — but cannot judge whether writing is *good*. When
  only they have run, accuracy is left null and the writing score is untouched
  rather than invented.

Scoring is also asymmetric: `MAX_LOSS` exceeds `MAX_GAIN`, and the neutral pivot
sits at 70% rather than 50%, so a mediocre attempt is not recorded as progress.

## 14. Lessons are generated as a hybrid

Lesson *structure* — which skills, how many minutes, in what order, pointing at
which passage or queue — is computed from the database by
`_template_activities()`. Lesson *content* — a theme, prompts using the
learner's interests, target expressions — is AI-enriched by `_enrich_with_ai()`.

The enrichment overlays text onto the skeleton and nothing else. Kinds, minutes
and routes stay authoritative, and each generated activity is matched to a
skeleton slot by kind rather than by position.

**Why not let the model write the whole lesson:** it would make the single most
important screen depend on a local model behaving, let a hallucination decide
the learner's schedule, and turn a partial response into a broken day. As built,
a model that returns two activities for a six-block plan improves two of them
and leaves the rest with their (deliberately useful) template wording; a model
that returns nonsense produces a complete template lesson.

Lessons are unique per learner per day. Asking for today's lesson twice returns
the same lesson, so refreshing never regenerates it or discards progress.
Replacing it is a separate, explicit `regenerate` action.

## 15. Conversation: talk first, correct afterwards

The conversation partner is instructed never to correct the learner mid-flow,
and `reply()` has no correction path at all. Being stopped every sentence
destroys fluency practice, which is the entire point of the activity.

All correction happens in `generate_feedback()` once the learner ends the
session, and only the learner's own turns are sent for review — including the
partner's replies would invite the model to critique its own output.

Two robustness details worth keeping: every scenario has a scripted opener, so a
conversation can start with no model running; and the learner's turn is saved
*before* the model is called, so their words are never lost because a reply
failed.

## 16. Content: copyright is the design constraint

We never fetch or store the body of a copyrighted article. What is kept is
metadata, the publisher's own RSS syndication summary (capped), and learning
material written by our own model *about* the story. Every card links to the
original. That is the difference between a study aid and a scraper.

`prepare()` refuses to generate material from a summary under 120 characters:
with nothing to retell, the model would have to invent the story, and inventing
facts about current events is worse than showing nothing.

**Idempotency comes from database constraints**, not from checking first — a
get-or-create check can still be raced, and the constraint is the only thing
that genuinely cannot be. `url` is unique across the whole table as well as
(source, guid), so a story syndicated to two feeds appears once.

RSS parsing uses `xml.etree` rather than feedparser: the fields we need are few,
and it keeps the dependency list short. `parse_feed()` is the single seam to
swap behind if real feeds prove too messy.

## 17. The mistake bank

Mistakes are keyed on the **corrected pair**, normalised — "discussed about" →
"discussed" is one mistake however many times it appears and whichever activity
found it. Keying on a description instead would make counting meaningless, and
counting is the entire point: it is what separates a habit from a slip.

Two filters keep the bank usable:

- **Noise.** Corrections that differ only in punctuation or case are discarded.
  Small local models generate a great deal of comma advice, and recording it
  would bury the genuine repeated errors.
- **Category drift.** Models report "verb_tense", "tense", "agreement" for the
  same thing. `normalize_category()` folds these together, or the bank
  fragments into buckets that never accumulate enough evidence to act on.

Status ages from active → improving → resolved on silence, but only ever
downwards: silence is weak evidence of improvement, and a single repeat makes a
mistake active again immediately.

Everything that produces a correction — writing feedback, conversation review —
funnels through `record()`. That single entry point is what turns scattered
one-off notes into a picture of what this learner actually keeps getting wrong,
and it feeds straight back into `learner_context()`.

## 18. Frontend

Vite + React 19 + Tailwind 4, with a dev proxy so the frontend is
origin-relative (no CORS surprises, and the same build works behind one domain
in production). `lib/api.js` is the only module that knows about fetch, tokens,
or the error envelope.

Navigation shows Review / Real World / Progress as disabled entries. The
information architecture is visible from Phase 1, so later phases slot in
without a navigation redesign.

### The design system

`lib/ui.jsx` holds every visual primitive: `Card`, `Button`, `Field`, `Input`,
`Select`, `Chip`, `Switch`, `Pill`, `ProgressBar`, `ProgressRing`, `StatTile`,
`Skeleton`, `EmptyState`, `ErrorNote`. Pages compose these and pass semantic
props (`tone`, `size`, `variant`) rather than raw Tailwind strings.

**Why:** consistency becomes structural instead of something each page has to
remember, and a restyle is a one-file change. It also keeps page files readable
— they describe layout and data, not colour values.

Design tokens live in `index.css` under `@theme`: a single brand ramp
(`brand-50` … `brand-900`), two shadow depths, and the Inter font stack. Every
accent in the app draws from that one hue family, which is what makes the
interface read as one product.

### Dark mode

Driven by a class on `<html>`, declared in Tailwind v4 with
`@custom-variant dark (&:where(.dark, .dark *))`. It defaults to the OS setting
and remembers an explicit choice in `localStorage`.

An inline script in `index.html` applies the saved theme **before first paint**.
Without it the app renders light for one frame and then flashes to dark — the
single most noticeable polish bug in a themed app.

### Motion and loading

Content enters with a short staggered `rise` animation, and loading states are
skeletons rather than a spinner, so the page keeps its shape and nothing jumps
when data lands. All of it collapses to near-zero duration under
`prefers-reduced-motion`, which is honoured globally rather than per component.

### Mobile

A fixed bottom tab bar, not a shrunken sidebar — that is where thumbs are. The
bar respects `env(safe-area-inset-bottom)` so it clears the iPhone home
indicator, and the Profile page's save bar sits above it rather than under it.

## What is deliberately *not* here yet

FSRS scheduling, the mistake bank, RSS ingestion, embeddings and Celery. Each
belongs to a later phase. The architecture leaves room for all of them — the
`ai` app already has a cache and a request log, and `constants.py` already
defines the shared CEFR/skill/register vocabulary they will need.
