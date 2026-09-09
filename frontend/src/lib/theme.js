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

export function isDark() {
  const stored = storedTheme();
  return stored ? stored === "dark" : prefersDark();
}

export function applyTheme(dark) {
  document.documentElement.classList.toggle("dark", dark);
}

export function setTheme(dark) {
  localStorage.setItem(KEY, dark ? "dark" : "light");
  applyTheme(dark);
}
