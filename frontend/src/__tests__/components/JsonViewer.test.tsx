import { render, screen } from "@testing-library/react";

import { JsonViewer } from "@/components/common/JsonViewer";

/**
 * Span detail rendering.
 *
 * Long string values used to be cut with `slice(0, 120)` and an ellipsis. Unlike
 * objects and arrays, a string node has no expand toggle, so the remainder was
 * unreachable — the `content` of an LLM message was only ever partly readable.
 */

const LONG = "x".repeat(500);

describe("JsonViewer string values", () => {
  it("renders a long nested string in full", () => {
    render(<JsonViewer data={{ content: LONG }} />);

    expect(screen.getByText(`"${LONG}"`)).toBeInTheDocument();
  });

  it("does not render a truncation ellipsis", () => {
    const { container } = render(<JsonViewer data={{ content: LONG }} />);

    expect(container.textContent).not.toContain("…");
  });

  it("keeps every character of the original value", () => {
    const { container } = render(<JsonViewer data={{ content: LONG }} />);

    // 500 chars plus the two rendered quote characters.
    expect(container.textContent).toContain(LONG);
    expect(container.textContent?.match(/x/g)).toHaveLength(500);
  });

  it("renders short strings unchanged", () => {
    render(<JsonViewer data={{ role: "assistant" }} />);

    expect(screen.getByText('"assistant"')).toBeInTheDocument();
  });

  it("preserves line breaks inside content", () => {
    const multiline = "line one\nline two\nline three";
    const { container } = render(<JsonViewer data={{ content: multiline }} />);

    expect(container.textContent).toContain(multiline);
  });

  it("renders long content nested below the old expand depth", () => {
    render(
      <JsonViewer data={{ messages: [{ role: "user", content: LONG }] }} />,
    );

    expect(screen.getByText(`"${LONG}"`)).toBeInTheDocument();
  });

  it("renders a top-level string in full", () => {
    const { container } = render(<JsonViewer data={LONG} />);

    expect(container.textContent).toBe(LONG);
  });
});

describe("JsonViewer default expansion", () => {
  /** A tool-call shape, nested well past the old depth-3 cap. */
  const DEEP = {
    messages: [
      {
        role: "assistant",
        tool_calls: [
          { function: { name: "search", arguments: { query: "needle" } } },
        ],
      },
    ],
  };

  it("expands every level by default", () => {
    render(<JsonViewer data={DEEP} />);

    // Visible only if messages -> [0] -> tool_calls -> [0] -> function ->
    // arguments are all expanded on first render.
    expect(screen.getByText('"query"')).toBeInTheDocument();
    expect(screen.getByText('"needle"')).toBeInTheDocument();
  });

  it("shows no collapsed placeholders by default", () => {
    const { container } = render(<JsonViewer data={DEEP} />);

    expect(container.textContent).not.toMatch(/\d+ keys/);
    expect(container.textContent).not.toMatch(/\d+ items/);
  });

  it("still honours an explicit depth cap", () => {
    const { container } = render(
      <JsonViewer data={DEEP} maxInitialDepth={1} />,
    );

    // The nested array is collapsed to a placeholder, so the leaf is absent.
    expect(container.textContent).toMatch(/\d+ items|\d+ keys/);
    expect(screen.queryByText('"needle"')).not.toBeInTheDocument();
  });

  it("still honours defaultExpanded=false", () => {
    const { container } = render(
      <JsonViewer data={DEEP} defaultExpanded={false} />,
    );

    expect(container.textContent).toMatch(/\d+ keys/);
    expect(screen.queryByText('"needle"')).not.toBeInTheDocument();
  });
});
