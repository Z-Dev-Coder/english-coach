import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import WordDiff from "../components/WordDiff";
import { api } from "../lib/api";
import { cx } from "../lib/cx";
import { canSpeak, pickVoice, speak, stopSpeaking } from "../lib/speech";
import {
  Button,
  Card,
  CardSkeleton,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  Pill,
  SectionHeading,
  Select,
} from "../lib/ui";

const TABS = [
  { key: "listening", label: "Listening", icon: "🎧" },
  { key: "reading", label: "Reading", icon: "📖" },
  { key: "writing", label: "Writing", icon: "✍️" },
];

const WRITING_PROMPTS = [
  "What did you do today? Write it as if you were telling a friend.",
  "Describe a problem you solved recently and how you solved it.",
  "Write a short message asking a colleague to postpone a meeting.",
  "What is something you changed your mind about this year?",
  "Describe your ideal weekend, and why it appeals to you.",
];

/* ------------------------------------------------------------- Listening */

function Listening({ passages, voice }) {
  const [passageId, setPassageId] = useState("");
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

  const passage = passages.find((item) => String(item.id) === passageId) || passages[0];
  const sentences = passage?.sentences ?? [];
  const sentence = sentences[index];

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

  return (
    <div className="space-y-5">
      <Card>
        <Field label="Passage">
          <Select
            value={passage ? String(passage.id) : ""}
            onChange={(event) => {
              setPassageId(event.target.value);
              setIndex(0);
              setWritten("");
              setResult(null);
            }}
          >
            {passages.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title} ({item.level})
              </option>
            ))}
          </Select>
        </Field>

        <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
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
            <span aria-hidden="true">▶</span> Play
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              beginTiming();
              speak(sentence, { rate: 0.65, voice });
            }}
            disabled={!canSpeak}
          >
            <span aria-hidden="true">🐢</span> Slowly
          </Button>
        </div>

        <textarea
          value={written}
          onChange={(event) => setWritten(event.target.value)}
          rows={3}
          placeholder="Type what you hear…"
          className="mt-4 w-full rounded-xl border-0 bg-slate-50 p-4 ring-1 ring-slate-200 focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:ring-white/10"
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

function Reading({ passages, onAdded }) {
  const [reading, setReading] = useState(null);
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
      <div className="space-y-5">
        <Button variant="secondary" onClick={() => setReading(null)}>
          ← Back to passages
        </Button>
        <Card>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-bold">{reading.title}</h2>
            <Pill tone="brand">{reading.level}</Pill>
            <Pill>{reading.word_count} words</Pill>
          </div>
          <div className="space-y-3 text-lg leading-relaxed">
            {reading.text.split("\n").map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button onClick={finish} disabled={saved}>
              {saved ? "✓ Recorded" : "I've finished reading"}
            </Button>
            <Button variant="secondary" onClick={() => speak(reading.text)} disabled={!canSpeak}>
              <span aria-hidden="true">▶</span> Read it aloud
            </Button>
          </div>
          <p className="mt-3 text-xs text-slate-400">
            Reading time is recorded, but it doesn't move your reading score on its own — speed
            isn't comprehension.
          </p>
        </Card>
        <ErrorNote error={error} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
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
                className="w-full rounded-xl border-0 bg-slate-50 p-4 text-sm ring-1 ring-slate-200 focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:ring-white/10"
              />
            </Field>
            <Button onClick={add} loading={busy} disabled={text.trim().length < 20}>
              Save passage
            </Button>
            <p className="text-xs text-slate-400">
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

function Writing() {
  const [prompt, setPrompt] = useState(WRITING_PROMPTS[0]);
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Starts on the first keystroke, so a prompt left open in a tab does not
  // report an hour of "writing time".
  const startedAt = useRef(0);

  const onType = (event) => {
    if (!startedAt.current) startedAt.current = Date.now();
    setText(event.target.value);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.submitWriting({
          text,
          task: prompt,
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
  const detail = result?.detail;

  return (
    <div className="space-y-5">
      <Card>
        <SectionHeading
          title="Writing prompt"
          action={
            <button
              onClick={() =>
                setPrompt(WRITING_PROMPTS[Math.floor(Math.random() * WRITING_PROMPTS.length)])
              }
              className="text-sm font-medium text-brand-600 hover:underline dark:text-brand-300"
            >
              Another prompt
            </button>
          }
        />
        <p className="text-lg">{prompt}</p>

        <textarea
          value={text}
          onChange={onType}
          rows={8}
          placeholder="Write as much as you can. Don't worry about mistakes — that's the point."
          className="mt-4 w-full rounded-xl border-0 bg-slate-50 p-4 leading-relaxed ring-1 ring-slate-200 focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:ring-white/10"
        />

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={submit} loading={busy} disabled={!text.trim()}>
            Get feedback
          </Button>
          <span className="text-sm tabular-nums text-slate-400">{words} words</span>
        </div>
      </Card>

      <ErrorNote error={error} />

      {detail && (
        <Card className="animate-rise">
          <SectionHeading
            title="Feedback"
            action={
              <Pill tone={detail.source === "ai" ? "good" : "default"}>
                {detail.source === "ai" ? "AI review" : "Basic checks"}
              </Pill>
            }
          />

          {detail.source !== "ai" && (
            <p className="mb-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
              The local AI isn't running, so these are structural checks only. Start Ollama for
              full grammar and naturalness feedback — your writing was still saved.
            </p>
          )}

          {detail.strengths?.length > 0 && (
            <div className="mb-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                What worked
              </p>
              <ul className="space-y-1 text-slate-700 dark:text-slate-200">
                {detail.strengths.map((item, index) => (
                  <li key={index} className="flex gap-2">
                    <span aria-hidden="true" className="text-emerald-500">
                      ✓
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {detail.issues?.length > 0 && (
            <div className="mb-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Things to fix
              </p>
              <ul className="space-y-3">
                {detail.issues.map((issue, index) => (
                  <li
                    key={index}
                    className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800/60"
                  >
                    {issue.original && (
                      <p>
                        <span className="rounded bg-rose-100 px-1 line-through dark:bg-rose-500/20">
                          {issue.original}
                        </span>
                        {issue.correction && (
                          <>
                            {" → "}
                            <span className="rounded bg-emerald-100 px-1 font-medium dark:bg-emerald-500/20">
                              {issue.correction}
                            </span>
                          </>
                        )}
                      </p>
                    )}
                    <p className={cx("text-slate-600 dark:text-slate-300", issue.original && "mt-1")}>
                      {issue.explanation}
                    </p>
                    {issue.category && (
                      <span className="mt-1.5 inline-block text-xs text-slate-400">
                        {issue.category.replace(/_/g, " ")}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {detail.natural_version && (
            <div className="mb-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                A natural version
              </p>
              <p className="rounded-xl bg-brand-50 p-4 leading-relaxed dark:bg-brand-500/10">
                {detail.natural_version}
              </p>
              <p className="mt-2 text-xs text-slate-400">
                Compare it with yours — the differences are the lesson.
              </p>
            </div>
          )}

          {detail.practice_prompt && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                Practise this
              </p>
              <p className="text-slate-700 dark:text-slate-200">{detail.practice_prompt}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- Hub */

export default function Practice() {
  const [tab, setTab] = useState("listening");
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

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Practice</h1>
        <p className="mt-1.5 text-slate-500 dark:text-slate-400">
          Each activity updates the skill it trains, which is what reshapes tomorrow's plan.
        </p>
      </header>

      <Card className="bg-gradient-to-br from-brand-600 to-violet-600 text-white ring-0">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold">Listen → Speak → Write</h2>
            <p className="mt-1 text-sm text-white/75">
              One sentence, five ways. The most efficient single exercise here.
            </p>
          </div>
          <Link
            to="/drill"
            className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-brand-700 transition hover:bg-white/90"
          >
            Start drill →
          </Link>
        </div>
      </Card>

      <div className="flex gap-1.5 overflow-x-auto">
        {TABS.map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={cx(
              "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition",
              tab === item.key
                ? "bg-brand-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700",
            )}
          >
            <span aria-hidden="true">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </div>

      <ErrorNote error={error} onRetry={load} />

      {!passages && tab !== "writing" ? (
        <CardSkeleton lines={4} />
      ) : (
        <>
          {tab === "listening" && <Listening passages={passages ?? []} voice={voice} />}
          {tab === "reading" && (
            <Reading
              passages={passages ?? []}
              onAdded={(created) => setPassages((current) => [created, ...(current ?? [])])}
            />
          )}
          {tab === "writing" && <Writing />}
        </>
      )}
    </div>
  );
}
