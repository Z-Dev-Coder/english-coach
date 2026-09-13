import { useEffect, useState } from "react";

import Glossed from "../Glossed";
import { api } from "../../lib/api";
import { cx } from "../../lib/cx";
import Icon from "../../lib/icons";
import { Button, Spinner } from "../../lib/ui";

/**
 * A choose-the-answer exercise the learner can actually check.
 *
 * The lesson wrote these as prose -- "1. I need to drop ___ ... (by / off / in)"
 * -- with no answer anywhere, so the learner could read the options and never
 * find out if they were right. Here each item's options are buttons: pick one
 * and see immediately whether it is right, with the explanation of why, and
 * why the others don't fit. A score and a "try again" close it.
 *
 * Falls back to the plain text (`fallback`) when the prompt isn't a
 * choose-the-answer exercise, and to unmarked choices when no answer key could
 * be produced -- saying so rather than pretending to mark.
 */

function Item({ number, item, checkable, chosen, onChoose }) {
  const answered = chosen != null;
  const correct = answered && checkable && chosen === item.answer;
  const [before, after] = item.sentence.split(/_{2,}|\.{3,}|…/);

  return (
    <li className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
      <p className="text-[16px] leading-relaxed">
        <span className="mr-1.5 text-ink-3">{number}.</span>
        {before}
        <span
          className={cx(
            "mx-1 inline-block min-w-12 border-b-2 px-1 text-center font-semibold",
            !answered && "border-[color:var(--color-line)] text-transparent",
            answered && correct && "border-[color:var(--color-good-ink)] text-[color:var(--color-good-ink)]",
            answered && checkable && !correct && "border-[color:var(--color-accent)] text-[color:var(--color-accent)]",
            answered && !checkable && "border-ink",
          )}
        >
          {answered ? chosen : "___"}
        </span>
        {after}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {item.options.map((option) => {
          const isChosen = chosen === option;
          const isAnswer = checkable && answered && option === item.answer;
          return (
            <button
              key={option}
              onClick={() => !answered && onChoose(option)}
              disabled={answered}
              className={cx(
                "rounded-full px-4 py-1.5 text-[14px] ring-1 transition",
                !answered && "ring-[color:var(--color-line)] hover:bg-surface dark:ring-white/15 dark:hover:bg-white/10",
                isAnswer && "bg-[color:var(--color-good-ink)] text-white ring-[color:var(--color-good-ink)]",
                isChosen && checkable && !isAnswer && "bg-[color:var(--color-accent)] text-white ring-[color:var(--color-accent)]",
                isChosen && !checkable && "bg-ink text-white ring-ink dark:bg-white dark:text-black",
                answered && !isChosen && !isAnswer && "opacity-50 ring-[color:var(--color-line)] dark:ring-white/10",
              )}
            >
              {option}
            </button>
          );
        })}
      </div>

      {answered && checkable && (
        <div className="mt-3 text-[14px]">
          <p className={cx("flex items-center gap-1.5 font-semibold", correct ? "text-[color:var(--color-good-ink)]" : "text-[color:var(--color-accent)]")}>
            <Icon name={correct ? "check" : "close"} size={14} />
            {correct ? "Correct" : `Not quite — the answer is "${item.answer}"`}
          </p>
          {item.explanation && (
            <Glossed as="p" className="mt-1 text-ink-2 dark:text-white/70">
              {item.explanation}
            </Glossed>
          )}
        </div>
      )}
    </li>
  );
}

import MatchExercise from "./MatchExercise";

export default function ChoiceExercise({ lessonId, activityId, fallback }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [chosen, setChosen] = useState({});

  useEffect(() => {
    if (!lessonId || !activityId) {
      setFailed(true);
      return;
    }
    let live = true;
    api
      .lessonExercise(lessonId, activityId)
      .then((result) => live && setData(result))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [lessonId, activityId]);

  if (data?.type === "matching" && data.pairs?.length) return <MatchExercise data={data} />;
  if (failed || (data && !data.items?.length)) return fallback ?? null;
  if (!data) {
    return (
      <p className="mt-3 flex items-center gap-2 text-[13px] text-ink-3">
        <Spinner /> Preparing the exercise…
      </p>
    );
  }

  const items = data.items;
  const answeredCount = Object.keys(chosen).length;
  const score = data.checkable
    ? items.filter((item, index) => chosen[index] === item.answer).length
    : null;
  const finished = answeredCount === items.length;

  return (
    <div className="mt-4">
      {!data.checkable && (
        <p className="mb-3 text-[13px] text-ink-3">
          The AI mentor isn&rsquo;t reachable, so answers can&rsquo;t be marked this time. Choose
          anyway, and say each sentence out loud.
        </p>
      )}
      <ol className="space-y-3">
        {items.map((item, index) => (
          <Item
            key={index}
            number={index + 1}
            item={item}
            checkable={data.checkable}
            chosen={chosen[index]}
            onChoose={(option) => setChosen((current) => ({ ...current, [index]: option }))}
          />
        ))}
      </ol>

      {finished && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl p-4 ring-1 ring-[color:var(--color-line)] dark:ring-white/10">
          {score != null && (
            <p className="font-semibold">
              {score} / {items.length} correct
              {score === items.length ? " — well done" : ""}
            </p>
          )}
          <Button variant="secondary" size="sm" onClick={() => setChosen({})}>
            Try again
          </Button>
          <span className="micro">then say each full sentence out loud</span>
        </div>
      )}
    </div>
  );
}
