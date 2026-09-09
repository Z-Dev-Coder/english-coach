import { useState } from "react";

import { api, setToken } from "../lib/api";
import Icon from "../lib/icons";
import { Button, ErrorNote, Field, Input } from "../lib/ui";

const HIGHLIGHTS = [
  {
    n: "01",
    title: "Built around your weak spots",
    body: "Eight skills tracked separately. Read at B2 but speak at A2? You get A2 speaking practice, not B1 everything.",
  },
  {
    n: "02",
    title: "Speaking scripts you can take anywhere",
    body: "Roleplay here, or copy the prompt into ChatGPT or Gemini and practise there.",
  },
  {
    n: "03",
    title: "Runs on your machine",
    body: "Local AI models. No subscription, no API bills, nothing leaves your computer.",
  },
];

export default function Login({ dark, onToggleTheme, onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "login"
          ? await api.login(username, password)
          : await api.register({ username, password });
      setToken(result.token);
      onAuthenticated(result.username);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      {/* Marketing panel. Hidden on small screens, where it would just push the
          form below the fold. */}
      <section className="relative hidden overflow-hidden bg-ink p-12 text-white lg:flex lg:flex-col lg:justify-center">

        <div className="relative max-w-md">
          <div className="mb-8 flex items-center gap-3">
            <span className="grid h-8 w-8 place-items-center rounded-md bg-white font-mono text-[11px] font-bold text-ink">
              EC
            </span>
            <span className="text-[15px] font-semibold tracking-tight">English Coach</span>
          </div>

          <h1 className="display text-[46px]">
            Real English, turned into your{" "}
            <span className="text-[color:var(--color-accent)]">daily plan</span>.
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-white/55">
            Not flashcards. A coach that measures what you struggle with and decides what you
            practise next.
          </p>

          <ul className="mt-12 space-y-5">
            {HIGHLIGHTS.map((item) => (
              <li key={item.title} className="flex gap-4 border-t border-white/12 pt-5">
                <span className="micro shrink-0 pt-0.5 text-white/35">{item.n}</span>
                <div>
                  <p className="text-[15px] font-medium">{item.title}</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-white/50">{item.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Form panel */}
      <section className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 flex items-center justify-between lg:hidden">
            <div className="flex items-center gap-2.5">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-ink font-mono text-[11px] font-bold text-white dark:bg-white dark:text-black">
                EC
              </span>
              <span className="font-semibold tracking-tight">English Coach</span>
            </div>
            <button
              onClick={onToggleTheme}
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
              className="grid h-9 w-9 place-items-center rounded-xl text-ink-3 hover:bg-sunken dark:hover:bg-white/[0.06]"
            >
              <Icon name={dark ? "sun" : "moon"} size={16} />
            </button>
          </div>

          <h2 className="display text-[30px]">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="mt-1.5 mb-8 text-sm text-ink-2 dark:text-white/55">
            {mode === "login"
              ? "Pick up where you left off."
              : "Takes a few seconds. Your profile builds itself as you practise."}
          </p>

          <form onSubmit={submit} className="space-y-4">
            <Field label="Username">
              <Input
                placeholder="you"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </Field>
            <Field
              label="Password"
              hint={mode === "register" ? "at least 8 characters" : undefined}
            >
              <Input
                type="password"
                placeholder="••••••••"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </Field>

            <ErrorNote error={error} />

            <Button type="submit" size="lg" loading={busy} className="w-full">
              {busy ? "Please wait" : mode === "login" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-2 dark:text-white/55">
            {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="font-medium text-ink underline underline-offset-4 dark:text-white"
            >
              {mode === "login" ? "Sign up" : "Sign in"}
            </button>
          </p>
        </div>
      </section>
    </div>
  );
}
