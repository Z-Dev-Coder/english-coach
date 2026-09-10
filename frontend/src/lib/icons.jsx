/**
 * Line icons.
 *
 * Emoji were doing this job, and they were the loudest remaining tell that the
 * interface was assembled rather than designed: they carry their own colour and
 * style, ignore the theme entirely, and render differently on every platform.
 * These are one stroke weight, one grid, and inherit the current colour — so
 * they follow the accent, dim with disabled text, and invert on dark surfaces
 * without any extra work.
 */

const paths = {
  // Navigation
  home: "M3 9.5 10 4l7 5.5V16a1 1 0 0 1-1 1h-4v-4H8v4H4a1 1 0 0 1-1-1z",
  review: "M16 5.5A6.5 6.5 0 1 0 17 10M16 3v3h-3",
  practice: "M4 12v-2a6 6 0 1 1 12 0v2M4 12a2 2 0 0 0 2 2V10a2 2 0 0 0-2 2Zm12 0a2 2 0 0 1-2 2V10a2 2 0 0 1 2 2Z",
  world: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm0 0c-2 2-3 4.2-3 7s1 5 3 7m0-14c2 2 3 4.2 3 7s-1 5-3 7M3.5 8h13M3.5 12h13",
  progress: "M3 16.5h14M5.5 13V8m4 5V4.5M13.5 13v-3",
  profile: "M10 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-6 7c0-2.8 2.7-4.5 6-4.5s6 1.7 6 4.5",

  // Skills
  speak: "M10 3a2 2 0 0 1 2 2v5a2 2 0 1 1-4 0V5a2 2 0 0 1 2-2Zm-5 7a5 5 0 0 0 10 0M10 15v3",
  talk: "M17 11.5a1.5 1.5 0 0 1-1.5 1.5H7l-3 3V5.5A1.5 1.5 0 0 1 5.5 4h10A1.5 1.5 0 0 1 17 5.5z",
  read: "M10 5.5S8.5 4 5 4H3v11h2c3.5 0 5 1.5 5 1.5m0-11S11.5 4 15 4h2v11h-2c-3.5 0-5 1.5-5 1.5m0-11v11",
  write: "M4 16h12M4.5 12.5 12 5l3 3-7.5 7.5H4.5z",
  drill: "M10 3v14M5 8l5-5 5 5M5 12l5 5 5-5",
  vocab: "M5 4h10v12l-5-2.5L5 16z",

  // Media controls
  play: "M6.5 4.5v11l9-5.5z",
  stop: "M5.5 5.5h9v9h-9z",
  mic: "M10 3a2 2 0 0 1 2 2v5a2 2 0 1 1-4 0V5a2 2 0 0 1 2-2Zm-5 7a5 5 0 0 0 10 0M10 15v3H7m3 0h3",
  volume: "M4 8v4h3l4 3V5L7 8zm10-1.5a5 5 0 0 1 0 7M16.5 4a8 8 0 0 1 0 12",
  slow: "M4 8v4h3l4 3V5L7 8zm9 1.2a3 3 0 0 1 0 1.6",

  // Actions and status
  check: "M4.5 10.5 8 14l7.5-8",
  chevronDown: "m5.5 8 4.5 4.5L14.5 8",
  chevronUp: "m5.5 12 4.5-4.5L14.5 12",
  close: "M5.5 5.5l9 9m0-9-9 9",
  arrowRight: "M4 10h12m-4.5-4.5L16 10l-4.5 4.5",
  arrowLeft: "M16 10H4m4.5-4.5L4 10l4.5 4.5",
  external: "M8 5H5.5A1.5 1.5 0 0 0 4 6.5v8A1.5 1.5 0 0 0 5.5 16h8a1.5 1.5 0 0 0 1.5-1.5V12M11 4h5v5M9 11l7-7",
  shuffle: "M3 6h3l8 8h3M3 14h3l3-3m5-5h3v3m0 5v3h-3",
  idea: "M10 3a4.5 4.5 0 0 0-2.5 8.2V13h5v-1.8A4.5 4.5 0 0 0 10 3ZM8 15.5h4M8.5 17.5h3",
  film: "M3.5 4.5h13v11h-13zM3.5 8h13M3.5 12h13M7 4.5v11m6-11v11",
  sparkle: "M10 3.5 11.6 8 16 9.6 11.6 11.2 10 15.7 8.4 11.2 4 9.6 8.4 8z",
  target: "M10 17a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm0-3.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
  lock: "M6 9V6.5a4 4 0 0 1 8 0V9M5 9h10v7.5H5z",

  // Theme
  sun: "M10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM10 2v1.5M10 16.5V18M18 10h-1.5M3.5 10H2m12.2-4.2-1 1M6.8 13.2l-1 1m8.4 0-1-1M6.8 6.8l-1-1",
  moon: "M16 11.2A6.5 6.5 0 0 1 8.8 4a6.5 6.5 0 1 0 7.2 7.2Z",
};

// Skills map onto the icons above.
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
  const key = paths[name] ? name : SKILL_ICONS[name];
  const d = paths[key] ?? paths.vocab;
  // Solid shapes read better filled at small sizes than as outlines.
  const filled = key === "play" || key === "stop" || key === "sparkle";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={filled ? 0 : strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d={d} />
    </svg>
  );
}
