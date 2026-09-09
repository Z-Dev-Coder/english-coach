import { cx } from "../lib/cx";
import { Pill } from "../lib/ui";

/**
 * Shows a word-level diff of what the learner produced.
 *
 * The percentage is deliberately secondary. "82%" teaches nothing; seeing that
 * you wrote "very" where the sentence said "really" teaches the collocation.
 */

const OP_STYLES = {
  correct: "text-slate-700 dark:text-slate-200",
  wrong:
    "rounded bg-amber-100 px-1 text-amber-900 dark:bg-amber-500/20 dark:text-amber-200",
  missing:
    "rounded bg-rose-100 px-1 text-rose-900 line-through dark:bg-rose-500/20 dark:text-rose-200",
  extra:
    "rounded bg-slate-200 px-1 text-slate-500 line-through dark:bg-slate-700 dark:text-slate-400",
};

export default function WordDiff({ result, caveat }) {
  if (!result) return null;
  const { tokens = [], percentage, summary, is_perfect: isPerfect } = result;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone={isPerfect ? "good" : percentage >= 70 ? "brand" : "warn"}>
          {percentage}%
        </Pill>
        <span className="text-sm text-slate-500 dark:text-slate-400">{summary}</span>
      </div>

      <p className="flex flex-wrap gap-x-1.5 gap-y-1 text-lg leading-relaxed">
        {tokens.map((token, index) => (
          <span key={index} className={cx(OP_STYLES[token.op])}>
            {token.op === "extra" ? token.actual : token.expected}
            {token.op === "wrong" && token.actual && (
              <span className="ml-1 text-sm opacity-70">(you said “{token.actual}”)</span>
            )}
          </span>
        ))}
      </p>

      {!isPerfect && (
        <ul className="space-y-1 text-sm text-slate-500 dark:text-slate-400">
          {tokens
            .filter((token) => token.op !== "correct")
            .slice(0, 6)
            .map((token, index) => (
              <li key={index}>
                {token.op === "wrong" && (
                  <>
                    You said <b>{token.actual}</b> — it was <b>{token.expected}</b>
                  </>
                )}
                {token.op === "missing" && (
                  <>
                    You left out <b>{token.expected}</b>
                  </>
                )}
                {token.op === "extra" && (
                  <>
                    You added <b>{token.actual}</b>
                  </>
                )}
              </li>
            ))}
        </ul>
      )}

      {caveat && <p className="text-xs leading-relaxed text-slate-400">{caveat}</p>}
    </div>
  );
}
