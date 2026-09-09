import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import { skillIcon, skillLabel } from "../lib/skills";
import { Button, Card, ErrorNote, Pill, ProgressRing, SectionHeading } from "../lib/ui";

/**
 * Today's lesson: the plan made concrete.
 *
 * Each activity links to the screen that actually runs it, carrying its
 * parameters, so "what should I do today" is one click from being done rather
 * than a description the learner has to act on themselves.
 */

function activityHref(activity) {
  const params = new URLSearchParams();
  Object.entries(activity.params || {}).forEach(([key, value]) => {
    if (value != null && value !== "") params.set(key, value);
  });
  const query = params.toString();
  return `${activity.route}${query ? `?${query}` : ""}`;
}

export default function TodayLesson({ lesson, onChange }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  if (!lesson) return null;

  const complete = async (activityId) => {
    setBusy(activityId);
    setError(null);
    try {
      onChange(await api.completeActivity(lesson.id, activityId));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const regenerate = async () => {
    setBusy("regenerate");
    setError(null);
    try {
      onChange(await api.regenerateLesson());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const done = lesson.activities.filter((activity) => activity.is_complete).length;

  return (
    <section aria-labelledby="lesson-heading" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <SectionHeading id="lesson-heading" title={lesson.title} />
          {lesson.theme && (
            <p className="-mt-2 text-sm text-slate-500 dark:text-slate-400">{lesson.theme}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ProgressRing value={(done / lesson.activities.length) * 100} size={52} stroke={5}>
            <span className="text-xs font-bold tabular-nums">
              {done}/{lesson.activities.length}
            </span>
          </ProgressRing>
          <Button
            variant="ghost"
            size="sm"
            onClick={regenerate}
            loading={busy === "regenerate"}
            title="Discard today's lesson and build another"
          >
            Shuffle
          </Button>
        </div>
      </div>

      {lesson.encouragement && (
        <p className="rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">
          {lesson.encouragement}
        </p>
      )}

      <ErrorNote error={error} />

      <ol className="space-y-3">
        {lesson.activities.map((activity, index) => (
          <li key={activity.id}>
            <Card
              className={cx(
                "animate-rise transition",
                activity.is_complete && "opacity-60",
              )}
              style={{ animationDelay: `${index * 40}ms` }}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <span
                    aria-hidden="true"
                    className={cx(
                      "grid h-9 w-9 shrink-0 place-items-center rounded-xl text-lg",
                      activity.is_complete
                        ? "bg-emerald-50 dark:bg-emerald-500/15"
                        : "bg-brand-50 dark:bg-brand-500/15",
                    )}
                  >
                    {activity.is_complete ? "✓" : skillIcon(activity.kind)}
                  </span>
                  <div className="min-w-0">
                    <p
                      className={cx(
                        "font-semibold",
                        activity.is_complete && "line-through decoration-slate-400",
                      )}
                    >
                      {activity.title}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                      {activity.instructions}
                    </p>
                  </div>
                </div>
                <Pill tone="brand">{activity.minutes} min</Pill>
              </div>

              {activity.prompt && (
                <p className="mt-3 rounded-xl bg-slate-50 p-3 text-sm italic text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
                  {activity.prompt}
                </p>
              )}

              {activity.target_expressions?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span className="text-xs text-slate-400">Try to use:</span>
                  {activity.target_expressions.map((expression) => (
                    <Pill key={expression}>{expression}</Pill>
                  ))}
                </div>
              )}

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Link
                  to={activityHref(activity)}
                  className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700"
                >
                  {activity.is_complete ? "Do it again" : "Start"} →
                </Link>
                {!activity.is_complete && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => complete(activity.id)}
                    loading={busy === activity.id}
                  >
                    Mark done
                  </Button>
                )}
                <span className="ml-auto text-xs text-slate-400">
                  {skillLabel(activity.kind)}
                </span>
              </div>
            </Card>
          </li>
        ))}
      </ol>

      {lesson.status === "completed" && (
        <Card className="bg-emerald-50 text-center ring-emerald-200 dark:bg-emerald-500/10 dark:ring-emerald-500/20">
          <p className="text-2xl" aria-hidden="true">
            🎉
          </p>
          <p className="mt-2 font-semibold text-emerald-900 dark:text-emerald-200">
            Today's lesson is done.
          </p>
          <p className="mt-1 text-sm text-emerald-800 dark:text-emerald-300/90">
            Tomorrow's plan will shift based on how today went.
          </p>
        </Card>
      )}
    </section>
  );
}
