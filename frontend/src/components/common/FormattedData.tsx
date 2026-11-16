"use client";

import { Fragment, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { JsonViewer } from "./JsonViewer";
import { cn } from "@/lib/utils/cn";

interface FormattedDataProps {
  data: unknown;
  className?: string;
}

/** Readable, lossless cards for arbitrary JSON and common chat-message payloads. */
export function FormattedData({ data, className }: FormattedDataProps) {
  return (
    <div
      className={cn(
        "ph-no-capture min-w-0 font-sans text-sm text-text leading-relaxed [overflow-wrap:anywhere]",
        className,
      )}
    >
      <Value data={data} depth={0} />
    </div>
  );
}

function isRecord(data: unknown): data is Record<string, unknown> {
  return data !== null && typeof data === "object" && !Array.isArray(data);
}

function messageRole(data: Record<string, unknown>): string | null {
  if (typeof data.role === "string") return data.role;
  if (
    typeof data.type === "string" &&
    ["human", "ai", "system", "tool", "function"].includes(data.type)
  )
    return data.type;
  return null;
}

function Value({ data, depth }: { data: unknown; depth: number }) {
  if (data == null)
    return <p className="text-xs text-text-muted">No content</p>;
  if (typeof data === "string") {
    if (data === "")
      return <p className="text-xs text-text-muted">Empty string</p>;
    // Tool outputs are often serialized JSON. Raw mode retains the original string.
    if (/^\s*[\[{]/.test(data)) {
      let parsed: unknown;
      try {
        parsed = JSON.parse(data);
      } catch {
        /* Ordinary prose is displayed verbatim. */
      }
      if (isRecord(parsed) || Array.isArray(parsed))
        return <Value data={parsed} depth={depth + 1} />;
    }
    return <ReadableText text={data} />;
  }
  if (typeof data !== "object")
    return <span className="text-xs tabular-nums">{String(data)}</span>;
  // Bound visual nesting while keeping every field available.
  if (depth >= 8) return <JsonViewer data={data} maxInitialDepth={1} />;
  if (Array.isArray(data)) {
    if (!data.length)
      return <span className="text-xs text-text-muted">Empty list</span>;
    return (
      <div className="space-y-3">
        {data.map((item, index) => (
          <div
            key={index}
            className={cn(
              !isRecord(item) &&
                "rounded-md border border-divider bg-bg/30 p-3",
            )}
          >
            <Value data={item} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }
  const record = data as Record<string, unknown>;
  const role = messageRole(record);
  if (role && ("content" in record || "tool_calls" in record)) {
    const extras = Object.fromEntries(
      Object.entries(record).filter(
        ([key]) => !["role", "content", "tool_calls"].includes(key),
      ),
    );
    return (
      <article className="rounded-md border border-divider bg-bg/25">
        <div className="flex flex-wrap items-center gap-2 px-3 pt-3">
          <span className="text-caption text-info">
            {role.charAt(0).toUpperCase() + role.slice(1)}
          </span>
          {typeof record.name === "string" && (
            <span className="text-xs text-text-dim">{record.name}</span>
          )}
        </div>
        <div className="space-y-3 p-3">
          {"content" in record && (
            <Value data={record.content} depth={depth + 1} />
          )}
          {"tool_calls" in record && (
            <div>
              <p className="mb-2 text-caption text-text-muted">Tool calls</p>
              <Value data={record.tool_calls} depth={depth + 1} />
            </div>
          )}
        </div>
        {Object.keys(extras).length > 0 && (
          <details className="group/message mx-3 mb-3 rounded-md border border-divider bg-surface-hi/40">
            <summary className="flex items-center gap-1.5 rounded-control px-3 py-2 text-caption text-text-muted list-none hover:bg-surface-hi/60 hover:text-text transition-colors focus-visible:outline focus-visible:outline-primary [&::-webkit-details-marker]:hidden">
              <ChevronRight
                aria-hidden="true"
                className="h-3 w-3 shrink-0 transition-transform group-open/message:rotate-90"
              />
              Message details
            </summary>
            <div className="px-3 pb-3 pt-1">
              <Fields data={extras} depth={depth + 1} plain />
            </div>
          </details>
        )}
      </article>
    );
  }
  if ("messages" in record && Array.isArray(record.messages)) {
    const extras = Object.fromEntries(
      Object.entries(record).filter(([key]) => key !== "messages"),
    );
    return (
      <div className="space-y-3">
        <Value data={record.messages} depth={depth + 1} />
        {Object.keys(extras).length > 0 && (
          <Fields data={extras} depth={depth + 1} />
        )}
      </div>
    );
  }
  return <Fields data={record} depth={depth} />;
}

function Fields({
  data,
  depth,
  plain = false,
}: {
  data: Record<string, unknown>;
  depth: number;
  plain?: boolean;
}) {
  const entries = Object.entries(data);
  if (!entries.length)
    return <span className="text-xs text-text-muted">Empty object</span>;
  return (
    <dl
      className={cn(
        "space-y-3 min-w-0",
        !plain && "rounded-md border border-divider bg-bg/30 p-3",
      )}
    >
      {entries.map(([key, value]) => (
        <div key={key} className="space-y-1.5 min-w-0">
          <dt className="text-caption text-text-muted">{key}</dt>
          <dd className="min-w-0">
            <Value data={value} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** A deliberately small presentation layer: prose, emphasis and fenced code.
 * All content stays React text; trace payloads never become HTML or remote embeds.
 */
function ReadableText({ text }: { text: string }) {
  const parts = text.split(/(```[^\n]*\n[\s\S]*?```)/g);
  return (
    <div className="space-y-3">
      {parts.map((part, index) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const firstLine = part.indexOf("\n");
          return (
            <pre
              key={index}
              className="overflow-x-auto whitespace-pre-wrap rounded-md border border-divider bg-surface-hi/60 p-3 text-xs font-mono"
            >
              {part.slice(firstLine + 1, -3)}
            </pre>
          );
        }
        if (!part) return null;
        return (
          <p key={index} className="whitespace-pre-wrap">
            {inlineText(part)}
          </p>
        );
      })}
    </div>
  );
}

function inlineText(text: string): ReactNode[] {
  return text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return (
        <strong key={index} className="font-semibold text-primary">
          {part.slice(2, -2)}
        </strong>
      );
    if (part.startsWith("`") && part.endsWith("`"))
      return (
        <code
          key={index}
          className="rounded-sm bg-surface-hi px-1 font-mono text-xs"
        >
          {part.slice(1, -1)}
        </code>
      );
    return <Fragment key={index}>{part}</Fragment>;
  });
}
