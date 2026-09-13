import { useEffect, useMemo, useRef, useState } from "react";

import Glossed from "./Glossed";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { Button, CardSkeleton, ErrorNote, Pill } from "../lib/ui";

/**
 * A writing task taught as a lesson.
 *
 * A prompt alone -- "write a message asking a colleague to postpone a meeting"
 * -- tells a learner what to write and nothing about how, so they fall back on
 * the English they already have. So the lesson comes first: the vocabulary,
 * phrasal verbs, expressions and sentence patterns for this topic, a plan, and
 * a model text. Then the learner writes with a checklist that ticks as they use
 * what they were taught, and the feedback says what was used and what to try.
 *
 * Used by the lesson runner and by Practice > Writing, so both teach the same
 * way. `onFinished` is called once feedback has been read.
 */

/** Rough client-side mirror of the server's usage check, for live ticks only. */
function stem(word) {
  for (const suffix of ["ing", "ied", "ies", "ed", "es", "s"]) {
    if (word.endsWith(suffix) && word.length - suffix.length >= 3) return word.slice(0, -suffix.length);
  }
  return word;
}
const DROPPABLE = new Set(["a", "an", "the", "my", "your", "his", "her", "our", "their", "sb", "sth", "someone", "something"]);
const words = (text) =>
  text
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/\.\.\.|…/g, " ")
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);

function isUsed(text, item) {
  const tokens = words(text).map(stem);
  const keys = words(item).filter((word) => !DROPPABLE.has(word)).map(stem);
  if (!keys.length) return false;
  let position = 0;
  for (let index = 0; index < keys.length; index += 1) {
    const window = index === 0 ? tokens.slice(position) : tokens.slice(position, position + 4);
    const offset = window.indexOf(keys[index]);
    if (offset === -1) return false;
    position += offset + 1;
  }
  return true;
}

function ItemList({ title, items }) {
  if (!items?.length) return null;
  return (
    <section className="mt-5">
      <h3 className="micro">{title}</h3>
      <ul className="mt-2 grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.text} className="rounded-xl bg-sunken p-3 dark:bg-white/[0.04]">
            <p className="font-semibold">{item.text}</p>
            <Glossed as="p" className="mt-0.5 text-[14px] text-ink-2 dark:text-white/70">
              {item.meaning}
            </Glossed>
            {item.example && (
              <p className="mt-1 border-l-2 border-[color:var(--color-line)] pl-2.5 text-[13px] italic text-ink-3">
                {item.example}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function WritingLesson({ task, onFinished, finishLabel = "Finish" }) {
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState(null);
  const [phase, setPhase] = useState("learn");
  const [showModel, setShowModel] = useState(false);
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const startedAt = useRef(0);

  useEffect(() => {
    let live = true;
    setLesson(null);
    setPhase("learn");
    setResult(null);
    setText("");
    api
      .writingLesson({ task })
      .then((data) => live && setLesson(data))
      .catch((err) => live && setError(err));
    return () => {
      live = false;
    };
  }, [task]);

  const targets = useMemo(() => {
    if (!lesson) return [];
    return [
      ...(lesson.vocabulary ?? []).map((item) => item.text),
      ...(lesson.phrasal_verbs ?? []).map((item) => item.text),
      ...(lesson.expressions ?? []).map((item) => item.text),
      ...(lesson.sentence_patterns ?? []).map((item) => item.pattern),
    ];
  }, [lesson]);

  const usedNow = useMemo(() => targets.filter((item) => isUsed(text, item)), [targets, text]);
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  // A realistic bar: use a handful of what was taught, not all of it.
  const goal = Math.min(5, Math.max(3, Math.ceil(targets.length / 3)));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.submitWriting({
          text,
          task,
          targets,
          duration_ms: startedAt.current ? Date.now() - startedAt.current : 0,
        }),
      );
      setPhase("feedback");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (error && !lesson) return <ErrorNote error={error} />;
  if (!lesson) return <CardSkeleton lines={6} />;

  const tabs = [
    { key: "learn", label: "1. Learn the language" },
    { key: "write", label: "2. Write" },
    { key: "feedback", label: "3. Feedback", disabled: !result },
  ];

  return (
    <div>
      <p className="micro">your writing task · {lesson.level} level{lesson.genre ? ` · ${lesson.genre}` : ""}</p>
      <Glossed as="p" className="mt-1.5 text-[17px] font-medium">
        {task}
      </Glossed>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            disabled={tab.disabled}
            onClick={() => setPhase(tab.key)}
            className={cx(
              "rounded-full px-3 py-1 text-[13px] transition disabled:opacity-40",
              phase === tab.key
                ? "bg-ink text-white dark:bg-white dark:text-black"
                : "text-ink-2 ring-1 ring-[color:var(--color-line)] hover:bg-sunken dark:ring-white/10",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {phase === "learn" && (
        <div>
          {lesson.is_fallback && (
            <p className="mt-4 text-[13px] text-ink-3">
              The AI mentor isn&rsquo;t reachable, so this is general writing language rather than
              words for this topic.
            </p>
          )}

          <ItemList title="topic vocabulary" items={lesson.vocabulary} />
          <ItemList title="phrasal verbs" items={lesson.phrasal_verbs} />
          <ItemList title="expressions" items={lesson.expressions} />

          {lesson.sentence_patterns?.length > 0 && (
            <section className="mt-5">
              <h3 className="micro">sentence patterns</h3>
              <ul className="mt-2 space-y-2">
                {lesson.sentence_patterns.map((item) => (
                  <li key={item.pattern} className="rounded-xl bg-sunken p-3 dark:bg-white/[0.04]">
                    <p className="font-mono text-[14px]">{item.pattern}</p>
                    {item.use && <p className="micro mt-1">{item.use}</p>}
                    {item.example && (
                      <p className="mt-1 text-[13px] italic text-ink-2 dark:text-white/65">{item.example}</p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {lesson.plan?.length > 0 && (
            <section className="mt-6">
              <h3 className="micro">how to organise it</h3>
              <ol className="mt-2 space-y-3">
                {lesson.plan.map((step, index) => (
                  <li key={step.part} className="flex gap-3">
                    <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-ink text-[11px] font-semibold text-white dark:bg-white dark:text-black">
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-medium">{step.part}</p>
                      <p className="text-[14px] text-ink-2 dark:text-white/65">{step.what_to_write}</p>
                      {step.starter && <p className="mt-0.5 font-mono text-[13px] text-ink-3">{step.starter}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {lesson.style_tips?.length > 0 && (
            <section className="mt-5">
              <h3 className="micro">style</h3>
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[14px] text-ink-2 dark:text-white/70">
                {lesson.style_tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </section>
          )}

          {lesson.model_text && (
            <section className="mt-6">
              <h3 className="micro">a model text</h3>
              {!showModel ? (
                <button
                  onClick={() => setShowModel(true)}
                  className="mt-2 w-full rounded-xl border border-dashed border-[color:var(--color-line)] p-4 text-left text-[14px] text-ink-2 hover:bg-sunken dark:border-white/15 dark:text-white/60"
                >
                  Show a model answer
                  <span className="micro mt-1 block">study how it uses the language above — then write your own</span>
                </button>
              ) : (
                <Glossed className="mt-2 whitespace-pre-line rounded-xl bg-sunken p-4 text-[15px] leading-relaxed dark:bg-white/[0.04]">
                  {lesson.model_text}
                </Glossed>
              )}
            </section>
          )}

          <div className="mt-6">
            <Button onClick={() => setPhase("write")}>
              Start writing <Icon name="arrowRight" size={13} />
            </Button>
          </div>
        </div>
      )}

      {phase === "write" && (
        <div className="mt-4 grid gap-5 lg:grid-cols-[1fr_16rem]">
          <div>
            <textarea
              value={text}
              onChange={(event) => {
                if (!startedAt.current) startedAt.current = Date.now();
                setText(event.target.value);
              }}
              rows={12}
              placeholder={lesson.plan?.[0]?.starter ? `${lesson.plan[0].starter} …` : "Start writing…"}
              className="w-full rounded-xl bg-sunken p-4 text-[15px] leading-relaxed ring-1 ring-[color:var(--color-line)] focus:outline-none focus:ring-2 focus:ring-ink dark:bg-white/[0.04] dark:ring-white/10"
            />
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <span className="micro">
                {wordCount} / ~{lesson.word_target} words
              </span>
              <span
                className={cx(
                  "micro",
                  usedNow.length >= goal && "text-[color:var(--color-good-ink)]",
                )}
              >
                used {usedNow.length} of what you learned · aim for {goal}
              </span>
            </div>
            <ErrorNote error={error} />
            <div className="mt-4 flex flex-wrap gap-3">
              <Button onClick={submit} loading={busy} disabled={wordCount < 15 || busy}>
                Get feedback
              </Button>
              {wordCount < 15 && <span className="micro self-center">write at least 15 words</span>}
            </div>
          </div>

          {/* The checklist is what ties the exercise to the lesson: it ticks as
              the learner uses what they were just taught. */}
          <aside className="rounded-xl bg-sunken p-3 dark:bg-white/[0.04]">
            <h3 className="micro">try to use</h3>
            <ul className="mt-2 space-y-1.5">
              {targets.map((item) => {
                const used = usedNow.includes(item);
                return (
                  <li key={item} className="flex items-start gap-2 text-[13px]">
                    <span
                      className={cx(
                        "mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full",
                        used
                          ? "bg-[color:var(--color-good-ink)] text-white"
                          : "ring-1 ring-[color:var(--color-line)] dark:ring-white/20",
                      )}
                    >
                      {used && <Icon name="check" size={10} />}
                    </span>
                    <span className={cx(used && "text-ink-3 line-through")}>{item}</span>
                  </li>
                );
              })}
            </ul>
          </aside>
        </div>
      )}

      {phase === "feedback" && result && (
        <div className="mt-4 space-y-4">
          {result.detail?.targets && (
            <section className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
              <h3 className="micro">what you used from the lesson</h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {result.detail.targets.used.map((item) => (
                  <Pill key={item} tone="good">
                    ✓ {item}
                  </Pill>
                ))}
              </div>
              {result.detail.targets.missing.length > 0 && (
                <>
                  <p className="mt-3 text-[14px] text-ink-2 dark:text-white/70">
                    Next time, try to fit in:
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {result.detail.targets.missing.slice(0, 6).map((item) => (
                      <Pill key={item}>{item}</Pill>
                    ))}
                  </div>
                </>
              )}
            </section>
          )}

          {result.detail?.issues?.length > 0 && (
            <section>
              <h3 className="micro">corrections</h3>
              <ul className="mt-2 space-y-2">
                {result.detail.issues.slice(0, 6).map((issue, index) => (
                  <li key={index} className="rounded-xl p-3 text-[14px] ring-1 ring-[color:var(--color-line)] dark:ring-white/10">
                    {issue.original && <p className="text-ink-3 line-through">{issue.original}</p>}
                    {issue.correction && <p className="font-medium">{issue.correction}</p>}
                    {issue.explanation && (
                      <p className="mt-0.5 text-[13px] text-ink-2 dark:text-white/60">{issue.explanation}</p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {result.detail?.natural_version && (
            <section>
              <h3 className="micro">a more natural version of yours</h3>
              <Glossed className="mt-2 whitespace-pre-line rounded-xl bg-sunken p-4 text-[15px] leading-relaxed dark:bg-white/[0.04]">
                {result.detail.natural_version}
              </Glossed>
            </section>
          )}

          <div className="flex flex-wrap gap-3">
            <Button onClick={onFinished}>{finishLabel}</Button>
            <button
              onClick={() => {
                setResult(null);
                setPhase("write");
              }}
              className="micro hover:text-ink dark:hover:text-white"
            >
              rewrite it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
