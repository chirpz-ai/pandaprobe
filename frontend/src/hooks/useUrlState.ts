"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

type ParamConfig = Record<string, { default: string }>;

/**
 * Synchronises component filter/pagination state with URL search parameters.
 * Each key in `config` maps to a search param; default values are omitted from the URL.
 */
export function useUrlState<T extends ParamConfig>(config: T) {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const values = useMemo(() => {
    const result = {} as { [K in keyof T]: string };
    for (const key of Object.keys(config) as Array<keyof T & string>) {
      result[key] = searchParams.get(key) ?? config[key].default;
    }
    return result;
  }, [searchParams, config]);

  const set = useCallback(
    (updates: Partial<{ [K in keyof T]: string }>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, val] of Object.entries(updates)) {
        if (val === undefined || val === config[key as keyof T]?.default) {
          params.delete(key);
        } else {
          params.set(key, val as string);
        }
      }
      const qs = params.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [searchParams, pathname, router, config],
  );

  const page = parseInt(values.page as string, 10) || 1;
  const limit = parseInt(values.limit as string, 10) || 50;
  const offset = (page - 1) * limit;

  const setPage = useCallback(
    (p: number) =>
      set({ page: String(Math.max(1, p)) } as Partial<{
        [K in keyof T]: string;
      }>),
    [set],
  );

  const resetPage = useCallback(
    () => set({ page: "1" } as Partial<{ [K in keyof T]: string }>),
    [set],
  );

  const totalPages = useCallback(
    (total: number) => Math.max(1, Math.ceil(total / limit)),
    [limit],
  );

  return { values, set, page, limit, offset, setPage, resetPage, totalPages };
}
