import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { skillIcon, skillLabel } from "../lib/skills";
import { Card, ErrorNote, Pill, ProgressBar, Spinner } from "../lib/ui";

function greeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/** The home screen answers exactly one question: what should I do today? */
export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);

  const load = () => {
    setError(null);
    api.dashboard().then(setData).catch(setError);
    // AI status must never block the dashboard: it renders fine without it.
    api.aiStatus().then(setAiStatus).catch(() => setAiStatus(null));
  };

  useEffect(load, []);

  if (error) return <ErrorNote error={error} onRetry={load} />;
  if (!data) return <Spinner label="Building today's plan" />;

  const { learner, plan, skills, streak_days: streak, weak_areas: weak } = data;
  const focus = data.focus.map(skillLabel).join(" + ");

  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm text-slate-500">
          {greeting()} 👋
          {streak > 0 && <span className="ml-2">Day {streak} of your streak</span>}
        </p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">
          Today's focus: <span className="text-indigo-600">{focus || "getting started"}</span>
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          {learner.overall_level} now · aiming for {learner.target_level} ·{" "}
          {learner.daily_minutes} minutes a day
        </p>
      </header>

      <section aria-labelledby="plan-heading">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 id="plan-heading" className="text-lg font-semibold">
            Today's plan
          </h2>
          <span className="text-sm text-slate-500">
            {plan.reduce((total, block) => total + block.minutes, 0)} min total
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {plan.map((block) => (
            <Card key={block.skill} className="transition hover:shadow-md">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span aria-hidden="true" className="text-xl">
                    {skillIcon(block.skill)}
                  </span>
                  <span className="font-semibold">{skillLabel(block.skill)}</span>
                </div>
                <Pill tone="brand">{block.minutes} min</Pill>
              </div>
              <p className="mt-2.5 text-sm leading-relaxed text-slate-500">{block.reason}</p>
            </Card>
          ))}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-4 text-lg font-semibold">Your skills</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {skills.map((skill) => (
              <ProgressBar
                key={skill.skill}
                value={skill.score}
                label={`${skillIcon(skill.skill)} ${skillLabel(skill.skill)}`}
                sublabel={skill.level}
                weak={skill.is_weak}
              />
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-400">
            Scores are estimates that grow more reliable as you practise. Amber marks the areas
            today's plan is prioritising.
          </p>
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="mb-3 text-lg font-semibold">This week</h2>
            <dl className="space-y-2.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Streak</dt>
                <dd className="font-semibold tabular-nums">{streak} days</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Time studied</dt>
                <dd className="font-semibold tabular-nums">{data.weekly_minutes} min</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Sessions</dt>
                <dd className="font-semibold tabular-nums">
                  {data.sessions_this_week} / {data.weekly_goal_sessions}
                </dd>
              </div>
            </dl>
          </Card>

          <Card>
            <h2 className="mb-3 text-lg font-semibold">Work on these</h2>
            <ul className="space-y-2 text-sm">
              {weak.map((item) => (
                <li key={item.skill} className="flex items-center justify-between">
                  <span className="text-slate-600">
                    {skillIcon(item.skill)} {skillLabel(item.skill)}
                  </span>
                  <span className="tabular-nums text-amber-600">{Math.round(item.score)}%</span>
                </li>
              ))}
            </ul>
            <Link
              to="/speaking"
              className="mt-4 inline-block text-sm font-semibold text-indigo-600 hover:underline"
            >
              Practise speaking now →
            </Link>
          </Card>

          {aiStatus && !aiStatus.reachable && (
            <Card className="bg-amber-50 ring-amber-200">
              <p className="text-sm font-medium text-amber-900">Local AI is offline</p>
              <p className="mt-1 text-xs leading-relaxed text-amber-800">
                {aiStatus.setup_hint}
              </p>
              <p className="mt-2 text-xs text-amber-700">
                Everything else still works — practice scripts and your plan don't need it.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
