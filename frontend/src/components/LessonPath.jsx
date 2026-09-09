import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { skillLabel } from "../lib/skills";
import { Button, ErrorNote, Pill, ProgressRing, SectionHeading } from "../lib/ui";

/**
 * Today's lesson as a path.
 *
 * A list tells you what there is; a path tells you where you are. The
 * connecting line fills in behind you, so progress is visible without a
 * separate progress bar explaining it.
 *
 * One honest limit on the metaphor: Duolingo's path is a fixed curriculum you
 * climb over months, and this app has no such thing — the plan is recomputed
 * every day from measured weakness, so a permanent path would be a lie about
 * how it works. What is drawn here is *today*, which really is a sequence.
 */

function activityHref(activity) {
  const params = new URLSearchParams();
  Object.entries(activity.params || {}).forEach(([key, value]) => {
    if (value != null && value !== "") params.set(key, value);
  });
  const query = params.toString();
  return `${activity.route}${query ? `?${query}` : ""}`;
}

// Tried a lateral drift to make the column read as a winding route. At this
// scale the connector then meets the next node off-centre, which looks like a
// rendering bug rather than a curve — and the labels sit beside the nodes, so
// real winding would break the text alignment anyway. A straight trail with
// distinct node states carries the same meaning and stays precise.

function Node({ activity, state }) {
  const isDone = state === "done";
  const isCurrent = state === "current";

  return (
    <span
      className={cx(
        "relative z-10 grid h-11 w-11 shrink-0 place-items-center rounded-full transition",
        isDone && "bg-[color:var(--color-accent)] text-white",
        isCurrent &&
          "bg-ink text-white ring-4 ring-[color:var(--color-accent)]/30 dark:bg-white dark:text-black",
        !isDone && !isCurrent &&
          "bg-paper text-ink-3 ring-1 ring-[color:var(--color-line)]",
      )}
    >
      {isDone ? (
        <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="m5 10.5 3.5 3.5L15 7"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <Icon name={activity.kind} size={19} />
      )}
    </span>
  );
}

export default function LessonPath({ lesson, onChange }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  if (!lesson) return null;

  const activities = lesson.activities;
  const done = activities.filter((a) => a.is_complete).length;
  const currentIndex = activities.findIndex((a) => !a.is_complete);

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

  return (
    <section aria-labelledby="lesson-heading" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <SectionHeading id="lesson-heading" title={lesson.title} />
          {lesson.theme && (
            <p className="-mt-2 text-[13px] text-ink-2">{lesson.theme}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ProgressRing value={(done / activities.length) * 100} size={46} stroke={4}>
            <span className="font-mono text-[11px] tabular-nums">
              {done}/{activities.length}
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
        <p className="text-[13px] leading-relaxed text-ink-2">{lesson.encouragement}</p>
      )}

      <ErrorNote error={error} />

      <ol className="relative">
        {activities.map((activity, index) => {
          const state = activity.is_complete
            ? "done"
            : index === currentIndex
              ? "current"
              : "todo";
          const isLast = index === activities.length - 1;

          return (
            <li key={activity.id} className="relative flex gap-4 pb-5 last:pb-0">
              {/* The trail. Filled behind you, hairline ahead. */}
              {!isLast && (
                <span
                  aria-hidden="true"
                  className={cx(
                    "absolute top-11 bottom-0 w-px",
                    activity.is_complete
                      ? "bg-[color:var(--color-accent)]"
                      : "bg-[color:var(--color-line)]",
                  )}
                  style={{ left: "22px" }}
                />
              )}

              <Node activity={activity} state={state} />

              <div
                className={cx(
                  "min-w-0 flex-1 pt-1.5 transition",
                  state === "todo" && "opacity-55",
                )}
              >
                <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                  {state === "current" && (
                    <span className="micro text-[color:var(--color-accent)]">You are here</span>
                  )}
                  <h3
                    className={cx(
                      "text-[15px] font-semibold",
                      activity.is_complete && "line-through decoration-ink-3",
                    )}
                  >
                    {activity.title}
                  </h3>
                  <Pill>{activity.minutes} min</Pill>
                </div>

                {!activity.is_complete && (
                  <>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">
                      {activity.instructions}
                    </p>

                    {activity.prompt && (
                      <p className="mt-2.5 border-l border-[color:var(--color-line)] pl-3 text-[13px] italic text-ink-2">
                        {activity.prompt}
                      </p>
                    )}

                    {activity.target_expressions?.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                        <span className="micro">use</span>
                        {activity.target_expressions.map((expression) => (
                          <Pill key={expression}>{expression}</Pill>
                        ))}
                      </div>
                    )}

                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <Link
                        to={activityHref(activity)}
                        className={cx(
                          "rounded-full px-4 py-1.5 text-[13px] font-medium transition",
                          state === "current"
                            ? "bg-ink text-white hover:opacity-90 dark:bg-white dark:text-black"
                            : "text-ink ring-1 ring-[color:var(--color-line)] hover:bg-sunken",
                        )}
                      >
                        {state === "current" ? "Start →" : "Jump to this"}
                      </Link>
                      <button
                        onClick={() => complete(activity.id)}
                        disabled={busy === activity.id}
                        className="micro hover:text-ink"
                      >
                        mark done
                      </button>
                      <span className="micro ml-auto">{skillLabel(activity.kind)}</span>
                    </div>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {lesson.status === "completed" && (
        <div className="border-t border-[color:var(--color-accent)] pt-4 text-center">
          <p className="micro text-[color:var(--color-accent)]">( day complete )</p>
          <p className="mt-2 text-[15px] font-semibold">That is today's lesson finished.</p>
          <p className="mt-1 text-[13px] text-ink-2">
            Tomorrow's plan will shift based on how today went.
          </p>
        </div>
      )}
    </section>
  );
}
