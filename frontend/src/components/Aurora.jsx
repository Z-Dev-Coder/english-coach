/**
 * The hero backdrop.
 *
 * This replaces an earlier canvas of drifting 3px dots. That version was
 * technically animated and practically invisible, which is the worst of both:
 * it cost a requestAnimationFrame loop and bought nothing. The mistake was
 * treating "subtle" as the goal. Subtlety is a means -- the goal is that the
 * top of the page should look lit and alive, and you cannot get there with
 * marks small enough that a screenshot can't show them.
 *
 * So the light is now the subject. Two large accent blooms drift slowly behind
 * a graph-paper grid, a beam sweeps the top edge, and a few grid cells blink in
 * sequence. All of it is composited transform and opacity -- no per-frame
 * JavaScript at all, which makes it both cheaper than the dots it replaces and
 * far more visible.
 *
 * It stays readable because the light is pushed to the right, away from the
 * headline, and a gradient scrim (in the parent) fades it out under the text.
 */

/* Deterministic cells, so the "activity" reads as a status board rather than
   as random flicker. Each is [column, row, delay in seconds]. */
const CELLS = [
  [4, 0, 0], [6, 2, 1.4], [5, 4, 2.9], [8, 1, 0.7],
  [7, 3, 2.1], [9, 4, 3.6], [10, 2, 4.3],
];

export default function Aurora() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* Grid, masked to a soft ellipse so it has no hard edge. */}
      <div className="techgrid absolute inset-0 opacity-70" />

      {/* Cells lighting up on the grid. Positioned on the same 44px module as
          the grid itself, so they land in the squares rather than near them. */}
      <div className="absolute inset-0 opacity-60">
      {CELLS.map(([column, row, delay]) => (
        <span
          key={`${column}-${row}`}
          // Inset by a pixel so the lit square sits inside the grid line
          // rather than painting over it -- otherwise the cells read as blocks
          // dropped on top of the grid instead of squares of it lighting up.
          className="absolute rounded-[2px] bg-[color:var(--color-accent)]/45"
          style={{
            left: `calc(50% + ${column * 44}px + 1px)`,
            top: `${row * 44 + 1}px`,
            width: 42,
            height: 42,
            animation: `pulse-cell 6s ease-in-out ${delay}s infinite`,
          }}
        />
      ))}
      </div>

      {/* The blooms. Sized in vw so they scale with the hero rather than
          becoming two small circles on a wide screen. */}
      <div
        className="glow animate-drift-a bg-[color:var(--color-accent)]/40"
        style={{ width: "34vw", height: "34vw", right: "-6vw", top: "-14vw" }}
      />
      <div
        className="glow animate-drift-b bg-[color:var(--color-accent)]/20"
        style={{ width: "26vw", height: "26vw", right: "16vw", bottom: "-16vw" }}
      />
      {/* A cool second light. Two hues make the area read as depth; one hue
          reads as a coloured panel. */}
      <div
        className="glow animate-drift-b bg-indigo-500/20 dark:bg-indigo-400/25"
        style={{ width: "22vw", height: "22vw", right: "30vw", top: "-8vw", animationDelay: "-8s" }}
      />

      {/* Beam along the top edge — the clearest single signal that a page is
          alive, and it costs one transform. */}
      <div className="absolute inset-x-0 top-0 h-px overflow-hidden">
        <div className="animate-sweep h-px w-1/3 bg-gradient-to-r from-transparent via-[color:var(--color-accent)] to-transparent" />
      </div>

      {/* Grain last, over everything, so the blooms have a surface. */}
      <div className="grain absolute inset-0 opacity-[0.14] mix-blend-overlay dark:opacity-20" />
    </div>
  );
}
