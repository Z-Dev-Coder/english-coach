import { useCallback, useEffect, useRef, useState } from "react";

import WordDiff from "../components/WordDiff";
import PracticeNav from "../components/PracticeNav";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import { canListen, canSpeak, listen, pickVoice, speak, stopSpeaking } from "../lib/speech";
import {
  Button,
  Card,
  CardSkeleton,
  ErrorNote,
  HowTo,
  Pill,
  SectionHeading,
} from "../lib/ui";

/**
 * The Listen → Speak → Write drill.
 *
 * One sentence, worked five ways: hear it, say it, write it from memory, change
 * one element, then make it about your own life. It trains listening,
 * pronunciation, spelling, grammar and production from a single piece of
 * material, which is why it earns its own screen rather than being one tab
 * among four.
 */

const STEPS = [
  { key: "listen", label: "Listen", icon: "🎧", hint: "Play it a few times. Don't read anything yet." },
  { key: "repeat", label: "Repeat", icon: "🗣️", hint: "Say it out loud, matching the rhythm." },
  { key: "write", label: "Write", icon: "✍️", hint: "Type what you heard, from memory." },
  { key: "change", label: "Change", icon: "🔀", hint: "Swap one word for another that still works." },
  { key: "personalise", label: "Make it yours", icon: "💡", hint: "Rewrite it as something true about you." },
];

function StepRail({ current, furthest, onJump }) {
  return (
    <ol className="flex flex-wrap gap-1.5" aria-label="Drill steps">
      {STEPS.map((step, index) => {
        const done = index < furthest;
        const active = index === current;
        return (
          <li key={step.key}>
            <button
              onClick={() => index <= furthest && onJump(index)}
              disabled={index > furthest}
              className={cx(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition",
                active && "bg-ink text-white dark:bg-white dark:text-ink",
                !active && done && "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
                !active && !done && "bg-sunken text-ink-3 dark:bg-white/[0.05] dark:text-ink-2",
                index > furthest && "cursor-not-allowed",
              )}
            >
              <span aria-hidden="true">{done && !active ? "✓" : step.icon}</span>
              {step.label}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function PlayButton({ text, rate, label, voice }) {
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(null);

  const play = () => {
    setError(null);
    setPlaying(true);
    speak(text, {
      rate,
      voice,
      onEnd: () => setPlaying(false),
      onError: (err) => {
        setPlaying(false);
        setError(err);
      },
    });
  };

  return (
    <div>
      <Button variant={rate < 1 ? "secondary" : "primary"} onClick={play} disabled={!canSpeak}>
        <span aria-hidden="true">{playing ? "🔊" : "▶"}</span>
        {label}
      </Button>
      {error && <p className="mt-1 text-xs text-rose-600">{error.message}</p>}
    </div>
  );
}

export default function Drill() {
  const [drill, setDrill] = useState(null);
  const [step, setStep] = useState(0);
  const [furthest, setFurthest] = useState(0);
  const [voice, setVoice] = useState(null);

  const [spoken, setSpoken] = useState("");
  const [recording, setRecording] = useState(false);
  const [written, setWritten] = useState("");
  const [variation, setVariation] = useState("");
  const [personal, setPersonal] = useState("");

  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  // Set when a drill actually loads, not at first render: Date.now() in a
  // render body is impure and would also start timing too early.
  const startedAt = useRef(0);
  const recognition = useRef(null);

  const load = useCallback(() => {
    setError(null);
    setResult(null);
    setStep(0);
    setFurthest(0);
    setSpoken("");
    setWritten("");
    setVariation("");
    setPersonal("");
    startedAt.current = Date.now();
    api.drill().then(setDrill).catch(setError);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    pickVoice().then(setVoice);
    return () => stopSpeaking();
  }, []);

  const advance = () => {
    const next = Math.min(step + 1, STEPS.length - 1);
    setStep(next);
    setFurthest((value) => Math.max(value, next));
  };

  const record = async () => {
    setError(null);
    if (recording) {
      recognition.current?.stop();
      return;
    }
    setRecording(true);
    setSpoken("");
    const session = listen({ interim: setSpoken });
    recognition.current = session;
    try {
      setSpoken(await session.promise);
    } catch (err) {
      setError(err);
    } finally {
      setRecording(false);
    }
  };

  const finish = async () => {
    setSaving(true);
    setError(null);
    try {
      setResult(
        await api.submitDrill({
          sentence: drill.sentence,
          spoken,
          written,
          variation: [variation, personal].filter(Boolean).join(" / "),
          duration_ms: Date.now() - startedAt.current,
        }),
      );
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  if (error && !drill) return <ErrorNote error={error} onRetry={load} />;
  if (!drill) return <CardSkeleton lines={5} />;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">
          Listen <span className="text-gradient">Speak</span> Write
        </h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          One sentence, five ways. Listening, pronunciation, spelling and production from a single
          piece of material.
        </p>
      </header>

      <PracticeNav />

      <HowTo
        id="drill"
        title="How the drill works"
        steps={[
          "One sentence, five steps. Do them in order — each one builds on the last.",
          "Don't read ahead: the sentence stays hidden until step 4 on purpose.",
          "The last two steps are where the learning is. Write something true about you.",
        ]}
      />

      <StepRail current={step} furthest={furthest} onJump={setStep} />

      {!canSpeak && (
        <Card className="bg-amber-50 ring-amber-200 dark:bg-amber-500/10 dark:ring-amber-500/20">
          <p className="text-sm text-amber-900 dark:text-amber-200">
            This browser can't play audio speech. Chrome or Edge will work; you can still do the
            writing steps by reading the sentence.
          </p>
        </Card>
      )}

      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Pill tone="brand">
            {current.icon} Step {step + 1} of {STEPS.length}
          </Pill>
          {drill.expression && <Pill>from “{drill.expression}”</Pill>}
        </div>

        <p className="text-sm text-ink-2 dark:text-white/55">{current.hint}</p>

        {/* Step 1: listen. The sentence stays hidden — showing it would turn a
            listening exercise into a reading one. */}
        {step === 0 && (
          <div className="mt-5 space-y-4">
            <div className="flex flex-wrap gap-2">
              <PlayButton text={drill.sentence} rate={1} label="Play" voice={voice} />
              <PlayButton text={drill.sentence} rate={0.65} label="Slowly" voice={voice} />
            </div>
            <p className="rounded-xl bg-sunken p-4 text-center text-ink-3 dark:bg-white/[0.04]">
              The sentence is hidden on purpose. Listen until you can hold it in your head.
            </p>
            <Button onClick={advance}>I've got it</Button>
          </div>
        )}

        {/* Step 2: repeat aloud. */}
        {step === 1 && (
          <div className="mt-5 space-y-4">
            <div className="flex flex-wrap gap-2">
              <PlayButton text={drill.sentence} rate={1} label="Play again" voice={voice} />
              {canListen && (
                <Button variant={recording ? "danger" : "secondary"} onClick={record}>
                  <span aria-hidden="true">{recording ? "⏹" : "🎙"}</span>
                  {recording ? "Stop" : "Record my attempt"}
                </Button>
              )}
            </div>

            {spoken && (
              <div className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
                <p className="text-xs font-medium uppercase tracking-wide text-ink-3">
                  What was recognised
                </p>
                <p className="mt-1 text-ink dark:text-white/85">{spoken}</p>
              </div>
            )}

            {!canListen && (
              <p className="text-sm text-ink-3">
                This browser can't record speech, so this step isn't scored. Say the sentence out
                loud anyway — that's the part that matters.
              </p>
            )}

            <Button onClick={advance}>Next</Button>
          </div>
        )}

        {/* Step 3: write it from memory. */}
        {step === 2 && (
          <div className="mt-5 space-y-4">
            <PlayButton text={drill.sentence} rate={0.8} label="Play once more" voice={voice} />
            <textarea
              value={written}
              onChange={(event) => setWritten(event.target.value)}
              rows={3}
              autoFocus
              placeholder="Type exactly what you heard…"
              className="w-full rounded-xl border-0 bg-sunken p-4 text-lg ring-1 ring-[color:var(--color-line)] focus:ring-2 focus:ring-brand-500 dark:bg-white/[0.05] dark:ring-white/10"
            />
            <Button onClick={advance} disabled={!written.trim()}>
              Next
            </Button>
          </div>
        )}

        {/* Steps 4 and 5: produce something new. The sentence is revealed here,
            because these steps are about manipulating it, not recalling it. */}
        {step >= 3 && (
          <div className="mt-5 space-y-4">
            <div className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
              <p className="text-xs font-medium uppercase tracking-wide text-ink dark:text-white">
                The sentence
              </p>
              <p className="mt-1 text-lg font-medium">{drill.sentence}</p>
              {drill.meaning && (
                <p className="mt-1 text-sm text-ink-2 dark:text-white/55">{drill.meaning}</p>
              )}
            </div>

            {step === 3 ? (
              <>
                <textarea
                  value={variation}
                  onChange={(event) => setVariation(event.target.value)}
                  rows={2}
                  autoFocus
                  placeholder="Change one word or phrase, keeping it natural…"
                  className="w-full rounded-xl border-0 bg-sunken p-4 ring-1 ring-[color:var(--color-line)] focus:ring-2 focus:ring-brand-500 dark:bg-white/[0.05] dark:ring-white/10"
                />
                <Button onClick={advance} disabled={!variation.trim()}>
                  Next
                </Button>
              </>
            ) : (
              <>
                <textarea
                  value={personal}
                  onChange={(event) => setPersonal(event.target.value)}
                  rows={2}
                  autoFocus
                  placeholder="Now write it as something true about your life…"
                  className="w-full rounded-xl border-0 bg-sunken p-4 ring-1 ring-[color:var(--color-line)] focus:ring-2 focus:ring-brand-500 dark:bg-white/[0.05] dark:ring-white/10"
                />
                <Button onClick={finish} loading={saving} disabled={!personal.trim()}>
                  Finish drill
                </Button>
              </>
            )}
          </div>
        )}
      </Card>

      <ErrorNote error={error} />

      {result && (
        <Card className="animate-rise">
          <SectionHeading title="How that went" />

          {result.detail.written && (
            <div className="mb-6">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
                What you wrote
              </p>
              <WordDiff result={result.detail.written} />
            </div>
          )}

          {result.detail.spoken && (
            <div className="mb-6">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
                What you said
              </p>
              <WordDiff result={result.detail.spoken} caveat={result.detail.caveat} />
            </div>
          )}

          {result.detail.variation && (
            <div className="mb-6">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
                Your own versions
              </p>
              <p className="text-ink dark:text-white/85">{result.detail.variation}</p>
            </div>
          )}

          <Button onClick={load}>Another sentence</Button>
        </Card>
      )}

      {isLast && !result && (
        <p className="text-center text-sm text-ink-3">
          Finishing scores your listening, speaking and writing together.
        </p>
      )}
    </div>
  );
}
