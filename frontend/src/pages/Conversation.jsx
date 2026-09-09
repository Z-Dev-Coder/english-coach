import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import { canListen, canSpeak, listen, pickVoice, speak, stopSpeaking } from "../lib/speech";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Pill,
  SectionHeading,
  Select,
  Switch,
} from "../lib/ui";

/**
 * Conversation tutor.
 *
 * The defining rule is that nothing corrects the learner mid-conversation.
 * Being stopped every sentence destroys fluency practice, which is the entire
 * point. All feedback arrives at the end, when they choose to finish.
 */

function Bubble({ message, onSpeak }) {
  const isLearner = message.role === "learner";
  return (
    <div className={cx("flex", isLearner && "justify-end")}>
      <div
        className={cx(
          "group max-w-[80%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed shadow-sm",
          isLearner
            ? "rounded-br-md bg-brand-600 text-white"
            : "rounded-bl-md bg-white text-slate-700 ring-1 ring-slate-900/5 dark:bg-slate-800 dark:text-slate-200 dark:ring-white/10",
        )}
      >
        {message.content}
        {!isLearner && canSpeak && (
          <button
            onClick={() => onSpeak(message.content)}
            aria-label="Play this reply"
            className="ml-2 align-middle text-xs opacity-0 transition group-hover:opacity-60 hover:!opacity-100"
          >
            🔊
          </button>
        )}
      </div>
    </div>
  );
}

function Feedback({ feedback }) {
  if (!feedback) return null;

  if (!feedback.available) {
    return (
      <Card className="bg-amber-50 ring-amber-200 dark:bg-amber-500/10 dark:ring-amber-500/20">
        <p className="text-sm text-amber-900 dark:text-amber-200">{feedback.summary}</p>
        <p className="mt-1 text-xs text-amber-800 dark:text-amber-300/90">
          Start Ollama and have another conversation to get a full review. The practice still
          counted.
        </p>
      </Card>
    );
  }

  return (
    <Card className="animate-rise">
      <SectionHeading
        title="How that went"
        action={
          feedback.estimated_level ? <Pill tone="brand">{feedback.estimated_level}</Pill> : null
        }
      />
      <p className="text-slate-600 dark:text-slate-300">{feedback.summary}</p>

      {feedback.did_well?.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            What worked
          </p>
          <ul className="space-y-1.5">
            {feedback.did_well.map((item, index) => (
              <li key={index} className="flex gap-2 text-slate-700 dark:text-slate-200">
                <span aria-hidden="true" className="text-emerald-500">
                  ✓
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback.corrections?.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            More natural versions
          </p>
          <ul className="space-y-3">
            {feedback.corrections.map((item, index) => (
              <li key={index} className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800/60">
                <p>
                  <span className="rounded bg-rose-100 px-1 line-through dark:bg-rose-500/20">
                    {item.original}
                  </span>
                  {" → "}
                  <span className="rounded bg-emerald-100 px-1 font-medium dark:bg-emerald-500/20">
                    {item.natural}
                  </span>
                </p>
                <p className="mt-1 text-slate-600 dark:text-slate-300">{item.explanation}</p>
                {item.category && (
                  <span className="mt-1 inline-block text-xs text-slate-400">
                    {item.category.replace(/_/g, " ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback.useful_expressions?.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Expressions that would have fitted
          </p>
          <div className="flex flex-wrap gap-2">
            {feedback.useful_expressions.map((item) => (
              <Pill key={item} tone="brand">
                {item}
              </Pill>
            ))}
          </div>
        </div>
      )}

      {feedback.focus_next_time && (
        <div className="mt-5 rounded-xl bg-brand-50 p-4 dark:bg-brand-500/10">
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-700 dark:text-brand-300">
            Next time
          </p>
          <p className="mt-1 text-slate-700 dark:text-slate-200">{feedback.focus_next_time}</p>
        </div>
      )}
    </Card>
  );
}

export default function Conversation() {
  const [scenarios, setScenarios] = useState([]);
  const [scenario, setScenario] = useState("casual");
  const [session, setSession] = useState(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [ending, setEnding] = useState(false);
  const [recording, setRecording] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [voice, setVoice] = useState(null);
  const [error, setError] = useState(null);
  const bottom = useRef(null);
  const recognition = useRef(null);

  useEffect(() => {
    api
      .conversationScenarios()
      .then((data) => setScenarios(data.scenarios))
      .catch(() => setScenarios([]));
    pickVoice().then(setVoice);
    return () => stopSpeaking();
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages?.length]);

  const say = useCallback(
    (content) => speak(content, { voice }),
    [voice],
  );

  const start = async () => {
    setError(null);
    setSending(true);
    try {
      const created = await api.startConversation({ scenario });
      setSession(created);
      if (autoSpeak) say(created.messages.at(-1)?.content);
    } catch (err) {
      setError(err);
    } finally {
      setSending(false);
    }
  };

  const send = async () => {
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    const mine = text;
    setText("");
    try {
      const data = await api.sendConversationMessage(session.id, { text: mine });
      setSession(data.session);
      if (autoSpeak) say(data.reply.content);
    } catch (err) {
      setError(err);
      setText(mine); // Give them their words back rather than losing them.
    } finally {
      setSending(false);
    }
  };

  const record = async () => {
    setError(null);
    if (recording) {
      recognition.current?.stop();
      return;
    }
    setRecording(true);
    const active = listen({ interim: setText });
    recognition.current = active;
    try {
      setText(await active.promise);
    } catch (err) {
      setError(err);
    } finally {
      setRecording(false);
    }
  };

  const finish = async () => {
    setEnding(true);
    setError(null);
    try {
      const data = await api.endConversation(session.id);
      setSession(data.session);
    } catch (err) {
      setError(err);
    } finally {
      setEnding(false);
    }
  };

  const ended = session?.status === "ended";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Conversation</h1>
        <p className="mt-1.5 text-slate-500 dark:text-slate-400">
          Talk freely. Nothing corrects you while you speak — the review comes at the end.
        </p>
      </header>

      <ErrorNote error={error} />

      {!session ? (
        <Card>
          <SectionHeading title="Pick a situation" />
          <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <Field label="Situation">
              <Select value={scenario} onChange={(event) => setScenario(event.target.value)}>
                {scenarios.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.key.replace(/_/g, " ")} — {item.description}
                  </option>
                ))}
              </Select>
            </Field>
            <Button onClick={start} loading={sending} size="lg">
              Start talking
            </Button>
          </div>
          <div className="mt-5 border-t border-slate-100 pt-4 dark:border-white/5">
            <Switch
              checked={autoSpeak}
              onChange={setAutoSpeak}
              label="Read replies out loud"
              description="Turns this into listening practice as well."
            />
          </div>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="brand">{session.scenario.replace(/_/g, " ")}</Pill>
            <Pill>{session.level}</Pill>
            <Pill>{session.turn_count} turns</Pill>
            {ended && <Pill tone="good">finished</Pill>}
          </div>

          <div className="space-y-3 rounded-2xl bg-slate-100/60 p-4 dark:bg-slate-900/60">
            {session.messages.map((message) => (
              <Bubble key={message.id} message={message} onSpeak={say} />
            ))}
            {sending && (
              <p className="text-sm text-slate-400" aria-live="polite">
                thinking…
              </p>
            )}
            <div ref={bottom} />
          </div>

          {!ended ? (
            <Card>
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
                rows={2}
                placeholder="Say something… (Enter to send, Shift+Enter for a new line)"
                className="w-full rounded-xl border-0 bg-slate-50 p-3.5 ring-1 ring-slate-200 focus:ring-2 focus:ring-brand-500 dark:bg-slate-800 dark:ring-white/10"
              />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button onClick={send} loading={sending} disabled={!text.trim()}>
                  Send
                </Button>
                {canListen && (
                  <Button variant={recording ? "danger" : "secondary"} onClick={record}>
                    <span aria-hidden="true">{recording ? "⏹" : "🎙"}</span>
                    {recording ? "Stop" : "Speak"}
                  </Button>
                )}
                <div className="ml-auto">
                  <Button variant="ghost" onClick={finish} loading={ending}>
                    Finish and get feedback
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <>
              <Feedback feedback={session.feedback} />
              <Button
                onClick={() => {
                  setSession(null);
                  setText("");
                }}
              >
                New conversation
              </Button>
            </>
          )}
        </>
      )}

      {!session && scenarios.length === 0 && (
        <EmptyState
          icon="💬"
          title="Scenarios could not be loaded"
          body="The backend may not be running. Conversation needs the local AI model to reply."
        />
      )}
    </div>
  );
}
