import { useEffect, useRef, useState } from "react";

import Glossed from "../Glossed";
import { api } from "../../lib/api";
import { cx } from "../../lib/cx";
import Icon from "../../lib/icons";
import { useRecorder } from "../../lib/recorder";
import { canListen, canSpeak, listen, speak, stopSpeaking } from "../../lib/speech";
import { Button, ErrorNote, Pill, Spinner } from "../../lib/ui";

/**
 * The exercises a lesson step can be.
 *
 * Each one runs *inside* the lesson rather than being a link to the page that
 * owns that skill. That is the whole difference between a plan and a launcher:
 * before this, pressing Start navigated away, the learner did something, came
 * back, and told the app they had finished. Self-reported completion is not
 * evidence, it breaks the thread of the session, and it puts the work of
 * remembering where you were onto the person doing the practising.
 *
 * Every step takes the same two props and nothing else:
 *
 *   activity  the lesson activity, already carrying its prompt and params
 *   onDone    call when the exercise is genuinely finished
 *
 * so the runner never has to know what kind it is rendering. Adding a new kind
 * means adding a component here and one line in the map at the bottom.
 *
 * None of them advance on their own. Duolingo does not skip you past a wrong
 * answer, and neither does this: the step ends when the learner presses
 * Continue, after they have seen how it went.
 */

/* ---------------------------------------------------------------- shared */

/** The bar every step ends with, so "what now" is never a question. */
export function StepFooter({ onDone, label = "Continue", disabled, children }) {
  return (
    <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-[color:var(--color-line)] pt-4 dark:border-white/10">
      <Button onClick={onDone} disabled={disabled} size="lg">
        {label}
      </Button>
      {children}
    </div>
  );
}

/** Right/wrong, stated plainly and immediately. */
function Verdict({ good, title, children }) {
  return (
    <div
      className={cx(
        "mt-4 rounded-xl p-4",
        good
          ? "bg-[color:var(--color-good)]/15 ring-1 ring-[color:var(--color-good-ink)]/25"
          : "bg-[color:var(--color-accent)]/10 ring-1 ring-[color:var(--color-accent)]/25",
      )}
    >
      <p
        className={cx(
          "micro",
          good ? "text-[color:var(--color-good-ink)]" : "text-[color:var(--color-accent)]",
        )}
      >
        {title}
      </p>
      <div className="mt-1.5 text-[14px]">{children}</div>
    </div>
  );
}

function Instructions({ activity }) {
  if (!activity.instructions) return null;
  return (
    <Glossed as="p" className="text-[15px] leading-relaxed text-ink-2 dark:text-white/70">
      {activity.instructions}
    </Glossed>
  );
}

function PlayLine({ text, voice, label = "Play", rate = 1 }) {
  return (
    <Button variant="secondary" onClick={() => speak(text, { rate, voice })} disabled={!canSpeak}>
      <Icon name={rate < 1 ? "slow" : "play"} size={13} /> {label}
    </Button>
  );
}

/* -------------------------------------------------------------- listening */

function ListeningStep({ activity, voice, onDone }) {
  const [passage, setPassage] = useState(null);
  const [index, setIndex] = useState(0);
  const [written, setWritten] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const passageId = activity.params?.passage_id;

  useEffect(() => {
    if (!passageId) return;
    api
      .passages()
      .then((list) => setPassage(list.find((item) => String(item.id) === String(passageId))))
      .catch(setError);
  }, [passageId]);

  const sentences = passage?.sentences ?? [];
  const sentence = sentences[index];

  const check = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.submitDictation({
          // The endpoint compares the sentence it played against what was
          // typed, so it needs both -- not a sentence index it would have to
          // resolve itself.
          expected: sentence,
          written,
          passage_id: passage.id,
          duration_ms: 0,
        }),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const nextSentence = () => {
    setIndex((current) => current + 1);
    setWritten("");
    setResult(null);
  };

  if (!passage) return <Spinner />;
  if (!sentence) return <StepFooter onDone={onDone} label="Finish this step" />;

  const last = index >= sentences.length - 1;

  return (
    <div>
      <Instructions activity={activity} />
      <p className="micro mt-4">
        sentence {index + 1} of {sentences.length}
      </p>

      <div className="mt-2 flex flex-wrap gap-2">
        <PlayLine text={sentence} voice={voice} />
        <PlayLine text={sentence} voice={voice} rate={0.65} label="Slowly" />
      </div>

      <textarea
        value={written}
        onChange={(event) => setWritten(event.target.value)}
        placeholder="Type what you hear…"
        rows={3}
        disabled={!!result}
        className="mt-4 w-full rounded-xl bg-sunken p-4 text-[15px] ring-1 ring-[color:var(--color-line)] focus:outline-none focus:ring-2 focus:ring-ink disabled:opacity-70 dark:bg-white/[0.04] dark:ring-white/10"
      />

      <ErrorNote error={error} />

      {result && (
        <Verdict good={result.score >= 80} title={`${Math.round(result.score)}% match`}>
          <p className="text-ink-2 dark:text-white/70">{sentence}</p>
        </Verdict>
      )}

      {!result ? (
        <StepFooter onDone={check} label={busy ? "Checking…" : "Check"} disabled={!written.trim() || busy} />
      ) : (
        <StepFooter
          onDone={last ? onDone : nextSentence}
          label={last ? "Finish this step" : "Next sentence"}
        />
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- reading */

function ReadingStep({ activity, onDone }) {
  const [passage, setPassage] = useState(null);
  const [error, setError] = useState(null);
  const startedAt = useRef(Date.now());
  const passageId = activity.params?.passage_id;

  useEffect(() => {
    if (!passageId) return;
    api
      .passages()
      .then((list) => setPassage(list.find((item) => String(item.id) === String(passageId))))
      .catch(setError);
  }, [passageId]);

  const finish = async () => {
    try {
      await api.submitReading({
        passage_id: passage.id,
        seconds: Math.max(1, Math.round((Date.now() - startedAt.current) / 1000)),
      });
    } catch {
      // Recording the read is a nice-to-have; failing to record it must not
      // trap the learner on this step.
    }
    onDone();
  };

  if (!passage) return <Spinner />;

  return (
    <div>
      <Instructions activity={activity} />
      <h3 className="mt-4 text-lg font-semibold">{passage.title}</h3>
      <Glossed className="mt-2 space-y-3 text-[17px] leading-relaxed">
        {passage.text.split("\n").map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
      </Glossed>
      <p className="micro mt-3">click any word you don&rsquo;t know</p>

      {/* The questions belong with the text they ask about. They used to be
          glued into the prompt alongside a second copy of a passage. */}
      {activity.params?.questions?.length > 0 && (
        <section className="mt-5 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
          <h3 className="micro">answer out loud, or in your head</h3>
          <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-[15px]">
            {activity.params.questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ol>
        </section>
      )}
      <ErrorNote error={error} />
      <StepFooter onDone={finish} label="I've read it" />
    </div>
  );
}

/* ---------------------------------------------------------------- writing */

function WritingStep({ activity, onDone }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const startedAt = useRef(0);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.submitWriting({
          text,
          task: activity.prompt || activity.instructions,
          duration_ms: startedAt.current ? Date.now() - startedAt.current : 0,
        }),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const words = text.trim() ? text.trim().split(/\s+/).length : 0;

  return (
    <div>
      <Instructions activity={activity} />
      {activity.prompt && (
        <Glossed as="p" className="mt-3 text-[17px] font-medium">
          {activity.prompt}
        </Glossed>
      )}

      <textarea
        value={text}
        onChange={(event) => {
          if (!startedAt.current) startedAt.current = Date.now();
          setText(event.target.value);
        }}
        placeholder="Write as much as you can. Mistakes are the point."
        rows={6}
        disabled={!!result}
        className="mt-4 w-full rounded-xl bg-sunken p-4 text-[15px] ring-1 ring-[color:var(--color-line)] focus:outline-none focus:ring-2 focus:ring-ink disabled:opacity-70 dark:bg-white/[0.04] dark:ring-white/10"
      />
      <p className="micro mt-1.5">{words} words</p>

      <ErrorNote error={error} />

      {result?.detail && (
        <Verdict good={(result.score ?? 0) >= 70} title={`${Math.round(result.score ?? 0)}%`}>
          {result.detail.natural_version && (
            <p className="text-ink-2 dark:text-white/70">{result.detail.natural_version}</p>
          )}
          {result.detail.issues?.length > 0 && (
            <ul className="mt-2 space-y-1 text-[13px] text-ink-2 dark:text-white/60">
              {result.detail.issues.slice(0, 3).map((issue, i) => (
                <li key={i}>· {issue.explanation || issue.correction}</li>
              ))}
            </ul>
          )}
        </Verdict>
      )}

      {!result ? (
        <StepFooter
          onDone={submit}
          label={busy ? "Reading it…" : "Get feedback"}
          disabled={words < 5 || busy}
        >
          <span className="micro">at least 5 words</span>
        </StepFooter>
      ) : (
        <StepFooter onDone={onDone} label="Finish this step" />
      )}
    </div>
  );
}

/* --------------------------------------------------------------- speaking */

function SpeakingStep({ activity, voice, onDone }) {
  const [spoken, setSpoken] = useState("");
  const [recording, setRecording] = useState(false);
  const [support, setSupport] = useState(null);
  // Prepare first. The record button being on screen while the learner is
  // still reading is the pressure that makes people skip preparing.
  const [ready, setReady] = useState(false);
  const [showAnswer, setShowAnswer] = useState(false);
  const recognition = useRef(null);
  const recorder = useRecorder();

  useEffect(() => {
    api
      .speakingSupport({
        prompt: activity.prompt || activity.instructions,
        expressions: activity.target_expressions ?? [],
        withAnswer: true,
      })
      .then(setSupport)
      // Scaffolding is help, not a prerequisite: if it fails to load the
      // learner can still do the exercise.
      .catch(() => setSupport(null));
  }, [activity]);

  const toggle = async () => {
    if (recording) {
      recognition.current?.stop();
      recorder.stop();
      return;
    }
    setSpoken("");
    recorder.clear();
    recorder.start();
    setRecording(true);
    const session = listen({ interim: setSpoken });
    recognition.current = session;
    try {
      setSpoken(await session.promise);
    } catch {
      // Recognition failing is not a reason to block the step: speaking out
      // loud is the practice, and the transcript is only the evidence.
    } finally {
      recorder.stop();
      setRecording(false);
    }
  };

  const frame = support?.frame ?? [];
  const expressions = support?.target_expressions ?? [];

  if (!ready) {
    return (
      <div>
        <Instructions activity={activity} />
        {activity.prompt && (
          <Glossed as="p" className="mt-3 text-[17px] font-medium">
            {activity.prompt}
          </Glossed>
        )}

        {expressions.length > 0 && (
          <section className="mt-5">
            <h3 className="micro">words and expressions for this</h3>
            <ul className="mt-2 space-y-2">
              {expressions.map((item) => (
                <li
                  key={item.text}
                  className="rounded-xl bg-sunken p-3 dark:bg-white/[0.04]"
                >
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="font-semibold">{item.text}</span>
                    {item.register && item.register !== "neutral" && (
                      <span className="micro">{item.register}</span>
                    )}
                  </div>
                  {/* The meaning is the point. A chip reading "after that"
                      tells a learner nothing they could not already guess. */}
                  {item.meaning && (
                    <Glossed as="p" className="mt-0.5 text-[14px] text-ink-2 dark:text-white/70">
                      {item.meaning}
                    </Glossed>
                  )}
                  {item.example && (
                    <p className="mt-1 border-l-2 border-[color:var(--color-line)] pl-2.5 text-[13px] italic text-ink-3">
                      {item.example}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {support?.model_answer?.answer && (
          <section className="mt-6">
            <h3 className="micro">an example answer</h3>
            {!showAnswer ? (
              <button
                onClick={() => setShowAnswer(true)}
                className="mt-2 w-full rounded-xl border border-dashed border-[color:var(--color-line)] p-4 text-left text-[14px] text-ink-2 transition hover:bg-sunken dark:border-white/15 dark:text-white/60"
              >
                Show me one way to answer this
                <span className="micro mt-1 block">
                  read it, then say your own version — don&rsquo;t recite it
                </span>
              </button>
            ) : (
              <div className="mt-2 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
                {support.model_answer.is_skeleton && (
                  <p className="micro mb-2">
                    a skeleton, not a full answer — the model wasn&rsquo;t reachable
                  </p>
                )}
                <Glossed className="space-y-2 text-[15px] leading-relaxed">
                  {support.model_answer.answer.split("\n").map((line, i) => (
                    <p key={i}>{line}</p>
                  ))}
                </Glossed>

                <div className="mt-3">
                  <PlayLine
                    text={support.model_answer.answer}
                    voice={voice}
                    label="Hear it"
                    rate={0.9}
                  />
                </div>

                {support.model_answer.notes?.length > 0 && (
                  <ul className="mt-4 space-y-2 border-t border-[color:var(--color-line)] pt-3 dark:border-white/10">
                    {support.model_answer.notes.map((note) => (
                      <li key={note.quote} className="text-[13px]">
                        <span className="font-medium">&ldquo;{note.quote}&rdquo;</span>{" "}
                        <span className="text-ink-2 dark:text-white/60">{note.why}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </section>
        )}

        {frame.length > 0 && (
          <section className="mt-6">
            <h3 className="micro">how it was built</h3>
            <ol className="mt-2 space-y-3">
              {frame.map((step, index) => (
                <li key={step.move} className="flex gap-3">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-ink text-[11px] font-semibold text-white dark:bg-white dark:text-black">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[15px] font-medium">{step.move}</p>
                    <p className="text-[13px] text-ink-2 dark:text-white/60">{step.hint}</p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {step.phrases.map((phrase) => (
                        <Pill key={phrase}>{phrase}</Pill>
                      ))}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}

        {support?.stalling_phrases?.length > 0 && (
          <section className="mt-5">
            <h3 className="micro">if you get stuck mid-sentence</h3>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {support.stalling_phrases.map((phrase) => (
                <Pill key={phrase}>{phrase}</Pill>
              ))}
            </div>
            <p className="mt-1.5 text-[13px] text-ink-3">
              Say one of these out loud rather than going silent — that&rsquo;s what fluent
              speakers do.
            </p>
          </section>
        )}

        <StepFooter onDone={() => setReady(true)} label="I'm ready — let me speak" />
      </div>
    );
  }

  return (
    <div>
      {activity.prompt && (
        <Glossed as="p" className="text-[17px] font-medium">
          {activity.prompt}
        </Glossed>
      )}

      {/* The frame stays up while they speak. Scaffolding that disappears the
          moment it is needed is decoration. */}
      {frame.length > 0 && (
        <ol className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          {frame.map((step, index) => (
            <li key={step.move} className="micro">
              {index + 1}. {step.move}
            </li>
          ))}
        </ol>
      )}

      {expressions.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="micro">try to use</span>
          {expressions.map((item) => (
            <Pill key={item.text}>{item.text}</Pill>
          ))}
        </div>
      )}

      <div className="mt-4">
        <Button variant={recording ? "danger" : "secondary"} onClick={toggle} disabled={!canListen}>
          <Icon name={recording ? "stop" : "mic"} size={14} />
          {recording ? "Stop" : "Record my answer"}
        </Button>
      </div>

      {spoken && (
        <div className="mt-4 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
          <p className="micro">what was recognised</p>
          <p className="mt-1 text-[15px]">{spoken}</p>
        </div>
      )}

      {recorder.url && (
        <div className="mt-3 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
          <p className="micro">hear yourself back</p>
          <audio src={recorder.url} controls className="mt-2 w-full" />
        </div>
      )}

      {!canListen && (
        <p className="mt-3 text-[13px] text-ink-3">
          This browser can&rsquo;t record. Say it out loud anyway — that&rsquo;s the practice.
        </p>
      )}

      <StepFooter onDone={onDone} label="Finish this step">
        <button onClick={() => setReady(false)} className="micro hover:text-ink">
          back to the notes
        </button>
      </StepFooter>
    </div>
  );
}

/* ----------------------------------------------------------------- review */

function ReviewStep({ activity, onDone }) {
  const [queue, setQueue] = useState(null);
  const [position, setPosition] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .reviewQueue({ limit: 8 })
      .then((data) => setQueue(data.items ?? []))
      .catch(setError);
  }, []);

  if (error) return <ErrorNote error={error} />;
  if (!queue) return <Spinner />;

  if (!queue.length) {
    return (
      <div>
        <Instructions activity={activity} />
        <p className="mt-4 text-[15px] text-ink-2 dark:text-white/70">
          Nothing is due right now — that&rsquo;s a good sign, not a gap.
        </p>
        <StepFooter onDone={onDone} label="Finish this step" />
      </div>
    );
  }

  const item = queue[position];
  const last = position >= queue.length - 1;

  const answer = async (rating) => {
    try {
      await api.reviewAnswer({ progress_id: item.progress.id, rating, duration_ms: 0 });
    } catch (err) {
      setError(err);
      return;
    }
    if (last) onDone();
    else {
      setPosition((current) => current + 1);
      setRevealed(false);
    }
  };

  return (
    <div>
      <p className="micro">
        card {position + 1} of {queue.length}
      </p>
      <p className="mt-3 text-[13px] text-ink-2 dark:text-white/60">{item.prompt.instruction}</p>
      <p className="mt-1.5 text-2xl font-semibold">{item.prompt.front}</p>

      {!revealed ? (
        <StepFooter onDone={() => setRevealed(true)} label="Show answer" />
      ) : (
        <>
          <Glossed className="mt-4 border-t border-[color:var(--color-line)] pt-4 dark:border-white/10">
            <p className="text-ink-2 dark:text-white/70">
              {item.progress.expression.meaning}
            </p>
            {item.progress.expression.examples?.[0] && (
              <p className="mt-2 border-l-2 border-ink/25 pl-3 italic text-ink-2">
                {item.progress.expression.examples[0].text}
              </p>
            )}
          </Glossed>

          <p className="mt-5 text-sm font-medium">How did that go?</p>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              { value: 1, label: "Again" },
              { value: 2, label: "Hard" },
              { value: 3, label: "Good" },
              { value: 4, label: "Easy" },
            ].map((choice) => (
              <button
                key={choice.value}
                onClick={() => answer(choice.value)}
                className="rounded-xl px-3 py-2.5 text-sm font-medium ring-1 ring-[color:var(--color-line)] transition hover:bg-sunken dark:ring-white/10"
              >
                {choice.label}
              </button>
            ))}
          </div>
        </>
      )}
      <ErrorNote error={error} />
    </div>
  );
}

/* ------------------------------------------------------------------ drill */

function DrillStep({ activity, voice, onDone }) {
  const [guide, setGuide] = useState(null);
  const [index, setIndex] = useState(0);
  const recorder = useRecorder();

  useEffect(() => {
    const text = activity.prompt || activity.instructions;
    if (!text) return;
    api
      .shadowingGuide({ text })
      .then(setGuide)
      .catch(() => setGuide({ chunks: [] }));
  }, [activity]);

  if (!guide) return <Spinner />;

  const chunks = guide.chunks ?? [];
  const chunk = chunks[index];
  if (!chunk) {
    return (
      <div>
        <Instructions activity={activity} />
        <StepFooter onDone={onDone} label="Finish this step" />
      </div>
    );
  }

  const last = index >= chunks.length - 1;
  const stress = new Set(chunk.stress);

  return (
    <div>
      <Instructions activity={activity} />
      <p className="micro mt-4">
        chunk {index + 1} of {chunks.length} · bold = stress
      </p>

      <p className="mt-2 rounded-xl bg-sunken p-4 text-lg dark:bg-white/[0.04]">
        {chunk.words.map((word, i) => (
          <span key={i} className={cx("mr-1.5", stress.has(i) ? "font-bold" : "text-ink-3")}>
            {word}
          </span>
        ))}
        <span className="text-[color:var(--color-accent)]">
          {chunk.intonation === "rise" ? "↗" : "↘"}
        </span>
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <PlayLine text={chunk.text} voice={voice} label="Play chunk" rate={0.85} />
        {recorder.supported && (
          <Button
            variant={recorder.recording ? "danger" : "secondary"}
            onClick={() => (recorder.recording ? recorder.stop() : recorder.start())}
          >
            <Icon name={recorder.recording ? "stop" : "mic"} size={13} />
            {recorder.recording ? "Stop" : "Record"}
          </Button>
        )}
      </div>

      {recorder.url && <audio src={recorder.url} controls className="mt-3 w-full" />}

      <StepFooter
        onDone={
          last
            ? onDone
            : () => {
                stopSpeaking();
                recorder.clear();
                setIndex((current) => current + 1);
              }
        }
        label={last ? "Finish this step" : "Next chunk"}
      />
    </div>
  );
}

/* -------------------------------------------------------------- dispatch */

const STEPS = {
  listening: ListeningStep,
  reading: ReadingStep,
  writing: WritingStep,
  speaking: SpeakingStep,
  review: ReviewStep,
  vocabulary: ReviewStep,
  drill: DrillStep,
};

/** Anything without a purpose-built exercise still has to be completable. */
function GenericStep({ activity, onDone }) {
  return (
    <div>
      <Instructions activity={activity} />
      {activity.prompt && (
        <Glossed as="p" className="mt-3 text-[17px] font-medium">
          {activity.prompt}
        </Glossed>
      )}
      <StepFooter onDone={onDone} label="Finish this step" />
    </div>
  );
}

export default function LessonStep({ activity, voice, onDone }) {
  const Component = STEPS[activity.kind] ?? GenericStep;
  return <Component activity={activity} voice={voice} onDone={onDone} />;
}
