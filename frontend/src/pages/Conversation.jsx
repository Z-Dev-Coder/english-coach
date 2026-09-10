import { useCallback, useEffect, useRef, useState } from "react";

import PracticeNav from "../components/PracticeNav";
import { api } from "../lib/api";
import Icon from "../lib/icons";
import { cx } from "../lib/cx";
import { canListen, canSpeak, listen, pickVoice, speak, stopSpeaking } from "../lib/speech";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  HowTo,
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
            ? "rounded-br-md bg-ink text-white"
            : "rounded-bl-md bg-surface text-ink ring-1 ring-[color:var(--color-line)] dark:bg-white/[0.06] dark:text-white/85 dark:ring-white/10",
        )}
      >
        {message.content}
        {!isLearner && canSpeak && (
          <button
            onClick={() => onSpeak(message.content)}
            aria-label="Play this reply"
            className="ml-2 align-middle text-xs opacity-0 transition group-hover:opacity-60 hover:!opacity-100"
          >
            <Icon name="volume" size={13} />
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
      <Card className="border-dashed">
        <p className="text-[13px] text-ink-2 dark:text-white/60">{feedback.summary}</p>
        <p className="mt-1 text-xs text-ink-3">
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
      <p className="text-ink-2 dark:text-white/70">{feedback.summary}</p>

      {feedback.did_well?.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
            What worked
          </p>
          <ul className="space-y-1.5">
            {feedback.did_well.map((item, index) => (
              <li key={index} className="flex gap-2 text-ink dark:text-white/85">
                <Icon name="check" size={14} className="mt-1 shrink-0 text-[color:var(--color-good-ink)]" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback.corrections?.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
            More natural versions
          </p>
          <ul className="space-y-3">
            {feedback.corrections.map((item, index) => (
              <li key={index} className="rounded-xl bg-sunken p-3 text-sm dark:bg-white/[0.04]">
                <p>
                  <span className="text-[color:var(--color-accent)] line-through">
                    {item.original}
                  </span>
                  {" → "}
                  <span className="font-medium text-ink dark:text-white">
                    {item.natural}
                  </span>
                </p>
                <p className="mt-1 text-ink-2 dark:text-white/70">{item.explanation}</p>
                {item.category && (
                  <span className="mt-1 inline-block text-xs text-ink-3">
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
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
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
        <div className="mt-5 border-t border-[color:var(--color-line)] pt-4 dark:border-white/10">
          <p className="text-xs font-semibold uppercase tracking-wider text-ink dark:text-white">
            Next time
          </p>
          <p className="mt-1 text-ink dark:text-white/85">{feedback.focus_next_time}</p>
        </div>
      )}
    </Card>
  );
}

export default function Conversation() {
  const [scenarios, setScenarios] = useState([]);
  const [scenario, setScenario] = useState("");
  const [session, setSession] = useState(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [picking, setPicking] = useState(false);
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
      .then((data) => {
        setScenarios(data.scenarios);
        // The rotation lives on the server, so the page is told what it would
        // choose rather than guessing and showing something different.
        if (data.suggested) setScenario(data.suggested);
      })
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

  // The situation on screen, so the card can name it before starting.
  const chosen = scenarios.find((item) => item.key === scenario) ?? null;

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
    <div className="space-y-6">
      <header>
        <h1 className="display text-[38px]">Conversation</h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          Talk freely. Nothing corrects you while you speak — the review comes at the end.
        </p>
      </header>

      <PracticeNav />

      <ErrorNote error={error} />

      {!session && (
        <HowTo
          id="conversation"
          title="How to get the most from this"
          steps={[
            "Talk freely and make mistakes — nothing corrects you while you speak.",
            "Answer in full sentences, not one word. Longer replies are worth more.",
            "Press Finish when you're done, and you get the full review then.",
          ]}
        />
      )}

      {!session ? (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <span className="micro">today&rsquo;s conversation</span>
              <p className="mt-1.5 font-semibold">
                {(chosen?.key ?? "casual").replace(/_/g, " ")}
              </p>
              {chosen?.description && (
                <p className="mt-0.5 text-sm text-ink-2 dark:text-white/60">
                  {chosen.description}
                </p>
              )}
            </div>
            <Button onClick={start} loading={sending} size="lg">
              Start talking
            </Button>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-[color:var(--color-line)] pt-3 dark:border-white/10">
            {/* Not the default, but not a dead end: being handed a medical
                appointment on a day you want small talk should be escapable. */}
            <button onClick={() => setPicking((open) => !open)} className="micro hover:text-ink">
              {picking ? "never mind" : "practise something else"}
            </button>
            {picking && (
              <Select
                className="max-w-72"
                value={scenario}
                onChange={(event) => setScenario(event.target.value)}
              >
                {scenarios.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.key.replace(/_/g, " ")} — {item.description}
                  </option>
                ))}
              </Select>
            )}
          </div>
          <div className="mt-5 border-t border-[color:var(--color-line)] pt-4 dark:border-white/5">
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

          <div className="space-y-3 rounded-2xl bg-sunken/60 p-4 dark:bg-white/[0.03]/60">
            {session.messages.map((message) => (
              <Bubble key={message.id} message={message} onSpeak={say} />
            ))}
            {sending && (
              <p className="text-sm text-ink-3" aria-live="polite">
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
                className="w-full rounded-xl border-0 bg-sunken p-3.5 ring-1 ring-[color:var(--color-line)] focus:ring-2 focus:ring-brand-500 dark:bg-white/[0.05] dark:ring-white/10"
              />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button onClick={send} loading={sending} disabled={!text.trim()}>
                  Send
                </Button>
                {canListen && (
                  <Button variant={recording ? "danger" : "secondary"} onClick={record}>
                    <Icon name={recording ? "stop" : "mic"} size={13} />
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
          icon="talk"
          title="Scenarios could not be loaded"
          body="The backend may not be running. Conversation needs the local AI model to reply."
        />
      )}
    </div>
  );
}
