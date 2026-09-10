import { useEffect, useRef, useState } from "react";

import { cx } from "../lib/cx";
import { prefersReducedMotion } from "../lib/motion";

/**
 * Reveals its children the first time they scroll into view.
 *
 * Once only -- re-animating on every scroll past is the thing that makes these
 * effects feel cheap, and it makes a long page tiring to move around in.
 */
export default function Reveal({ children, delay = 0, className = "", as: Tag = "div" }) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(() => prefersReducedMotion());

  useEffect(() => {
    if (seen) return undefined;
    const node = ref.current;
    if (!node) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setSeen(true);
        observer.disconnect();
      },
      // A little margin so a block has started animating by the time it is
      // properly on screen, rather than beginning as it lands.
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    observer.observe(node);

    // Failsafe. Hiding content until an observer fires means any case where it
    // does not fire leaves that content invisible forever -- printing, a
    // full-page screenshot, an in-page find, a browser that throttles
    // observers in a background tab. A decorative entrance is never worth
    // losing content over, so reveal unconditionally after a beat.
    const failsafe = setTimeout(() => setSeen(true), 2500);

    return () => {
      observer.disconnect();
      clearTimeout(failsafe);
    };
  }, [seen]);

  return (
    <Tag
      ref={ref}
      className={cx("reveal", seen && "is-in", className)}
      style={seen && delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}
