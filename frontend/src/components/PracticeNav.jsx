import { Link, useLocation, useSearchParams } from "react-router-dom";

import { cx } from "../lib/cx";

/**
 * Sub-navigation for the practice family.
 *
 * Speaking and Conversation used to be top-level entries called "Speaking" and
 * "Talk", which meant the main nav had eight items and two of them sounded like
 * the same thing. They are all skill practice, so they live under one heading
 * and the top nav drops to six.
 */
const TABS = [
  { label: "Listening", to: "/practice?tab=listening", match: ["listening"] },
  { label: "Reading", to: "/practice?tab=reading", match: ["reading"] },
  { label: "Writing", to: "/practice?tab=writing", match: ["writing"] },
  { label: "Speaking", to: "/speaking" },
  { label: "Talk", to: "/conversation" },
  { label: "Drill", to: "/drill" },
];

export default function PracticeNav() {
  const location = useLocation();
  const [params] = useSearchParams();
  const tab = params.get("tab") || "listening";

  const isActive = (item) => {
    const [path] = item.to.split("?");
    if (path !== location.pathname) return false;
    return item.match ? item.match.includes(tab) : true;
  };

  return (
    <nav
      aria-label="Practice activities"
      className="-mx-1 flex gap-1 overflow-x-auto pb-1"
    >
      {TABS.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={cx(
            "shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium transition",
            isActive(item)
              ? "bg-ink text-white dark:bg-white dark:text-ink"
              : "text-ink-2 hover:bg-sunken dark:text-ink-3 dark:hover:bg-white/[0.06]",
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
