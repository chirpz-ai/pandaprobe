import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SpanWaterfall } from "@/components/features/SpanWaterfall";
import { makeTrace, makeSpan } from "../fixtures/trace";

describe("Trace waterfall", () => {
  it("positions bars by elapsed start and duration, keeping zero-duration markers", () => {
    const { container } = render(<SpanWaterfall trace={makeTrace()} />);
    const bar = container.querySelector<HTMLElement>(
      '[data-timeline-bar="llm"]',
    )!;
    expect(bar.style.left).toContain("20%");
    expect(bar.style.width).toBe("20%");
    expect(bar).not.toHaveAttribute("data-timeline-marker");
    const marker = container.querySelector<HTMLElement>(
      '[data-timeline-bar="tool"]',
    )!;
    expect(marker.style.width).toBe("2px");
    expect(marker.style.minWidth).toBe("2px");
    expect(marker).toHaveAttribute("data-timeline-marker", "true");
    expect(screen.getByLabelText("Elapsed time")).toHaveTextContent(
      "0s2s4s6s8s10s",
    );
  });

  it("collapses descendants independently from selection and preserves nested collapse state", async () => {
    const user = userEvent.setup();
    render(<SpanWaterfall trace={makeTrace()} />);
    await user.click(screen.getByRole("button", { name: "Collapse Agent" }));
    expect(
      screen.queryByRole("button", { name: /ChatOpenAI LLM/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Support workflow" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Collapse Support workflow" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Expand Support workflow" }),
    );
    expect(
      screen.getByRole("button", { name: "Expand Agent" }),
    ).toHaveAttribute("aria-expanded", "false");
    await user.click(screen.getByRole("button", { name: "Expand Agent" }));
    expect(
      screen.getByRole("button", { name: /ChatOpenAI LLM/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Expand all" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Collapse all" }),
    ).not.toBeInTheDocument();
  });

  it("keeps short spans visible as markers and longer spans as unoutlined bars", () => {
    const { container } = render(
      <SpanWaterfall
        trace={makeTrace({
          spans: [
            makeSpan({ span_id: "short", latency_ms: 16 }),
            makeSpan({ span_id: "long", latency_ms: 2000 }),
          ],
        })}
      />,
    );
    const short = container.querySelector<HTMLElement>(
      '[data-timeline-bar="short"]',
    )!;
    const long = container.querySelector<HTMLElement>(
      '[data-timeline-bar="long"]',
    )!;
    expect(short).toHaveAttribute("data-timeline-marker", "true");
    expect(short.style.width).toBe("2px");
    expect(long).not.toHaveAttribute("data-timeline-marker");
    expect(long.className).not.toContain("border-l");
  });

  it("switches between Waterfall and Timeline with shared selection and collapsed branches", async () => {
    const user = userEvent.setup();
    render(<SpanWaterfall trace={makeTrace()} />);
    expect(screen.getByRole("tab", { name: "Timeline" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.click(screen.getByRole("button", { name: /ChatOpenAI LLM/ }));
    await user.click(screen.getByRole("tab", { name: "Waterfall" }));
    expect(screen.queryByLabelText("Elapsed time")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /ChatOpenAI LLM/ }),
    ).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Collapse Agent" }));
    expect(
      screen.queryByRole("button", { name: /ChatOpenAI LLM/ }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Timeline" }));
    expect(screen.getByLabelText("Elapsed time")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /ChatOpenAI LLM/ }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Expand Agent" }));
    expect(
      screen.getByRole("button", { name: /ChatOpenAI LLM/ }),
    ).toHaveAttribute("aria-pressed", "true");
    // Radix tabs also support keyboard switching.
    screen.getByRole("tab", { name: "Timeline" }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Waterfall" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("heading", { name: "ChatOpenAI" }),
    ).toBeInTheDocument();
  });

  it("defaults to readable cards, selects spans and keeps the raw preference across selections", async () => {
    const user = userEvent.setup();
    render(<SpanWaterfall trace={makeTrace()} />);
    expect(screen.getByRole("tab", { name: "Formatted" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.click(screen.getByRole("button", { name: /ChatOpenAI LLM/ }));
    const details = screen.getByRole("region", {
      name: "Selected span details",
    });
    expect(
      within(details).getByRole("heading", { name: "ChatOpenAI" }),
    ).toBeInTheDocument();
    expect(within(details).getByText("+2.0s")).toBeInTheDocument();
    expect(within(details).getByText("test-model")).toBeInTheDocument();
    expect(within(details).getByText("Find my order")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Raw" }));
    expect(within(details).getByText('"Find my order"')).toBeInTheDocument();
    details.scrollTop = 500;
    await user.click(screen.getByRole("button", { name: /Lookup order TOOL/ }));
    expect(details.scrollTop).toBe(0);
    expect(screen.getByRole("tab", { name: "Raw" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(within(details).getByText('"shipped"')).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Span details" }),
    ).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Waterfall · 3" }));
    expect(
      screen.getByRole("button", { name: "Waterfall · 3" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps trace content accessible with no spans and exposes errors without relying on color", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <SpanWaterfall trace={makeTrace({ spans: [] })} />,
    );
    expect(screen.getByText("No spans recorded")).toBeInTheDocument();
    expect(screen.getByText("Find my order")).toBeInTheDocument();
    rerender(
      <SpanWaterfall
        trace={makeTrace({
          spans: [makeSpan({ status: "ERROR", error: "Model unavailable" })],
        })}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Agent AGENT 8.0s Error" }),
    );
    expect(screen.getByText("Model unavailable")).toBeInTheDocument();
  });
});
