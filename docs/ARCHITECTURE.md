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

## 10. Custom User from day one

`AUTH_USER_MODEL = "accounts.User"` even though the app is single-learner.
Swapping the user model later is one of Django's genuinely painful migrations;
doing it now costs nothing and keeps multi-user viable.

## 11. Frontend

Vite + React 19 + Tailwind 4, with a dev proxy so the frontend is
origin-relative (no CORS surprises, and the same build works behind one domain
in production). `lib/api.js` is the only module that knows about fetch, tokens,
or the error envelope.

Navigation shows Review / Real World / Progress as disabled entries. The
information architecture is visible from Phase 1, so later phases slot in
without a navigation redesign.

## What is deliberately *not* here yet

FSRS scheduling, the mistake bank, RSS ingestion, embeddings and Celery. Each
belongs to a later phase. The architecture leaves room for all of them — the
`ai` app already has a cache and a request log, and `constants.py` already
defines the shared CEFR/skill/register vocabulary they will need.
