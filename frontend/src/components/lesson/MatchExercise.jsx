import { useState } from "react";

import Glossed from "../Glossed";
import { cx } from "../../lib/cx";
import Icon from "../../lib/icons";
import { Button } from "../../lib/ui";

/**
 * Match each phrase to its meaning, and check.
 *
 * The lesson wrote these as two lines of text -- "Phrases: drop off, pick up..."
 * and "Meanings: a) ...; b) ..." -- with nothing to click and no answers. Here
 * each phrase gets the meanings as choices; after choosing, it says right or
 * wrong with an explanation and an example. A meaning already used for another
 * phrase is marked, since each meaning belongs to exactly one phrase.
 */
export default function MatchExercise({ data }) {
  const [chosen, setChosen] = useState({});
  const { meanings, pairs, checkable } = data;
  const byLetter = Object.fromEntries(meanings.map((meaning) => [meaning.letter, meaning.text]));
  const usedLetters = new Set(Object.values(chosen));
  const finished = Object.keys(chosen).length === pairs.length;
  const score = checkable ? pairs.filter((pair, index) => chosen[index] === pair.answer).length : null;

  return (
    <div className="mt-4">
      {!checkable && (
        <p className="mb-3 text-[13px] text-ink-3">
          The AI mentor isn&rsquo;t reachable, so matches can&rsquo;t be marked this time.
        </p>
      )}
      <ol className="space-y-3">
        {pairs.map((pair, index) => {
          const pick = chosen[index];
          const answered = pick != null;
          const correct = answered && checkable && pick === pair.answer;
          return (
            <li key={pair.phrase} className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
              <p className="text-[16px] font-semibold">
                {index + 1}. {pair.phrase}
                {answered && (
                  <span
                    className={cx(
                      "ml-2 text-[14px] font-normal",
                      !checkable && "text-ink-2",
                      checkable && (correct ? "text-[color:var(--color-good-ink)]" : "text-[color:var(--color-accent)]"),
                    )}
                  >
                    → {byLetter[pick]}
                  </span>
                )}
              </p>

              {!answered && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {meanings.map((meaning) => (
                    <button
                      key={meaning.letter}
                      onClick={() => setChosen((current) => ({ ...current, [index]: meaning.letter }))}
                      className={cx(
                        "rounded-full px-3 py-1.5 text-left text-[13px] ring-1 transition hover:bg-surface dark:hover:bg-white/10",
                        usedLetters.has(meaning.letter)
                          ? "text-ink-3 ring-[color:var(--color-line)] line-through dark:ring-white/10"
                          : "ring-[color:var(--color-line)] dark:ring-white/15",
                      )}
                    >
                      {meaning.text}
                    </button>
                  ))}
                </div>
              )}

              {answered && checkable && (
                <div className="mt-2 text-[14px]">
                  <p
                    className={cx(
                      "flex items-center gap-1.5 font-semibold",
                      correct ? "text-[color:var(--color-good-ink)]" : "text-[color:var(--color-accent)]",
                    )}
                  >
                    <Icon name={correct ? "check" : "close"} size={14} />
                    {correct ? "Correct" : `Not quite — it means "${byLetter[pair.answer]}"`}
                  </p>
                  {pair.explanation && (
                    <Glossed as="p" className="mt-1 text-ink-2 dark:text-white/70">
                      {pair.explanation}
                    </Glossed>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {finished && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl p-4 ring-1 ring-[color:var(--color-line)] dark:ring-white/10">
          {score != null && (
            <p className="font-semibold">
              {score} / {pairs.length} correct{score === pairs.length ? " — well done" : ""}
            </p>
          )}
          <Button variant="secondary" size="sm" onClick={() => setChosen({})}>
            Try again
          </Button>
          <span className="micro">then use each phrase in a sentence about your own routine</span>
        </div>
      )}
    </div>
  );
}
