import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Match the custom font-size tokens in styles/typography.css so size overrides
// merge correctly without being mistaken for text colors.
const twMerge = extendTailwindMerge({
  extend: { theme: { text: ["caption", "compact"] } },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
