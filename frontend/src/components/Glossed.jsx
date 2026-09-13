import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";

import { api } from "../lib/api";
import Icon from "../lib/icons";
import { Spinner } from "../lib/ui";
import { wordAtPoint } from "../lib/wordAtPoint";

/**
 * Makes every word inside it look-up-able.
 *
 * Wrap any block of English and hovering or clicking a word shows what it
 * means. The children are rendered untouched -- see lib/wordAtPoint for why
 * the words are found by hit-testing rather than by wrapping each one.
 *
 * Interaction, and the reasoning:
 *
 *  - **Hover opens after a pause.** Instant hover definitions are miserable to
 *    read against, because the panel chases the pointer across the sentence.
 *    A short delay means only a word you stopped on is looked up.
 *  - **Click pins.** A pinned panel survives pointer movement, which is what
 *    you need to actually read it, and it is the only thing that works on a
 *    touch screen where there is no hover at all.
 *  - **Double-click works too**, because selecting a word is what people
 *    already do when they want to know what it means -- including keyboard
 *    users, who have no pointer to hover with.
 *
 * Definitions are cached per word for the life of the page on top of the
 * server-side cache, so re-reading a paragraph costs nothing.
 */

const HOVER_DELAY = 450;
// Long enough to move the pointer from a word onto its panel.
const CLOSE_DELAY = 700;
const PANEL_WIDTH = 320;
const GAP = 10;
// Below this the panel is not worth showing in place; above it, a
// definition popover starts to feel like a page.
const MIN_HEIGHT = 180;
const MAX_HEIGHT = 420;

// Shared across every Glossed block on the page: the same word in a passage
// and in its question should not be fetched twice.
const cache = new Map();

function useDefinition(word) {
  const [state, setState] = useState(() =>
    word && cache.has(word) ? { status: "ready", data: cache.get(word) } : { status: "idle" },
  );

  useEffect(() => {
    if (!word) return undefined;
    if (cache.has(word)) {
      setState({ status: "ready", data: cache.get(word) });
      return undefined;
    }

    let live = true;
    setState({ status: "loading" });
    api
      .defineWord(word)
      .then((data) => {
        cache.set(word, data);
        if (live) setState({ status: "ready", data });
      })
      .catch(() => {
        // A failed lookup is not an error the reader needs handling: the word
        // simply has no definition to show.
        if (live) setState({ status: "ready", data: { found: false, entries: [] } });
      });

    return () => {
      live = false;
    };
  }, [word]);

  return state;
}

/**
 * Places the panel beside its word, inside the window.
 *
 * Returns a `maxHeight` as well as a position: a panel that is taller than the
 * space it has is a panel whose last sense cannot be read, and being `fixed`
 * means no ancestor scrollbar will rescue it.
 */
function position(rect) {
  const left = Math.min(
    Math.max(GAP, rect.left + rect.width / 2 - PANEL_WIDTH / 2),
    Math.max(GAP, window.innerWidth - PANEL_WIDTH - GAP),
  );

  const roomBelow = window.innerHeight - rect.bottom - GAP * 2;
  const roomAbove = rect.top - GAP * 2;
  // Prefer below -- it keeps the word visible above the panel while you read
  // it -- unless above genuinely has more space to offer.
  const below = roomBelow >= MIN_HEIGHT || roomBelow >= roomAbove;
  const room = below ? roomBelow : roomAbove;

  return {
    left,
    // One edge is pinned to the word and the other is left to the content.
    // Deliberately not `top` + translateY(-100%): the entry animation ends on
    // `transform: none`, and an animation overrides an inline style, so the
    // panel was placed above and then painted below the word.
    top: below ? rect.bottom + GAP : undefined,
    bottom: below ? undefined : window.innerHeight - rect.top + GAP,
    maxHeight: Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, room)),
  };
}

function Panel({ target, onClose, pinned, onHover }) {
  const { status, data } = useDefinition(target.word);
  const [saving, setSaving] = useState(false);
  const { left, top, bottom, maxHeight } = position(target.rect);

  const entry = data?.entries?.[0];
  const senses = entry?.senses ?? [];

  const save = async () => {
    setSaving(true);
    try {
      await api.addVocabulary({
        text: entry.word,
        meaning: senses[0].definition,
        kind: "word",
        example: senses[0].example || "",
      });
      toast.success(`Added "${entry.word}"`, {
        description: "It will come up in your reviews.",
      });
      onClose();
    } catch (error) {
      toast.error("Could not add that word", { description: error.message });
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div
      role="dialog"
      aria-label={`Definition of ${target.word}`}
      className="fixed z-50 animate-rise"
      style={{ left, top, bottom, width: PANEL_WIDTH }}
      // The panel is portalled outside the text, so leaving the text to read
      // it must not close it: entering cancels the pending close, leaving
      // schedules one.
      onPointerEnter={() => onHover?.(true)}
      onPointerLeave={() => onHover?.(false)}
    >
      <div
        className="flex flex-col overflow-hidden rounded-xl bg-surface shadow-lift ring-1 ring-[color:var(--color-line)] dark:bg-[#141414] dark:ring-white/12"
        style={{ maxHeight }}
      >
        <div className="flex shrink-0 items-baseline gap-2 border-b border-[color:var(--color-line)] px-4 py-2.5 dark:border-white/10">
          <span className="font-semibold">{entry?.word ?? target.word}</span>
          {entry?.phonetic && (
            <span className="font-mono text-[11px] text-ink-3">{entry.phonetic}</span>
          )}
          {data?.source === "app" && <span className="micro ml-auto">your words</span>}
          {pinned && (
            <button
              onClick={onClose}
              aria-label="Close"
              className="ml-auto text-ink-3 hover:text-ink"
            >
              <Icon name="close" size={14} />
            </button>
          )}
        </div>

        {/* The only part that scrolls. `overscroll-contain` stops a flick
            at the end of the list from scrolling the passage behind it. */}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3">
          {status === "loading" && (
            <div className="flex items-center gap-2 text-[13px] text-ink-3">
              <Spinner /> Looking it up…
            </div>
          )}

          {status === "ready" && senses.length === 0 && (
            <p className="text-[13px] text-ink-3">
              {data?.source === "unavailable"
                ? "Can’t reach the dictionary right now."
                : "No definition found for this word."}
            </p>
          )}

          {status === "ready" && senses.length > 0 && (
            <ol className="space-y-2.5">
              {senses.map((sense, index) => (
                <li key={index} className="text-[13px]">
                  {sense.part_of_speech && (
                    <span className="mr-1.5 font-mono text-[10px] uppercase tracking-wide text-ink-3">
                      {sense.part_of_speech}
                    </span>
                  )}
                  <span className="text-ink-2 dark:text-white/75">{sense.definition}</span>
                  {sense.example && (
                    <p className="mt-1 border-l border-[color:var(--color-line)] pl-2.5 text-[12px] italic text-ink-3">
                      {sense.example}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>

        {status === "ready" && senses.length > 0 && data?.source !== "app" && (
          <div className="shrink-0 border-t border-[color:var(--color-line)] px-4 py-2 dark:border-white/10">
            <button
              onClick={save}
              disabled={saving}
              className="micro inline-flex items-center gap-1.5 hover:text-ink disabled:opacity-50 dark:hover:text-white"
            >
              <Icon name="vocab" size={13} />
              {saving ? "adding…" : "add to my words"}
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

export default function Glossed({ children, className = "", as: Tag = "div" }) {
  const [target, setTarget] = useState(null);
  const [pinned, setPinned] = useState(false);
  const timer = useRef(null);
  const closeTimer = useRef(null);
  const container = useRef(null);

  const clear = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const cancelClose = useCallback(() => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = null;
  }, []);

  const close = useCallback(() => {
    clear();
    cancelClose();
    setTarget(null);
    setPinned(false);
  }, [clear, cancelClose]);

  // Closing on hover is delayed, so the pointer can cross the gap between a
  // word and its panel -- or drift between words -- without losing it. It
  // closed instantly before, which made it vanish while being read.
  const closeSoon = useCallback(() => {
    cancelClose();
    closeTimer.current = setTimeout(close, CLOSE_DELAY);
  }, [cancelClose, close]);

  // A pinned panel is dismissed the way every other transient surface is.
  useEffect(() => {
    if (!pinned) return undefined;
    const onKey = (event) => event.key === "Escape" && close();
    const onDown = (event) => {
      // The panel is portalled outside the container, so a press inside it --
      // on "add to my words" -- must not count as a press outside.
      if (container.current?.contains(event.target)) return;
      if (event.target.closest?.('[role="dialog"]')) return;
      close();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    // Scrolling moves the word out from under the panel, and repositioning it
    // mid-scroll is more distracting than dismissing it.
    window.addEventListener("scroll", close, { passive: true, once: true });
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", close);
    };
  }, [pinned, close]);

  useEffect(() => () => {
    clear();
    cancelClose();
  }, [clear, cancelClose]);

  const lookUpAt = (x, y, { pin }) => {
    const found = wordAtPoint(x, y);
    if (!found) {
      // Between words, or on punctuation: keep what is showing rather than
      // closing on the smallest drift of the pointer.
      return;
    }
    cancelClose();
    setTarget(found);
    if (pin) setPinned(true);
  };

  const onPointerMove = (event) => {
    if (pinned || event.pointerType !== "mouse") return;
    clear();
    timer.current = setTimeout(
      () => lookUpAt(event.clientX, event.clientY, { pin: false }),
      HOVER_DELAY,
    );
  };

  return (
    <Tag
      ref={container}
      className={className}
      onPointerMove={onPointerMove}
      onPointerEnter={cancelClose}
      onPointerLeave={() => {
        clear();
        if (!pinned) closeSoon();
      }}
      onClick={(event) => {
        // Never hijack a link or button inside glossed content.
        if (event.target.closest("a, button, input, textarea, select")) return;
        lookUpAt(event.clientX, event.clientY, { pin: true });
      }}
    >
      {children}
      {target && (
        <Panel
          target={target}
          pinned={pinned}
          onClose={close}
          onHover={(inside) => {
            if (inside) cancelClose();
            else if (!pinned) closeSoon();
          }}
        />
      )}
    </Tag>
  );
}
