import { useEffect, useState } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";

import { api, getToken, setToken } from "./lib/api";
import { applyTheme, isDark, setTheme } from "./lib/theme";
import { cx } from "./lib/cx";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Conversation from "./pages/Conversation";
import Practice from "./pages/Practice";
import Profile from "./pages/Profile";
import Progress from "./pages/Progress";
import RealWorld from "./pages/RealWorld";
import Review from "./pages/Review";
import Drill from "./pages/Drill";
import SpeakingStudio from "./pages/SpeakingStudio";

const NAV = [
  { to: "/", label: "Home", icon: "🏠" },
  { to: "/review", label: "Review", icon: "🔁" },
  { to: "/practice", label: "Practice", icon: "🎧" },
  { to: "/real-world", label: "Real World", icon: "🌍" },
  { to: "/conversation", label: "Talk", icon: "💬" },
  { to: "/speaking", label: "Speaking", icon: "🗣️" },
  { to: "/progress", label: "Progress", icon: "📈" },
  { to: "/profile", label: "Profile", icon: "👤" },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-lg shadow-sm">
        <span aria-hidden="true">🎓</span>
      </span>
      <span className="text-[15px] font-bold tracking-tight">English Coach</span>
    </div>
  );
}

function ThemeToggle({ dark, onToggle }) {
  return (
    <button
      onClick={onToggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
      className="grid h-9 w-9 place-items-center rounded-xl text-slate-500 transition hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
    >
      <span aria-hidden="true">{dark ? "☀️" : "🌙"}</span>
    </button>
  );
}

/** Desktop: a persistent left rail. Mobile: a fixed bottom tab bar, which is
 *  where thumbs actually are — a horizontally scrolling top nav is the classic
 *  "desktop layout shrunk down" mistake. */
function Shell({ dark, onToggleTheme, onSignOut, children }) {
  const railLink = ({ isActive }) =>
    cx(
      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition duration-150",
      isActive
        ? "bg-brand-600 text-white shadow-sm"
        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
    );

  const tabLink = ({ isActive }) =>
    cx(
      "flex flex-1 flex-col items-center gap-0.5 rounded-xl py-2 text-[11px] font-medium transition",
      isActive
        ? "text-brand-600 dark:text-brand-300"
        : "text-slate-400 dark:text-slate-500",
    );

  return (
    <div className="mx-auto flex min-h-full w-full max-w-6xl gap-6 px-4 md:px-6">
      {/* Desktop rail */}
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col py-6 md:flex">
        <div className="mb-6 flex items-center justify-between pl-1">
          <Brand />
          <ThemeToggle dark={dark} onToggle={onToggleTheme} />
        </div>

        <nav aria-label="Main" className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={railLink} end={item.to === "/"}>
              <span aria-hidden="true" className="text-base">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}

        </nav>

        <button
          onClick={onSignOut}
          className="mt-auto rounded-xl px-3 py-2.5 text-left text-sm text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
        >
          Sign out
        </button>
      </aside>

      {/* Mobile top bar */}
      <header className="fixed inset-x-0 top-0 z-20 flex items-center justify-between border-b border-slate-200/70 bg-slate-50/85 px-4 py-3 backdrop-blur-md md:hidden dark:border-white/10 dark:bg-slate-950/85">
        <Brand />
        <div className="flex items-center gap-1">
          <ThemeToggle dark={dark} onToggle={onToggleTheme} />
          <button
            onClick={onSignOut}
            className="rounded-xl px-3 py-2 text-sm text-slate-400 transition hover:text-slate-600 dark:hover:text-slate-300"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="min-w-0 flex-1 pt-20 pb-28 md:py-8 md:pb-16">{children}</main>

      {/* Mobile bottom tabs */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 flex gap-1 border-t border-slate-200/70 bg-white/90 px-3 pt-1 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-md md:hidden dark:border-white/10 dark:bg-slate-900/90"
      >
        {/* Five tabs is the practical maximum on a phone; the rest stay
            reachable from the desktop rail and by URL. */}
        {NAV.filter((item) => item.to !== "/speaking" && item.to !== "/profile")
          .slice(0, 5)
          .map((item) => (
            <NavLink key={item.to} to={item.to} className={tabLink} end={item.to === "/"}>
              <span aria-hidden="true" className="text-lg">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
      </nav>
    </div>
  );
}

export default function App() {
  // "checking" until a stored token has been verified: a token in localStorage
  // may be stale or revoked, and rendering the app around one produces a shell
  // where every request fails.
  const [authState, setAuthState] = useState(() => (getToken() ? "checking" : "anonymous"));
  const [dark, setDark] = useState(isDark);

  // The class lives on <html>, outside React's tree, so it is synced here.
  useEffect(() => {
    applyTheme(dark);
  }, [dark]);

  useEffect(() => {
    if (authState !== "checking") return;
    let cancelled = false;
    api
      .me()
      .then(() => !cancelled && setAuthState("authenticated"))
      .catch(() => !cancelled && setAuthState("anonymous"));
    return () => {
      cancelled = true;
    };
  }, [authState]);

  // Any 401 anywhere in the app drops us back to the login screen.
  useEffect(() => {
    const onSignedOut = () => setAuthState("anonymous");
    window.addEventListener("english-coach:signed-out", onSignedOut);
    return () => window.removeEventListener("english-coach:signed-out", onSignedOut);
  }, []);

  const toggleTheme = () => {
    setDark((previous) => {
      setTheme(!previous);
      return !previous;
    });
  };

  if (authState === "checking") {
    return (
      <div className="grid min-h-full place-items-center">
        <span
          aria-label="Signing you in"
          role="status"
          className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600"
        />
      </div>
    );
  }

  if (authState === "anonymous") {
    return (
      <Login
        dark={dark}
        onToggleTheme={toggleTheme}
        onAuthenticated={() => setAuthState("authenticated")}
      />
    );
  }

  const signOut = async () => {
    // Revoke server-side first so the token cannot be reused, but sign out
    // locally regardless -- a failed request must never trap someone signed in.
    try {
      await api.logout();
    } catch {
      /* already invalid, or offline */
    }
    setToken(null);
    setAuthState("anonymous");
  };

  return (
    <BrowserRouter>
      <Shell dark={dark} onToggleTheme={toggleTheme} onSignOut={signOut}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/review" element={<Review />} />
          <Route path="/practice" element={<Practice />} />
          <Route path="/drill" element={<Drill />} />
          <Route path="/real-world" element={<RealWorld />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/conversation" element={<Conversation />} />
          <Route path="/speaking" element={<SpeakingStudio />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
