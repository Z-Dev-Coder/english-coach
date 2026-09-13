import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import PracticeNav from "../components/PracticeNav";
import WordDiff from "../components/WordDiff";
import Glossed from "../components/Glossed";
import TopicLanguage from "../components/TopicLanguage";
import WritingLesson from "../components/WritingLesson";
import { api } from "../lib/api";
import Icon from "../lib/icons";
import { canSpeak, pickVoice, speak, stopSpeaking } from "../lib/speech";
import {
  Button,
  Card,
  CardSkeleton,
  EmptyState,
  ErrorNote,
  Field,
  HowTo,
  Input,
  Pill,
  SectionHeading,
  Select,
} from "../lib/ui";

const WRITING_PROMPTS = [
  "What did you do today? Write it as if you were telling a friend.",
  "Describe a problem you solved recently and how you solved it.",
  "Write a short message asking a colleague to postpone a meeting.",
  "What is something you changed your mind about this year?",
  "Describe your ideal weekend, and why it appeals to you.",
];

/* ------------------------------------------------------------- Listening */

function Listening({ passages, voice, assignedId, level }) {
  // Starts on whatever today's lesson assigned. Empty means "no lesson sent me
  // here", and only then does the first passage make sense as a default.
  const [passageId, setPassageId] = useState(() => (assignedId ? String(assignedId) : ""));
  const [index, setIndex] = useState(0);
  const [written, setWritten] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Timing starts when the learner engages with the sentence, not at render.
  const startedAt = useRef(0);

  const beginTiming = () => {
    if (!startedAt.current) startedAt.current = Date.now();
  };

  const [browsing, setBrowsing] = useState(false);
  const passage = passages.find((item) => String(item.id) === passageId) || passages[0];
  const assigned = assignedId != null && String(assignedId) === String(passage?.id);

  // Own level only, unless they have asked to see everything. A picker that
  // lists every level next to a profile that states one is just a way to
  // practise at the wrong difficulty.
  const atLevel = passages.filter((item) => item.level === level);
  const choices = browsing || atLevel.length === 0 ? passages : atLevel;
  const sentences = passage?.sentences ?? [];
  const sentence = sentences[index];

  const [language, setLanguage] = useState(null);
  const [showLanguage, setShowLanguage] = useState(true);
  useEffect(() => {
    if (!passage?.id) return;
    let live = true;
    setLanguage(null);
    api
      .passageLesson(passage.id)
      .then((data) => live && setLanguage(data))
      .catch(() => live && setLanguage(null));
    return () => {
      live = false;
    };
  }, [passage?.id]);

  const check = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.submitDictation({
          expected: sentence,
          written,
          passage_id: passage.id,
          duration_ms: startedAt.current ? Date.now() - startedAt.current : 0,
        }),
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    setIndex((value) => (value + 1) % sentences.length);
    setWritten("");
    setResult(null);
    startedAt.current = 0;
  };

  if (!passages.length) {
    return <EmptyState icon="🎧" title="No passages yet" body="Add some text on the Reading tab first." />;
  }

  const choose = (value) => {
    setPassageId(value);
    setIndex(0);
    setWritten("");
    setResult(null);
  };

  return (
    <div className="space-y-6">
      {language && (language.vocabulary?.length > 0 || language.expressions?.length > 0) && (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <h3 className="micro">before you listen — words from this text</h3>
            <button onClick={() => setShowLanguage((open) => !open)} className="micro hover:text-ink">
              {showLanguage ? "hide" : "show"}
            </button>
          </div>
          {showLanguage && <TopicLanguage language={language} questionsTitle="listen for the answers" />}
        </Card>
      )}
      <Card>
        {assigned && !browsing ? (
          // Assigned by today's plan. Stated, not offered: the plan already
          // weighed this against the learner's level and weak skills, and
          // re-opening that as a dropdown just invites contradicting it.
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <span className="micro">today&rsquo;s listening</span>
              <p className="mt-1 font-semibold">
                {passage.title} <Pill>{passage.level}</Pill>
              </p>
            </div>
            <button onClick={() => setBrowsing(true)} className="micro hover:text-ink">
              browse all passages
            </button>
          </div>
        ) : (
          <Field label="Passage">
            <Select value={passage ? String(passage.id) : ""} onChange={(e) => choose(e.target.value)}>
              {choices.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title} ({item.level})
                </option>
              ))}
            </Select>
          </Field>
        )}

        {passage?.audio_url && (
          <div className="mt-4 rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
            <p className="micro">real recording · {passage.audio_credit}</p>
            <p className="mt-1 text-[13px] text-ink-2 dark:text-white/60">
              Listen to the whole thing first for the gist — real speakers, real rhythm.
            </p>
            <audio src={passage.audio_url} controls preload="none" className="mt-2 w-full" />
          </div>
        )}

        <p className="mt-4 text-sm text-ink-2 dark:text-white/55">
          Sentence {index + 1} of {sentences.length}. Listen, then type what you hear — the text
          stays hidden until you check.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            onClick={() => {
              beginTiming();
              speak(sentence, { voice });
            }}
            disabled={!canSpeak}
          >
            <Icon name="play" size={13} /> Play
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              beginTiming();
              speak(sentence, { rate: 0.65, voice });
            }}
            disabled={!canSpeak}
          >
            <Icon name="slow" size={13} /> Slowly
          </Button>
        </div>

        <textarea
          value={written}
          onChange={(event) => setWritten(event.target.value)}
          rows={3}
          placeholder="Type what you hear…"
          className="mt-4 w-full rounded-xl border-0 bg-sunken p-4 ring-1 ring-[color:var(--color-line)] focus:ring-2 focus:ring-brand-500 dark:bg-white/[0.05] dark:ring-white/10"
        />

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={check} loading={busy} disabled={!written.trim() || !sentence}>
            Check
          </Button>
          {result && (
            <Button variant="secondary" onClick={next}>
              Next sentence
            </Button>
          )}
        </div>
      </Card>

      <ErrorNote error={error} />

      {result && (
        <Card className="animate-rise">
          <SectionHeading title="Result" />
          <WordDiff result={result.detail} />
        </Card>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- Reading */

function Reading({ passages, assignedId, onAdded }) {
  // Opened straight onto the assigned text. Landing on the passage list after
  // pressing Start on a lesson step means being asked to choose something the
  // plan already chose.
  const [reading, setReading] = useState(
    () => passages.find((item) => String(item.id) === String(assignedId)) ?? null,
  );
  const [showAdd, setShowAdd] = useState(false);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const startedAt = useRef(null);

  const open = (passage) => {
    setReading(passage);
    setSaved(false);
    startedAt.current = Date.now();
  };

  const finish = async () => {
    const seconds = Math.max(1, Math.round((Date.now() - startedAt.current) / 1000));
    try {
      await api.submitReading({ passage_id: reading.id, seconds });
      setSaved(true);
    } catch (err) {
      setError(err);
    }
  };

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.addPassage({ title, text });
      setTitle("");
      setText("");
      setShowAdd(false);
      onAdded(created);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (reading) {
    return (
      <div className="space-y-6">
        <Button variant="secondary" onClick={() => setReading(null)}>
          Back to passages
        </Button>
        <Card>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-bold">{reading.title}</h2>
            <Pill tone="brand">{reading.level}</Pill>
            <Pill>{reading.word_count} words</Pill>
          </div>
          <Glossed className="space-y-3 text-lg leading-relaxed">
            {reading.text.split("\n").map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </Glossed>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button onClick={finish} disabled={saved}>
              {saved ? "Recorded" : "I've finished reading"}
            </Button>
            {!reading.audio_url && (
              <Button variant="secondary" onClick={() => speak(reading.text)} disabled={!canSpeak}>
                <Icon name="play" size={13} /> Read it aloud
              </Button>
            )}
          </div>
          {reading.audio_url && (
            <div className="mt-4">
              <p className="micro">read along with the real recording · {reading.audio_credit}</p>
              <audio src={reading.audio_url} controls preload="none" className="mt-2 w-full" />
            </div>
          )}
          <p className="mt-3 text-xs text-ink-3">
            Reading time is recorded, but it doesn't move your reading score on its own — speed
            isn't comprehension.
          </p>
        </Card>
        <ErrorNote error={error} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <Button variant={showAdd ? "secondary" : "primary"} onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? "Cancel" : "+ Add your own text"}
        </Button>
      </div>

      {showAdd && (
        <Card className="animate-rise">
          <SectionHeading title="Paste anything you want to study" />
          <div className="space-y-3">
            <Field label="Title" hint="(optional)">
              <Input value={title} onChange={(event) => setTitle(event.target.value)} />
            </Field>
            <Field label="Text">
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={6}
                placeholder="An article, an email, subtitles, a message someone sent you…"
                className="w-full rounded-xl border-0 bg-sunken p-4 text-sm ring-1 ring-[color:var(--color-line)] focus:ring-2 focus:ring-brand-500 dark:bg-white/[0.05] dark:ring-white/10"
              />
            </Field>
            <Button onClick={add} loading={busy} disabled={text.trim().length < 20}>
              Save passage
            </Button>
            <p className="text-xs text-ink-3">
              Its level is estimated automatically, and it becomes available for listening and
              dictation too. Only you can see it.
            </p>
          </div>
        </Card>
      )}

      <ErrorNote error={error} />

      <div className="grid gap-3 sm:grid-cols-2">
        {passages.map((passage, index) => (
          <Card
            key={passage.id}
            as="button"
            interactive
            onClick={() => open(passage)}
            className="animate-rise text-left"
            style={{ animationDelay: `${index * 40}ms` }}
          >
            <p className="font-semibold">{passage.title}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Pill tone="brand">{passage.level}</Pill>
              <Pill>{passage.word_count} words</Pill>
              {passage.is_mine && <Pill tone="good">yours</Pill>}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- Writing */

function Writing({ assignedPrompt }) {
  // Today's lesson decides. The fallback is only for arriving here directly.
  const prompt = assignedPrompt || WRITING_PROMPTS[0];
  const [round, setRound] = useState(0);

  return (
    <Card>
      <WritingLesson
        key={round}
        task={prompt}
        finishLabel="Done — start fresh"
        onFinished={() => setRound((value) => value + 1)}
      />
    </Card>
  );
}

/* ------------------------------------------------------------------- Hub */

export default function Practice() {
  // The tab lives in the URL so the practice sub-nav can link straight to it,
  // and so a lesson activity can deep-link to the right exercise.
  // Read-only: PracticeNav owns switching, via links rather than state.
  const [params] = useSearchParams();
  const tab = params.get("tab") || "listening";
  // What today's lesson sent us here to do. Absent when the learner navigated
  // to Practice on their own, which is a different situation and looks it.
  const assignedPassageId = params.get("passage_id");
  const assignedPrompt = params.get("prompt");
  const [profile, setProfile] = useState(null);
  const [passages, setPassages] = useState(null);
  const [voice, setVoice] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api
      .passages()
      .then((data) => setPassages(data.results ?? data))
      .catch(setError);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    pickVoice().then(setVoice);
    return () => stopSpeaking();
  }, []);

  useEffect(() => {
    // Only for choosing difficulty, so a failure here must not stop practice.
    api.profile().then(setProfile).catch(() => setProfile(null));
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="display text-[38px]">Practice</h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          Each activity updates the skill it trains, which is what reshapes tomorrow's plan.
        </p>
      </header>

      <PracticeNav />

      {tab === "listening" && (
        <HowTo
          id="listening"
          title="How dictation works"
          steps={[
            "Press Play and listen. The text stays hidden on purpose.",
            "Type what you hear, then Check. Punctuation and capitals don't count against you.",
            "Use Slowly only after two normal plays — the struggle is the practice.",
          ]}
        />
      )}
      {tab === "reading" && (
        <HowTo
          id="reading"
          title="How to use reading"
          steps={[
            "Read once for the gist, then again for phrases you couldn't have written yourself.",
            "Click any word you don't know to see what it means, and add it to your reviews.",
            "Add your own text to study an email, article or message you actually received.",
          ]}
        />
      )}
      {tab === "writing" && (
        <HowTo
          id="writing"
          title="How a writing lesson works"
          steps={[
            "Learn the language first: topic words, phrasal verbs, expressions and sentence patterns for this task.",
            "Write using the plan. The checklist ticks as you use what you just learned — aim for the number shown.",
            "Feedback shows what you used, what to try next time, and a corrected, more natural version.",
          ]}
        />
      )}

      <ErrorNote error={error} onRetry={load} />

      {!passages && tab !== "writing" ? (
        <CardSkeleton lines={4} />
      ) : (
        <>
          {tab === "listening" && (
            <Listening
              passages={passages ?? []}
              voice={voice}
              assignedId={assignedPassageId}
              level={profile?.overall_level}
            />
          )}
          {tab === "reading" && (
            <Reading
              passages={passages ?? []}
              assignedId={assignedPassageId}
              onAdded={(created) => setPassages((current) => [created, ...(current ?? [])])}
            />
          )}
          {tab === "writing" && <Writing assignedPrompt={assignedPrompt} />}
        </>
      )}
    </div>
  );
}
