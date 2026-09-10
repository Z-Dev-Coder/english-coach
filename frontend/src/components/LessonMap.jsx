import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { skillLabel } from "../lib/skills";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { Button, ErrorNote, Pill, SectionHeading } from "../lib/ui";

/**
 * Today's lesson as a horizontal map.
 *
 * Nodes sit on a curve that scrolls sideways; the trail behind you is drawn in
 * the accent, the road ahead as a hairline. Selecting a node opens its detail
 * below rather than expanding in place, so the map keeps a fixed height and the
 * route stays readable at a glance.
 *
 * One honest limit on the metaphor: Duolingo's map is a fixed curriculum
 * climbed over months. This app recomputes the plan every morning from measured
 * weakness, so a permanent map would misrepresent it. This is today's route.
 */

const STEP_X = 128;   // horizontal spacing between nodes
const AMPLITUDE = 22; // how far the route rises and falls
const MID_Y = 46;
const NODE = 44;
// Just enough to hold the curve, the node and its number — the first version
// left forty wasted pixels above and below the route.
const MAP_HEIGHT = MID_Y + AMPLITUDE + NODE / 2 + 18;

function activityHref(activity) {
  const params = new URLSearchParams();
  Object.entries(activity.params || {}).forEach(([key, value]) => {
    if (value != null && value !== "") params.set(key, value);
  });
  const query = params.toString();
  return `${activity.route}${query ? `?${query}` : ""}`;
}

/** Smooth curve through the node centres, as a cubic path. */
function routePath(points) {
  if (points.length < 2) return "";
  return points.reduce((d, point, i) => {
    if (i === 0) return `M ${point.x} ${point.y}`;
    const previous = points[i - 1];
    const midX = (previous.x + point.x) / 2;
    return `${d} C ${midX} ${previous.y}, ${midX} ${point.y}, ${point.x} ${point.y}`;
  }, "");
}

export default function LessonMap({ lesson, onChange }) {
  const activities = lesson?.activities ?? [];
  const currentIndex = activities.findIndex((a) => !a.is_complete);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  // The current step is what you want to see unless you have picked another.
  const openIndex = selected ?? (currentIndex === -1 ? activities.length - 1 : currentIndex);

  const points = useMemo(
    () =>
      activities.map((_, i) => ({
        x: 40 + i * STEP_X,
        y: MID_Y + Math.sin(i * 0.9) * AMPLITUDE,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [lesson?.id, activities.length],
  );

  if (!lesson) return null;

  const done = activities.filter((a) => a.is_complete).length;
  const width = 80 + Math.max(0, activities.length - 1) * STEP_X;
  const open = activities[openIndex];

  const complete = async (activityId) => {
    setBusy(activityId);
    setError(null);
    try {
      onChange(await api.completeActivity(lesson.id, activityId));
      setSelected(null);
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
      setSelected(null);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  // How far along the route the accent should reach.
  const travelled = done === 0 ? 0 : done / Math.max(1, activities.length - 1);

  return (
    <section aria-labelledby="lesson-heading" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <SectionHeading id="lesson-heading" title={lesson.title} />
          {lesson.theme && <p className="-mt-2 text-[13px] text-ink-2">{lesson.theme}</p>}
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] tabular-nums text-ink-2">
            {done}/{activities.length}
          </span>
          <Button variant="ghost" size="sm" onClick={regenerate} loading={busy === "regenerate"}>
            Shuffle
          </Button>
        </div>
      </div>

      {/* The map. Scrolls sideways when the day is long. */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-surface to-[color-mix(in_oklab,var(--color-surface)_92%,var(--color-ink))] ring-1 ring-[color:var(--color-line)] dark:from-white/[0.05] dark:to-white/[0.015] dark:ring-white/10">
        <div aria-hidden="true" className="techgrid absolute inset-0 opacity-50" />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--color-ink)]/15 to-transparent dark:via-white/25"
        />
        {/* Light where the learner currently is, so the eye lands on the step
            they are meant to do next rather than on the middle of the row. */}
        <div
          aria-hidden="true"
          className="glow bg-[color:var(--color-accent)]/25"
          style={{ width: 260, height: 260, left: Math.max(0, (points[currentIndex]?.x ?? 40) - 130), top: -90 }}
        />
        <div className="relative overflow-x-auto p-5">
        <div className="relative" style={{ width, height: MAP_HEIGHT }}>
          <svg
            className="absolute inset-0 overflow-visible"
            width={width}
            height={MAP_HEIGHT}
            aria-hidden="true"
          >
            <path
              d={routePath(points)}
              fill="none"
              stroke="var(--color-line)"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* The distance already covered, drawn over the top. */}
            <path
              d={routePath(points)}
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="2"
              strokeLinecap="round"
              pathLength="1"
              strokeDasharray="1"
              strokeDashoffset={1 - travelled}
              style={{ transition: "stroke-dashoffset 700ms ease-out" }}
            />
          </svg>

          <ol className="absolute inset-0">
            {activities.map((activity, index) => {
              const isDone = activity.is_complete;
              const isCurrent = index === currentIndex;
              const isOpen = index === openIndex;
              const point = points[index];

              return (
                <li
                  key={activity.id}
                  className="absolute"
                  style={{ left: point.x - NODE / 2, top: point.y - NODE / 2 }}
                >
                  <Tooltip>
                    <TooltipTrigger asChild>
                  <button
                    onClick={() => setSelected(index)}
                    onMouseEnter={() => setSelected(index)}
                    onFocus={() => setSelected(index)}
                    aria-current={isCurrent ? "step" : undefined}
                    aria-label={`Step ${index + 1}: ${activity.title}`}
                    className={cx(
                      "group grid place-items-center rounded-full transition",
                      "h-11 w-11 focus-visible:outline-offset-4",
                      isDone && "bg-[color:var(--color-accent)] text-white",
                      !isDone && isCurrent &&
                        "bg-ink text-white shadow-[0_0_0_6px_color-mix(in_oklab,var(--color-accent)_22%,transparent)] dark:bg-white dark:text-black",
                      !isDone && !isCurrent && "bg-paper text-ink-3 ring-1 ring-[color:var(--color-line)]",
                      isOpen && "ring-4 ring-[color:var(--color-accent)]/35",
                      "hover:scale-110 hover:shadow-[0_0_20px_-2px_var(--color-accent)]",
                    )}
                  >
                    {isDone ? <Icon name="check" size={17} /> : <Icon name={activity.kind} size={18} />}
                  </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-[220px]">
                      <p className="font-medium">{activity.title}</p>
                      <p className="opacity-70">
                        {activity.minutes} min · {skillLabel(activity.kind)}
                      </p>
                    </TooltipContent>
                  </Tooltip>

                  {/* Step number under each node keeps the order explicit. */}
                  <span className="micro mt-1.5 block text-center">{index + 1}</span>
                </li>
              );
            })}
          </ol>
        </div>
        </div>
      </div>

      <ErrorNote error={error} />

      {/* The selected step, opened below so the map keeps its height. */}
      {open && (
        <div className="rounded-2xl bg-surface p-4 ring-1 ring-[color:var(--color-line)]">
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            {openIndex === currentIndex && !open.is_complete && (
              <span className="micro text-[color:var(--color-accent)]">You are here</span>
            )}
            {open.is_complete && (
              <span className="micro text-[color:var(--color-good-ink)]">Done</span>
            )}
            <h3 className="text-[15px] font-semibold">{open.title}</h3>
            <Pill>{open.minutes} min</Pill>
            <span className="micro ml-auto">{skillLabel(open.kind)}</span>
          </div>

          <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{open.instructions}</p>

          {open.prompt && (
            <p className="mt-2.5 border-l border-[color:var(--color-line)] pl-3 text-[13px] italic text-ink-2">
              {open.prompt}
            </p>
          )}

          {open.target_expressions?.length > 0 && (
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <span className="micro">use</span>
              {open.target_expressions.map((expression) => (
                <Pill key={expression}>{expression}</Pill>
              ))}
            </div>
          )}

          <div className="mt-3.5 flex flex-wrap items-center gap-3">
            <Link
              to={activityHref(open)}
              className={cx(
                "rounded-full px-4 py-1.5 text-[13px] font-medium transition",
                open.is_complete
                  ? "text-ink ring-1 ring-[color:var(--color-line)] hover:bg-sunken"
                  : "bg-ink text-white hover:opacity-90 dark:bg-white dark:text-black",
              )}
            >
              {open.is_complete ? "Do it again" : "Start"}
            </Link>
            {!open.is_complete && (
              <button
                onClick={() => complete(open.id)}
                disabled={busy === open.id}
                className="micro hover:text-ink"
              >
                mark done
              </button>
            )}
          </div>
        </div>
      )}

      {lesson.status === "completed" && (
        <p className="micro text-center text-[color:var(--color-accent)]">
          ( day complete — tomorrow&rsquo;s plan shifts based on how today went )
        </p>
      )}
    </section>
  );
}
