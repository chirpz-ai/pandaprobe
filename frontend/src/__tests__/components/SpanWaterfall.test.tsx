import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef, useRef } from "react";

import { SpanWaterfall } from "@/components/features/SpanWaterfall";
import type { TraceResponse } from "@/lib/api/types";

// The panel expands upward over the metadata card to gain reading room.

const OVERLAY_HEIGHT = 180;
const STACK_GAP = 24;

function makeTrace(): TraceResponse {
  const started = "2026-08-01T00:00:00Z";
  return {
    trace_id: "t1",
    name: "trace",
    status: "COMPLETED",
    input: null,
    output: null,
    metadata: {},
    started_at: started,
    ended_at: started,
    session_id: null,
    user_id: null,
    tags: [],
    environment: null,
    release: null,
    total_tokens: 0,
    total_cost: 0,
    spans: [
      {
        span_id: "s1",
        trace_id: "t1",
        parent_span_id: null,
        name: "root span",
        kind: "LLM",
        status: "OK",
        input: null,
        output: null,
        model: null,
        token_usage: null,
        metadata: {},
        started_at: started,
        ended_at: started,
        error: null,
        completion_start_time: null,
        model_parameters: null,
        cost: null,
      },
    ],
  } as unknown as TraceResponse;
}

/** Mirrors the trace page's layout. */
function Harness({ withTarget = true }: { withTarget?: boolean }) {
  const targetRef = useRef<HTMLDivElement>(null);
  return (
    <div>
      <div ref={targetRef} data-testid="metadata" />
      <SpanWaterfall
        trace={makeTrace()}
        overlayTargetRef={withTarget ? targetRef : undefined}
      />
    </div>
  );
}

function panelOf(container: HTMLElement): HTMLElement {
  const panel = container.querySelector<HTMLElement>(
    "div.border.border-border",
  );
  if (!panel) throw new Error("panel not found");
  return panel;
}

beforeAll(() => {
  // jsdom reports every element as 0x0.
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    get(this: HTMLElement) {
      return this.dataset.testid === "metadata" ? OVERLAY_HEIGHT : 0;
    },
  });
});

describe("SpanWaterfall expand control", () => {
  it("is collapsed initially, with no upward offset", () => {
    const { container } = render(<Harness />);

    expect(
      screen.getByRole("button", { name: /expand span panel/i }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(panelOf(container).style.marginTop).toBe("");
  });

  it("grows upward by the covered height when expanded", async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);

    await user.click(
      screen.getByRole("button", { name: /expand span panel/i }),
    );

    const panel = panelOf(container);
    expect(panel.style.marginTop).toBe(`-${OVERLAY_HEIGHT + STACK_GAP}px`);
    // Same amount added back, so the bottom edge does not move.
    expect(panel.style.maxHeight).toContain(
      `+ ${OVERLAY_HEIGHT + STACK_GAP}px`,
    );
  });

  it("becomes opaque and raised so it covers the card beneath", async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);

    await user.click(
      screen.getByRole("button", { name: /expand span panel/i }),
    );

    const panel = panelOf(container);
    expect(panel.className).toContain("bg-surface");
    // Below the scores drawer (z-40/z-50).
    expect(panel.className).toContain("z-30");
  });

  it("collapses again on a second click", async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);

    await user.click(
      screen.getByRole("button", { name: /expand span panel/i }),
    );
    await user.click(
      screen.getByRole("button", { name: /collapse span panel/i }),
    );

    expect(panelOf(container).style.marginTop).toBe("");
  });

  it("collapses on Escape", async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);

    await user.click(
      screen.getByRole("button", { name: /expand span panel/i }),
    );
    await user.keyboard("{Escape}");

    expect(panelOf(container).style.marginTop).toBe("");
  });

  it("swaps the icon to match the action available", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    // Scoped to the button; the tree renders its own icons.
    const collapsed = screen.getByRole("button", {
      name: /expand span panel/i,
    });
    expect(collapsed.querySelector(".lucide-maximize-2")).toBeTruthy();
    expect(collapsed.querySelector(".lucide-minimize-2")).toBeNull();

    await user.click(collapsed);

    const expandedBtn = screen.getByRole("button", {
      name: /collapse span panel/i,
    });
    expect(expandedBtn.querySelector(".lucide-minimize-2")).toBeTruthy();
    expect(expandedBtn.querySelector(".lucide-maximize-2")).toBeNull();
  });

  it("gives both panes the surface background, collapsed as well as expanded", () => {
    const { container } = render(<Harness />);

    // The tree pane had no background and fell through to the page colour, so
    // it only matched the detail pane once expanding painted the whole panel.
    const panes = panelOf(container).children;
    expect(panes[0].className).toContain("bg-surface");
    expect(panes[1].className).toContain("bg-surface");
  });

  it("pins the control to the detail panel's top-right corner", () => {
    render(<Harness />);

    // On the panel, not the detail header — that header scrolls away.
    const button = screen.getByRole("button", { name: /expand span panel/i });
    expect(button.className).toMatch(/\babsolute\b/);
    expect(button.className).toMatch(/\btop-\d/);
    expect(button.className).toMatch(/\bright-\d/);
  });

  it("hides the control when there is nothing to overlay", () => {
    render(<Harness withTarget={false} />);

    expect(screen.queryByRole("button", { name: /span panel/i })).toBeNull();
  });

  it("renders nothing to expand for a trace with no spans", () => {
    const trace = { ...makeTrace(), spans: [] } as unknown as TraceResponse;
    const ref = createRef<HTMLDivElement>();

    render(<SpanWaterfall trace={trace} overlayTargetRef={ref} />);

    expect(screen.getByText(/no spans recorded/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /span panel/i })).toBeNull();
  });
});
