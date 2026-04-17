"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/utils/cn";

interface DebouncedInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  debounceMs?: number;
}

export function DebouncedInput({
  value,
  onChange,
  placeholder,
  className,
  debounceMs = 500,
}: DebouncedInputProps) {
  const [local, setLocal] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    setLocal(value);
  }, [value]);

  const handleChange = useCallback(
    (v: string) => {
      setLocal(v);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onChangeRef.current(v), debounceMs);
    },
    [debounceMs],
  );

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  return (
    <Input
      value={local}
      onChange={(e) => handleChange(e.target.value)}
      placeholder={placeholder}
      className={cn("text-xs", className)}
    />
  );
}
