import { useEffect, useRef } from "react";

/**
 * The moving field behind the hero.
 *
 * The reference site puts a large animated graph behind a marketing headline,
 * where there is nothing to read and the animation *is* the content. Here the
 * same area sits above a lesson, so the brief is different: it has to suggest
 * the same family of design without competing with text for attention.
 *
 * So this is deliberately quiet. A sparse grid of dots drifts on two slow sine
 * waves; a dot brightens to the accent only as its wave crests, which makes a
 * slow pulse travel across the block rather than the whole field blinking at
 * once. Nothing moves faster than a few pixels a second.
 *
 * Three things keep it honest as a background:
 *
 * - It is drawn on a canvas at device resolution and marked aria-hidden, so it
 *   costs the accessibility tree nothing.
 * - It stops completely when the tab is hidden and when the element scrolls out
 *   of view. A background animation that keeps a laptop fan running while the
 *   user reads a different tab is a bug, not a flourish.
 * - Under prefers-reduced-motion it paints one static frame and never starts
 *   the loop. That setting is often a request from someone who gets motion
 *   sickness or migraines, so it deserves an early return, not a slower speed.
 */

const SPACING = 26;   // px between dots
const DOT = 1.6;
const SPEED = 0.00022; // radians per ms — one full wave takes about 8 minutes

export default function HeroField({ className = "" }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const context = canvas.getContext("2d");
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let frame = null;
    let visible = true;

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const draw = (time) => {
      context.clearRect(0, 0, width, height);
      const columns = Math.ceil(width / SPACING);
      const rows = Math.ceil(height / SPACING);

      for (let column = 0; column <= columns; column += 1) {
        for (let row = 0; row <= rows; row += 1) {
          // Two waves at different angles and periods, so the pattern never
          // repeats visibly on the scale of a session.
          const wave =
            Math.sin(column * 0.32 + time * SPEED) +
            Math.sin(row * 0.45 - time * SPEED * 0.7);
          const strength = (wave + 2) / 4; // 0..1

          const x = column * SPACING;
          const y = row * SPACING + Math.sin(column * 0.32 + time * SPEED) * 5;

          if (strength > 0.82) {
            // Only the crests take the accent, so the colour reads as a pulse
            // moving through the field rather than as decoration everywhere.
            context.fillStyle = `rgba(255, 87, 26, ${(strength - 0.82) * 3.4})`;
            context.beginPath();
            context.arc(x, y, DOT * 1.5, 0, Math.PI * 2);
            context.fill();
          } else {
            context.fillStyle = `rgba(128, 128, 128, ${0.06 + strength * 0.13})`;
            context.beginPath();
            context.arc(x, y, DOT, 0, Math.PI * 2);
            context.fill();
          }
        }
      }
    };

    const loop = (time) => {
      draw(time);
      frame = requestAnimationFrame(loop);
    };

    const start = () => {
      if (frame == null && visible && !reduced) frame = requestAnimationFrame(loop);
    };
    const stop = () => {
      if (frame != null) cancelAnimationFrame(frame);
      frame = null;
    };

    resize();
    if (reduced) {
      draw(0); // one still frame; the pattern still reads, nothing moves
      return undefined;
    }

    // Don't animate a hero the user has scrolled past, or a tab they left.
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) start();
      else stop();
    });
    observer.observe(canvas);

    const onVisibility = () => {
      if (document.hidden) stop();
      else start();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("resize", resize);
    start();

    return () => {
      stop();
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
    />
  );
}
