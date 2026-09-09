import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { cx } from "../lib/cx";
import { canSpeak, pickVoice, speak, stopSpeaking } from "../lib/speech";
import {
  Button,
  Card,
  CardSkeleton,
  EmptyState,
  ErrorNote,
  HowTo,
  Pill,
  SectionHeading,
} from "../lib/ui";

/**
 * Real-world English: current stories, and dialogue the learner brings in.
 *
 * Every article links back to the original. What is shown here is metadata,
 * the publisher's own feed summary, and learning material written by our own
 * model — never a copy of someone's article.
 */

/** Sends extracted vocabulary into the review queue.
 *
 *  Without this the loop stops at "read once": vocabulary a learner met in real
 *  content has to become scheduled review, or it is not learning, it is
 *  browsing. */
function AddToReview({ items, sourceUrl, label = "Add all to review" }) {
  const [state, setState] = useState("idle");
  const [added, setAdded] = useState(0);

  if (!items?.length) return null;

  const add = async () => {
    setState("saving");
    try {
      const result = await api.addExtractedVocabulary({
        items,
        source: "content",
        source_url: sourceUrl || "",
      });
      setAdded(result.added);
      setState("done");
    } catch {
      setState("error");
    }
  };

  if (state === "done") {
    return (
      <p className="micro text-[color:var(--color-good-ink)]">
        ✓ {added} added to your review queue
      </p>
    );
  }

  return (
    <div>
      <Button variant="secondary" size="sm" onClick={add} loading={state === "saving"}>
        <span aria-hidden="true">＋</span> {label} ({items.length})
      </Button>
      {state === "error" && (
        <p className="mt-1 text-xs text-[color:var(--color-accent)]">Could not add those. Try again.</p>
      )}
    </div>
  );
}

function ArticleCard({ article, onPrepare, preparing, voice }) {
  const [open, setOpen] = useState(false);
  const material = article.has_material;

  return (
    <Card className="animate-rise">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold leading-snug">{article.title}</h3>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Pill tone="brand">{article.topic}</Pill>
            <Pill>{article.source_name}</Pill>
            {article.level && <Pill tone="good">{article.level}</Pill>}
          </div>
        </div>
      </div>

      {article.summary && (
        <p className="mt-3 text-sm leading-relaxed text-ink-2 dark:text-white/55">
          {article.summary.slice(0, 260)}
          {article.summary.length > 260 && "…"}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {material ? (
          <Button variant="secondary" size="sm" onClick={() => setOpen(!open)}>
            {open ? "Hide lesson" : "Study this"}
          </Button>
        ) : (
          <Button
            size="sm"
            onClick={() => onPrepare(article.id)}
            loading={preparing === article.id}
          >
            Make a lesson
          </Button>
        )}
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer noopener"
          className="text-sm font-medium text-brand-600 hover:underline dark:text-brand-300"
        >
          Read the original ↗
        </a>
      </div>

      {article.preparation_error && !material && (
        <p className="mt-2 text-xs text-[color:var(--color-accent)]">
          {article.preparation_error}
        </p>
      )}

      {open && material && (
        <div className="mt-5 space-y-5 border-t border-[color:var(--color-line)] pt-5 dark:border-white/5">
          {article.adapted_text && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">
                  In simpler English
                </p>
                {canSpeak && (
                  <button
                    onClick={() => speak(article.adapted_text, { voice })}
                    className="text-xs text-brand-600 hover:underline dark:text-brand-300"
                  >
                    🔊 Listen
                  </button>
                )}
              </div>
              <p className="leading-relaxed">{article.adapted_text}</p>
              <p className="mt-2 text-xs text-ink-3">
                Written for you at your level — not a copy of the article.
              </p>
            </div>
          )}

          {article.vocabulary?.length > 0 && (
            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">
                  Vocabulary
                </p>
                <AddToReview items={article.vocabulary} sourceUrl={article.url} />
              </div>
              <ul className="space-y-2">
                {article.vocabulary.map((item, index) => (
                  <li key={index} className="rounded-xl bg-sunken p-3 text-sm dark:bg-white/[0.04]">
                    <span className="font-semibold">{item.expression}</span>
                    {item.kind && (
                      <span className="ml-2 text-xs text-ink-3">
                        {item.kind.replace(/_/g, " ")}
                      </span>
                    )}
                    <p className="mt-0.5 text-ink-2 dark:text-white/70">{item.meaning}</p>
                    {item.example && (
                      <p className="mt-1 italic text-ink-2 dark:text-white/55">
                        “{item.example}”
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {article.questions?.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-3">
                Check you understood
              </p>
              <ol className="list-decimal space-y-1 pl-5 text-ink-2 dark:text-white/70">
                {article.questions.map((question, index) => (
                  <li key={index}>{question}</li>
                ))}
              </ol>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            {article.speaking_prompt && (
              <div className="border-t border-[color:var(--color-line)] pt-3 dark:border-white/10">
                <p className="text-xs font-semibold uppercase tracking-wider text-ink dark:text-white">
                  Say it
                </p>
                <p className="mt-1 text-sm">{article.speaking_prompt}</p>
              </div>
            )}
            {article.writing_prompt && (
              <div className="border-t border-[color:var(--color-line)] pt-3 dark:border-white/10">
                <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">
                  Write it
                </p>
                <p className="mt-1 text-sm">{article.writing_prompt}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

function DialogueStudio() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const study = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.studyDialogue({ text }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card>
        <SectionHeading title="Bring in dialogue from anything you watch" />
        <p className="-mt-1 mb-4 text-sm text-ink-2 dark:text-white/55">
          Paste a few lines from a film, a show, or a real conversation. You'll get the spoken
          English explained — the expressions whose meaning is nothing like the words.
        </p>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={6}
          placeholder={"A: What are you getting at?\nB: Nothing, forget it.\nA: No, go on."}
          className="w-full rounded-xl border-0 bg-sunken p-4 font-mono text-sm ring-1 ring-[color:var(--color-line)] focus:ring-2 focus:ring-brand-500 dark:bg-white/[0.05] dark:ring-white/10"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={study} loading={busy} disabled={text.trim().length < 20}>
            Explain this
          </Button>
          <span className="text-xs text-ink-3">
            Your own short excerpts only — nothing is scraped or shared.
          </span>
        </div>
      </Card>

      <ErrorNote error={error} />

      {result && !result.available && (
        <Card className="border-dashed">
          <p className="text-[13px] text-ink-2 dark:text-white/60">
            The local AI isn't running, so this needs Ollama. Everything else in the app still
            works.
          </p>
        </Card>
      )}

      {result?.available && (
        <Card className="animate-rise">
          <SectionHeading
            title="What's going on here"
            action={result.register ? <Pill tone="brand">{result.register}</Pill> : null}
          />
          {result.summary && (
            <p className="text-ink-2 dark:text-white/70">{result.summary}</p>
          )}

          <ul className="mt-5 space-y-3">
            {result.expressions.map((item, index) => (
              <li key={index} className="rounded-xl bg-sunken p-4 dark:bg-white/[0.04]">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{item.expression}</span>
                  {item.register && <Pill>{item.register}</Pill>}
                </div>
                <p className="mt-1 text-ink-2 dark:text-white/70">{item.meaning}</p>
                {item.literal_trap && (
                  <p className="mt-2 text-[13px] text-ink-2 dark:text-white/55">
                    <span className="font-medium">Careful: </span>
                    {item.literal_trap}
                  </p>
                )}
                {item.example && (
                  <p className="mt-2 italic text-ink-2 dark:text-white/55">
                    “{item.example}”
                  </p>
                )}
                {item.alternatives?.length > 0 && (
                  <p className="mt-2 text-sm text-ink-2 dark:text-white/55">
                    Also: {item.alternatives.join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ul>

          <div className="mt-5">
            <AddToReview
              items={result.expressions}
              label="Add these expressions to review"
            />
          </div>

          {result.roleplay_prompt && (
            <div className="mt-5 border-t border-[color:var(--color-line)] pt-4 dark:border-white/10">
              <p className="text-xs font-semibold uppercase tracking-wider text-ink dark:text-white">
                Try using them
              </p>
              <p className="mt-1">{result.roleplay_prompt}</p>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

export default function RealWorld() {
  const [tab, setTab] = useState("today");
  const [data, setData] = useState(null);
  const [topic, setTopic] = useState("");
  const [preparing, setPreparing] = useState(null);
  const [fetching, setFetching] = useState(false);
  const [voice, setVoice] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    api.todayArticles().then(setData).catch(setError);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    pickVoice().then(setVoice);
    return () => stopSpeaking();
  }, []);

  const prepare = async (id) => {
    setPreparing(id);
    setError(null);
    try {
      const prepared = await api.prepareArticle(id);
      setData((current) => ({
        ...current,
        articles: current.articles.map((item) => (item.id === id ? prepared : item)),
      }));
    } catch (err) {
      setError(err);
    } finally {
      setPreparing(null);
    }
  };

  const refresh = async () => {
    setFetching(true);
    setError(null);
    try {
      await api.ingestContent({});
      load();
    } catch (err) {
      setError(err);
    } finally {
      setFetching(false);
    }
  };

  const articles = (data?.articles ?? []).filter(
    (article) => !topic || article.topic === topic,
  );

  return (
    <div className="space-y-5">
      <header>
        <h1 className="display text-[38px]">
          Real <em className="italic">World</em> English
        </h1>
        <p className="mt-1 text-sm text-ink-2 dark:text-white/55">
          Current stories and real dialogue, turned into things you can actually study.
        </p>
      </header>

      <div className="flex gap-1.5">
        {[
          { key: "today", label: "Today in English", icon: "🌍" },
          { key: "dialogue", label: "Movies & TV", icon: "🎬" },
        ].map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={cx(
              "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition",
              tab === item.key
                ? "bg-ink text-white dark:bg-white dark:text-ink"
                : "bg-sunken text-ink-2 hover:bg-[color:var(--color-line)] dark:bg-white/[0.05] dark:text-ink-3 dark:hover:bg-white/10",
            )}
          >
            <span aria-hidden="true">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </div>

      <ErrorNote error={error} onRetry={load} />

      {tab === "today" ? (
        <HowTo
          id="realworld"
          title="Turn the news into study material"
          steps={[
            "Pick a story you'd actually want to read anyway.",
            "Make a lesson — you get a simpler retelling, vocabulary and questions.",
            "Add all to review, so those words come back on schedule instead of being forgotten.",
          ]}
        />
      ) : (
        <HowTo
          id="dialogue"
          title="Study real spoken English"
          steps={[
            "Paste a few lines from a film, show, or a message someone sent you.",
            "You get the expressions explained — especially ones whose meaning isn't obvious.",
            "Add them to review to keep them.",
          ]}
        />
      )}

      {tab === "dialogue" ? (
        <DialogueStudio />
      ) : !data ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <CardSkeleton key={index} lines={3} />
          ))}
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setTopic("")}
              className={cx(
                "rounded-full px-3 py-1.5 text-sm transition",
                !topic
                  ? "bg-ink text-white"
                  : "bg-sunken text-ink-2 dark:bg-white/[0.05] dark:text-ink-3",
              )}
            >
              All
            </button>
            {(data.topics ?? []).map((item) => (
              <button
                key={item}
                onClick={() => setTopic(item)}
                className={cx(
                  "rounded-full px-3 py-1.5 text-sm transition",
                  topic === item
                    ? "bg-ink text-white"
                    : "bg-sunken text-ink-2 hover:bg-[color:var(--color-line)] dark:bg-white/[0.05] dark:text-ink-3",
                )}
              >
                {item}
              </button>
            ))}
            <div className="ml-auto">
              <Button variant="secondary" size="sm" onClick={refresh} loading={fetching}>
                Fetch latest
              </Button>
            </div>
          </div>

          {articles.length === 0 ? (
            <EmptyState
              icon="📰"
              title="No stories yet"
              body="Fetch the latest to pull in current news, or run: python manage.py ingest_content --seed"
              action={
                <Button onClick={refresh} loading={fetching}>
                  Fetch latest
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {articles.map((article) => (
                <ArticleCard
                  key={article.id}
                  article={article}
                  onPrepare={prepare}
                  preparing={preparing}
                  voice={voice}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
