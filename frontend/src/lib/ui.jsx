/**
 * The design system.
 *
 * Every screen is built from these, so visual consistency is structural rather
 * than something each page has to remember. Components take semantic props
 * (tone, size, variant) instead of raw class strings — that keeps Tailwind
 * classes out of page files and makes a restyle a one-file change.
 */

import { useState } from "react";

import { cx } from "./cx";

/* ---------------------------------------------------------------- Surface */

export function Card({ children, className = "", interactive = false, as: Tag = "div", ...props }) {
  return (
    <Tag
      className={cx(
        "rounded-2xl bg-surface p-4 ring-1 ring-[color:var(--color-line)]",
        "dark:bg-white/[0.03] dark:ring-white/10",
        interactive &&
          "transition duration-200 hover:-translate-y-0.5 hover:shadow-lift focus-visible:-translate-y-0.5",
        className,
      )}
      {...props}
    >
      {children}
    </Tag>
  );
}

export function SectionHeading({ title, action, id }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-4">
      <h2 id={id} className="text-[15px] font-semibold">
        {title}
      </h2>
      {action}
    </div>
  );
}

/* ---------------------------------------------------------------- Controls */

// Black pills. The primary action reads as primary through contrast, which
// leaves the accent colour free to actually mean something.
const BUTTON_VARIANTS = {
  primary:
    "bg-ink text-white hover:opacity-90 disabled:opacity-25 dark:bg-white dark:text-ink",
  secondary:
    "bg-surface text-ink ring-1 ring-[color:var(--color-line)] hover:bg-sunken dark:bg-white/[0.06] dark:text-white/90 dark:ring-white/10",
  ghost: "text-ink-2 hover:bg-sunken dark:text-white/70 dark:hover:bg-white/[0.06]",
  danger: "bg-[color:var(--color-accent)] text-white hover:opacity-90",
};

const BUTTON_SIZES = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-[13px]",
  lg: "px-5 py-2.5 text-sm",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  loading = false,
  disabled,
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium",
        "transition duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...props}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current/30 border-t-current"
        />
      )}
      {children}
    </button>
  );
}

const FIELD_CLASS =
  "w-full rounded-xl border-0 bg-sunken px-3.5 py-2.5 text-sm text-ink " +
  "ring-1 ring-[color:var(--color-line)] transition placeholder:text-ink-3 " +
  "focus:bg-surface focus:ring-2 focus:ring-ink " +
  "dark:bg-white/[0.04] dark:text-white/90 dark:ring-white/10 dark:focus:ring-white";

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="micro mb-1.5 block">
        {label}
        {hint && <span className="ml-1 normal-case tracking-normal">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

export function Input({ className = "", ...props }) {
  return <input className={cx(FIELD_CLASS, className)} {...props} />;
}

export function Select({ className = "", children, ...props }) {
  return (
    <select className={cx(FIELD_CLASS, "pr-8", className)} {...props}>
      {children}
    </select>
  );
}

/** A toggle rendered as a chip. Used for interests, skills, immersion level. */
export function Chip({ active, children, ...props }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cx(
        "rounded-full px-3.5 py-1.5 text-sm font-medium transition duration-150 active:scale-95",
        active
          ? "bg-ink text-white dark:bg-white dark:text-ink"
          : "bg-sunken text-ink-2 hover:bg-[color:var(--color-line)] dark:bg-white/[0.06] dark:text-white/60",
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Switch({ checked, onChange, label, description }) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx(
          "mt-0.5 h-5 w-9 shrink-0 rounded-full p-0.5 transition",
          checked ? "bg-ink dark:bg-white" : "bg-[color:var(--color-line)] dark:bg-white/20",
        )}
      >
        <span
          className={cx(
            "block h-4 w-4 rounded-full bg-white shadow transition-transform duration-200",
            checked && "translate-x-4",
          )}
        />
      </button>
      <span className="text-sm">
        <span className="font-medium text-ink-2 dark:text-white/70">{label}</span>
        {description && (
          <span className="block text-ink-3 dark:text-white/40">{description}</span>
        )}
      </span>
    </label>
  );
}

/* ------------------------------------------------------------------ Status */

const PILL_TONES = {
  default: "text-ink-3 ring-[color:var(--color-line)] dark:text-white/50 dark:ring-white/15",
  brand: "text-ink ring-ink/25 dark:text-white/90 dark:ring-white/25",
  warn: "text-[color:var(--color-warn-ink)] ring-[color:var(--color-warn-ink)]/30",
  good: "text-[color:var(--color-good-ink)] ring-[color:var(--color-good-ink)]/30",
};

export function Pill({ children, tone = "default", className = "" }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-2 py-0.5 ring-1",
        "font-mono text-[10px] font-medium uppercase tracking-[0.1em]",
        PILL_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ProgressBar({ value, label, sublabel, weak }) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2 text-[13px]">
        <span className="font-medium text-ink-2 dark:text-white/70">{label}</span>
        <span
          className={cx(
            "font-mono text-[11px] tabular-nums",
            weak ? "text-[color:var(--color-accent)]" : "text-ink-3",
          )}
        >
          {Math.round(pct)}%{sublabel ? ` · ${sublabel}` : ""}
        </span>
      </div>
      <div
        className="h-1 overflow-hidden rounded-full bg-[color:var(--color-line)] dark:bg-white/10"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={typeof label === "string" ? label : undefined}
      >
        <div
          className={cx(
            "h-full rounded-full transition-all duration-700 ease-out",
            weak ? "bg-[color:var(--color-accent)]" : "bg-ink dark:bg-white",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** Circular progress. Used for the headline numbers where a bar would read as
 *  just another row of data. */
export function ProgressRing({ value, size = 72, stroke = 7, children, tone = "brand" }) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const tones = {
    brand: "stroke-ink dark:stroke-white",
    warn: "stroke-[color:var(--color-accent)]",
    good: "stroke-[color:var(--color-good-ink)]",
  };

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-[color:var(--color-line)] dark:stroke-white/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (pct / 100) * circumference}
          className={cx(tones[tone], "transition-[stroke-dashoffset] duration-1000 ease-out")}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">{children}</div>
    </div>
  );
}

export function StatTile({ label, value, unit, tone = "default" }) {
  const tones = {
    default: "text-ink dark:text-white",
    brand: "text-ink dark:text-white",
    warn: "text-[color:var(--color-accent)]",
  };
  return (
    <div>
      <dt className="micro">{label}</dt>
      <dd className={cx("mt-1.5 text-[26px] font-semibold leading-none tabular-nums", tones[tone])}>
        {value}
        {unit && <span className="ml-1 font-mono text-[11px] font-normal text-ink-3">{unit}</span>}
      </dd>
    </div>
  );
}

/* ----------------------------------------------------------------- Feedback */

/** Skeletons instead of a spinner: the page keeps its shape while loading, so
 *  content does not jump into place when it arrives. */
export function Skeleton({ className = "" }) {
  return (
    <div
      className={cx(
        "animate-shimmer rounded-xl bg-sunken dark:bg-white/[0.06]",
        "bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.55),transparent)] bg-[length:200%_100%]",
        className,
      )}
    />
  );
}

export function CardSkeleton({ lines = 2 }) {
  return (
    <Card>
      <Skeleton className="h-4 w-1/3" />
      <div className="mt-3 space-y-2">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton key={index} className="h-3 w-full last:w-2/3" />
        ))}
      </div>
    </Card>
  );
}

export function Spinner({ label = "Loading" }) {
  return (
    <div className="flex items-center gap-3 p-8 text-slate-500" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-[color:var(--color-line)] border-t-ink dark:border-t-white" />
      <span className="text-sm">{label}…</span>
    </div>
  );
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      className="animate-rise border-t border-[color:var(--color-accent)]/40 pt-3 text-[13px]"
    >
      <p className="micro mb-1 text-[color:var(--color-accent)]">Something went wrong</p>
      <p className="text-ink-2 dark:text-white/70">{error.message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 font-semibold underline underline-offset-2 hover:no-underline"
        >
          Try again
        </button>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- Guidance */

// A thin rule on the left over a near-white wash. A filled mint or indigo
// block is what made the old interface read as a default framework alert.
// No panel, no border, no tint. A note is a hairline, a small monospace label,
// and text. Colour appears only in the label, which is the one place it means
// something rather than decorating.
const CALLOUT_TONES = {
  tip: "text-[color:var(--color-warn-ink)] dark:text-amber-300",
  info: "text-ink-3",
  good: "text-[color:var(--color-good-ink)] dark:text-emerald-300",
  warn: "text-[color:var(--color-accent)]",
};

/** A highlighted note. Use for the one thing on a screen worth reading twice. */
export function Callout({ tone = "info", title, children, className = "" }) {
  const label = CALLOUT_TONES[tone] ?? CALLOUT_TONES.info;
  return (
    <div
      className={cx(
        "border-t border-[color:var(--color-line)] pt-3 dark:border-white/10",
        "text-[13px] leading-relaxed text-ink-2 dark:text-white/60",
        className,
      )}
    >
      {title && <p className={cx("micro mb-1.5", label)}>{title}</p>}
      <div>{children}</div>
    </div>
  );
}

/**
 * Numbered instructions, dismissible and remembered.
 *
 * Instructions are only useful the first few times. Leaving them on screen
 * forever turns them into furniture that gets scrolled past, so this collapses
 * to a single quiet link once the learner has read it.
 */
export function HowTo({ id, title = "How this works", steps = [], children }) {
  const storageKey = `english-coach:howto:${id}`;
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(storageKey) !== "done";
    } catch {
      return true;
    }
  });

  const dismiss = () => {
    try {
      localStorage.setItem(storageKey, "done");
    } catch {
      /* private mode: it just reappears next time, which is harmless */
    }
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="micro underline-offset-4 hover:text-ink hover:underline dark:hover:text-white"
      >
        {title}?
      </button>
    );
  }

  return (
    <Callout tone="info" title={title}>
      {steps.length > 0 && (
        <ol className="mt-1 space-y-1.5">
          {steps.map((step, index) => (
            <li key={index} className="flex gap-2.5">
              <span className="mt-px grid h-[17px] w-[17px] shrink-0 place-items-center rounded-full border border-current font-mono text-[10px] opacity-55">
                {index + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      )}
      {children}
      <button
        onClick={dismiss}
        className="micro mt-3 opacity-60 hover:opacity-100"
      >
        Got it
      </button>
    </Callout>
  );
}

export function EmptyState({ icon = "✦", title, body, action }) {
  return (
    <div className="rounded-2xl border border-dashed border-[color:var(--color-line)] p-10 text-center dark:border-white/10">
      <div aria-hidden="true" className="text-2xl text-ink-3">
        {icon}
      </div>
      <p className="mt-3 text-[15px] font-semibold text-ink dark:text-white/90">{title}</p>
      {body && (
        <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">{body}</p>
      )}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}
