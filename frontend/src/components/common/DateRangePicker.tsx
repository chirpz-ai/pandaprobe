"use client";

import { Input } from "@/components/ui/Input";

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onStartChange: (date: string) => void;
  onEndChange: (date: string) => void;
}

export function DateRangePicker({
  startDate,
  endDate,
  onStartChange,
  onEndChange,
}: DateRangePickerProps) {
  return (
    <div className="flex items-center gap-2">
      <Input
        type="datetime-local"
        value={startDate}
        onChange={(e) => onStartChange(e.target.value)}
        className="w-auto text-xs"
      />
      <span className="text-xs text-text-muted">to</span>
      <Input
        type="datetime-local"
        value={endDate}
        onChange={(e) => onEndChange(e.target.value)}
        className="w-auto text-xs"
      />
    </div>
  );
}
