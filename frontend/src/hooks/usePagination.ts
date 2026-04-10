"use client";

import { useState, useCallback, useMemo } from "react";
import { DEFAULT_PAGE_SIZE } from "@/lib/utils/constants";

interface UsePaginationResult {
  limit: number;
  offset: number;
  page: number;
  setPage: (page: number) => void;
  setLimit: (limit: number) => void;
  totalPages: (total: number) => number;
  reset: () => void;
}

export function usePagination(
  initialLimit = DEFAULT_PAGE_SIZE
): UsePaginationResult {
  const [limit, setLimitState] = useState(initialLimit);
  const [page, setPageState] = useState(1);

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);

  const setPage = useCallback((p: number) => {
    setPageState(Math.max(1, p));
  }, []);

  const setLimit = useCallback((l: number) => {
    setLimitState(l);
    setPageState(1);
  }, []);

  const totalPages = useCallback(
    (total: number) => Math.max(1, Math.ceil(total / limit)),
    [limit]
  );

  const reset = useCallback(() => {
    setPageState(1);
  }, []);

  return { limit, offset, page, setPage, setLimit, totalPages, reset };
}
