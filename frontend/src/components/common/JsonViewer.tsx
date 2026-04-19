"use client";

import { useState, useCallback } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface JsonViewerProps {
  data: unknown;
  className?: string;
  defaultExpanded?: boolean;
  maxInitialDepth?: number;
}

export function JsonViewer({
  data,
  className,
  defaultExpanded = true,
  maxInitialDepth = 3,
}: JsonViewerProps) {
  if (data == null) {
    return <span className="token-keyword text-xs font-mono">null</span>;
  }

  if (typeof data === "string") {
    return (
      <pre
        className={cn(
          "text-xs font-mono text-text-dim whitespace-pre-wrap break-words",
          className,
        )}
      >
        {data}
      </pre>
    );
  }

  return (
    <div className={cn("text-xs font-mono", className)}>
      <JsonNode
        value={data}
        depth={0}
        maxDepth={maxInitialDepth}
        defaultExpanded={defaultExpanded}
      />
    </div>
  );
}

function JsonNode({
  value,
  depth,
  maxDepth,
  defaultExpanded,
}: {
  value: unknown;
  depth: number;
  maxDepth: number;
  defaultExpanded: boolean;
}) {
  if (value === null) return <span className="token-keyword">null</span>;
  if (value === undefined)
    return <span className="token-keyword">undefined</span>;

  switch (typeof value) {
    case "string":
      return <JsonString value={value} />;
    case "number":
      return <span className="token-number">{value}</span>;
    case "boolean":
      return <span className="token-keyword">{String(value)}</span>;
    case "object":
      if (Array.isArray(value)) {
        return (
          <JsonArray
            items={value}
            depth={depth}
            maxDepth={maxDepth}
            defaultExpanded={defaultExpanded}
          />
        );
      }
      return (
        <JsonObject
          obj={value as Record<string, unknown>}
          depth={depth}
          maxDepth={maxDepth}
          defaultExpanded={defaultExpanded}
        />
      );
    default:
      return <span className="text-text-dim">{String(value)}</span>;
  }
}

const MAX_INLINE_STRING = 120;

function JsonString({ value }: { value: string }) {
  if (value.length <= MAX_INLINE_STRING) {
    return <span className="token-string">&quot;{value}&quot;</span>;
  }
  return (
    <span className="token-string">
      &quot;{value.slice(0, MAX_INLINE_STRING)}
      <span className="text-text-muted">…</span>
      &quot;
    </span>
  );
}

function JsonObject({
  obj,
  depth,
  maxDepth,
  defaultExpanded,
}: {
  obj: Record<string, unknown>;
  depth: number;
  maxDepth: number;
  defaultExpanded: boolean;
}) {
  const keys = Object.keys(obj);
  const [expanded, setExpanded] = useState(defaultExpanded && depth < maxDepth);
  const toggle = useCallback(() => setExpanded((e) => !e), []);

  if (keys.length === 0) {
    return <span className="token-punctuation">{"{}"}</span>;
  }

  if (!expanded) {
    return (
      <span>
        <CollapseToggle expanded={false} onClick={toggle} />
        <span className="token-punctuation">{"{ "}</span>
        <span className="text-text-muted">{keys.length} keys</span>
        <span className="token-punctuation">{" }"}</span>
      </span>
    );
  }

  return (
    <span>
      <CollapseToggle expanded onClick={toggle} />
      <span className="token-punctuation">{"{"}</span>
      <div className="ml-4 border-l border-border/50 pl-3">
        {keys.map((key, i) => (
          <div key={key} className="leading-5">
            <span className="token-param">&quot;{key}&quot;</span>
            <span className="token-punctuation">: </span>
            <JsonNode
              value={obj[key]}
              depth={depth + 1}
              maxDepth={maxDepth}
              defaultExpanded={defaultExpanded}
            />
            {i < keys.length - 1 && (
              <span className="token-punctuation">,</span>
            )}
          </div>
        ))}
      </div>
      <span className="token-punctuation">{"}"}</span>
    </span>
  );
}

function JsonArray({
  items,
  depth,
  maxDepth,
  defaultExpanded,
}: {
  items: unknown[];
  depth: number;
  maxDepth: number;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded && depth < maxDepth);
  const toggle = useCallback(() => setExpanded((e) => !e), []);

  if (items.length === 0) {
    return <span className="token-punctuation">{"[]"}</span>;
  }

  if (!expanded) {
    return (
      <span>
        <CollapseToggle expanded={false} onClick={toggle} />
        <span className="token-punctuation">{"[ "}</span>
        <span className="text-text-muted">{items.length} items</span>
        <span className="token-punctuation">{" ]"}</span>
      </span>
    );
  }

  return (
    <span>
      <CollapseToggle expanded onClick={toggle} />
      <span className="token-punctuation">{"["}</span>
      <div className="ml-4 border-l border-border/50 pl-3">
        {items.map((item, i) => (
          <div key={i} className="leading-5">
            <JsonNode
              value={item}
              depth={depth + 1}
              maxDepth={maxDepth}
              defaultExpanded={defaultExpanded}
            />
            {i < items.length - 1 && (
              <span className="token-punctuation">,</span>
            )}
          </div>
        ))}
      </div>
      <span className="token-punctuation">{"]"}</span>
    </span>
  );
}

function CollapseToggle({
  expanded,
  onClick,
}: {
  expanded: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center justify-center w-4 h-4 ml-0 mr-0 text-text-muted hover:text-text transition-colors align-middle"
    >
      {expanded ? (
        <ChevronDown className="h-3 w-3" />
      ) : (
        <ChevronRight className="h-3 w-3" />
      )}
    </button>
  );
}
