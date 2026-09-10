import { Toaster as Sonner } from "sonner";

/**
 * Toasts, themed from our own tokens.
 *
 * The generated version read the active theme from next-themes and drew its
 * own icons from lucide. This app already carries the theme as a `dark` class
 * on <html>, and `theme="system"` lets sonner follow the same signal without a
 * second source of truth to keep in sync.
 */
const Toaster = ({ ...props }) => (
  <Sonner
    theme="system"
    className="toaster group"
    toastOptions={{
      classNames: {
        toast:
          "group toast flex gap-3 rounded-xl bg-surface p-4 text-sm text-ink " +
          "shadow-lg ring-1 ring-[color:var(--color-line)]",
        description: "text-ink-3 text-[13px]",
        actionButton: "bg-ink text-white dark:bg-white dark:text-black rounded-full px-3 py-1",
        cancelButton: "text-ink-3",
        error: "text-[color:var(--color-accent)]",
      },
    }}
    style={{ "--normal-bg": "var(--color-surface)", "--normal-text": "var(--color-ink)" }}
    {...props}
  />
);

export { Toaster };
