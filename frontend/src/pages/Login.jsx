import { useState } from "react";

import { api, setToken } from "../lib/api";
import { Button, ErrorNote, Field, Input } from "../lib/ui";

const HIGHLIGHTS = [
  {
    icon: "🎯",
    title: "Built around your weak spots",
    body: "Eight skills tracked separately. Read at B2 but speak at A2? You get A2 speaking practice, not B1 everything.",
  },
  {
    icon: "🗣️",
    title: "Speaking scripts you can take anywhere",
    body: "Roleplay here, or copy the prompt into ChatGPT or Gemini and practise there.",
  },
  {
    icon: "🔒",
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
      <section className="relative hidden overflow-hidden bg-gradient-to-br from-brand-600 via-brand-700 to-violet-700 p-12 text-white lg:flex lg:flex-col lg:justify-center">
        <div
          aria-hidden="true"
          className="absolute -top-24 -right-24 h-96 w-96 rounded-full bg-white/10 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-violet-400/20 blur-3xl"
        />

        <div className="relative max-w-md">
          <div className="mb-8 flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-white/15 text-xl backdrop-blur">
              <span aria-hidden="true">🎓</span>
            </span>
            <span className="text-lg font-bold tracking-tight">English Coach</span>
          </div>

          <h1 className="text-4xl font-bold leading-tight tracking-tight">
            Real English, turned into your daily plan.
          </h1>
          <p className="mt-4 text-white/70">
            Not flashcards. A coach that measures what you struggle with and decides what you
            practise next.
          </p>

          <ul className="mt-10 space-y-6">
            {HIGHLIGHTS.map((item) => (
              <li key={item.title} className="flex gap-4">
                <span
                  aria-hidden="true"
                  className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/10 text-lg backdrop-blur"
                >
                  {item.icon}
                </span>
                <div>
                  <p className="font-semibold">{item.title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-white/65">{item.body}</p>
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
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-lg">
                <span aria-hidden="true">🎓</span>
              </span>
              <span className="font-bold tracking-tight">English Coach</span>
            </div>
            <button
              onClick={onToggleTheme}
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
              className="grid h-9 w-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <span aria-hidden="true">{dark ? "☀️" : "🌙"}</span>
            </button>
          </div>

          <h2 className="text-2xl font-bold tracking-tight">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="mt-1.5 mb-8 text-sm text-slate-500 dark:text-slate-400">
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

          <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
            {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
            <button
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="font-semibold text-brand-600 hover:underline dark:text-brand-300"
            >
              {mode === "login" ? "Sign up" : "Sign in"}
            </button>
          </p>
        </div>
      </section>
    </div>
  );
}
