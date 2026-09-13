import { useCallback, useEffect, useState } from "react";

import Glossed from "./Glossed";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { canSpeak, playTracked, speak, stopSpeaking } from "../lib/speech";
import { Button, Card, CardSkeleton, ErrorNote, Pill } from "../lib/ui";

/**
 * Movies & TV lessons.
 *
 * The app hands the learner a scene at their listening level instead of asking
 * them to paste something in. Scenes are original writing in screen style --
 * real film and TV dialogue is copyrighted -- built around the spoken English
 * that makes screen dialogue hard: idioms, phrasal verbs, fixed expressions.
 *
 * The lesson runs in the order a learner needs it:
 *   1. listen with the text hidden, to hear it the way you would on screen
 *   2. read along with every line, clicking any word
 *   3. learn the expressions, including where the words mislead
 *   4. answer the questions, then add the expressions to review
 */

function speakLines(lines, voice, onDone) {
  // Line by line, so a listener can follow who is speaking; each line waits
  // for the previous one to finish.
  let index = 0;
  let cancelled = false;
  const next = () => {
    if (cancelled || index >= lines.length) {
      onDone?.();
      return;
    }
    const line = lines[index];
    index += 1;
    speak(line.text, { rate: 0.95, voice, onEnd: next, onError: next });
  };
  next();
  return () => {
    cancelled = true;
    stopSpeaking();
  };
}

function Stage({ step, onStep }) {
  const steps = ["Listen", "Read along", "Expressions", "Check"];
  return (
    <ol className="flex flex-wrap gap-1.5">
      {steps.map((label, index) => (
        <li key={label}>
          <button
            onClick={() => onStep(index)}
            className={cx(
              "rounded-full px-3 py-1 text-[13px] transition",
              step === index
                ? "bg-ink text-white dark:bg-white dark:text-black"
                : "text-ink-2 ring-1 ring-[color:var(--color-line)] hover:bg-sunken dark:ring-white/10",
            )}
          >
            {index + 1}. {label}
          </button>
        </li>
      ))}
    </ol>
  );
}

export default function MoviesTV({ voice, AddToReview }) {
  const [scene, setScene] = useState(null);
  const [library, setLibrary] = useState(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [activeLine, setActiveLine] = useState(-1);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [stopper, setStopper] = useState(null);

  const loadLibrary = useCallback(() => {
    api.scenes().then(setLibrary).catch(() => setLibrary(null));
  }, []);

  const loadNext = useCallback(() => {
    setError(null);
    setScene(null);
    api
      .nextScene()
      .then((data) => {
        setScene(data);
        setStep(0);
      })
      .catch(setError);
  }, []);

  useEffect(() => {
    loadNext();
    loadLibrary();
  }, [loadNext, loadLibrary]);

  useEffect(() => () => stopper?.(), [stopper]);

  const open = async (id) => {
    stopper?.();
    setPlaying(false);
    setError(null);
    try {
      setScene(await api.scene(id));
      setStep(0);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err);
    }
  };

  const togglePlay = () => {
    if (playing) {
      stopper?.();
      setPlaying(false);
      return;
    }
    setPlaying(true);
    if (scene.audio_url) {
      // The real recording, with the line being spoken estimated from how far
      // through the audio it is.
      const joined = scene.lines.map((line) => line.text).join(" ");
      const ends = [];
      scene.lines.reduce((total, line) => {
        ends.push(total + line.text.length + 1);
        return total + line.text.length + 1;
      }, 0);
      setStopper(() =>
        playTracked(scene.audio_url, joined, {
          onProgress: (offset) => setActiveLine(ends.findIndex((end) => offset < end)),
          onEnd: () => {
            setPlaying(false);
            setActiveLine(-1);
          },
          onError: (err) => {
            setError(err);
            setPlaying(false);
          },
        }),
      );
      return;
    }
    setStopper(() => speakLines(scene.lines, voice, () => setPlaying(false)));
  };

  const finish = async () => {
    setBusy(true);
    try {
      await api.completeScene(scene.id);
      loadLibrary();
      loadNext();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (error && !scene) return <ErrorNote error={error} onRetry={loadNext} />;
  if (!scene) return <CardSkeleton lines={6} />;

  const speakers = [...new Set(scene.lines.map((line) => line.speaker))];

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="micro">your scene · {library?.level ?? scene.level} level</span>
              {scene.done && <span className="micro text-[color:var(--color-good-ink)]">watched</span>}
            </div>
            <h2 className="mt-1 text-xl font-semibold">{scene.title}</h2>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <Pill tone="brand">{scene.level}</Pill>
              {scene.genre && <Pill>{scene.genre}</Pill>}
              {scene.audio_url ? (
                <Pill tone="good">real voices</Pill>
              ) : (
                <span className="micro">computer voice</span>
              )}
            </div>
            {scene.audio_credit && <p className="micro mt-1">{scene.audio_credit}</p>}
          </div>
        </div>
        {scene.setting && (
          <p className="mt-3 text-[15px] text-ink-2 dark:text-white/70">{scene.setting}</p>
        )}
        <div className="mt-4">
          <Stage step={step} onStep={setStep} />
        </div>
      </Card>

      {step === 0 && (
        <Card>
          <h3 className="micro">listen first — the text is hidden on purpose</h3>
          <p className="mt-2 text-[15px] text-ink-2 dark:text-white/70">
            On screen you can&rsquo;t read the lines. Listen once or twice and try to follow who
            says what and what&rsquo;s going on.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={togglePlay} disabled={!canSpeak && !scene.audio_url}>
              <Icon name={playing ? "stop" : "play"} size={13} /> {playing ? "Stop" : "Play the scene"}
            </Button>
            <Button variant="secondary" onClick={() => setStep(1)}>
              Now read along <Icon name="arrowRight" size={13} />
            </Button>
          </div>
          <p className="micro mt-3">{speakers.join(" · ")}</p>
        </Card>
      )}

      {step === 1 && (
        <Card>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="micro">the scene · click any word you don&rsquo;t know</h3>
            <Button variant="secondary" size="sm" onClick={togglePlay} disabled={!canSpeak && !scene.audio_url}>
              <Icon name={playing ? "stop" : "play"} size={12} /> {playing ? "Stop" : "Play"}
            </Button>
          </div>
          <Glossed className="space-y-2.5">
            {scene.lines.map((line, index) => (
              <div
                key={index}
                className={cx(
                  "flex gap-3 rounded-lg px-1 transition-colors",
                  playing && activeLine === index && "bg-[color:var(--color-accent)]/15",
                )}
              >
                <span className="w-16 shrink-0 pt-0.5 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                  {line.speaker}
                </span>
                <p className="flex-1 text-[16px] leading-relaxed">{line.text}</p>
                {/* A recording has no per-line timings, so single-line replay
                    would have to fall back to the computer voice. Not offered. */}
                {!scene.audio_url && (
                  <button
                    onClick={() => speak(line.text, { rate: 0.9, voice })}
                    aria-label="Play this line"
                    className="shrink-0 text-ink-3 hover:text-ink dark:hover:text-white"
                    disabled={!canSpeak}
                  >
                    <Icon name="volume" size={14} />
                  </button>
                )}
              </div>
            ))}
          </Glossed>
          <div className="mt-5">
            <Button onClick={() => setStep(2)}>
              Learn the expressions <Icon name="arrowRight" size={13} />
            </Button>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <h3 className="micro">expressions from this scene</h3>
          <ul className="mt-3 space-y-3">
            {scene.expressions.map((item) => (
              <li key={item.expression} className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
                <p className="font-semibold">&ldquo;{item.expression}&rdquo;</p>
                <p className="mt-1 text-[15px] text-ink-2 dark:text-white/75">{item.meaning}</p>
                {item.literal_trap && (
                  <p className="mt-1.5 text-[13px]">
                    <span className="font-medium text-[color:var(--color-accent)]">Careful: </span>
                    <span className="text-ink-2 dark:text-white/60">{item.literal_trap}</span>
                  </p>
                )}
                {item.example && (
                  <p className="mt-1.5 border-l-2 border-[color:var(--color-line)] pl-2.5 text-[13px] italic text-ink-3">
                    {item.example}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button onClick={() => setStep(3)}>
              Check yourself <Icon name="arrowRight" size={13} />
            </Button>
            {AddToReview && <AddToReview items={scene.expressions} label="Add these to review" />}
          </div>
        </Card>
      )}

      {step === 3 && (
        <Card>
          <h3 className="micro">answer out loud, then check against the scene</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-[15px]">
            {scene.questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ol>
          <p className="mt-4 text-[14px] text-ink-2 dark:text-white/65">
            Then try to use two of the expressions in a sentence about your own life. Say them out
            loud.
          </p>
          <ErrorNote error={error} />
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button onClick={finish} loading={busy}>
              {scene.done ? "Next scene" : "Finish — next scene"}
            </Button>
            <button onClick={() => setStep(1)} className="micro hover:text-ink dark:hover:text-white">
              read the scene again
            </button>
          </div>
        </Card>
      )}

      {library?.scenes?.length > 0 && (
        <section>
          <h3 className="micro mb-2">scenes at your level</h3>
          <ul className="grid gap-2 sm:grid-cols-2">
            {library.scenes.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => open(item.id)}
                  className={cx(
                    "flex w-full items-center justify-between gap-3 rounded-xl p-3 text-left ring-1 transition hover:bg-sunken",
                    item.id === scene.id
                      ? "ring-ink dark:ring-white"
                      : "ring-[color:var(--color-line)] dark:ring-white/10",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{item.title}</span>
                    <span className="micro">{item.genre} · {item.level}</span>
                  </span>
                  {item.done ? (
                    <Icon name="check" size={14} className="shrink-0 text-[color:var(--color-good-ink)]" />
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
