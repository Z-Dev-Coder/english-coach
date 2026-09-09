import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
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
  // The single most useful thing on the whole screen: the next unfinished step.
  const next = lesson.activities.find((activity) => !activity.is_complete);

  return (
    <section aria-labelledby="lesson-heading" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <SectionHeading id="lesson-heading" title={lesson.title} />
          {lesson.theme && (
            <p className="-mt-2 text-sm text-ink-2 dark:text-white/55">{lesson.theme}</p>
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

      {next && (
        <Link
          to={activityHref(next)}
          className="flex items-center justify-between gap-3 rounded-xl bg-ink px-4 py-3.5 text-white transition hover:opacity-90 dark:bg-white dark:text-black"
        >
          <span className="min-w-0">
            <span className="micro block text-white/50 dark:text-black/50">Do this next</span>
            <span className="block truncate font-semibold">{next.title}</span>
          </span>
          <span className="flex shrink-0 items-center gap-2 text-sm font-semibold">
            {next.minutes} min <span aria-hidden="true">→</span>
          </span>
        </Link>
      )}

      {lesson.encouragement && (
        <p className="text-[13px] leading-relaxed text-ink-2 dark:text-white/55">
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
                      "grid h-8 w-8 shrink-0 place-items-center rounded-lg ring-1",
                      activity.is_complete
                        ? "ring-[color:var(--color-good-ink)]/25"
                        : "ring-[color:var(--color-line)] dark:ring-white/12",
                    )}
                  >
                    {activity.is_complete ? (
                      <span className="text-[color:var(--color-good-ink)]">✓</span>
                    ) : (
                      <Icon name={activity.kind} size={16} className="text-ink-2" />
                    )}
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
                    {!activity.is_complete && (
                      <p className="mt-1 text-sm leading-relaxed text-ink-2 dark:text-white/55">
                        {activity.instructions}
                      </p>
                    )}
                  </div>
                </div>
                <Pill tone="brand">{activity.minutes} min</Pill>
              </div>

              {activity.prompt && !activity.is_complete && (
                <p className="mt-3 rounded-xl bg-sunken p-3 text-sm italic text-ink-2 dark:bg-white/[0.04]">
                  {activity.prompt}
                </p>
              )}

              {activity.target_expressions?.length > 0 && !activity.is_complete && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span className="text-xs text-ink-3">Try to use:</span>
                  {activity.target_expressions.map((expression) => (
                    <Pill key={expression}>{expression}</Pill>
                  ))}
                </div>
              )}

              {!activity.is_complete && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Link
                    to={activityHref(activity)}
                    className="rounded-full bg-ink px-3.5 py-1.5 text-[13px] font-medium text-white transition hover:opacity-90 dark:bg-white dark:text-black"
                  >
                    Start →
                  </Link>
                  <button
                    onClick={() => complete(activity.id)}
                    disabled={busy === activity.id}
                    className="text-xs text-ink-3 underline-offset-2 hover:text-ink-2 hover:underline dark:hover:text-black-3"
                  >
                    mark done
                  </button>
                </div>
              )}
            </Card>
          </li>
        ))}
      </ol>

      {lesson.status === "completed" && (
        <Card className="border-dashed text-center">
          <p className="micro" aria-hidden="true">
            ( done )
          </p>
          <p className="mt-2 font-semibold text-ink dark:text-white/85">
            Today's lesson is done.
          </p>
          <p className="mt-1 text-[13px] text-ink-2 dark:text-white/55">
            Tomorrow's plan will shift based on how today went.
          </p>
        </Card>
      )}
    </section>
  );
}
