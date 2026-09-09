import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { Button, Card, EmptyState, ErrorNote, Pill } from "../lib/ui";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

/** Where the learner can take the generated prompt. Deep links pre-open the
 *  assistant; the prompt itself still has to be pasted, because none of these
 *  accept prefilled text reliably via URL. */
const ASSISTANTS = [
  { name: "ChatGPT", url: "https://chat.openai.com/" },
  { name: "Gemini", url: "https://gemini.google.com/app" },
  { name: "Claude", url: "https://claude.ai/new" },
];

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard API needs a secure context; fall back to a manual selection.
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button onClick={copy} aria-live="polite">
      {copied ? "✓ Copied" : "Copy prompt"}
    </Button>
  );
}

function ScriptView({ script, onPracticed }) {
  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold">{script.title}</h2>
          <Pill tone="brand">{script.level}</Pill>
          <Pill>{script.scenario.replace(/_/g, " ")}</Pill>
          {script.source === "ai" && <Pill tone="good">AI generated</Pill>}
        </div>
        <p className="mt-2 text-slate-600">{script.setting}</p>
        {script.goal && (
          <p className="mt-1 text-sm text-slate-500">
            <span className="font-medium text-slate-600">Your goal:</span> {script.goal}
          </p>
        )}
      </div>

      {script.target_expressions?.length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Try to use these
          </h3>
          <ul className="space-y-2">
            {script.target_expressions.map((expression) => (
              <li key={expression} className="flex items-start gap-2 text-slate-700">
                <span aria-hidden="true" className="mt-0.5 text-indigo-400">
                  ▸
                </span>
                <span>{expression}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {script.lines?.length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            How it starts
          </h3>
          <div className="space-y-2.5">
            {script.lines.map((line, index) => (
              <div
                key={index}
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                  line.speaker === "You"
                    ? "ml-auto bg-indigo-600 text-white"
                    : "bg-slate-100 text-slate-700"
                }`}
              >
                <span className="mb-0.5 block text-xs opacity-70">{line.speaker}</span>
                {line.text}
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="bg-slate-900 text-slate-100 ring-slate-900">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">Practise with any AI</h3>
            <p className="mt-0.5 text-sm text-slate-400">
              Copy this and paste it into ChatGPT, Gemini or Claude. It runs the whole roleplay
              and gives you feedback when you type <code className="text-indigo-300">FEEDBACK</code>.
            </p>
          </div>
          <CopyButton text={script.portable_prompt} />
        </div>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-black/40 p-4 text-xs leading-relaxed text-slate-200">
          {script.portable_prompt}
        </pre>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400">Open:</span>
          {ASSISTANTS.map((assistant) => (
            <a
              key={assistant.name}
              href={assistant.url}
              target="_blank"
              rel="noreferrer noopener"
              className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/20"
            >
              {assistant.name} ↗
            </a>
          ))}
        </div>
      </Card>

      {script.follow_up_questions?.length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Keep going
          </h3>
          <ul className="list-disc space-y-1.5 pl-5 text-slate-600">
            {script.follow_up_questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </Card>
      )}

      <div className="flex items-center gap-3">
        <Button variant="secondary" onClick={() => onPracticed(script.id)}>
          I practised this
        </Button>
        {script.times_practiced > 0 && (
          <span className="text-sm text-slate-500">
            Practised {script.times_practiced}×
          </span>
        )}
      </div>
    </div>
  );
}

export default function SpeakingStudio() {
  const [meta, setMeta] = useState(null);
  const [scenario, setScenario] = useState("");
  const [level, setLevel] = useState("");
  const [topic, setTopic] = useState("");
  const [useAi, setUseAi] = useState(false);
  const [script, setScript] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.scenarios().then(setMeta).catch(setError);
    api
      .scripts()
      .then((data) => setHistory(data.results ?? data))
      .catch(() => setHistory([]));
  }, []);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.generateScript({ scenario, level, topic, use_ai: useAi });
      setScript(created);
      setHistory((previous) => [created, ...previous]);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const markPracticed = async (id) => {
    const updated = await api.markPracticed(id);
    setScript(updated);
    setHistory((previous) => previous.map((s) => (s.id === updated.id ? updated : s)));
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Speaking Script Studio</h1>
        <p className="mt-1 text-slate-500">
          Get a roleplay script pitched at your speaking level, then practise it here or with any
          AI assistant.
        </p>
      </header>

      <Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">Situation</span>
            <select
              value={scenario}
              onChange={(event) => setScenario(event.target.value)}
              className="w-full rounded-xl border-0 bg-slate-50 px-3 py-2.5 text-sm ring-1 ring-slate-200 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Surprise me</option>
              {meta?.scenarios.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.key.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">Level</span>
            <select
              value={level}
              onChange={(event) => setLevel(event.target.value)}
              className="w-full rounded-xl border-0 bg-slate-50 px-3 py-2.5 text-sm ring-1 ring-slate-200 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">My speaking level</option>
              {LEVELS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              Topic <span className="font-normal text-slate-400">(optional)</span>
            </span>
            <input
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="e.g. a delayed flight"
              className="w-full rounded-xl border-0 bg-slate-50 px-3 py-2.5 text-sm ring-1 ring-slate-200 focus:ring-2 focus:ring-indigo-500"
            />
          </label>

          <div className="flex items-end">
            <Button onClick={generate} disabled={busy} className="w-full">
              {busy ? "Writing…" : "Generate script"}
            </Button>
          </div>
        </div>

        <label className="mt-4 flex items-center gap-2.5 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={useAi}
            onChange={(event) => setUseAi(event.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
          />
          Use the local AI for a custom script
          <span className="text-slate-400">
            (slower; falls back to a built-in script if the model is offline)
          </span>
        </label>
      </Card>

      <ErrorNote error={error} />

      {script ? (
        <ScriptView script={script} onPracticed={markPracticed} />
      ) : (
        <EmptyState
          title="No script yet"
          body="Pick a situation and generate one. Built-in scripts are instant and work with no AI at all."
        />
      )}

      {history.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Recent scripts</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {history.slice(0, 6).map((item) => (
              <button
                key={item.id}
                onClick={() => setScript(item)}
                className="rounded-2xl bg-white p-4 text-left shadow-sm ring-1 ring-slate-900/5 transition hover:shadow-md"
              >
                <p className="font-medium">{item.title}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {item.level} · {item.scenario.replace(/_/g, " ")}
                  {item.times_practiced > 0 && ` · practised ${item.times_practiced}×`}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
