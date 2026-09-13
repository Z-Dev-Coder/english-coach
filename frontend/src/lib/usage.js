/**
 * Whether a taught word or expression appears in the learner's own English.
 *
 * A client-side mirror of apps/skills/writing_support.used_items, for live
 * checklists. Matched on stems and in order, allowing a few words in between,
 * so natural use counts: "put the meeting off" uses "put off", "works for you"
 * uses "work for", and "..." in a pattern marks where the learner's own words
 * go. A strict string match would mark correct use of a phrasal verb as
 * missing -- punishing exactly what was taught.
 */

const DROPPABLE = new Set([
  "a", "an", "the", "my", "your", "his", "her", "our", "their",
  "sb", "sth", "someone", "something",
]);

function stem(word) {
  for (const suffix of ["ing", "ied", "ies", "ed", "es", "s"]) {
    if (word.endsWith(suffix) && word.length - suffix.length >= 3) {
      let base = word.slice(0, -suffix.length);
      // "running" -> "runn", "stopped" -> "stopp": undo the doubled consonant,
      // matching the server, or the -ing/-ed form never matches its base verb.
      if ((suffix === "ing" || suffix === "ed") && base.length >= 3 && base.at(-1) === base.at(-2) && !"aeiouls".includes(base.at(-1))) {
        base = base.slice(0, -1);
      }
      return base;
    }
  }
  return word;
}

function words(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/\.\.\.|…/g, " ")
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

export function isUsed(text, item) {
  const tokens = words(text).map(stem);
  const keys = words(item).filter((word) => !DROPPABLE.has(word)).map(stem);
  if (!keys.length) return false;
  let position = 0;
  for (let index = 0; index < keys.length; index += 1) {
    const window = index === 0 ? tokens.slice(position) : tokens.slice(position, position + 4);
    const offset = window.indexOf(keys[index]);
    if (offset === -1) return false;
    position += offset + 1;
  }
  return true;
}

export function usedItems(text, items) {
  return (items || []).filter((item) => isUsed(text, item));
}
