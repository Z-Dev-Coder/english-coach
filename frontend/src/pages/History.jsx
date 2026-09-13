import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { skillLabel } from "../lib/skills";
import { CardSkeleton, EmptyState, ErrorNote, Pill } from "../lib/ui";

/**
 * Every lesson the learner has had, to go back through.
 *
 * Lessons renew on completion, so the home page only ever shows the current
 * one -- which meant a finished lesson, with its passage, its prompts and its
 * scripts, was simply gone from view. This is where they live afterwards.
 *
 * Opening one replays it in review mode: the same runner, every step open, and
 * the lesson's own progress left alone. Exercises that score an answer still
 * record the attempt, because redoing one is genuine practice.
 */

const FILTERS = [
  { key: "all", label: "All" },
  { key: "completed", label: "Finished" },
  { key: "open", label: "In progress" },
  { key: "abandoned", label: "Replaced" },
];

const STATUS = {
  completed: { label: "Finished", tone: "text-[color:var(--color-good-ink)]" },
  abandoned: { label: "Replaced", tone: "text-ink-3" },
  in_progress: { label: "In progress", tone: "text-[color:var(--color-accent)]" },
  ready: { label: "Not started", tone: "text-[color:var(--color-accent)]" },
};

function formatDate(value) {
  try {
    return new Date(value).toLocaleDateString(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

function LessonRow({ lesson }) {
  const [open, setOpen] = useState(false);
  const status = STATUS[lesson.status] ?? STATUS.ready;
  const activities = lesson.activities ?? [];
  const done = activities.filter((activity) => activity.is_complete).length;
  const current = lesson.status === "ready" || lesson.status === "in_progress";

  return (
    <li className="rounded-2xl bg-surface ring-1 ring-[color:var(--color-line)] dark:bg-white/[0.03] dark:ring-white/10">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-start gap-4 p-4 text-left"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cx("micro", status.tone)}>{status.label}</span>
            <span className="micro">{formatDate(lesson.date)}</span>
          </div>
          <p className="mt-1 font-semibold">{lesson.title}</p>
          {lesson.theme && (
            <p className="mt-0.5 text-[13px] text-ink-2 dark:text-white/60">{lesson.theme}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(lesson.focus_skills ?? []).map((skill) => (
              <Pill key={skill}>{skillLabel(skill)}</Pill>
            ))}
            <Pill>
              {done}/{activities.length} steps
            </Pill>
          </div>
        </div>
        <Icon
          name="arrowRight"
          size={16}
          className={cx("mt-1 shrink-0 text-ink-3 transition", open && "rotate-90")}
        />
      </button>

      {open && (
        <div className="border-t border-[color:var(--color-line)] px-4 pb-4 pt-3 dark:border-white/10">
          <ol className="space-y-2">
            {activities.map((activity, index) => (
              <li key={activity.id} className="flex gap-3 text-[14px]">
                <span
                  className={cx(
                    "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px]",
                    activity.is_complete
                      ? "bg-[color:var(--color-accent)] text-white"
                      : "ring-1 ring-[color:var(--color-line)] text-ink-3 dark:ring-white/15",
                  )}
                >
                  {activity.is_complete ? <Icon name="check" size={11} /> : index + 1}
                </span>
                <div className="min-w-0">
                  <p className="font-medium">{activity.title}</p>
                  <p className="micro">
                    {skillLabel(activity.kind)} · {activity.minutes} min
                  </p>
                  {activity.prompt && (
                    <p className="mt-0.5 text-[13px] italic text-ink-2 dark:text-white/60">
                      {activity.prompt}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>

          <div className="mt-4 flex flex-wrap gap-2">
            {current ? (
              // The live lesson is continued, not reviewed: its steps still
              // count, and it resumes at the first unfinished one.
              <Link
                to="/lesson"
                className="rounded-full bg-ink px-4 py-1.5 text-[13px] font-medium text-white dark:bg-white dark:text-black"
              >
                Continue this lesson
              </Link>
            ) : (
              <Link
                to={`/lesson/${lesson.id}`}
                className="rounded-full bg-ink px-4 py-1.5 text-[13px] font-medium text-white dark:bg-white dark:text-black"
              >
                Go through it again
              </Link>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export default function History() {
  const [lessons, setLessons] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all");

  const load = useCallback(() => {
    setError(null);
    api
      .lessons()
      .then((data) => setLessons(data.results ?? data))
      .catch(setError);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const shown = useMemo(() => {
    if (!lessons) return [];
    if (filter === "all") return lessons;
    if (filter === "open") {
      return lessons.filter((lesson) => ["ready", "in_progress"].includes(lesson.status));
    }
    return lessons.filter((lesson) => lesson.status === filter);
  }, [lessons, filter]);

  const finished = lessons?.filter((lesson) => lesson.status === "completed").length ?? 0;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="display text-[38px]">History</h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          Every lesson you&rsquo;ve had. Open one to go back through its steps. Reviewing doesn&rsquo;t
          reopen the lesson, but answers you check still count as practice.
        </p>
      </header>

      <ErrorNote error={error} onRetry={load} />

      {!lessons ? (
        <CardSkeleton lines={4} />
      ) : lessons.length === 0 ? (
        <EmptyState
          icon="📘"
          title="No lessons yet"
          body="Your first lesson appears on the home page. Once you've done it, it shows up here."
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              {FILTERS.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setFilter(item.key)}
                  className={cx(
                    "rounded-full px-3 py-1 text-[13px] transition",
                    filter === item.key
                      ? "bg-ink text-white dark:bg-white dark:text-black"
                      : "text-ink-2 ring-1 ring-[color:var(--color-line)] hover:bg-sunken dark:ring-white/10",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <span className="micro">
              {finished} finished · {lessons.length} total
            </span>
          </div>

          {shown.length === 0 ? (
            <p className="text-[14px] text-ink-3">Nothing here under this filter.</p>
          ) : (
            <ul className="space-y-3">
              {shown.map((lesson) => (
                <LessonRow key={lesson.id} lesson={lesson} />
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
