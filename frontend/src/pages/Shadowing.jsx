import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import PracticeNav from "../components/PracticeNav";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { useRecorder } from "../lib/recorder";
import { pickVoice, playTracked, speakTracked, stopSpeaking } from "../lib/speech";
import { Button, Card, CardSkeleton, ErrorNote, HowTo, Pill } from "../lib/ui";

/**
 * Shadowing: speak along with the audio, a beat behind, without stopping.
 *
 * The first version of this page was a chunk drill -- play a phrase, stop,
 * press Next, play the next one. That is a reasonable exercise and it is not
 * shadowing. Shadowing works precisely *because* it does not stop: the learner
 * has no time to translate, assemble a sentence, or self-correct, so they are
 * forced onto the rhythm and stress of the speaker instead of their own. Take
 * the continuity away and you have removed the mechanism, leaving repetition
 * after a model, which the drill page already does better.
 *
 * So the audio now runs start to finish and the page tracks it, highlighting
 * the phrase being spoken right now. The learner reads ahead by a beat and
 * speaks along.
 *
 * Speed is the accommodation instead of pausing. Slowing the whole passage
 * keeps it continuous, which is the part that matters, while making it
 * followable -- a beginner shadowing at 0.6 is still shadowing.
 */

/** A token as it appears in the word list: no surrounding punctuation. */
const bare = (token) => token.toLowerCase().replace(/^[^\p{Letter}']+|[^\p{Letter}']+$/gu, "");

const SPEEDS = [
  { value: 0.6, label: "0.6×" },
  { value: 0.75, label: "0.75×" },
  { value: 0.9, label: "0.9×" },
  { value: 1, label: "Full" },
];

export default function Shadowing() {
  const [params] = useSearchParams();
  const [guide, setGuide] = useState(null);
  const [passages, setPassages] = useState(null);
  const [passageId, setPassageId] = useState(params.get("passage_id") ?? "");
  const [voice, setVoice] = useState(null);
  const [error, setError] = useState(null);
  const [rate, setRate] = useState(0.75);
  const [offset, setOffset] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [playError, setPlayError] = useState(null);
  const recorder = useRecorder();
  const stopRef = useRef(null);
  const activeRef = useRef(null);
  const textRef = useRef(null);

  const load = useCallback(
    (id) => {
      setError(null);
      api
        .passages()
        .then((list) => {
          setPassages(list);
          // Real recordings first: those are what shadowing should be done with.
          list = [...list].sort((a, b) => Boolean(b.audio_url) - Boolean(a.audio_url));
          setPassages(list);
          const chosen = id || (list[0] && String(list[0].id)) || "";
          setPassageId(chosen);
          return chosen ? api.shadowingGuide({ passage_id: chosen }) : null;
        })
        .then((data) => data && setGuide(data))
        .catch(setError);
    },
    [],
  );

  useEffect(() => {
    load(params.get("passage_id") ?? "");
  }, [load, params]);

  useEffect(() => {
    pickVoice().then(setVoice);
    return () => stopSpeaking();
  }, []);

  const chunks = guide?.chunks ?? [];
  // Which phrase the voice is in the middle of. -1 before playback starts, so
  // nothing is highlighted until there is something to follow.
  const activeIndex =
    offset < 0 ? -1 : chunks.findIndex((chunk) => offset >= chunk.start && offset < chunk.end);
  const current = activeIndex === -1 && offset >= 0 ? chunks.length - 1 : activeIndex;

  // Keep the spoken line in view, moving the text box and nothing else.
  //
  // Deliberately not scrollIntoView: that scrolls every scrollable ancestor,
  // so it moved the window too and the whole page jumped on every phrase.
  // Scrolling only when the line has left a comfortable band turns twenty-odd
  // scrolls per passage into one per line -- the text should move when you
  // reach the bottom of it, not each time a phrase ends.
  useEffect(() => {
    const container = textRef.current;
    const active = activeRef.current;
    if (!container || !active) return;

    // Measured from rects rather than offsetTop. offsetTop is relative to the
    // nearest positioned ancestor, which may or may not be this container
    // depending on how the box is styled -- rects do not care.
    const containerBox = container.getBoundingClientRect();
    const activeBox = active.getBoundingClientRect();
    const top = activeBox.top - containerBox.top + container.scrollTop;
    const bottom = top + activeBox.height;
    const viewTop = container.scrollTop;
    const viewBottom = viewTop + container.clientHeight;
    // A margin of roughly a line, so the next phrase is already visible before
    // the one being spoken reaches the edge.
    const margin = activeBox.height * 1.5;

    if (top >= viewTop + margin && bottom <= viewBottom - margin) return;

    container.scrollTo({
      top: Math.max(0, top - container.clientHeight / 2),
      behavior: "smooth",
    });
  }, [current]);

  const stop = useCallback(() => {
    stopRef.current?.();
    stopRef.current = null;
    setPlaying(false);
    if (recorder.recording) recorder.stop();
  }, [recorder]);

  const play = () => {
    if (!guide?.text) return;
    setPlayError(null);
    // With real timings nothing is lit until the speaker's first word, so a
    // programme intro doesn't sit on the first phrase for 15 seconds.
    setOffset(guide.audio_url && guide.timings?.length ? -1 : 0);
    setPlaying(true);
    recorder.clear();
    // Recording runs for the whole pass, so the learner can hear their own
    // delivery against the model rather than one phrase at a time.
    if (recorder.supported) recorder.start();
    const player = guide.audio_url
      ? (text, options) => playTracked(guide.audio_url, text, { ...options, timings: guide.timings })
      : speakTracked;
    stopRef.current = player(guide.text, {
      rate,
      voice,
      onProgress: setOffset,
      onEnd: () => {
        setPlaying(false);
        if (recorder.recording) recorder.stop();
      },
      onError: (err) => {
        // A playback problem belongs next to the Play button, not in place of the page.
        setPlayError(err.message || "Playback failed.");
        setPlaying(false);
        if (recorder.recording) recorder.stop();
      },
    });
  };

  const choose = (id) => {
    stop();
    setOffset(-1);
    setGuide(null);
    setPassageId(id);
    api.shadowingGuide({ passage_id: id }).then(setGuide).catch(setError);
  };

  if (error) return <ErrorNote error={error} onRetry={() => load(passageId)} />;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="display text-[38px]">
          Shadowing <span className="text-[color:var(--color-accent)]">Studio</span>
        </h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          Speak along with the voice, a beat behind. It doesn&rsquo;t stop — that&rsquo;s the point.
        </p>
      </header>

      <PracticeNav />

      <HowTo
        id="shadowing"
        title="How shadowing works"
        steps={[
          "Press Play and start speaking about a second behind the voice. Don't wait for gaps.",
          "Follow the highlight. Read slightly ahead of it so you're never catching up.",
          "You will fall behind and lose your place. Keep going — rejoining is the skill.",
          "Too fast? Slow the whole thing down. Slower is still shadowing; stopping isn't.",
        ]}
      />

      {!guide ? (
        <CardSkeleton lines={6} />
      ) : (
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="brand">{guide.level}</Pill>
              {guide.passage && <span className="micro">{guide.passage.title}</span>}
              {guide.audio_url ? (
                <Pill tone="good">real voice · {guide.audio_credit}</Pill>
              ) : (
                <span className="micro">computer voice — pick a real-voice passage below</span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="micro">speed</span>
              {SPEEDS.map((speed) => (
                <button
                  key={speed.value}
                  onClick={() => setRate(speed.value)}
                  className={cx(
                    "rounded-full px-2.5 py-1 font-mono text-[11px] transition",
                    rate === speed.value
                      ? "bg-ink text-white dark:bg-white dark:text-black"
                      : "text-ink-3 ring-1 ring-[color:var(--color-line)] hover:text-ink dark:ring-white/10",
                  )}
                >
                  {speed.label}
                </button>
              ))}
            </div>
          </div>

          {/* The passage, whole, with the spoken phrase lit. Reading the text
              as continuous prose is deliberate: chopping it into cards is what
              made the last version a drill. */}
          <div
            ref={textRef}
            // overflow-x-hidden: a highlighted phrase's padding could push past the edge and
            // show a horizontal bar; dark:[color-scheme:dark] keeps the scrollbar from being white.
            className="relative max-h-[46vh] overflow-y-auto overflow-x-hidden rounded-xl bg-sunken p-5 text-[19px] leading-[1.9] break-words dark:bg-white/[0.04] dark:[color-scheme:dark]"
          >
            {chunks.map((chunk, index) => {
              const spoken = current > index;
              const active = current === index;
              // Matched by word rather than by index: the rendered tokens
              // carry punctuation, so their positions do not line up with the
              // stripped word list the stress indices refer to.
              const stressWords = new Set(
                chunk.stress.map((i) => chunk.words[i]?.toLowerCase()).filter(Boolean),
              );
              return (
                <span
                  key={index}
                  ref={active ? activeRef : undefined}
                  className={cx(
                    "rounded px-1 transition-colors duration-200",
                    active && "bg-[color:var(--color-accent)]/20 text-ink dark:text-white",
                    !active && spoken && "text-ink-3",
                    !active && !spoken && "text-ink-2 dark:text-white/70",
                  )}
                >
                  {/* The chunk's own text, not its extracted words: the word
                      list drops punctuation, and someone reading a beat ahead
                      of the voice needs the commas and full stops to know
                      where the phrasing is going. */}
                  {chunk.text.split(/(\s+)/).map((token, i) =>
                    /^\s+$/.test(token) ? (
                      token
                    ) : (
                      <span
                        key={i}
                        className={cx(active && stressWords.has(bare(token)) && "font-bold")}
                      >
                        {token}
                      </span>
                    ),
                  )}{" "}
                </span>
              );
            })}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            {playing ? (
              <Button variant="danger" onClick={stop} size="lg">
                <Icon name="stop" size={14} /> Stop
              </Button>
            ) : (
              <Button onClick={play} size="lg">
                <Icon name="play" size={14} /> {offset >= 0 ? "Play again" : "Play and speak along"}
              </Button>
            )}
            {recorder.recording && (
              <span className="micro text-[color:var(--color-accent)]">recording you</span>
            )}
            {playError && (
              <span className="text-[13px] text-[color:var(--color-accent)]">
                {playError} Check your connection and press Play again.
              </span>
            )}
          </div>

          {recorder.url && !playing && (
            <div className="mt-4 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
              <p className="micro">your run — listen for where the rhythm drifted</p>
              <audio src={recorder.url} controls className="mt-2 w-full" />
            </div>
          )}

          {!recorder.supported && (
            <p className="mt-3 text-[13px] text-ink-3">
              This browser can&rsquo;t record, so there&rsquo;s nothing to play back. Shadowing out
              loud still works — that&rsquo;s the part that matters.
            </p>
          )}

          {passages?.length > 1 && (
            <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-[color:var(--color-line)] pt-4 dark:border-white/10">
              <span className="micro">shadow something else</span>
              {passages.map((item) => (
                <button
                  key={item.id}
                  onClick={() => choose(String(item.id))}
                  className={cx(
                    "rounded-full px-3 py-1 text-[12px] transition",
                    String(item.id) === String(passageId)
                      ? "bg-ink text-white dark:bg-white dark:text-black"
                      : "text-ink-2 ring-1 ring-[color:var(--color-line)] hover:bg-sunken dark:ring-white/10",
                  )}
                >
                  {item.title}
                </button>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
