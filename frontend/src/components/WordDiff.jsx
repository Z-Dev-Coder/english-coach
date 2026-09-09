import { cx } from "../lib/cx";
import { Pill } from "../lib/ui";

/**
 * Shows a word-level diff of what the learner produced.
 *
 * The percentage is deliberately secondary. "82%" teaches nothing; seeing that
 * you wrote "very" where the sentence said "really" teaches the collocation.
 */

const OP_STYLES = {
  correct: "text-ink dark:text-white/85",
  wrong:
    "rounded bg-[color:var(--color-highlight)]/45 px-1 text-ink dark:text-black",
  missing:
    "rounded bg-[color:var(--color-bad-bg)] px-1 text-[color:var(--color-accent)] line-through",
  extra: "rounded bg-sunken px-1 text-ink-3 line-through dark:bg-white/[0.06]",
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
        <span className="text-sm text-ink-2 dark:text-white/55">{summary}</span>
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
        <ul className="space-y-1 text-sm text-ink-2 dark:text-white/55">
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

      {caveat && <p className="text-xs leading-relaxed text-ink-3">{caveat}</p>}
    </div>
  );
}
