/**
 * Find the word under a screen coordinate.
 *
 * The obvious way to make words clickable is to split text into one <span> per
 * word. It is also the wrong way here, and badly so:
 *
 *  - It breaks text selection. Copying a sentence out of a reading passage is
 *    something a learner actually does.
 *  - It changes what a screen reader announces: a paragraph becomes a list of
 *    disconnected fragments instead of a sentence.
 *  - Native find-in-page stops matching across the span boundaries.
 *  - It multiplies the DOM by the word count of every passage on screen.
 *
 * So the text stays exactly as it is -- plain text nodes -- and the word is
 * resolved from the pointer position instead, using the browser's own caret
 * hit-testing. Nothing in the markup knows this feature exists.
 */

// Letters, plus the marks that live *inside* English words. Apostrophes must
// be included or "don't" resolves as "don"; hyphens or "well-being" splits.
const WORD_CHARACTER = /[\p{Letter}'’‑-]/u;

/** The caret hit-test, which two engines spell differently. */
function caretAt(x, y) {
  // The standard, and what Firefox implements.
  if (document.caretPositionFromPoint) {
    const position = document.caretPositionFromPoint(x, y);
    return position ? { node: position.offsetNode, offset: position.offset } : null;
  }
  // WebKit and Blink.
  if (document.caretRangeFromPoint) {
    const range = document.caretRangeFromPoint(x, y);
    return range ? { node: range.startContainer, offset: range.startOffset } : null;
  }
  return null;
}

/**
 * Returns `{ word, rect }` for the word under (x, y), or null.
 *
 * `rect` is the word's own bounding box rather than the element's, so a
 * popover can point at the word itself even in the middle of a paragraph.
 */
export function wordAtPoint(x, y) {
  const caret = caretAt(x, y);
  if (!caret) return null;

  const { node, offset } = caret;
  if (!node || node.nodeType !== Node.TEXT_NODE) return null;

  const text = node.textContent ?? "";
  if (!text) return null;

  // The caret lands *between* characters, so walk outwards from it to the
  // word's edges.
  let start = Math.min(offset, text.length);
  let end = start;
  while (start > 0 && WORD_CHARACTER.test(text[start - 1])) start -= 1;
  while (end < text.length && WORD_CHARACTER.test(text[end])) end += 1;

  const word = text.slice(start, end);
  // A caret in a space, or on punctuation between words, is not a lookup.
  if (!word || word.length < 2) return null;

  const range = document.createRange();
  range.setStart(node, start);
  range.setEnd(node, end);
  const rect = range.getBoundingClientRect();
  range.detach?.();

  // A zero-size rect means the text is not actually laid out where we think.
  if (!rect.width || !rect.height) return null;

  return { word, rect };
}
