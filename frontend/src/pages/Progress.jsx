import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import { skillIcon, skillLabel } from "../lib/skills";
import {
  Button,
  Card,
  CardSkeleton,
  EmptyState,
  ErrorNote,
  HowTo,
  Pill,
  ProgressBar,
  SectionHeading,
  StatTile,
} from "../lib/ui";

/**
 * Progress and the mistake bank.
 *
 * The honest framing matters here: hours studied is activity, not improvement.
 * This page leads with what changed — skills measured, mistakes retired — and
 * treats volume as context rather than as the achievement.
 */

const STATUS_TONES = { active: "warn", improving: "brand", resolved: "good" };

function MistakeRow({ mistake, onAvoided, busy }) {
  return (
    <li className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0">
          <span className="rounded bg-rose-100 px-1 line-through dark:bg-rose-500/20">
            {mistake.incorrect}
          </span>
          <span className="mx-1.5 text-ink-3">→</span>
          <span className="rounded bg-emerald-100 px-1 font-medium dark:bg-emerald-500/20">
            {mistake.correct}
          </span>
        </p>
        <div className="flex shrink-0 items-center gap-1.5">
          <Pill tone={STATUS_TONES[mistake.status] ?? "default"}>{mistake.status}</Pill>
          {mistake.occurrences > 1 && <Pill tone="warn">×{mistake.occurrences}</Pill>}
        </div>
      </div>

      {mistake.explanation && (
        <p className="mt-2 text-sm text-ink-2 dark:text-white/70">{mistake.explanation}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span className="text-xs text-ink-3">{mistake.category.replace(/_/g, " ")}</span>
        {mistake.status === "active" && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onAvoided(mistake.id)}
            loading={busy === mistake.id}
            title="Tell the coach you got this right"
          >
            I've got this now
          </Button>
        )}
        {mistake.times_avoided > 0 && (
          <span className="text-xs text-emerald-600 dark:text-emerald-400">
            avoided {mistake.times_avoided}×
          </span>
        )}
      </div>
    </li>
  );
}

export default function Progress() {
  const [dashboard, setDashboard] = useState(null);
  const [summary, setSummary] = useState(null);
  const [mistakes, setMistakes] = useState([]);
  const [practice, setPractice] = useState([]);
  const [skills, setSkills] = useState(null);
  const [reviewStats, setReviewStats] = useState(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    api.dashboard().then(setDashboard).catch(setError);
    api.mistakeSummary().then(setSummary).catch(() => setSummary(null));
    api
      .mistakes()
      .then((data) => setMistakes(data.results ?? data))
      .catch(() => setMistakes([]));
    api
      .mistakePractice()
      .then((data) => setPractice(data.items))
      .catch(() => setPractice([]));
    api.skillSummary().then(setSkills).catch(() => setSkills(null));
    api.reviewStats().then(setReviewStats).catch(() => setReviewStats(null));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const markAvoided = async (id) => {
    setBusy(id);
    try {
      const updated = await api.mistakeAvoided(id);
      setMistakes((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  if (error && !dashboard) return <ErrorNote error={error} onRetry={load} />;
  if (!dashboard) {
    return (
      <div className="space-y-6">
        {Array.from({ length: 3 }).map((_, index) => (
          <CardSkeleton key={index} lines={4} />
        ))}
      </div>
    );
  }

  const visible = filter
    ? mistakes.filter((mistake) => mistake.status === filter)
    : mistakes;
  const measured = dashboard.skills.filter((skill) => skill.confidence > 0);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Progress</h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          What has actually changed — not how long you sat here.
        </p>
      </header>

      <HowTo
        id="progress"
        title="What this page is for"
        steps={[
          "Skill scores move only when you actually do an activity, not when you browse.",
          "Anything you get wrong twice becomes a task under “Work on these today”.",
          "Press “I've got this now” when a mistake stops happening, and it retires.",
        ]}
      />

      <Card>
        <SectionHeading title="Where you are" />
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile label="Streak" value={dashboard.streak_days} unit="days" tone="brand" />
          <StatTile label="Skills measured" value={`${measured.length}/${dashboard.skills.length}`} />
          <StatTile
            label="Words tracked"
            value={dashboard.review?.total_tracked ?? 0}
          />
          <StatTile
            label="Mistakes fixed"
            value={summary?.resolved ?? 0}
            tone="brand"
          />
        </dl>
        <p className="mt-4 text-xs leading-relaxed text-ink-3">
          Time studied is deliberately not the headline. Ten hours of activity is not ten hours of
          improvement, and treating it as progress is the easiest way to fool yourself.
        </p>
      </Card>

      <Card>
        <SectionHeading title="Skills" />
        <div className="grid gap-4 sm:grid-cols-2">
          {dashboard.skills.map((skill) => (
            <ProgressBar
              key={skill.skill}
              value={skill.score}
              label={
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden="true">{skillIcon(skill.skill)}</span>
                  {skillLabel(skill.skill)}
                </span>
              }
              sublabel={
                skill.confidence > 0
                  ? `${skill.level} · ${Math.round(skill.confidence * 100)}% sure`
                  : "not measured"
              }
              weak={skill.is_weak}
            />
          ))}
        </div>
        {skills && Object.keys(skills).length > 0 && (
          <div className="mt-5 border-t border-[color:var(--color-line)] pt-4 dark:border-white/5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
              Last 30 days
            </p>
            <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
              {Object.entries(skills).map(([skill, stats]) => (
                <li key={skill} className="flex justify-between text-ink-2 dark:text-white/70">
                  <span>{skillLabel(skill)}</span>
                  <span className="tabular-nums text-ink-3">
                    {stats.attempts} attempts
                    {stats.mean_accuracy != null &&
                      ` · ${Math.round(stats.mean_accuracy * 100)}%`}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {practice.length > 0 && (
        <Card className="ring-amber-200 dark:ring-amber-500/20">
          <SectionHeading title="Work on these today" />
          <p className="-mt-1 mb-4 text-sm text-ink-2 dark:text-white/55">
            You have made each of these at least twice. They are the ones worth fixing on purpose.
          </p>
          <ul className="space-y-3">
            {practice.map((item) => (
              <li key={item.id} className="rounded-xl bg-amber-50 p-4 dark:bg-amber-500/10">
                <p>
                  <span className="line-through opacity-60">{item.incorrect}</span>
                  <span className="mx-1.5">→</span>
                  <span className="font-semibold">{item.correct}</span>
                </p>
                {item.explanation && (
                  <p className="mt-1 text-sm text-ink-2 dark:text-white/70">
                    {item.explanation}
                  </p>
                )}
                <p className="mt-2 text-sm font-medium text-amber-900 dark:text-amber-200">
                  {item.task}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <SectionHeading
          title="Mistake bank"
          action={
            summary ? (
              <span className="text-sm text-ink-3">
                {summary.active} active · {summary.improving} improving · {summary.resolved} fixed
              </span>
            ) : null
          }
        />

        <div className="mb-4 flex flex-wrap gap-2">
          {["", "active", "improving", "resolved"].map((value) => (
            <button
              key={value || "all"}
              onClick={() => setFilter(value)}
              className={cx(
                "rounded-full px-3 py-1.5 text-sm transition",
                filter === value
                  ? "bg-ink text-white"
                  : "bg-sunken text-ink-2 hover:bg-[color:var(--color-line)] dark:bg-white/[0.05] dark:text-ink-3",
              )}
            >
              {value || "all"}
            </button>
          ))}
        </div>

        {visible.length === 0 ? (
          <EmptyState
            icon="✨"
            title="No mistakes recorded yet"
            body="Write something or have a conversation, and anything you get wrong will be collected here — so the same error stops slipping past."
          />
        ) : (
          <ul className="space-y-3">
            {visible.slice(0, 20).map((mistake) => (
              <MistakeRow
                key={mistake.id}
                mistake={mistake}
                onAvoided={markAvoided}
                busy={busy}
              />
            ))}
          </ul>
        )}
      </Card>

      {reviewStats?.forecast && (
        <Card>
          <SectionHeading title="Review load ahead" />
          <div className="flex items-end gap-2">
            {reviewStats.forecast.map((day, index) => {
              const peak = Math.max(1, ...reviewStats.forecast.map((d) => d.count));
              return (
                <div key={day.date} className="flex flex-1 flex-col items-center gap-1.5">
                  <span className="text-xs tabular-nums text-ink-3">{day.count}</span>
                  <div
                    className="w-full rounded-t-md bg-gradient-to-t from-brand-500 to-violet-400"
                    style={{ height: `${Math.max(4, (day.count / peak) * 56)}px` }}
                  />
                  <span className="text-[10px] text-ink-3">
                    {index === 0
                      ? "today"
                      : new Date(day.date).toLocaleDateString(undefined, { weekday: "narrow" })}
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
