import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import {
  Button,
  Card,
  CardSkeleton,
  EmptyState,
  ErrorNote,
  Pill,
  ProgressRing,
  HowTo,
  SectionHeading,
  StatTile,
} from "../lib/ui";

/** The four FSRS grades. Order matters: it is the keyboard order too. */
const RATINGS = [
  { value: 1, label: "Again", hint: "I forgot", key: "1", tone: "rose" },
  { value: 2, label: "Hard", hint: "Struggled", key: "2", tone: "amber" },
  { value: 3, label: "Good", hint: "Got it", key: "3", tone: "emerald" },
  { value: 4, label: "Easy", hint: "Instant", key: "4", tone: "sky" },
];

const RATING_STYLES = {
  rose: "bg-rose-50 text-rose-700 ring-rose-200 hover:bg-rose-100 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/20",
  amber:
    "bg-amber-50 text-amber-700 ring-amber-200 hover:bg-amber-100 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/20",
  emerald:
    "bg-emerald-50 text-emerald-700 ring-emerald-200 hover:bg-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/20",
  sky: "bg-sky-50 text-sky-700 ring-sky-200 hover:bg-sky-100 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/20",
};

const STATE_TONES = {
  new: "brand",
  learning: "default",
  review: "default",
  weak: "warn",
  mastered: "good",
};

function formatInterval(days) {
  if (days < 1) return "today";
  if (days === 1) return "tomorrow";
  if (days < 30) return `in ${days} days`;
  if (days < 365) return `in ${Math.round(days / 30)} months`;
  return `in ${(days / 365).toFixed(1)} years`;
}

/** One card. Answer is hidden until the learner commits to recalling it —
 *  that commitment is what makes retrieval practice work, so the reveal is a
 *  deliberate step rather than everything being visible at once. */
function ReviewCard({ item, onAnswer, submitting }) {
  const [revealed, setRevealed] = useState(false);
  const { progress, prompt, exercise } = item;
  const expression = progress.expression;
  const example = expression.examples?.[0];

  useEffect(() => {
    const onKey = (event) => {
      if (event.target.matches("input, textarea")) return;
      if (!revealed && (event.key === " " || event.key === "Enter")) {
        event.preventDefault();
        setRevealed(true);
        return;
      }
      if (revealed && ["1", "2", "3", "4"].includes(event.key)) {
        event.preventDefault();
        onAnswer(Number(event.key));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [revealed, onAnswer]);

  return (
    <Card className="animate-rise">
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <Pill tone={STATE_TONES[progress.state] ?? "default"}>{progress.state}</Pill>
        <Pill>{expression.kind.replace(/_/g, " ")}</Pill>
        <Pill>{expression.cefr_level}</Pill>
        {progress.lapses > 0 && <Pill tone="warn">forgotten {progress.lapses}×</Pill>}
      </div>

      <p className="text-sm font-medium text-ink-3">{prompt.instruction}</p>
      <p className="mt-3 text-2xl font-bold leading-snug tracking-tight sm:text-3xl">
        {prompt.front}
      </p>
      {prompt.support && !revealed && (
        <p className="mt-2 text-ink-2 dark:text-white/55">{prompt.support}</p>
      )}

      {!revealed ? (
        <div className="mt-8">
          <Button size="lg" onClick={() => setRevealed(true)} className="w-full sm:w-auto">
            Show answer
          </Button>
          <p className="mt-3 text-xs text-ink-3">
            Try to answer out loud first — pressing space works too.
          </p>
        </div>
      ) : (
        <div className="animate-rise">
          <div className="mt-6 border-t border-[color:var(--color-line)] pt-5 dark:border-white/5">
            <p className="text-xl font-semibold">{expression.text}</p>
            <p className="mt-1 text-ink-2 dark:text-white/70">{expression.meaning}</p>

            {example && (
              <p className="mt-4 border-l-2 border-ink/25 pl-3 text-ink-2 italic dark:text-ink-3">
                {example.text}
              </p>
            )}

            {expression.common_mistake && (
              <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
                <span className="font-semibold">Watch out: </span>
                {expression.common_mistake}
              </p>
            )}

            {expression.register && expression.register !== "neutral" && (
              <p className="mt-3 text-xs text-ink-3">
                Register: <span className="font-medium">{expression.register}</span>
              </p>
            )}
          </div>

          <div className="mt-6">
            <p className="mb-2 text-sm font-medium text-ink-2">How did that go?</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {RATINGS.map((rating) => (
                <button
                  key={rating.value}
                  disabled={submitting}
                  onClick={() => onAnswer(rating.value)}
                  className={cx(
                    "rounded-xl px-3 py-3 text-left ring-1 transition active:scale-[0.97] disabled:opacity-50",
                    RATING_STYLES[rating.tone],
                  )}
                >
                  <span className="block text-sm font-semibold">{rating.label}</span>
                  <span className="block text-xs opacity-70">{rating.hint}</span>
                  <span className="mt-1 block text-[10px] font-medium opacity-50">
                    press {rating.key}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <p className="mt-5 text-xs text-ink-3">
        Exercise: {exercise.replace(/_/g, " ")}
        {progress.reps > 0 && ` · seen ${progress.reps}×`}
      </p>
    </Card>
  );
}

function SessionComplete({ answered, stats, onReload }) {
  return (
    <div className="space-y-6">
      <Card className="animate-rise text-center">
        <div className="text-4xl" aria-hidden="true">
          🎉
        </div>
        <h2 className="mt-3 text-xl font-bold">Review done</h2>
        <p className="mt-1 text-ink-2 dark:text-white/55">
          {answered} {answered === 1 ? "card" : "cards"} reviewed. Everything due today is
          cleared.
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <Button variant="secondary" onClick={onReload}>
            Check for more
          </Button>
        </div>
      </Card>

      {stats && <ForecastCard stats={stats} />}
    </div>
  );
}

function ForecastCard({ stats }) {
  const peak = Math.max(1, ...stats.forecast.map((day) => day.count));
  return (
    <Card>
      <SectionHeading title="Coming up" />
      <div className="flex items-end gap-2" role="list">
        {stats.forecast.map((day, index) => (
          <div key={day.date} className="flex flex-1 flex-col items-center gap-1.5" role="listitem">
            <span className="text-xs tabular-nums text-ink-3">{day.count}</span>
            <div
              className="w-full rounded-t-md bg-gradient-to-t from-brand-500 to-violet-400 transition-all duration-700"
              style={{ height: `${Math.max(4, (day.count / peak) * 64)}px` }}
              title={`${day.count} due`}
            />
            <span className="text-[10px] text-ink-3">
              {index === 0
                ? "today"
                : new Date(day.date).toLocaleDateString(undefined, { weekday: "narrow" })}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-ink-3">
        Your schedule for the next week. Spikes are normal — the scheduler spreads them out as you
        keep answering.
      </p>
    </Card>
  );
}

export default function Review() {
  const [queue, setQueue] = useState(null);
  const [index, setIndex] = useState(0);
  const [answered, setAnswered] = useState(0);
  const [lastResult, setLastResult] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(() => {
    setError(null);
    setIndex(0);
    api
      .reviewQueue()
      .then((data) => setQueue(data.items))
      .catch(setError);
    api.reviewStats().then(setStats).catch(() => setStats(null));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const current = queue?.[index];

  const submit = useCallback(
    async (rating) => {
      if (!current || submitting) return;
      setSubmitting(true);
      try {
        const result = await api.reviewAnswer({
          progress_id: current.progress.id,
          rating,
          exercise: current.exercise,
        });
        setLastResult({ rating, days: result.next_due_in_days });
        setAnswered((count) => count + 1);
        setIndex((position) => position + 1);
      } catch (err) {
        setError(err);
      } finally {
        setSubmitting(false);
      }
    },
    [current, submitting],
  );

  if (error && !queue) return <ErrorNote error={error} onRetry={load} />;
  if (!queue) {
    return (
      <div className="max-w-2xl space-y-6">
        <CardSkeleton lines={4} />
      </div>
    );
  }

  const total = queue.length;
  const progressPct = total ? (index / total) * 100 : 100;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Review</h1>
          <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
            Spaced repetition. Each answer decides when you next see the card.
          </p>
        </div>
        {total > 0 && (
          <ProgressRing value={progressPct} size={64} stroke={6}>
            <span className="text-sm font-bold tabular-nums">
              {Math.min(index, total)}/{total}
            </span>
          </ProgressRing>
        )}
      </header>

      <HowTo
        id="review"
        title="How review works"
        steps={[
          "Try to answer out loud before you reveal — the effort is what makes it stick.",
          "Press space to show the answer, then 1–4 to say how it went.",
          "Be honest. Saying “Easy” when you struggled just means you see it too late next time.",
        ]}
      />

      {lastResult && index > 0 && index <= total && (
        <p className="text-sm text-ink-3" aria-live="polite">
          Last card scheduled {formatInterval(lastResult.days)}.
        </p>
      )}

      <ErrorNote error={error} />

      {total === 0 ? (
        <>
          <EmptyState
            icon="✅"
            title="Nothing due right now"
            body="Your review queue is empty. Add expressions as you meet them, or seed the starter set with: python manage.py seed_vocabulary --user <you>"
            action={
              <Button variant="secondary" onClick={load}>
                Refresh
              </Button>
            }
          />
          {stats && stats.total_tracked > 0 && <ForecastCard stats={stats} />}
        </>
      ) : current ? (
        // key resets the revealed state between cards, so the next answer
        // never flashes into view before the learner has recalled it.
        <ReviewCard
          key={current.progress.id}
          item={current}
          onAnswer={submit}
          submitting={submitting}
        />
      ) : (
        <SessionComplete answered={answered} stats={stats} onReload={load} />
      )}

      {stats && stats.total_tracked > 0 && (
        <Card>
          <SectionHeading title="Your vocabulary" />
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Tracked" value={stats.total_tracked} />
            <StatTile label="Mastered" value={stats.by_state.mastered ?? 0} tone="brand" />
            <StatTile label="Weak" value={stats.by_state.weak ?? 0} tone="warn" />
            <StatTile
              label="Success"
              value={stats.success_rate == null ? "—" : `${Math.round(stats.success_rate * 100)}%`}
            />
          </dl>
        </Card>
      )}
    </div>
  );
}
