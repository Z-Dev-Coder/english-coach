/**
 * Line icons.
 *
 * Emoji were doing this job, and they were the loudest remaining tell that the
 * interface was assembled rather than designed: they carry their own colour,
 * their own style, and they render differently on every platform. These are
 * one stroke weight, one size, and inherit the current colour.
 */

const paths = {
  home: "M3 9.5 10 4l7 5.5V16a1 1 0 0 1-1 1h-4v-4H8v4H4a1 1 0 0 1-1-1z",
  review: "M16 5.5A6.5 6.5 0 1 0 17 10M16 3v3h-3",
  practice: "M4 12v-2a6 6 0 1 1 12 0v2M4 12a2 2 0 0 0 2 2V10a2 2 0 0 0-2 2Zm12 0a2 2 0 0 1-2 2V10a2 2 0 0 1 2 2Z",
  world: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm0 0c-2 2-3 4.2-3 7s1 5 3 7m0-14c2 2 3 4.2 3 7s-1 5-3 7M3.5 8h13M3.5 12h13",
  progress: "M3 16.5h14M5.5 13V8m4 5V4.5M13.5 13v-3",
  profile: "M10 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-6 7c0-2.8 2.7-4.5 6-4.5s6 1.7 6 4.5",
  speak: "M10 3a2 2 0 0 1 2 2v5a2 2 0 1 1-4 0V5a2 2 0 0 1 2-2Zm-5 7a5 5 0 0 0 10 0M10 15v3",
  talk: "M17 11.5a1.5 1.5 0 0 1-1.5 1.5H7l-3 3V5.5A1.5 1.5 0 0 1 5.5 4h10A1.5 1.5 0 0 1 17 5.5z",
  read: "M10 5.5S8.5 4 5 4H3v11h2c3.5 0 5 1.5 5 1.5m0-11S11.5 4 15 4h2v11h-2c-3.5 0-5 1.5-5 1.5m0-11v11",
  write: "M4 16h12M4.5 12.5 12 5l3 3-7.5 7.5H4.5z",
  drill: "M10 3v14M5 8l5-5 5 5M5 12l5 5 5-5",
  vocab: "M5 4h10v12l-5-2.5L5 16z",
  sun: "M10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM10 2v1.5M10 16.5V18M18 10h-1.5M3.5 10H2m12.2-4.2-1 1M6.8 13.2l-1 1m8.4 0-1-1M6.8 6.8l-1-1",
  moon: "M16 11.2A6.5 6.5 0 0 1 8.8 4a6.5 6.5 0 1 0 7.2 7.2Z",
};

// The skills each map onto one of the icons above.
const SKILL_ICONS = {
  listening: "practice",
  speaking: "speak",
  reading: "read",
  writing: "write",
  vocabulary: "vocab",
  grammar: "write",
  pronunciation: "speak",
  fluency: "talk",
  review: "review",
  drill: "drill",
};

export default function Icon({ name, size = 18, className = "", strokeWidth = 1.5 }) {
  const d = paths[name] ?? paths[SKILL_ICONS[name]] ?? paths.home;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d={d} />
    </svg>
  );
}
