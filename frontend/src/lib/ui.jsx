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
        "rounded-xl bg-white p-4 shadow-soft ring-1 ring-slate-900/5",
        "dark:bg-slate-900 dark:ring-white/10",
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
    <div className="mb-2.5 flex items-baseline justify-between gap-4">
      <h2 id={id} className="text-base font-semibold tracking-tight">
        {title}
      </h2>
      {action}
    </div>
  );
}

/* ---------------------------------------------------------------- Controls */

const BUTTON_VARIANTS = {
  primary:
    "bg-brand-600 text-white shadow-sm hover:bg-brand-700 active:bg-brand-800 disabled:bg-brand-300 dark:disabled:bg-brand-900",
  secondary:
    "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 active:bg-slate-100 dark:bg-slate-800 dark:text-slate-200 dark:ring-white/10 dark:hover:bg-slate-700",
  ghost:
    "text-brand-700 hover:bg-brand-50 active:bg-brand-100 dark:text-brand-300 dark:hover:bg-white/5",
  danger: "bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800",
};

const BUTTON_SIZES = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2.5 text-sm",
  lg: "px-5 py-3 text-base",
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
        "inline-flex items-center justify-center gap-2 rounded-xl font-semibold",
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
  "w-full rounded-xl border-0 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 " +
  "ring-1 ring-slate-200 transition placeholder:text-slate-400 " +
  "focus:bg-white focus:ring-2 focus:ring-brand-500 " +
  "dark:bg-slate-800 dark:text-slate-100 dark:ring-white/10 dark:focus:bg-slate-800";

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {hint && <span className="ml-1 font-normal text-slate-400">{hint}</span>}
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
          ? "bg-brand-600 text-white shadow-sm"
          : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700",
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
          checked ? "bg-brand-600" : "bg-slate-300 dark:bg-slate-700",
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
        <span className="font-medium text-slate-700 dark:text-slate-300">{label}</span>
        {description && (
          <span className="block text-slate-400 dark:text-slate-500">{description}</span>
        )}
      </span>
    </label>
  );
}

/* ------------------------------------------------------------------ Status */

const PILL_TONES = {
  default: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  brand: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  warn: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  good: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
};

export function Pill({ children, tone = "default", className = "" }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium",
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
      <div className="mb-1.5 flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium text-slate-700 dark:text-slate-300">{label}</span>
        <span
          className={cx(
            "tabular-nums",
            weak ? "text-amber-600 dark:text-amber-400" : "text-slate-400",
          )}
        >
          {Math.round(pct)}%{sublabel ? ` · ${sublabel}` : ""}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={typeof label === "string" ? label : undefined}
      >
        <div
          className={cx(
            "h-full rounded-full transition-all duration-700 ease-out",
            weak
              ? "bg-gradient-to-r from-amber-400 to-amber-500"
              : "bg-gradient-to-r from-brand-500 to-violet-500",
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
    brand: "stroke-brand-500",
    warn: "stroke-amber-500",
    good: "stroke-emerald-500",
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
          className="stroke-slate-100 dark:stroke-slate-800"
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
    default: "text-slate-900 dark:text-white",
    brand: "text-brand-600 dark:text-brand-300",
    warn: "text-amber-600 dark:text-amber-400",
  };
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className={cx("mt-1 text-2xl font-bold tabular-nums", tones[tone])}>
        {value}
        {unit && <span className="ml-1 text-sm font-medium text-slate-400">{unit}</span>}
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
        "animate-shimmer rounded-xl bg-slate-200/70 dark:bg-slate-800",
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
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      <span className="text-sm">{label}…</span>
    </div>
  );
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      className="animate-rise rounded-xl bg-rose-50 p-4 text-sm text-rose-800 ring-1 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-200 dark:ring-rose-500/20"
    >
      <p className="font-medium">{error.message}</p>
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

const CALLOUT_TONES = {
  tip: {
    box: "bg-amber-50 text-amber-900 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-100 dark:ring-amber-500/25",
    label: "text-amber-700 dark:text-amber-300",
    icon: "💡",
  },
  info: {
    box: "bg-brand-50 text-brand-900 ring-brand-200 dark:bg-brand-500/10 dark:text-brand-50 dark:ring-brand-500/25",
    label: "text-brand-700 dark:text-brand-300",
    icon: "ℹ️",
  },
  good: {
    box: "bg-emerald-50 text-emerald-900 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-100 dark:ring-emerald-500/25",
    label: "text-emerald-700 dark:text-emerald-300",
    icon: "✓",
  },
  warn: {
    box: "bg-rose-50 text-rose-900 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-100 dark:ring-rose-500/25",
    label: "text-rose-700 dark:text-rose-300",
    icon: "⚠",
  },
};

/** A highlighted note. Use for the one thing on a screen worth reading twice. */
export function Callout({ tone = "info", title, children, className = "" }) {
  const style = CALLOUT_TONES[tone] ?? CALLOUT_TONES.info;
  return (
    <div className={cx("rounded-xl px-3.5 py-3 text-sm ring-1", style.box, className)}>
      <div className="flex gap-2.5">
        <span aria-hidden="true" className="mt-px shrink-0">
          {style.icon}
        </span>
        <div className="min-w-0">
          {title && <p className={cx("mb-0.5 font-semibold", style.label)}>{title}</p>}
          <div className="leading-relaxed">{children}</div>
        </div>
      </div>
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
        className="text-xs font-medium text-slate-400 underline-offset-2 hover:text-brand-600 hover:underline dark:hover:text-brand-300"
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
              <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full bg-brand-600 text-[10px] font-bold text-white">
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
        className="mt-2.5 text-xs font-semibold text-brand-700 hover:underline dark:text-brand-300"
      >
        Got it, hide this
      </button>
    </Callout>
  );
}

export function EmptyState({ icon = "✨", title, body, action }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
      <div aria-hidden="true" className="text-3xl">
        {icon}
      </div>
      <p className="mt-3 font-semibold text-slate-700 dark:text-slate-200">{title}</p>
      {body && (
        <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">{body}</p>
      )}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}
