"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { PrismAsyncLight as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import { cn } from "@/lib/utils/cn";

SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("bash", bash);
SyntaxHighlighter.registerLanguage("json", json);

type SupportedLanguage = "python" | "bash" | "json" | "text";

interface CodeBlockProps {
  code: string;
  language?: SupportedLanguage;
  className?: string;
  caption?: string;
}

export function CodeBlock({
  code,
  language = "text",
  className,
  caption,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className={cn("relative border border-border bg-surface-hi", className)}
    >
      {caption && (
        <div className="flex items-center justify-between px-3 h-7 border-b border-border bg-surface">
          <span className="text-[10px] font-mono uppercase tracking-wider text-text-muted">
            {caption}
          </span>
        </div>
      )}

      <button
        type="button"
        onClick={handleCopy}
        aria-label="Copy to clipboard"
        className="absolute top-2 right-2 p-1.5 border border-border bg-surface hover:bg-surface-hi hover:border-primary/40 text-text-muted hover:text-text transition-colors z-10"
      >
        {copied ? (
          <Check className="h-3 w-3 text-success" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
      </button>

      <SyntaxHighlighter
        language={language}
        style={oneDark}
        PreTag="div"
        customStyle={{
          margin: 0,
          padding: "1rem",
          paddingRight: "3rem",
          background: "transparent",
          fontSize: "0.75rem",
          lineHeight: "1.5",
        }}
        codeTagProps={{
          style: {
            fontFamily:
              "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
            fontSize: "0.75rem",
            background: "transparent",
          },
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
