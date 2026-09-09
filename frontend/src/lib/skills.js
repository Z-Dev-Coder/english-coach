/** Skill display metadata. Separate from ui.jsx so that file only exports
 *  components (keeps React Fast Refresh working). */

const LABELS = {
  listening: "Listening",
  speaking: "Speaking",
  reading: "Reading",
  writing: "Writing",
  vocabulary: "Vocabulary",
  grammar: "Grammar",
  pronunciation: "Pronunciation",
  fluency: "Fluency",
  review: "Review",
};

const ICONS = {
  listening: "🎧",
  speaking: "🗣️",
  reading: "📖",
  writing: "✍️",
  vocabulary: "🧩",
  grammar: "🔧",
  pronunciation: "🔊",
  fluency: "💬",
  review: "🔁",
};

export const skillLabel = (skill) => LABELS[skill] ?? skill;
export const skillIcon = (skill) => ICONS[skill] ?? "•";
