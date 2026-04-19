"use client";

import { useState, useCallback } from "react";
import * as Popover from "@radix-ui/react-popover";
import { CalendarDays } from "lucide-react";
import { format, parse, isValid } from "date-fns";
import { Calendar } from "@/components/ui/Calendar";
import { TimeInput } from "@/components/ui/TimeInput";
import { cn } from "@/lib/utils/cn";

interface DateTimePickerProps {
  /** datetime-local format string (YYYY-MM-DDTHH:mm) or empty */
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

function toDate(value: string): Date | undefined {
  if (!value) return undefined;
  const d = new Date(value);
  return isValid(d) ? d : undefined;
}

function toDatetimeLocal(date: Date): string {
  return format(date, "yyyy-MM-dd'T'HH:mm");
}

export function DateTimePicker({
  value,
  onChange,
  placeholder = "Pick date",
  className,
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);
  const selected = toDate(value);

  const timeValue = selected ? format(selected, "HH:mm") : "";

  const handleDaySelect = useCallback(
    (day: Date | undefined) => {
      if (!day) return;
      const existing = selected ?? new Date();
      const merged = new Date(day);
      merged.setHours(existing.getHours(), existing.getMinutes(), 0, 0);
      onChange(toDatetimeLocal(merged));
    },
    [selected, onChange],
  );

  const handleTimeChange = useCallback(
    (time: string) => {
      const base = selected ?? new Date();
      const parsed = parse(time, "HH:mm", base);
      if (isValid(parsed)) {
        onChange(toDatetimeLocal(parsed));
      }
    },
    [selected, onChange],
  );

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className={cn(
            "flex h-9 items-center gap-2 bg-surface px-3 py-1 text-xs font-mono border border-border",
            "text-text hover:bg-surface-hi transition-colors duration-150",
            "focus-visible:outline-none focus-visible:border-border-hi focus-visible:ring-1 focus-visible:ring-border-hi",
            !value && "text-text-muted",
            className,
          )}
        >
          <CalendarDays className="h-3.5 w-3.5 text-text-dim flex-shrink-0" />
          {selected ? format(selected, "MMM d, yyyy  HH:mm") : placeholder}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={4}
          className="z-50 bg-surface border border-border shadow-md animate-fade-in"
        >
          <Calendar
            mode="single"
            selected={selected}
            onSelect={handleDaySelect}
            defaultMonth={selected}
          />
          <div className="border-t border-border px-3 py-2 flex items-center gap-2">
            <span className="text-[10px] text-text-muted font-mono uppercase tracking-wide">
              Time
            </span>
            <TimeInput
              value={timeValue || "00:00"}
              onChange={handleTimeChange}
            />
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
