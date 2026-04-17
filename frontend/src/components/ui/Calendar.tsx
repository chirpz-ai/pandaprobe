"use client";

import { DayPicker, type DayPickerProps } from "react-day-picker";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export type CalendarProps = DayPickerProps;

export function Calendar({ className, classNames, ...props }: CalendarProps) {
  return (
    <DayPicker
      className={cn("p-3 font-mono", className)}
      classNames={{
        months: "flex flex-col sm:flex-row gap-2",
        month: "flex flex-col gap-3",
        month_caption: "flex justify-center items-center h-7",
        caption_label: "text-xs font-mono text-text",
        nav: "flex items-center gap-1",
        button_previous:
          "absolute left-1 top-3 h-7 w-7 inline-flex items-center justify-center text-text-dim hover:text-text hover:bg-surface-hi transition-colors",
        button_next:
          "absolute right-1 top-3 h-7 w-7 inline-flex items-center justify-center text-text-dim hover:text-text hover:bg-surface-hi transition-colors",
        month_grid: "border-collapse",
        weekdays: "flex",
        weekday: "w-8 text-[10px] font-mono text-text-muted text-center",
        week: "flex mt-0.5",
        day: "relative p-0 text-center",
        day_button:
          "h-8 w-8 text-xs font-mono text-text-dim hover:bg-surface-hi hover:text-text transition-colors inline-flex items-center justify-center",
        selected: "!bg-primary !text-bg hover:!bg-accent",
        today: "text-accent font-bold",
        outside: "text-text-muted/40",
        disabled: "text-text-muted/30 pointer-events-none",
        hidden: "invisible",
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation }) =>
          orientation === "left" ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          ),
      }}
      {...props}
    />
  );
}
