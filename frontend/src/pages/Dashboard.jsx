import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { skillIcon, skillLabel } from "../lib/skills";
import {
  Card,
  CardSkeleton,
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

  return (
    <section className="animate-rise overflow-hidden rounded-3xl bg-gradient-to-br from-brand-600 via-brand-600 to-violet-600 p-6 text-white shadow-lift sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0">
          <p className="text-sm font-medium text-white/70">
            {greeting()}, {learner.username} 👋
          </p>
          <h1 className="mt-1.5 text-2xl font-bold tracking-tight sm:text-3xl">
            {focus ? (
              <>
                Today's focus is <span className="whitespace-nowrap">{focus}</span>
              </>
            ) : (
              "Let's find your starting point"
            )}
          </h1>
          <div className="mt-4 flex flex-wrap gap-2">
            <Pill className="bg-white/15 text-white">Now: {learner.overall_level}</Pill>
            <Pill className="bg-white/15 text-white">Goal: {learner.target_level}</Pill>
            <Pill className="bg-white/15 text-white">{learner.daily_minutes} min a day</Pill>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="text-center">
            <ProgressRing value={goalPct} size={78} tone="brand">
              <span className="text-xl font-bold tabular-nums">{streak}</span>
              <span className="text-[10px] font-medium uppercase tracking-wide text-white/70">
                day{streak === 1 ? "" : "s"}
              </span>
            </ProgressRing>
            <p className="mt-1.5 text-xs text-white/70">Streak</p>
          </div>
          <dl className="space-y-3 text-white">
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-white/60">This week</dt>
              <dd className="text-xl font-bold tabular-nums">
                {weeklyMinutes}
                <span className="ml-1 text-xs font-medium text-white/60">min</span>
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-white/60">Sessions</dt>
              <dd className="text-xl font-bold tabular-nums">
                {sessions}
                <span className="text-white/60"> / {goal}</span>
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

  const load = useCallback(() => {
    setError(null);
    api.dashboard().then(setData).catch(setError);
    // AI status must never block the dashboard: the page renders without it.
    api.aiStatus().then(setAiStatus).catch(() => setAiStatus(null));
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

      <section aria-labelledby="plan-heading">
        <SectionHeading
          id="plan-heading"
          title="Today's plan"
          action={
            <span className="text-sm tabular-nums text-slate-400">{totalMinutes} min total</span>
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
                    className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-lg dark:bg-brand-500/15"
                  >
                    {skillIcon(block.skill)}
                  </span>
                  <span className="font-semibold">{skillLabel(block.skill)}</span>
                </div>
                <Pill tone="brand">{block.minutes} min</Pill>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
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

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionHeading title="Your skills" />
          <div className="grid gap-4 sm:grid-cols-2">
            {skills.map((skill) => (
              <ProgressBar
                key={skill.skill}
                value={skill.score}
                label={
                  <span className="inline-flex items-center gap-1.5">
                    <span aria-hidden="true">{skillIcon(skill.skill)}</span>
                    {skillLabel(skill.skill)}
                  </span>
                }
                sublabel={skill.confidence > 0 ? skill.level : "not measured"}
                weak={skill.is_weak}
              />
            ))}
          </div>
          <p className="mt-5 text-xs leading-relaxed text-slate-400">
            Scores are estimates that get more reliable the more you practise. Amber marks the
            areas today's plan is prioritising.
          </p>
        </Card>

        <div className="space-y-6">
          <Card>
            <SectionHeading title="At a glance" />
            <dl className="grid grid-cols-2 gap-4">
              <StatTile label="Streak" value={streak} unit="days" tone="brand" />
              <StatTile label="This week" value={data.weekly_minutes} unit="min" />
              <StatTile label="Sessions" value={data.sessions_this_week} />
              <StatTile label="Measured" value={`${measured.length}/${skills.length}`} />
            </dl>
          </Card>

          <Card>
            <SectionHeading title="Work on these" />
            <ul className="space-y-2.5 text-sm">
              {weak.map((item) => (
                <li key={item.skill} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                    <span aria-hidden="true">{skillIcon(item.skill)}</span>
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
            <Card className="bg-amber-50 ring-amber-200 dark:bg-amber-500/10 dark:ring-amber-500/20">
              <p className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                Local AI is offline
              </p>
              <p className="mt-1 text-xs leading-relaxed text-amber-800 dark:text-amber-300/90">
                {aiStatus.setup_hint}
              </p>
              <p className="mt-2 text-xs text-amber-700 dark:text-amber-400/80">
                Everything else still works — your plan and practice scripts don't need it.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
