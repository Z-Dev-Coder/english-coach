# Roadmap

Each phase ships something usable. No phase starts before the previous one's
tests pass.

## Phase 1 — Foundation ✅ COMPLETE

**Goal:** a learner can sign in and be told what to study today.

- Custom `User`, token auth, registration with password validation
- `LearnerProfile`, `SkillProgress` (8 skills), `StudySession`
- Adaptive daily planner (weakness + priority + staleness)
- Streaks, weekly goals, dashboard payload
- `AIProvider` abstraction + `OllamaProvider` + health check with setup hints
- JSON schema validation, prompt-injection guard, content-hash cache, request log
- Speaking Script Studio with pasteable ChatGPT/Gemini prompts
- React frontend: login, dashboard, script studio, profile
- **93 backend tests, all green**

## Phase 2 — Vocabulary and spaced repetition ✅ COMPLETE

**Goal:** review is real, not random.

- `Expression` (word / phrase / idiom / phrasal verb / collocation / pattern),
  `ExampleSentence` with automatic cloze, `VocabularyProgress`, `Review` log
- **FSRS-5** scheduling implemented from the published algorithm, as pure
  functions with no Django imports (32 dedicated tests)
- Mastery states: NEW → LEARNING → REVIEW → WEAK → MASTERED, derived from
  stability and lapses rather than stored ad hoc
- Queue: most-overdue first, new items capped per day and interleaved rather
  than dumped at the end; length derived from the planner's review minutes
- Mixed exercise types (meet / recall / produce / cloze / use) chosen by mastery
  state, so review is never all recognition
- 30 hand-written starter expressions, idempotently seedable
- Review UI with keyboard grading, forecast chart and session summary
- Dashboard's review block now shows the real due count
- **208 backend tests, all green**

## Phase 3 — The four skills ✅ COMPLETE

**Goal:** each skill has an end-to-end activity that feeds the planner.

- `Passage` (shared or learner-owned) and `SkillAttempt`, with cached word
  count and Flesch readability
- `similarity.py`: word-level diff, two-pass contraction handling and
  readability estimation, as pure functions (30 tests)
- **Listening** — dictation against synthesised speech, scored word by word
- **Pronunciation** — shadowing via browser speech recognition, labelled
  explicitly as an estimate rather than a phonetic score
- **Reading** — passages plus paste-your-own text, with automatic level
  estimation; speed alone does not move the score
- **Writing** — AI feedback through the existing provider, falling back to
  structural checks when the model is offline
- **Listen → Speak → Write drill** — one sentence worked five ways, crediting
  listening, speaking and writing together
- Browser-native TTS and STT: zero cost, no dependencies, graceful degradation
  where a browser lacks support
- **302 backend tests, all green**

## Phase 4 — AI lessons and conversation ✅ COMPLETE

**Goal:** the daily plan becomes a lesson, and the learner can talk to someone.

- `Lesson` and `LessonActivity`, one lesson per learner per day, idempotent so
  a refresh never discards progress
- `learner_context()` assembles level, measured weaknesses, recent mistake
  categories, due vocabulary, interests and available time from the database,
  and is exposed at `/api/learner-context/` so personalisation is not a black box
- **Hybrid generation**: structure (skills, minutes, routing) is computed;
  only text is taken from the model, so a hallucination cannot rewrite the
  schedule and a partial response still produces a complete lesson
- Generation cached by content hash — identical learner state runs the model once
- `ConversationSession` / `ConversationMessage` with 13 scenarios
- Feedback after the conversation, never during it, and only on the learner's
  own turns
- Speaking and fluency credited by how much was actually said
- **346 backend tests, all green**

## Phase 5 — Real-world English ✅ COMPLETE

**Goal:** current, real English, legally.

- `ContentSource` and `Article`, with stdlib RSS/Atom parsing (no new dependency)
- **Ingestion is idempotent by database constraint**, not by checking first:
  unique on (source, guid) and on url, so re-running creates zero duplicates
  and syndicated stories cannot appear twice
- **Copyright is the design constraint**: only metadata, the publisher's own
  syndication summary, and material *we* write are stored. The full article is
  never fetched, and every card links to the original
- "Today in English" biases toward the learner's interests without walling off
  everything else
- Movies & TV: the learner pastes short excerpts they are watching, and gets the
  spoken English explained — no scraping or redistributing subtitles
- External text is fenced as untrusted before it reaches any model

## Phase 6 — Adaptive engine ✅ COMPLETE

**Goal:** the same mistake stops slipping past.

- `Mistake` / `MistakeOccurrence`, keyed on the corrected pair so the same error
  counts as one however it was surfaced
- Fed automatically by writing feedback and conversation review through a single
  entry point
- Noise filtering: punctuation-only and case-only "corrections" are discarded,
  and reported categories are normalised so the bank does not fragment
- Repeats reach the lesson generator verbatim, and turn into practice tasks
- Status ages from active → improving → resolved, and any repeat reactivates it
- Progress screen leads with what changed rather than hours spent
- **410 backend tests, all green**

## Later, if wanted

PWA/offline, semantic search over the learner's history (sentence-transformers
+ ChromaDB), YouTube import, browser extension, multi-user. The architecture
leaves room for each; none is started early.
