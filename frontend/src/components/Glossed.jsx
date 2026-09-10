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
const PANEL_WIDTH = 320;
const GAP = 10;

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

/** Keeps the panel on screen next to the word it belongs to. */
function position(rect) {
  const left = Math.min(
    Math.max(GAP, rect.left + rect.width / 2 - PANEL_WIDTH / 2),
    window.innerWidth - PANEL_WIDTH - GAP,
  );
  // Below the word by default, above it when there is no room below.
  const below = rect.bottom + GAP;
  const room = window.innerHeight - rect.bottom;
  return room > 220
    ? { left, top: below, placement: "below" }
    : { left, top: rect.top - GAP, placement: "above" };
}

function Panel({ target, onClose, pinned }) {
  const { status, data } = useDefinition(target.word);
  const [saving, setSaving] = useState(false);
  const { left, top, placement } = position(target.rect);

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
      style={{
        left,
        top,
        width: PANEL_WIDTH,
        transform: placement === "above" ? "translateY(-100%)" : undefined,
      }}
      // The panel sits inside the same pointer world as the text; without this
      // a hover-opened panel closes the moment you move onto it to read it.
      onPointerEnter={(event) => event.stopPropagation()}
    >
      <div className="overflow-hidden rounded-xl bg-surface shadow-lift ring-1 ring-[color:var(--color-line)] dark:bg-[#141414] dark:ring-white/12">
        <div className="flex items-baseline gap-2 border-b border-[color:var(--color-line)] px-4 py-2.5 dark:border-white/10">
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

        <div className="px-4 py-3">
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
          <div className="border-t border-[color:var(--color-line)] px-4 py-2 dark:border-white/10">
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
  const container = useRef(null);

  const clear = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const close = useCallback(() => {
    clear();
    setTarget(null);
    setPinned(false);
  }, [clear]);

  // A pinned panel is dismissed the way every other transient surface is.
  useEffect(() => {
    if (!pinned) return undefined;
    const onKey = (event) => event.key === "Escape" && close();
    const onDown = (event) => {
      if (!container.current?.contains(event.target)) close();
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

  useEffect(() => clear, [clear]);

  const lookUpAt = (x, y, { pin }) => {
    const found = wordAtPoint(x, y);
    if (!found) {
      if (!pin) close();
      return;
    }
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
      onPointerLeave={() => !pinned && close()}
      onClick={(event) => {
        // Never hijack a link or button inside glossed content.
        if (event.target.closest("a, button, input, textarea, select")) return;
        lookUpAt(event.clientX, event.clientY, { pin: true });
      }}
    >
      {children}
      {target && <Panel target={target} pinned={pinned} onClose={close} />}
    </Tag>
  );
}
