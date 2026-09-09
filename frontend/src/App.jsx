import { useState } from "react";
import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";

import { getToken, setToken } from "./lib/api";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Profile from "./pages/Profile";
import SpeakingStudio from "./pages/SpeakingStudio";

// Phase 1 ships Home, Speaking and Profile. Review / Real World / Progress are
// shown as disabled links so the information architecture is visible from the
// start and later phases slot in without a navigation redesign.
const NAV = [
  { to: "/", label: "Home", icon: "🏠" },
  { to: "/speaking", label: "Speaking", icon: "🗣️" },
  { to: "/profile", label: "Profile", icon: "👤" },
];

const COMING_SOON = [
  { label: "Review", icon: "🔁" },
  { label: "Real World", icon: "🌍" },
  { label: "Progress", icon: "📈" },
];

function Shell({ onSignOut, children }) {
  const linkClass = ({ isActive }) =>
    `flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
      isActive ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
    }`;

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 p-4 md:flex-row md:p-6">
      <nav className="md:w-52 md:shrink-0" aria-label="Main">
        <div className="mb-4 hidden px-3 md:block">
          <span className="text-lg font-bold tracking-tight">English Coach</span>
        </div>
        <div className="flex gap-1.5 overflow-x-auto md:flex-col">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={linkClass} end={item.to === "/"}>
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
          {COMING_SOON.map((item) => (
            <span
              key={item.label}
              title="Coming in a later phase"
              className="flex cursor-not-allowed items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-300"
            >
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
            </span>
          ))}
        </div>
        <button
          onClick={onSignOut}
          className="mt-4 hidden px-3 text-sm text-slate-400 hover:text-slate-600 md:block"
        >
          Sign out
        </button>
      </nav>
      <main className="min-w-0 flex-1 pb-10">{children}</main>
    </div>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(getToken()));

  if (!authenticated) return <Login onAuthenticated={() => setAuthenticated(true)} />;

  const signOut = () => {
    setToken(null);
    setAuthenticated(false);
  };

  return (
    <BrowserRouter>
      <Shell onSignOut={signOut}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/speaking" element={<SpeakingStudio />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
