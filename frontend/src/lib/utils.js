import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Class merge used by the shadcn components.
 *
 * Distinct from our own `cx`: this one resolves Tailwind conflicts, so a
 * variant's `px-4` can be overridden by a caller's `px-2` instead of both
 * landing in the class list and the later one winning by stylesheet order.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
