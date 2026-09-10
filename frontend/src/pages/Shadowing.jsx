import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import PracticeNav from "../components/PracticeNav";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { useRecorder } from "../lib/recorder";
import { pickVoice, speak, stopSpeaking } from "../lib/speech";
import {
  Button,
  Card,
  CardSkeleton,
  ErrorNote,
  HowTo,
  Pill,
} from "../lib/ui";

/**
 * Shadowing: speak along with the model, a beat behind.
 *
 * The hard part of shadowing is not the words -- it is that fluent English
 * arrives in chunks, with the beat on the words that carry meaning and the
 * pitch signalling whether the speaker has finished. A learner given a whole
 * sentence says it flat, one word at a time, and practises the wrong thing.
 *
 * So the sentence is not shown as a sentence. It is shown one chunk at a time,
 * sized to the learner's level, with the stressed words marked and an arrow for
 * where the pitch goes. The chunking, stress and intonation all come from the
 * server so the rules live in one tested place rather than being reimplemented
 * in JavaScript.
 *
 * Recording is deliberately paired with playback here rather than with a
 * score. Recognition can tell you the words were right; only hearing yourself
 * tells you the rhythm was wrong, and rhythm is the entire subject.
 */

const INTONATION = {
  rise: { arrow: "↗", label: "pitch rises — you have not finished" },
  fall: { arrow: "↘", label: "pitch falls — this closes the thought" },
};

function Chunk({ chunk, active }) {
  const tone = INTONATION[chunk.intonation] ?? INTONATION.fall;
  const stress = new Set(chunk.stress);

  return (
    <div
      className={cx(
        "rounded-xl px-4 py-3 transition",
        active
          ? "bg-sunken ring-1 ring-[color:var(--color-accent)]/40 dark:bg-white/[0.06]"
          : "opacity-45",
      )}
    >
      <p className="text-lg leading-relaxed">
        {chunk.words.map((word, index) => (
          <span
            key={index}
            className={cx(
              "mr-1.5 inline-block",
              // Stressed words are the beat. Weight rather than colour: the
              // accent is already doing other work on this page, and a
              // sentence half in orange is harder to read, not easier.
              stress.has(index) && "font-bold text-ink dark:text-white",
              !stress.has(index) && "text-ink-3",
            )}
          >
            {word}
          </span>
        ))}
        <span
          className="ml-1 text-[color:var(--color-accent)]"
          title={tone.label}
          aria-label={tone.label}
        >
          {tone.arrow}
        </span>
      </p>
      {active && (
        <p className="micro mt-1.5">
          bold = stress · {tone.label} · then pause {Math.round(chunk.pause_ms / 100) / 10}s
        </p>
      )}
    </div>
  );
}

export default function Shadowing() {
  const [params] = useSearchParams();
  const passageId = params.get("passage_id");

  const [guide, setGuide] = useState(null);
  const [passages, setPassages] = useState(null);
  const [index, setIndex] = useState(0);
  const [voice, setVoice] = useState(null);
  const [error, setError] = useState(null);
  const [rate, setRate] = useState(0.85);
  const recorder = useRecorder();
  const chosen = useRef(passageId);

  const load = useCallback(() => {
    setError(null);
    api
      .passages()
      .then((list) => {
        setPassages(list);
        if (!chosen.current && list.length) chosen.current = String(list[0].id);
        return api.shadowingGuide({ passage_id: chosen.current });
      })
      .then((data) => {
        setGuide(data);
        setIndex(0);
      })
      .catch(setError);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    pickVoice().then(setVoice);
    return () => stopSpeaking();
  }, []);

  const chunks = guide?.chunks ?? [];
  const chunk = chunks[index];

  const play = () => {
    if (chunk) speak(chunk.text, { rate, voice });
  };

  const move = (delta) => {
    stopSpeaking();
    recorder.clear();
    setIndex((current) => Math.min(chunks.length - 1, Math.max(0, current + delta)));
  };

  const toggleRecord = () => (recorder.recording ? recorder.stop() : recorder.start());

  if (error) return <ErrorNote error={error} onRetry={load} />;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="display text-[38px]">
          Shadowing <span className="text-[color:var(--color-accent)]">Studio</span>
        </h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          Speak along with the model, one chunk at a time — the rhythm is the exercise.
        </p>
      </header>

      <PracticeNav />

      <HowTo
        id="shadowing"
        title="How shadowing works"
        steps={[
          "Play the chunk and listen to where the beat falls. Don't read ahead.",
          "Say it along with the model, a beat behind — copy the rhythm, not just the words.",
          "Record yourself and play both back. Flat delivery is the thing to catch.",
          "Chunks are sized to your level, so shorter ones mean more control, not less progress.",
        ]}
      />

      {!guide ? (
        <CardSkeleton lines={5} />
      ) : (
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="brand">
                Chunk {index + 1} of {chunks.length}
              </Pill>
              <Pill>{guide.level}</Pill>
              {guide.passage && <span className="micro">{guide.passage.title}</span>}
            </div>
            {passages?.length > 1 && (
              <span className="micro">{guide.words_per_chunk} words a chunk at your level</span>
            )}
          </div>

          {chunk ? (
            <>
              <div className="space-y-2">
                {chunks.slice(Math.max(0, index - 1), index + 2).map((item, offset) => (
                  <Chunk
                    key={Math.max(0, index - 1) + offset}
                    chunk={item}
                    active={Math.max(0, index - 1) + offset === index}
                  />
                ))}
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-2">
                <Button onClick={play}>
                  <Icon name="play" size={13} /> Play chunk
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setRate((current) => (current === 0.85 ? 0.6 : 0.85));
                  }}
                >
                  <Icon name="slow" size={13} /> {rate === 0.85 ? "Slower" : "Normal speed"}
                </Button>
                {recorder.supported && (
                  <Button
                    variant={recorder.recording ? "danger" : "secondary"}
                    onClick={toggleRecord}
                  >
                    <Icon name={recorder.recording ? "stop" : "mic"} size={13} />
                    {recorder.recording ? "Stop" : "Record"}
                  </Button>
                )}
              </div>

              {recorder.url && (
                <div className="mt-4 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
                  <p className="micro">hear yourself back</p>
                  <audio src={recorder.url} controls className="mt-2 w-full" />
                  <button onClick={play} className="micro mt-2 hover:text-ink">
                    play the model again to compare
                  </button>
                </div>
              )}

              {!recorder.supported && (
                <p className="mt-3 text-[13px] text-ink-3">
                  This browser can&rsquo;t record audio, so there&rsquo;s nothing to play back.
                  Shadowing out loud still works — that&rsquo;s the part that matters.
                </p>
              )}

              <div className="mt-5 flex items-center gap-2 border-t border-[color:var(--color-line)] pt-4 dark:border-white/10">
                <Button variant="ghost" onClick={() => move(-1)} disabled={index === 0}>
                  <Icon name="arrowLeft" size={13} /> Back
                </Button>
                <Button onClick={() => move(1)} disabled={index >= chunks.length - 1}>
                  Next chunk <Icon name="arrowRight" size={13} />
                </Button>
              </div>
            </>
          ) : (
            <p className="text-[13px] text-ink-3">
              Nothing to shadow yet — add a passage on the Reading tab first.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
