import { useCallback, useEffect, useState } from "react";

import Glossed from "./Glossed";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { Button, Card, CardSkeleton, ErrorNote, Pill } from "../lib/ui";

/**
 * Watch on YouTube.
 *
 * Real videos at the learner's level. The video plays on YouTube itself; the
 * app is the teacher around it:
 *   1. before: what it's about and the expressions to catch
 *   2. watch on YouTube, with moments to listen for
 *   3. after: questions and a speaking prompt, then the next video
 */

const minutes = (seconds) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

function toSeconds(time) {
  const [m, s] = String(time).split(":").map(Number);
  return Number.isFinite(m) && Number.isFinite(s) ? m * 60 + s : 0;
}

export default function YouTubeLessons({ AddToReview }) {
  const [video, setVideo] = useState(null);
  const [library, setLibrary] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadNext = useCallback(() => {
    setError(null);
    api.nextVideo().then(setVideo).catch(setError);
  }, []);

  const loadLibrary = useCallback(() => {
    api.videos().then(setLibrary).catch(() => setLibrary(null));
  }, []);

  useEffect(() => {
    loadNext();
    loadLibrary();
  }, [loadNext, loadLibrary]);

  const open = async (id) => {
    setError(null);
    try {
      setVideo(await api.video(id));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err);
    }
  };

  const finish = async () => {
    setBusy(true);
    try {
      await api.completeVideo(video.id);
      loadLibrary();
      loadNext();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (error && !video) return <ErrorNote error={error} onRetry={loadNext} />;
  if (!video) return <CardSkeleton lines={6} />;

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row">
          <a
            href={video.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group relative block shrink-0 overflow-hidden rounded-xl sm:w-72"
          >
            <img src={video.thumbnail} alt="" className="aspect-video w-full object-cover" />
            <span className="absolute inset-0 grid place-items-center bg-black/30 opacity-90 transition group-hover:bg-black/40">
              <span className="flex items-center gap-1.5 rounded-full bg-[#ff0000] px-3 py-1.5 text-[13px] font-semibold text-white">
                <Icon name="play" size={12} /> Watch on YouTube
              </span>
            </span>
          </a>
          <div className="min-w-0">
            <span className="micro">your video · {library?.level ?? video.level} level</span>
            {video.done && <span className="micro ml-2 text-[color:var(--color-good-ink)]">watched</span>}
            <h2 className="mt-1 text-xl font-semibold">{video.title}</h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <Pill tone="brand">{video.level}</Pill>
              {video.kind && <Pill>{video.kind}</Pill>}
              <span className="micro">
                {video.channel} · {minutes(video.duration_seconds)}
              </span>
            </div>
            {video.summary && (
              <Glossed as="p" className="mt-3 text-[15px] text-ink-2 dark:text-white/70">
                {video.summary}
              </Glossed>
            )}
          </div>
        </div>
      </Card>

      {!video.prepared && (
        <Card>
          <p className="text-[15px] text-ink-2 dark:text-white/70">
            Notes for this video are still being written. Watch it on YouTube with English
            subtitles on, and note three phrases you&rsquo;d like to use yourself.
          </p>
        </Card>
      )}

      {video.expressions?.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="micro">1 · before you watch — expressions to catch</h3>
            {AddToReview && (
              <AddToReview items={video.expressions} sourceUrl={video.url} label="Add these to review" />
            )}
          </div>
          <ul className="mt-3 space-y-2">
            {video.expressions.map((item) => (
              <li key={item.expression} className="rounded-xl bg-sunken p-3 dark:bg-white/[0.04]">
                <span className="font-semibold">{item.expression}</span>
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
        </Card>
      )}

      {video.listen_for?.length > 0 && (
        <Card>
          <h3 className="micro">2 · while you watch — moments to listen for</h3>
          <p className="mt-1 text-[13px] text-ink-3">
            Tap a time to open the video at that moment. Turn on English subtitles the first time,
            then watch again without them.
          </p>
          <ul className="mt-3 space-y-2">
            {video.listen_for.map((moment, index) => (
              <li key={index} className="flex gap-3">
                <a
                  href={`${video.url}&t=${toSeconds(moment.time)}s`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 rounded-full px-2.5 py-0.5 font-mono text-[12px] ring-1 ring-[color:var(--color-line)] hover:bg-sunken dark:ring-white/15"
                >
                  {moment.time}
                </a>
                <Glossed as="p" className="text-[14px]">
                  {moment.note}
                </Glossed>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {video.questions?.length > 0 && (
        <Card>
          <h3 className="micro">3 · after you watch — check yourself</h3>
          <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-[15px]">
            {video.questions.map((question) => (
              <li key={question}>
                <Glossed>{question}</Glossed>
              </li>
            ))}
          </ol>
          {video.speaking_prompt && (
            <div className="mt-4 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
              <p className="micro">now talk about it — 1 to 2 minutes, out loud</p>
              <Glossed as="p" className="mt-1 text-[15px] font-medium">
                {video.speaking_prompt}
              </Glossed>
            </div>
          )}
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={finish} disabled={busy}>
          {video.done ? "Next video" : "I've watched it — next video"} <Icon name="arrowRight" size={13} />
        </Button>
        {error && <span className="text-[13px] text-[color:var(--color-accent)]">{error.message}</span>}
      </div>

      {library?.videos?.length > 1 && (
        <section>
          <h3 className="micro mb-2">videos at your level</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {library.videos.map((item) => (
              <button
                key={item.id}
                onClick={() => open(item.id)}
                className={cx(
                  "flex gap-3 rounded-xl p-2 text-left ring-1 transition hover:bg-sunken dark:hover:bg-white/5",
                  item.id === video.id
                    ? "ring-ink dark:ring-white"
                    : "ring-[color:var(--color-line)] dark:ring-white/10",
                )}
              >
                <img src={item.thumbnail} alt="" className="aspect-video w-28 shrink-0 rounded-lg object-cover" />
                <span className="min-w-0">
                  <span className="line-clamp-2 text-[14px] font-medium">{item.title}</span>
                  <span className="micro mt-1 block">
                    {item.channel} · {item.level}
                    {item.done ? " · watched" : ""}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
