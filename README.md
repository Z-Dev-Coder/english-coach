# English Coach

A personal, adaptive English-learning system. It turns real-world English into a
daily learning programme shaped by *your* measured weaknesses, and it runs at
**$0 recurring cost** on a local model.

> Status: **Phase 1 complete.** Auth, learner profile, per-skill proficiency,
> the adaptive daily planner, the AI provider abstraction, and Speaking Script
> Studio are working end to end. Later phases are listed in `docs/ROADMAP.md`.

## Why it is built this way

Three decisions shape everything else:

1. **No single "level".** The learner has eight independent skill scores. Someone
   who reads at B2 and speaks at A2 gets A2 speaking practice and B2 reading —
   not B1 everything.
2. **No vendor lock-in, no API bills.** All AI goes through an `AIProvider`
   abstraction backed by local Ollama models. Adding OpenAI or Anthropic later is
   one subclass; nothing in the business logic changes.
3. **Degrades gracefully.** The planner, the streak logic and the practice
   scripts are pure database and string work. If Ollama is off, the app still
   works — you just lose the generated content.

## Requirements

- Python 3.12+ (built and tested on 3.14)
- Node 20+ (built and tested on 24)
- [Ollama](https://ollama.com) — optional, but needed for AI features
- PostgreSQL — optional; SQLite is the dev default

## Quick start (Windows)

Double-click **`start.bat`**, or the **English Coach** shortcut on your desktop.

It installs anything missing on first run, starts both servers, waits until the
app actually answers, and opens your browser. Running it twice is safe: it
detects servers that are already up instead of starting duplicates.

Double-click **`stop.bat`** when you are finished. It closes only what is
listening on ports 8000 and 5173, leaving your other Python and Node processes
alone.

To recreate the desktop shortcut:

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\English Coach.lnk")
$s.TargetPath = "D:\Projects\english-coach\start.bat"
$s.WorkingDirectory = "D:\Projects\english-coach"
$s.WindowStyle = 7
$s.Save()
```

## Manual setup

```bash
git clone <this repo> && cd english-coach
cp .env.example .env          # then set SECRET_KEY

python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: .venv/bin/python

cd backend
../.venv/Scripts/python manage.py migrate
../.venv/Scripts/python manage.py runserver

# in another terminal
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and create an account.

### Optional: local AI

```bash
ollama pull qwen2.5:3b-instruct-q4_K_M    # fast tier: extraction, classification
ollama pull qwen2.5:7b-instruct-q4_K_M    # quality tier: lessons, feedback, chat
```

`GET /api/ai/status/` reports which models are installed and prints the exact
`ollama pull` command for anything missing. The dashboard surfaces the same
thing if the model is offline.

### Optional: a hosted model instead of local

Everything works on local Ollama at zero cost. A hosted model is worth
considering for one thing: **feedback quality**. Small local models reliably
notice that something is wrong but are vague about which exact words, and tend
to label every error "grammar" — which matters, because the mistake bank keys on
the corrected pair.

```bash
# in .env
DEEPSEEK_API_KEY=sk-...
AI_PROVIDER=deepseek
```

Restart. Nothing else changes: no business logic knows which provider is in use.
`openai` is registered the same way, and switching back is one line.

**Cost.** Measured from this app's real prompt sizes, not estimated. A heavy
day — a lesson, 3 articles, 2 writing submissions, a 10-turn conversation with
review, plus vocabulary lookups — is about 9k input / 7k output tokens.

| Strategy | Off-peak | Peak |
|---|---|---|
| everything on `v4-flash` | $0.20 / mo | $0.40 / mo |
| **mixed (default): flash, `v4-pro` for feedback** | **$0.29 / mo** | $0.58 / mo |
| everything on `v4-pro` | $0.60 / mo | $1.20 / mo |

The default is the mixed strategy. Writing feedback and conversation review run
on the large tier because the mistake bank keys on the exact wrong/right pair,
so vagueness there produces unusable entries. Everything else runs on Flash,
where it makes no perceptible difference.

Peak hours are 01:00–04:00 and 06:00–10:00 UTC, Monday to Friday; everything
else is charged at half rate. Rates from
<https://api-docs.deepseek.com/quick_start/pricing/> (September 2026).

**Don't trust that table — measure it.** Every provider call logs its real token
counts, including local ones, so you can know your own rate before paying
anything:

```bash
cd backend && ../.venv/Scripts/python manage.py ai_costs --days 7
```

It prices what actually happened and shows what the same work would have cost on
each hosted model. Use the app normally for a week first; a couple of calls
extrapolate to nonsense.

Model defaults, verified September 2026: `deepseek-v4-flash` for small and
medium, `deepseek-v4-pro` for large. The older `deepseek-chat` /
`deepseek-reasoner` aliases were retired on 2026-07-24 and no longer route.

### Optional: PostgreSQL

Set `DATABASE_URL=postgres://user:pass@localhost:5432/english_coach` in `.env`
and re-run `migrate`. No code changes; every model is Postgres-compatible.

## Tests

```bash
cd backend && ../.venv/Scripts/python manage.py test     # 433 tests, ~4s
cd frontend && npx oxlint src && npm run build
```

## Speaking Script Studio

Generates a roleplay script pitched at your **speaking** level, with target
expressions, a sample opening, and a self-contained prompt you can paste into
ChatGPT, Gemini or Claude to run the whole roleplay there.

The pasteable prompt tells the other assistant your CEFR level, how fast to
speak, which expressions to create openings for, not to correct you mid-
conversation, and to give structured feedback when you type `FEEDBACK`.

Built-in scripts are instant and need no AI. Tick "use the local AI" for a
custom one — and if the model is down, it silently falls back to a template.

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/register/`, `POST /api/auth/login/` | Token auth |
| `GET /api/dashboard/` | Everything the home screen needs, one round trip |
| `GET /api/lessons/today/?minutes=45` | Today's adaptive time allocation |
| `GET|PATCH /api/profile/` | Goals, interests, priority skills, immersion |
| `GET|POST /api/sessions/`, `POST /api/sessions/{id}/complete/` | Study sessions |
| `POST /api/practice/speaking-scripts/generate/` | New practice script |
| `GET /api/practice/speaking-scripts/scenarios/` | Available situations |
| `GET /api/ai/status/` | Local model health and setup hints |

Errors always come back as `{"error": {"code", "message", "detail"}}` — no stack
traces, and AI failures carry a message that tells you what still works.

## Layout

```
backend/
  config/       settings (env-driven), urls
  api/          DRF serializers, views, error envelope — no business logic
  apps/
    accounts/   custom User
    profiles/   LearnerProfile, SkillProgress, StudySession, the planner
    ai/         provider abstraction, prompts, schema validation, cache, logs
    practice/   Speaking Script Studio
frontend/       Vite + React 19 + Tailwind 4
docs/           ARCHITECTURE.md, ROADMAP.md
```

See `docs/ARCHITECTURE.md` for the design decisions and their tradeoffs.
