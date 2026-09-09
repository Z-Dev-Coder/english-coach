/** Dark mode: OS preference by default, overridable and remembered.
 *
 *  Applied by toggling a class on <html> (see the @custom-variant in
 *  index.css) rather than by re-rendering a provider, so the whole document —
 *  including the page background — flips in one paint. */

const KEY = "english-coach-theme";

export function storedTheme() {
  return localStorage.getItem(KEY); // "light" | "dark" | null (= follow OS)
}

export function prefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

// Dark is this app's default presentation, not merely the OS preference.
// Someone who wants light can still choose it, and that choice sticks.
export function isDark() {
  const stored = storedTheme();
  return stored ? stored === "dark" : true;
}

export function applyTheme(dark) {
  document.documentElement.classList.toggle("dark", dark);
}

export function setTheme(dark) {
  localStorage.setItem(KEY, dark ? "dark" : "light");
  applyTheme(dark);
}
