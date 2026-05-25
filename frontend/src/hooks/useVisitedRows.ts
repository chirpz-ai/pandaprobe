"use client";

import { useCallback, useEffect, useState } from "react";

interface LastVisitedState {
  id: string;
  page: string;
}

/**
 * Tracks the single most-recently-opened table row so it can be
 * highlighted when the user navigates back to the list view.
 *
 * The entry is read once on mount and immediately cleared from
 * sessionStorage, so the highlight only appears when returning
 * from the detail view — not when arriving from unrelated pages.
 */
export function useLastVisitedRow(storageKey: string) {
  const [state] = useState<LastVisitedState | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const raw = sessionStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    try {
      sessionStorage.removeItem(storageKey);
    } catch {}
  }, [storageKey]);

  const markVisited = useCallback(
    (id: string, page: string) => {
      try {
        sessionStorage.setItem(storageKey, JSON.stringify({ id, page }));
      } catch {}
    },
    [storageKey],
  );

  return {
    lastVisited: state?.id ?? null,
    restoredPage: state?.page ?? null,
    markVisited,
  };
}
