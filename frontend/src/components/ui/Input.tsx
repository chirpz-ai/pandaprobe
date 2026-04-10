"use client";

import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils/cn";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full bg-surface px-3 py-1 text-sm font-mono text-text border border-border",
          "placeholder:text-text-muted",
          "focus-visible:outline-none focus-visible:border-border-hi focus-visible:ring-1 focus-visible:ring-border-hi",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "transition-colors duration-150",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
