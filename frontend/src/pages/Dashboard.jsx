import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import Aurora from "../components/Aurora";
import LessonMap from "../components/LessonMap";
import Icon from "../lib/icons";
import { skillLabel } from "../lib/skills";
import Reveal from "../components/Reveal";
import { useCountUp } from "../lib/motion";
import {
  Card,
  CardSkeleton,
  HowTo,
  ErrorNote,
  Pill,
  ProgressBar,
  ProgressRing,
  SectionHeading,
  Skeleton,
  StatTile,
} from "../lib/ui";

function greeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <Skeleton className="h-36 w-full rounded-3xl" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </div>
    </div>
  );
}

/** Hero. Answers "what am I doing today?" before anything else on the page. */
function Hero({ learner, focus, streak, weeklyMinutes, goal, sessions }) {
  const goalPct = goal > 0 ? Math.min(100, (sessions / goal) * 100) : 0;
  const [shownMinutes, minutesRef] = useCountUp(weeklyMinutes);

  return (
    <section className="animate-rise relative overflow-hidden rounded-3xl bg-sunken p-7 ring-1 ring-[color:var(--color-line)] sm:p-10 dark:bg-[#080808]">
      <Aurora />
      {/* Scrim. The light lives on the right; this keeps an even ground under
          the headline so nothing has to be read against a moving gradient. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-gradient-to-r from-sunken via-sunken/80 to-transparent dark:from-[#080808] dark:via-[#080808]/75"
      />
      <div className="relative flex flex-wrap items-start justify-between gap-8">
        <div className="min-w-0">
          <p className="micro inline-flex items-center gap-2">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[color:var(--color-accent)] opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[color:var(--color-accent)]" />
            </span>
            {greeting()}, {learner.username}
          </p>
          <h1 className="display mt-4 text-[38px] sm:text-[56px]">
            {focus ? (
              <>
                Today's focus is{" "}
                <span className="whitespace-nowrap text-[color:var(--color-accent)]">{focus}</span>
              </>
            ) : (
              "Let's find your starting point"
            )}
          </h1>
          <div className="mt-4 flex flex-wrap gap-2">
            <Pill>Now {learner.overall_level}</Pill>
            <Pill>Goal {learner.target_level}</Pill>
            <Pill>{learner.daily_minutes} min a day</Pill>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="text-center">
            <ProgressRing value={goalPct} size={78} tone="brand">
              <span className="text-xl font-bold tabular-nums">{streak}</span>
              <span className="micro">day{streak === 1 ? "" : "s"}</span>
            </ProgressRing>
            <p className="micro mt-2">Streak</p>
          </div>
          <dl ref={minutesRef} className="space-y-4">
            <div>
              <dt className="micro">This week</dt>
              <dd className="text-2xl font-bold tabular-nums">
                {shownMinutes}
                <span className="ml-1 text-xs font-medium text-ink-3">min</span>
              </dd>
            </div>
            <div>
              <dt className="micro">Sessions</dt>
              <dd className="text-2xl font-bold tabular-nums">
                {sessions}
                <span className="text-ink-3"> / {goal}</span>
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);
  const [lesson, setLesson] = useState(null);

  const load = useCallback(() => {
    setError(null);
    api.dashboard().then(setData).catch(setError);
    // Neither of these may block the dashboard: the page is useful without
    // them, and lesson generation can be slow on a local model.
    api.aiStatus().then(setAiStatus).catch(() => setAiStatus(null));
    api.todayLesson().then(setLesson).catch(() => setLesson(null));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <ErrorNote error={error} onRetry={load} />;
  if (!data) return <DashboardSkeleton />;

  const { learner, plan, skills, streak_days: streak, weak_areas: weak } = data;
  const focus = data.focus.map(skillLabel).join(" + ");
  const totalMinutes = plan.reduce((total, block) => total + block.minutes, 0);
  const measured = skills.filter((skill) => skill.confidence > 0);

  return (
    <div className="space-y-8">
      <Hero
        learner={learner}
        focus={focus}
        streak={streak}
        weeklyMinutes={data.weekly_minutes}
        goal={data.weekly_goal_sessions}
        sessions={data.sessions_this_week}
      />

      <Reveal>
      <HowTo
        id="home"
        title="How this works"
        steps={[
          "Work down the plan in order. Each step links straight to the activity.",
          "Aim to finish it — the plan is already sized to the minutes you set.",
          "It waits for you. Miss a few days and it's still here, at the step you left.",
          "A new plan is built when you finish this one, from how it actually went.",
        ]}
      />
      </Reveal>

      {lesson ? (
        <Reveal>
        <LessonMap lesson={lesson} onChange={setLesson} />
        </Reveal>
      ) : (
        <section aria-labelledby="plan-heading">
          <SectionHeading
            id="plan-heading"
            title="Today's plan"
            action={
              <span className="text-sm tabular-nums text-ink-3">{totalMinutes} min total</span>
            }
          />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plan.map((block, index) => (
              <Card
                key={block.skill}
                interactive
                className="animate-rise"
                style={{ animationDelay: `${index * 45}ms` }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span
                      aria-hidden="true"
                      className="grid h-9 w-9 place-items-center rounded-xl bg-sunken dark:bg-white/[0.06]"
                    >
                      {/* Was calling skillIcon, which is not imported here --
                          this whole branch threw whenever no lesson existed.
                          The line icon set is what the rest of the page uses. */}
                      <Icon name={block.skill} size={17} className="text-ink-2" />
                    </span>
                    <span className="font-semibold">{skillLabel(block.skill)}</span>
                  </div>
                  <Pill tone="brand">{block.minutes} min</Pill>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-ink-2 dark:text-white/55">
                  {block.reason}
                </p>
                {block.skill === "review" && data.review && (
                  <Link
                    to="/review"
                    className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:gap-2 dark:text-brand-300"
                  >
                    {data.review.due_now > 0
                      ? `${data.review.due_now} due now`
                      : "Nothing due — add words"}
                    <span aria-hidden="true">→</span>
                  </Link>
                )}
              </Card>
            ))}
          </div>
        </section>
      )}

      <Reveal className="grid gap-6 lg:grid-cols-3">
        <Card interactive className="lg:col-span-2">
          <SectionHeading title="Your skills" />
          <div className="grid gap-4 sm:grid-cols-2">
            {skills.map((skill) => (
              <ProgressBar
                key={skill.skill}
                value={skill.score}
                label={
                  <span className="inline-flex items-center gap-2">
                    <Icon name={skill.skill} size={15} className="text-ink-3" />
                    {skillLabel(skill.skill)}
                  </span>
                }
                sublabel={skill.confidence > 0 ? skill.level : "not measured"}
                weak={skill.is_weak}
              />
            ))}
          </div>
          <p className="mt-5 text-xs leading-relaxed text-ink-3">
            Scores are estimates that get more reliable the more you practise. Amber marks the
            areas today's plan is prioritising.
          </p>
        </Card>

        <div className="space-y-6">
          <Card interactive>
            <SectionHeading title="At a glance" />
            <dl className="grid grid-cols-2 gap-4">
              <StatTile label="Streak" value={streak} unit="days" tone="brand" />
              <StatTile label="This week" value={data.weekly_minutes} unit="min" />
              <StatTile label="Sessions" value={data.sessions_this_week} />
              <StatTile label="Measured" value={`${measured.length}/${skills.length}`} />
            </dl>
          </Card>

          <Card interactive>
            <SectionHeading title="Work on these" />
            <ul className="space-y-2.5 text-sm">
              {weak.map((item) => (
                <li key={item.skill} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-ink-2 dark:text-white/70">
                    <Icon name={item.skill} size={15} className="text-ink-3" />
                    {skillLabel(item.skill)}
                  </span>
                  <span className="tabular-nums text-amber-600 dark:text-amber-400">
                    {Math.round(item.score)}%
                  </span>
                </li>
              ))}
            </ul>
            <Link
              to="/speaking"
              className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:gap-2 dark:text-brand-300"
            >
              Practise speaking now
              <span aria-hidden="true">→</span>
            </Link>
          </Card>

          {aiStatus && !aiStatus.reachable && (
            <Card className="border-dashed">
              <p className="micro text-[color:var(--color-accent)]">
                Local AI is offline
              </p>
              <p className="mt-1 text-xs leading-relaxed text-ink-3">
                {aiStatus.setup_hint}
              </p>
              <p className="mt-2 text-xs text-ink-3">
                Everything else still works — your plan and practice scripts don't need it.
              </p>
            </Card>
          )}
        </div>
      </Reveal>
    </div>
  );
}
