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

## Phase 3 — The four skills

- `ListeningAttempt`, `ReadingAttempt`, `WritingAttempt`, `SpeakingAttempt`
- Listening: audio, hidden transcript, dictation, shadowing
- Reading: unknown-word highlighting, inline explanation, comprehension
- Writing: prompt → submission → structured feedback
- Speaking: browser speech recognition, record and compare
- Listen → Speak → Write single-sentence drill
- Browser-native TTS/STT (free); pronunciation scores labelled as estimates
- **Done when:** each skill has one end-to-end activity that updates its score

## Phase 4 — AI lessons and conversation

- `Lesson`, `LessonActivity`, `LessonGenerator` service
- Learner context (level, weak skills, recent mistakes, due vocabulary,
  interests, available time) fed into generation
- Writing evaluation with explanations, never silent rewrites
- `ConversationSession` / `ConversationMessage`, feedback after the conversation
- All generations cached by content hash
- **Done when:** lessons generate from real learner state and survive a model
  that returns malformed JSON

## Phase 5 — Real-world English

- `ContentSource`, `Article`, idempotent RSS ingestion (metadata + adapted
  material + link to source, never full copyrighted text)
- "Today in English": several current topics, each with reading, vocabulary,
  listening, questions, speaking and writing
- Movie/TV module for legally available and user-provided material
- **Done when:** re-ingesting the same feed creates zero duplicates

## Phase 6 — Adaptive engine

- `Mistake` / `MistakeOccurrence` bank across all skills
- Repeated mistakes automatically resurface in lessons and reviews
- Natural-English engine: detect understandable-but-unnatural learner English
- Grammar weakness detection from writing and speaking
- Personalisation scoring documented and tested
- **Done when:** a mistake made twice provably changes tomorrow's lesson

## Later, if wanted

PWA/offline, semantic search over the learner's history (sentence-transformers
+ ChromaDB), YouTube import, browser extension, multi-user. The architecture
leaves room for each; none is started early.
