"use client";

import { useState, useRef, useEffect, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils/cn";

interface TimeInputProps {
  value: string; // "HH:mm" 24-hour format
  onChange: (value: string) => void;
  className?: string;
}

function pad(n: number): string {
  return n.toString().padStart(2, "0");
}

function to12(h24: number): { h12: number; period: "AM" | "PM" } {
  const period: "AM" | "PM" = h24 >= 12 ? "PM" : "AM";
  let h12 = h24 % 12;
  if (h12 === 0) h12 = 12;
  return { h12, period };
}

function to24(h12: number, period: "AM" | "PM"): number {
  if (period === "AM") return h12 === 12 ? 0 : h12;
  return h12 === 12 ? 12 : h12 + 12;
}

function parseSegments(value: string): [number, number] {
  const [h, m] = value.split(":");
  return [parseInt(h, 10) || 0, parseInt(m, 10) || 0];
}

export function TimeInput({ value, onChange, className }: TimeInputProps) {
  const [hours24, minutes] = parseSegments(value);
  const { h12, period } = to12(hours24);

  const [hourText, setHourText] = useState(pad(h12));
  const [minuteText, setMinuteText] = useState(pad(minutes));

  const hourRef = useRef<HTMLInputElement>(null);
  const minuteRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (document.activeElement !== hourRef.current) setHourText(pad(h12));
  }, [h12]);

  useEffect(() => {
    if (document.activeElement !== minuteRef.current) setMinuteText(pad(minutes));
  }, [minutes]);

  function emit(h24: number, m: number) {
    onChange(`${pad(h24)}:${pad(m)}`);
  }

  function commitHour(raw: string) {
    const n = parseInt(raw, 10);
    if (isNaN(n) || raw === "") {
      setHourText(pad(h12));
      return;
    }
    const clamped = Math.max(1, Math.min(n, 12));
    setHourText(pad(clamped));
    emit(to24(clamped, period), minutes);
  }

  function commitMinute(raw: string) {
    const n = parseInt(raw, 10);
    if (isNaN(n) || raw === "") {
      setMinuteText(pad(minutes));
      return;
    }
    const clamped = Math.min(n, 59);
    setMinuteText(pad(clamped));
    emit(hours24, clamped);
  }

  function togglePeriod() {
    const newPeriod = period === "AM" ? "PM" : "AM";
    emit(to24(h12, newPeriod), minutes);
  }

  function handleHourKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") {
      commitHour(hourText);
      minuteRef.current?.focus();
    }
  }

  function handleMinuteKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") {
      commitMinute(minuteText);
    }
  }

  const segmentClasses =
    "w-7 bg-transparent text-center text-xs font-mono text-text outline-none selection:bg-primary/20";

  return (
    <div
      className={cn(
        "inline-flex items-center h-7 bg-surface border border-border px-1.5 gap-0.5",
        "focus-within:border-border-hi focus-within:ring-1 focus-within:ring-border-hi",
        "transition-colors duration-150",
        className,
      )}
    >
      <input
        ref={hourRef}
        type="text"
        inputMode="numeric"
        maxLength={2}
        value={hourText}
        onChange={(e) => setHourText(e.target.value.replace(/\D/g, "").slice(0, 2))}
        onBlur={() => commitHour(hourText)}
        onKeyDown={handleHourKeyDown}
        onFocus={(e) => e.target.select()}
        className={segmentClasses}
      />

      <span className="text-xs font-mono text-text-muted select-none">:</span>

      <input
        ref={minuteRef}
        type="text"
        inputMode="numeric"
        maxLength={2}
        value={minuteText}
        onChange={(e) => setMinuteText(e.target.value.replace(/\D/g, "").slice(0, 2))}
        onBlur={() => commitMinute(minuteText)}
        onKeyDown={handleMinuteKeyDown}
        onFocus={(e) => e.target.select()}
        className={segmentClasses}
      />

      <button
        type="button"
        tabIndex={-1}
        onClick={togglePeriod}
        className="ml-0.5 px-1 h-5 text-[10px] font-mono font-medium bg-surface-hi text-text-dim hover:text-text border border-border transition-colors select-none"
      >
        {period}
      </button>
    </div>
  );
}
