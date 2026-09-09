import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { skillLabel } from "../lib/skills";
import { Button, Card, ErrorNote, Pill, Spinner } from "../lib/ui";

const SCHEDULABLE = ["listening", "speaking", "reading", "writing", "vocabulary"];
const TOPICS = [
  "technology", "movies", "music", "work", "travel", "food",
  "science", "business", "gaming", "news", "sports", "health",
];
const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const IMMERSION = [
  { value: 0, label: "Native-language support" },
  { value: 1, label: "English + translation" },
  { value: 2, label: "English only" },
];

function toggle(list, item) {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.profile().then(setProfile).catch(setError);
  }, []);

  const patch = (changes) => setProfile((previous) => ({ ...previous, ...changes }));

  const save = async () => {
    setError(null);
    try {
      const updated = await api.updateProfile({
        target_level: profile.target_level,
        daily_minutes: Number(profile.daily_minutes),
        weekly_goal_sessions: Number(profile.weekly_goal_sessions),
        immersion_level: Number(profile.immersion_level),
        interests: profile.interests,
        priority_skills: profile.priority_skills,
      });
      setProfile(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err);
    }
  };

  if (error && !profile) return <ErrorNote error={error} />;
  if (!profile) return <Spinner label="Loading your profile" />;

  const chip = (active) =>
    `rounded-full px-3 py-1.5 text-sm transition ${
      active
        ? "bg-indigo-600 text-white"
        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
    }`;

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Your learning profile</h1>
        <p className="mt-1 text-slate-500">
          This is what the daily planner uses to decide what you study.
        </p>
      </header>

      <Card>
        <h2 className="mb-4 text-lg font-semibold">Goals</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">Target level</span>
            <select
              value={profile.target_level}
              onChange={(event) => patch({ target_level: event.target.value })}
              className="w-full rounded-xl bg-slate-50 px-3 py-2.5 text-sm ring-1 ring-slate-200"
            >
              {LEVELS.map((level) => (
                <option key={level}>{level}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              Minutes per day
            </span>
            <input
              type="number"
              min="5"
              max="240"
              value={profile.daily_minutes}
              onChange={(event) => patch({ daily_minutes: event.target.value })}
              className="w-full rounded-xl bg-slate-50 px-3 py-2.5 text-sm ring-1 ring-slate-200"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              Sessions per week
            </span>
            <input
              type="number"
              min="1"
              max="7"
              value={profile.weekly_goal_sessions}
              onChange={(event) => patch({ weekly_goal_sessions: event.target.value })}
              className="w-full rounded-xl bg-slate-50 px-3 py-2.5 text-sm ring-1 ring-slate-200"
            />
          </label>
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold">Priority skills</h2>
        <p className="mt-1 mb-3 text-sm text-slate-500">
          The planner already favours your weakest skills. Use this to push it further.
        </p>
        <div className="flex flex-wrap gap-2">
          {SCHEDULABLE.map((skill) => (
            <button
              key={skill}
              onClick={() => patch({ priority_skills: toggle(profile.priority_skills, skill) })}
              className={chip(profile.priority_skills.includes(skill))}
            >
              {skillLabel(skill)}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold">Interests</h2>
        <p className="mt-1 mb-3 text-sm text-slate-500">
          Real-world content and practice topics are picked from these.
        </p>
        <div className="flex flex-wrap gap-2">
          {TOPICS.map((topic) => (
            <button
              key={topic}
              onClick={() => patch({ interests: toggle(profile.interests, topic) })}
              className={chip(profile.interests.includes(topic))}
            >
              {topic}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold">Immersion</h2>
        <p className="mt-1 mb-3 text-sm text-slate-500">
          How much English-only content you get. Raise it as you get more comfortable.
        </p>
        <div className="flex flex-wrap gap-2">
          {IMMERSION.map((option) => (
            <button
              key={option.value}
              onClick={() => patch({ immersion_level: option.value })}
              className={chip(Number(profile.immersion_level) === option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-lg font-semibold">Measured levels</h2>
        <div className="flex flex-wrap gap-2">
          {profile.skills.map((skill) => (
            <Pill key={skill.skill} tone={skill.is_weak ? "warn" : "default"}>
              {skillLabel(skill.skill)} · {skill.level}
            </Pill>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-400">
          These are estimated from your activity, not set by hand — that is why the app targets
          your weak skills rather than one overall level.
        </p>
      </Card>

      <ErrorNote error={error} />

      <div className="flex items-center gap-3">
        <Button onClick={save}>Save changes</Button>
        {saved && <span className="text-sm text-emerald-600">✓ Saved</span>}
      </div>
    </div>
  );
}
