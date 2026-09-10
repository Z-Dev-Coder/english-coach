import { useEffect, useRef, useState } from "react";

/**
 * Motion primitives.
 *
 * Two rules shape everything here:
 *
 * 1. Motion must never be the only way content appears. Every effect starts
 *    from a state that is already correct if the animation never runs -- a
 *    reveal that fails leaves visible text, and a counter that fails shows the
 *    real number. An interface that is blank when JavaScript stalls is broken,
 *    not animated.
 * 2. prefers-reduced-motion is checked in JavaScript, not just CSS, because
 *    these effects animate values rather than styles and CSS cannot shortcut
 *    them.
 */

export const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Counts up to a number when it first appears.
 *
 * Returns the final value immediately under reduced motion, and for anything
 * non-numeric, so callers never have to special-case it.
 */
export function useCountUp(value, { duration = 900 } = {}) {
  const target = Number(value);
  const valid = Number.isFinite(target);
  const [display, setDisplay] = useState(valid ? 0 : value);
  const ref = useRef(null);

  useEffect(() => {
    if (!valid) {
      setDisplay(value);
      return undefined;
    }
    if (prefersReducedMotion() || target === 0) {
      setDisplay(target);
      return undefined;
    }

    const node = ref.current;
    let frame = null;
    let start = null;

    const step = (time) => {
      if (start == null) start = time;
      const progress = Math.min(1, (time - start) / duration);
      // Ease-out: fast to most of the value, then settling. A linear count
      // reads like a loading spinner rather than a result arriving.
      const eased = 1 - (1 - progress) ** 3;
      setDisplay(Math.round(target * eased));
      if (progress < 1) frame = requestAnimationFrame(step);
    };

    const run = () => {
      frame = requestAnimationFrame(step);
    };

    if (!node) {
      run();
    } else {
      const observer = new IntersectionObserver(([entry]) => {
        if (!entry.isIntersecting) return;
        run();
        observer.disconnect();
      });
      observer.observe(node);
      return () => {
        observer.disconnect();
        if (frame) cancelAnimationFrame(frame);
      };
    }

    return () => {
      if (frame) cancelAnimationFrame(frame);
    };
  }, [target, valid, value, duration]);

  return [display, ref];
}

/**
 * Moves a CSS variable to track the pointer across an element, so a highlight
 * can follow the cursor.
 *
 * Written straight to the node rather than through state: this fires on every
 * mousemove, and re-rendering a card subtree at that rate is exactly how a
 * decorative touch turns into jank.
 */
export function useSpotlight() {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || prefersReducedMotion()) return undefined;
    if (!window.matchMedia("(hover: hover)").matches) return undefined;

    const onMove = (event) => {
      const rect = node.getBoundingClientRect();
      node.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
      node.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
    };

    node.addEventListener("pointermove", onMove);
    return () => node.removeEventListener("pointermove", onMove);
  }, []);

  return ref;
}
