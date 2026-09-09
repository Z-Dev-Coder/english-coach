import { useState } from "react";

import { api, setToken } from "../lib/api";
import { Button, Card, ErrorNote } from "../lib/ui";

export default function Login({ onAuthenticated }) {
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

  const field =
    "w-full rounded-xl border-0 bg-slate-50 px-3.5 py-3 text-sm ring-1 ring-slate-200 focus:ring-2 focus:ring-indigo-500";

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <h1 className="text-2xl font-bold tracking-tight">English Coach</h1>
        <p className="mt-1 mb-6 text-sm text-slate-500">
          {mode === "login"
            ? "Welcome back. Let's keep going."
            : "Set up your learner profile in a few seconds."}
        </p>

        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="sr-only">Username</span>
            <input
              className={field}
              placeholder="Username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>
          <label className="block">
            <span className="sr-only">Password</span>
            <input
              className={field}
              type="password"
              placeholder="Password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          <ErrorNote error={error} />

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>

        <button
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="mt-4 w-full text-sm text-slate-500 hover:text-indigo-600"
        >
          {mode === "login" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </Card>
    </div>
  );
}
