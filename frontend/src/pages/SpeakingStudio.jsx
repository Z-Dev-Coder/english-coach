import { useEffect, useState } from "react";

import PracticeNav from "../components/PracticeNav";
import { api } from "../lib/api";
import Icon from "../lib/icons";
import { cx } from "../lib/cx";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  HowTo,
  Input,
  Pill,
  SectionHeading,
  Select,
  Switch,
} from "../lib/ui";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

/** Where the learner can take the generated prompt. These open the assistant;
 *  the prompt still has to be pasted, since none of them accept prefilled text
 *  reliably through a URL. */
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
      // The clipboard API needs a secure context; fall back to a hidden field.
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
    <Button onClick={copy} variant={copied ? "secondary" : "primary"}>
      <span aria-hidden="true">{copied ? "✓" : "📋"}</span>
      <span aria-live="polite">{copied ? "Copied" : "Copy prompt"}</span>
    </Button>
  );
}

function ScriptView({ script, onPracticed }) {
  return (
    <div className="animate-rise space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold tracking-tight">{script.title}</h2>
          <Pill tone="brand">{script.level}</Pill>
          <Pill>{script.scenario.replace(/_/g, " ")}</Pill>
          {script.source === "ai" && <Pill tone="good">AI generated</Pill>}
        </div>
        <p className="mt-2 text-ink-2 dark:text-white/70">{script.setting}</p>
        {script.goal && (
          <p className="mt-1.5 text-sm text-ink-2 dark:text-white/55">
            <span className="font-medium text-ink-2 dark:text-white/70">Your goal:</span>{" "}
            {script.goal}
          </p>
        )}
      </div>

      {script.target_expressions?.length > 0 && (
        <Card>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-3">
            Try to use these
          </h3>
          <ul className="space-y-2.5">
            {script.target_expressions.map((expression) => (
              <li key={expression} className="flex items-start gap-2.5">
                <span aria-hidden="true" className="mt-1 text-xs text-ink-3">
                  ●
                </span>
                <span className="text-ink dark:text-white/85">{expression}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {script.lines?.length > 0 && (
        <Card>
          <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-ink-3">
            How it starts
          </h3>
          <div className="space-y-3">
            {script.lines.map((line, index) => (
              <div
                key={index}
                className={cx(
                  "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm shadow-sm",
                  line.speaker === "You"
                    ? "ml-auto rounded-br-md bg-ink text-white"
                    : "rounded-bl-md bg-sunken text-ink-2 dark:bg-white/[0.05] dark:text-white/85",
                )}
              >
                <span className="mb-0.5 block text-[11px] font-medium opacity-60">
                  {line.speaker}
                </span>
                {line.text}
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="border-0 bg-ink text-white/90 ring-1 ring-ink">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-semibold">Practise with any AI</h3>
            <p className="mt-1 text-sm leading-relaxed text-ink-3">
              Paste this into ChatGPT, Gemini or Claude. It runs the whole roleplay, and gives you
              feedback when you type{" "}
              <code className="rounded bg-white/10 px-1.5 py-0.5 text-xs font-semibold text-brand-300">
                FEEDBACK
              </code>
              .
            </p>
          </div>
          <CopyButton text={script.portable_prompt} />
        </div>

        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-black/40 p-4 text-xs leading-relaxed text-ink-3 ring-1 ring-white/5">
          {script.portable_prompt}
        </pre>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-2">Open:</span>
          {ASSISTANTS.map((assistant) => (
            <a
              key={assistant.name}
              href={assistant.url}
              target="_blank"
              rel="noreferrer noopener"
              className="rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/20"
            >
              {assistant.name}
            </a>
          ))}
        </div>
      </Card>

      {script.follow_up_questions?.length > 0 && (
        <Card>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-3">
            Keep the conversation going
          </h3>
          <ul className="space-y-2">
            {script.follow_up_questions.map((question) => (
              <li key={question} className="flex items-start gap-2.5 text-ink-2 dark:text-white/70">
                <span aria-hidden="true" className="mt-0.5 text-ink-3">
                  ?
                </span>
                {question}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" onClick={() => onPracticed(script.id)}>
          <Icon name="check" size={13} /> I practised this
        </Button>
        {script.times_practiced > 0 && (
          <span className="text-sm text-ink-2 dark:text-white/55">
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
        <h1 className="display text-[38px]">
          Speaking <span className="text-[color:var(--color-accent)]">Script Studio</span>
        </h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          A roleplay script pitched at your speaking level — practise it here, or take the prompt
          to any AI assistant.
        </p>
      </header>

      <PracticeNav />

      <HowTo
        id="speaking"
        title="How to use a script"
        steps={[
          "Generate a script, then say the lines out loud — quietly is fine.",
          "Or press Copy prompt and paste it into ChatGPT, Gemini or Claude to roleplay there.",
          "Type FEEDBACK in that chat when you're done and it reviews your English.",
        ]}
      />

      <Card>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Situation">
            <Select value={scenario} onChange={(event) => setScenario(event.target.value)}>
              <option value="">Surprise me</option>
              {meta?.scenarios.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.key.replace(/_/g, " ")}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Level">
            <Select value={level} onChange={(event) => setLevel(event.target.value)}>
              <option value="">My speaking level</option>
              {LEVELS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Topic" hint="(optional)">
            <Input
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="e.g. a delayed flight"
            />
          </Field>

          <div className="flex items-end">
            <Button onClick={generate} loading={busy} size="lg" className="w-full">
              {busy ? "Writing" : "Generate script"}
            </Button>
          </div>
        </div>

        <div className="mt-5 border-t border-[color:var(--color-line)] pt-4 dark:border-white/5">
          <Switch
            checked={useAi}
            onChange={setUseAi}
            label="Use the local AI for a custom script"
            description="Slower, and falls back to a built-in script if the model is offline."
          />
        </div>
      </Card>

      <ErrorNote error={error} />

      {script ? (
        <ScriptView script={script} onPracticed={markPracticed} />
      ) : (
        <EmptyState
          icon="speak"
          title="No script yet"
          body="Pick a situation and generate one. Built-in scripts are instant and need no AI at all."
          action={
            <Button onClick={generate} loading={busy}>
              Generate my first script
            </Button>
          }
        />
      )}

      {history.length > 0 && (
        <section>
          <SectionHeading title="Recent scripts" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {history.slice(0, 6).map((item, index) => (
              <Card
                key={item.id}
                as="button"
                interactive
                onClick={() => setScript(item)}
                className="animate-rise text-left"
                style={{ animationDelay: `${index * 40}ms` }}
              >
                <p className="font-semibold">{item.title}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Pill tone="brand">{item.level}</Pill>
                  <Pill>{item.scenario.replace(/_/g, " ")}</Pill>
                  {item.times_practiced > 0 && (
                    <Pill tone="good">practised {item.times_practiced}×</Pill>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
