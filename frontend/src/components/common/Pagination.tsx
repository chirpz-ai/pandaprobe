"use client";

import { Button } from "@/components/ui/Button";
import { ChevronLeft, ChevronRight } from "lucide-react";

const LIMIT_OPTIONS = [50, 100, 200] as const;

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  total?: number;
  limit?: number;
  onLimitChange?: (limit: number) => void;
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
  total,
  limit,
  onLimitChange,
}: PaginationProps) {
  return (
    <div className="flex items-center justify-between pt-3 flex-shrink-0">
      <span className="text-xs text-text-muted font-mono">
        {total != null ? `${total} total` : ""}
      </span>
      <div className="flex items-center gap-3">
        {limit != null && onLimitChange && (
          <div className="flex items-center gap-1.5">
            <div className="flex items-center gap-0.5">
              {LIMIT_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => onLimitChange(opt)}
                  className={`px-1.5 py-0.5 text-[10px] font-mono transition-colors ${
                    limit === opt
                      ? "text-primary bg-primary/10"
                      : "text-text-muted hover:text-text"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeft className="h-3 w-3" />
          </Button>
          <span className="text-xs font-mono text-text-dim">
            {page} / {totalPages}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
          >
            <ChevronRight className="h-3 w-3" />
          </Button>
        </div>
      </div>
    </div>
  );
}
