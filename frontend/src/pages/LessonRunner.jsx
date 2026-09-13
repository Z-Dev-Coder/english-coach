import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import LessonStep from "../components/lesson/steps";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import Icon from "../lib/icons";
import { pickVoice, stopSpeaking } from "../lib/speech";
import { skillLabel } from "../lib/skills";
import { CardSkeleton, ErrorNote, Spinner } from "../lib/ui";

/**
 * Runs the lesson, one step at a time.
 *
 * This replaces a launcher. The map used to link each step out to the page
 * that owns that skill; the learner did something there, came back, and
 * pressed "mark done". Three things were wrong with that. Self-reported
 * completion is not evidence of practice. Navigating away breaks the thread of
 * a twenty-minute session into six separate errands. And it puts the work of
 * remembering where you were onto the person who came here to be told.
 *
 * So: one screen, one exercise, a bar that fills, and no way to tell the app
 * you finished something you did not do. Completion is recorded by the
 * exercise itself when it actually ends.
 *
 * Steps are strictly in order. You cannot open step four while step two is
 * unfinished -- not to be strict for its own sake, but because the plan is
 * ordered by what the learner is weakest at, and letting them skip to the
 * comfortable one is how the whole thing quietly becomes revision of what they
 * can already do.
 */

function ProgressBar({ done, total }) {
  const pct = total ? (done / total) * 100 : 0;
  return (
    <div
      className="h-2 flex-1 overflow-hidden rounded-full bg-sunken dark:bg-white/10"
      role="progressbar"
      aria-valuenow={done}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label="Lesson progress"
    >
      <div
        className="h-full rounded-full bg-[color:var(--color-accent)] transition-[width] duration-500 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/** The end of the lesson. A finish worth having is worth marking. */
function Finished({ lesson, onNext, busy }) {
  const minutes = lesson.total_minutes;
  const steps = lesson.activities.length;

  return (
    <div className="mx-auto max-w-xl py-10 text-center">
      <div className="animate-rise">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-[color:var(--color-accent)] text-white">
          <Icon name="check" size={30} />
        </div>
        <h1 className="display mt-5 text-[34px]">Lesson complete</h1>
        <p className="mt-2 text-ink-2 dark:text-white/60">{lesson.title}</p>

        <dl className="mt-7 grid grid-cols-2 gap-4">
          <div className="rounded-2xl bg-sunken p-4 dark:bg-white/[0.04]">
            <dt className="micro">Steps</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums">{steps}</dd>
          </div>
          <div className="rounded-2xl bg-sunken p-4 dark:bg-white/[0.04]">
            <dt className="micro">Minutes planned</dt>
            <dd className="mt-1 text-2xl font-bold tabular-nums">{minutes}</dd>
          </div>
        </dl>

        {lesson.encouragement && (
          <p className="mt-6 text-[15px] text-ink-2 dark:text-white/70">{lesson.encouragement}</p>
        )}

        <div className="mt-8 flex flex-col items-center gap-3">
          <button
            onClick={onNext}
            disabled={busy}
            className="rounded-full bg-ink px-6 py-2.5 font-medium text-white transition hover:opacity-90 disabled:opacity-50 dark:bg-white dark:text-black"
          >
            {busy ? "Building it…" : "Start the next lesson"}
          </button>
          <Link to={`/lesson/${lesson.id}`} className="micro hover:text-ink dark:hover:text-white">
            go back through this lesson
          </Link>
          <Link to="/" className="micro hover:text-ink dark:hover:text-white">
            back to home
          </Link>
        </div>

        <p className="mt-6 text-[13px] text-ink-3">
          Or stop here. The next lesson is built from how this one went, and it waits for you.
        </p>
      </div>
    </div>
  );
}

export default function LessonRunner() {
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState(null);
  const [voice, setVoice] = useState(null);
  const [busy, setBusy] = useState(false);
  // Review mode's own cursor. The live lesson derives its step from the
  // server; a past lesson has no unfinished step to derive one from.
  const [reviewIndex, setReviewIndex] = useState(0);
  const navigate = useNavigate();
  const { id } = useParams();
  const [search] = useSearchParams();
  // In the live lesson, a finished step being looked back at. null means
  // "wherever the lesson actually is" -- the first unfinished step.
  const [viewIndex, setViewIndex] = useState(() => {
    // Only an explicit ?step= means "go back". Number(null) is 0, so without
    // this check every visit silently reopened step 1 instead of resuming.
    const raw = search.get("step");
    if (raw === null || raw === "") return null;
    const step = Number(raw);
    return Number.isInteger(step) && step >= 0 ? step : null;
  });

  const load = useCallback(() => {
    setError(null);
    (id ? api.lesson(id) : api.todayLesson()).then(setLesson).catch(setError);
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    pickVoice().then(setVoice);
    return () => stopSpeaking();
  }, []);

  if (error) return <ErrorNote error={error} onRetry={load} />;
  if (!lesson) return <CardSkeleton lines={6} />;

  const activities = lesson.activities ?? [];
  const live = lesson.status === "ready" || lesson.status === "in_progress";

  // The live lesson opened by id: there must be one way to progress it, and
  // that is the ordinary runner.
  if (id && live) return <Navigate to="/lesson" replace />;

  const review = Boolean(id) && !live;
  const done = review
    ? reviewIndex
    : activities.filter((activity) => activity.is_complete).length;
  // The first unfinished step. Not a stored cursor: the server already knows
  // which steps are complete, so deriving it means closing the tab and coming
  // back lands in exactly the right place.
  const firstOpen = activities.findIndex((activity) => !activity.is_complete);
  // Going back is only ever to finished steps; an unfinished one ahead stays
  // locked, so a requested step past the lesson's position is ignored.
  const lookingBack =
    !review &&
    viewIndex !== null &&
    viewIndex < (firstOpen === -1 ? activities.length : firstOpen) &&
    activities[viewIndex]?.is_complete;
  const currentIndex = review ? reviewIndex : lookingBack ? viewIndex : firstOpen;
  const activity = activities[currentIndex];

  const complete = async () => {
    stopSpeaking();
    if (lookingBack) {
      // Already done: moving on from it records nothing, and returns to where
      // the lesson really is once the finished steps run out.
      const next = currentIndex + 1;
      const end = firstOpen === -1 ? activities.length : firstOpen;
      setViewIndex(next < end ? next : null);
      return;
    }
    if (review) {
      // The lesson itself is untouched. Exercises that score an answer still
      // record the attempt -- redoing one is real practice, and pretending
      // otherwise would hide it from the skill scores.
      setReviewIndex((index) => index + 1);
      return;
    }
    setBusy(true);
    try {
      setLesson(await api.completeActivity(lesson.id, activity.id));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const startNext = async () => {
    setBusy(true);
    try {
      // Asking again returns the lesson in progress, or builds one when the
      // last is finished -- so this is all "next lesson" needs to be.
      setLesson(await api.todayLesson());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (!activity) {
    if (review) {
      return (
        <div className="mx-auto max-w-xl py-10 text-center">
          <h1 className="display text-[30px]">End of review</h1>
          <p className="mt-2 text-ink-2 dark:text-white/60">{lesson.title}</p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              onClick={() => setReviewIndex(0)}
              className="rounded-full px-5 py-2 ring-1 ring-[color:var(--color-line)] dark:ring-white/15"
            >
              Start again
            </button>
            <Link
              to="/history"
              className="rounded-full bg-ink px-5 py-2 font-medium text-white dark:bg-white dark:text-black"
            >
              Back to history
            </Link>
          </div>
        </div>
      );
    }
    return <Finished lesson={lesson} onNext={startNext} busy={busy} />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      {/* Fixed to the top, because the answer to "how much is left" should
          never require scrolling to find. */}
      <div className="sticky top-0 z-10 -mx-4 flex items-center gap-4 bg-paper/90 px-4 py-3 backdrop-blur-md md:-mx-6 md:px-6">
        <button
          onClick={() => navigate(review ? "/history" : "/")}
          aria-label={review ? "Leave the review" : "Leave the lesson"}
          className="text-ink-3 transition hover:text-ink dark:hover:text-white"
        >
          <Icon name="close" size={18} />
        </button>
        <ProgressBar done={done} total={activities.length} />
        <span className="font-mono text-[11px] tabular-nums text-ink-3">
          {done}/{activities.length}
        </span>
      </div>

      <div className="mt-4">
        <div className="flex flex-wrap items-center gap-2">
          {review && <span className="micro">reviewing · lesson progress isn&rsquo;t changed</span>}
          {lookingBack && <span className="micro">going back · already done</span>}
          <span className="micro text-[color:var(--color-accent)]">
            step {currentIndex + 1}
          </span>
          <span className="micro">{skillLabel(activity.kind)}</span>
          <span className="micro">· {activity.minutes} min</span>
        </div>
        <h1 className="mt-2 text-[22px] font-semibold">{activity.title}</h1>
      </div>

      <div
        // Keyed by activity, so every step starts genuinely fresh rather than
        // inheriting the previous one's half-typed answer.
        key={activity.id}
        className={cx("animate-rise mt-5", busy && "pointer-events-none opacity-60")}
      >
        <LessonStep activity={activity} voice={voice} onDone={complete} />
      </div>

      {(currentIndex > 0 || lookingBack || review) && (
        <div className="mt-4 flex items-center gap-4">
          {currentIndex > 0 && (
            <button
              onClick={() => {
                stopSpeaking();
                if (review) setReviewIndex((index) => Math.max(0, index - 1));
                else setViewIndex(Math.max(0, currentIndex - 1));
              }}
              className="micro hover:text-ink dark:hover:text-white"
            >
              ← previous step
            </button>
          )}
          {/* Looking back should not mean redoing an exercise to get past it:
              a finished dictation would otherwise demand a fresh answer
              before letting you return to where the lesson really is. */}
          {(lookingBack || review) && (
            <button onClick={complete} className="micro hover:text-ink dark:hover:text-white">
              next step →
            </button>
          )}
        </div>
      )}

      {busy && (
        <p className="mt-4 flex items-center gap-2 text-[13px] text-ink-3">
          <Spinner /> Saving…
        </p>
      )}

      <ErrorNote error={error} />
    </div>
  );
}
