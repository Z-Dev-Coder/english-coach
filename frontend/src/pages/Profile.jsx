import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { skillIcon, skillLabel } from "../lib/skills";
import {
  Button,
  Card,
  CardSkeleton,
  Chip,
  ErrorNote,
  Field,
  Input,
  Pill,
  SectionHeading,
  Select,
} from "../lib/ui";

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
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.profile().then(setProfile).catch(setError);
  }, []);

  const patch = (changes) => setProfile((previous) => ({ ...previous, ...changes }));

  const save = async () => {
    setSaving(true);
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
    } finally {
      setSaving(false);
    }
  };

  if (error && !profile) return <ErrorNote error={error} />;
  if (!profile) {
    return (
      <div className="space-y-5">
        {Array.from({ length: 4 }).map((_, index) => (
          <CardSkeleton key={index} lines={3} />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-24">
      <header>
        <h1 className="display text-[38px]">Your learning profile</h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          This is what the daily planner uses to decide what you study.
        </p>
      </header>

      <Card>
        <SectionHeading title="Goals" />
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Target level">
            <Select
              value={profile.target_level}
              onChange={(event) => patch({ target_level: event.target.value })}
            >
              {LEVELS.map((level) => (
                <option key={level}>{level}</option>
              ))}
            </Select>
          </Field>
          <Field label="Minutes per day">
            <Input
              type="number"
              min="5"
              max="240"
              value={profile.daily_minutes}
              onChange={(event) => patch({ daily_minutes: event.target.value })}
            />
          </Field>
          <Field label="Sessions per week">
            <Input
              type="number"
              min="1"
              max="7"
              value={profile.weekly_goal_sessions}
              onChange={(event) => patch({ weekly_goal_sessions: event.target.value })}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <SectionHeading title="Priority skills" />
        <p className="-mt-1 mb-4 text-sm text-ink-2 dark:text-white/55">
          The planner already favours your weakest skills. Use this to push it further.
        </p>
        <div className="flex flex-wrap gap-2">
          {SCHEDULABLE.map((skill) => (
            <Chip
              key={skill}
              active={profile.priority_skills.includes(skill)}
              onClick={() => patch({ priority_skills: toggle(profile.priority_skills, skill) })}
            >
              <span aria-hidden="true" className="mr-1">
                {skillIcon(skill)}
              </span>
              {skillLabel(skill)}
            </Chip>
          ))}
        </div>
      </Card>

      <Card>
        <SectionHeading title="Interests" />
        <p className="-mt-1 mb-4 text-sm text-ink-2 dark:text-white/55">
          Real-world content and practice topics are picked from these.
        </p>
        <div className="flex flex-wrap gap-2">
          {TOPICS.map((topic) => (
            <Chip
              key={topic}
              active={profile.interests.includes(topic)}
              onClick={() => patch({ interests: toggle(profile.interests, topic) })}
            >
              {topic}
            </Chip>
          ))}
        </div>
      </Card>

      <Card>
        <SectionHeading title="Immersion" />
        <p className="-mt-1 mb-4 text-sm text-ink-2 dark:text-white/55">
          How much English-only content you get. Raise it as you grow more comfortable.
        </p>
        <div className="flex flex-wrap gap-2">
          {IMMERSION.map((option) => (
            <Chip
              key={option.value}
              active={Number(profile.immersion_level) === option.value}
              onClick={() => patch({ immersion_level: option.value })}
            >
              {option.label}
            </Chip>
          ))}
        </div>
      </Card>

      <Card>
        <SectionHeading title="Measured levels" />
        <div className="flex flex-wrap gap-2">
          {profile.skills.map((skill) => (
            <Pill key={skill.skill} tone={skill.is_weak ? "warn" : "default"}>
              <span aria-hidden="true" className="mr-1">
                {skillIcon(skill.skill)}
              </span>
              {skillLabel(skill.skill)} · {skill.confidence > 0 ? skill.level : "—"}
            </Pill>
          ))}
        </div>
        <p className="mt-4 text-xs leading-relaxed text-ink-3">
          These are estimated from your activity rather than set by hand. It is why the app targets
          your weak skills instead of one overall level.
        </p>
      </Card>

      <ErrorNote error={error} />

      {/* Sticky save bar: on a long form the button should never be off-screen. */}
      <div className="fixed inset-x-0 bottom-16 z-10 border-t border-[color:var(--color-line)]/70 bg-white/90 px-4 py-3 backdrop-blur-md md:bottom-0 md:px-6 dark:border-white/10 dark:bg-white/[0.03]/90">
        <div className="mx-auto flex max-w-6xl items-center justify-end gap-3 md:pl-56">
          {saved && (
            <span className="micro text-[color:var(--color-good-ink)]">
              ✓ Saved
            </span>
          )}
          <Button onClick={save} loading={saving}>
            Save changes
          </Button>
        </div>
      </div>
    </div>
  );
}
