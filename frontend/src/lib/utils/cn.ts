import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Keep custom typography and radius tokens in sync with styles/*.css so
// component overrides merge in the correct Tailwind class groups.
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: ["caption", "compact"],
      radius: ["control", "panel"],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
