import { useEffect, useState } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { api, getToken, setToken } from "./lib/api";
import { applyTheme, isDark, setTheme } from "./lib/theme";
import { cx } from "./lib/cx";
import Icon from "./lib/icons";
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

// Six entries, not eight. Speaking and Conversation were separate top-level
// items called "Speaking" and "Talk" — two names for the same idea. They now
// sit under Practice, which is where the rest of the skill work already lives.
const NAV = [
  { to: "/", label: "Home", icon: "home" },
  { to: "/review", label: "Review", icon: "review" },
  { to: "/practice", label: "Practice", icon: "practice", family: ["/speaking", "/conversation", "/drill"] },
  { to: "/real-world", label: "Real World", icon: "world" },
  { to: "/progress", label: "Progress", icon: "progress" },
  { to: "/profile", label: "Profile", icon: "profile" },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-7 w-7 place-items-center rounded-md bg-ink font-mono text-[11px] font-bold text-white dark:bg-white dark:text-ink">
        EC
      </span>
      <span className="text-[14px] font-semibold tracking-tight">English Coach</span>
    </div>
  );
}

function ThemeToggle({ dark, onToggle }) {
  return (
    <button
      onClick={onToggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
      className="grid h-9 w-9 place-items-center rounded-xl text-ink-2 transition hover:bg-sunken dark:text-ink-3 dark:hover:bg-white/[0.06]"
    >
      <Icon name={dark ? "sun" : "moon"} size={16} />
    </button>
  );
}

/** Desktop: a persistent left rail. Mobile: a fixed bottom tab bar, which is
 *  where thumbs actually are — a horizontally scrolling top nav is the classic
 *  "desktop layout shrunk down" mistake. */
function Shell({ dark, onToggleTheme, onSignOut, children }) {
  const location = useLocation();
  const inFamily = (item) => (item.family || []).includes(location.pathname);

  const railLink = ({ isActive }) =>
    cx(
      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition duration-150",
      isActive
        ? "bg-ink text-white dark:bg-white dark:text-ink"
        : "text-ink-2 hover:bg-sunken dark:text-white/60 dark:hover:bg-white/[0.06]",
    );

  const tabLink = ({ isActive }) =>
    cx(
      "flex flex-1 flex-col items-center gap-0.5 rounded-xl py-2 text-[11px] font-medium transition",
      isActive ? "text-ink dark:text-white" : "text-ink-3 dark:text-white/40",
    );

  return (
    <div className="mx-auto flex min-h-full w-full max-w-6xl gap-6 px-4 md:px-6">
      {/* Desktop rail */}
      <aside className="sticky top-0 hidden h-screen w-48 shrink-0 flex-col py-5 md:flex">
        <div className="mb-6 flex items-center justify-between pl-1">
          <Brand />
          <ThemeToggle dark={dark} onToggle={onToggleTheme} />
        </div>

        <nav aria-label="Main" className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => railLink({ isActive: isActive || inFamily(item) })}
            >
              <Icon name={item.icon} size={17} />
              {item.label}
            </NavLink>
          ))}

        </nav>

        <button
          onClick={onSignOut}
          className="mt-auto rounded-xl px-3 py-2.5 text-left text-sm text-ink-3 transition hover:bg-sunken hover:text-ink-2 dark:hover:bg-white/[0.06] dark:hover:text-ink-3"
        >
          Sign out
        </button>
      </aside>

      {/* Mobile top bar */}
      <header className="fixed inset-x-0 top-0 z-20 flex items-center justify-between border-b border-[color:var(--color-line)]/70 bg-sunken/85 px-4 py-3 backdrop-blur-md md:hidden dark:border-white/10 dark:bg-slate-950/85">
        <Brand />
        <div className="flex items-center gap-1">
          <ThemeToggle dark={dark} onToggle={onToggleTheme} />
          <button
            onClick={onSignOut}
            className="rounded-xl px-3 py-2 text-sm text-ink-3 transition hover:text-ink-2 dark:hover:text-ink-3"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="min-w-0 flex-1 pt-16 pb-24 md:py-5 md:pb-12">{children}</main>

      {/* Mobile bottom tabs */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 flex gap-1 border-t border-[color:var(--color-line)]/70 bg-white/90 px-3 pt-1 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-md md:hidden dark:border-white/10 dark:bg-white/[0.03]/90"
      >
        {/* Five tabs is the practical maximum on a phone; the rest stay
            reachable from the desktop rail and by URL. */}
        {NAV.filter((item) => item.to !== "/profile").map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => tabLink({ isActive: isActive || inFamily(item) })}
          >
            <Icon name={item.icon} size={18} />
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
          className="h-6 w-6 animate-spin rounded-full border-2 border-[color:var(--color-line)] border-t-brand-600"
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
