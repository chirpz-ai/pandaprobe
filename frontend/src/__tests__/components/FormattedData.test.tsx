import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormattedData } from "@/components/common/FormattedData";

describe("FormattedData", () => {
  it("renders message cards and preserves extra fields and tool calls", async () => {
    const user = userEvent.setup();
    render(
      <FormattedData
        data={{
          messages: [
            {
              role: "assistant",
              content: "Found **three** matches.",
              tool_calls: [{ name: "search", args: { query: "order" } }],
              usage_metadata: { tokens: 34 },
            },
          ],
          request_id: "req-123",
        }}
      />,
    );
    expect(screen.getByText("assistant")).toBeInTheDocument();
    expect(screen.getByText("three").tagName).toBe("STRONG");
    expect(screen.getByText("search")).toBeInTheDocument();
    expect(screen.getByText("order")).toBeInTheDocument();
    expect(screen.getByText("req-123")).toBeInTheDocument();
    await user.click(screen.getByText("Message details"));
    expect(screen.getByText("34")).toBeVisible();
  });
  it("preserves falsy values, empty structures, mixed arrays and serialized JSON", () => {
    render(
      <FormattedData
        data={{
          count: 0,
          enabled: false,
          missing: null,
          text: "",
          list: [],
          object: {},
          results: ["one", 2, { title: "three" }],
          tool_output: '{"state":"ready"}',
        }}
      />,
    );
    for (const value of [
      "0",
      "false",
      "No content",
      "Empty string",
      "Empty list",
      "Empty object",
      "one",
      "2",
      "three",
      "ready",
    ])
      expect(screen.getByText(value)).toBeInTheDocument();
  });
  it("preserves multimodal content and renders untrusted markup as text", () => {
    const { container } = render(
      <FormattedData
        data={{
          role: "user",
          content: [
            { type: "text", text: "hello" },
            {
              type: "image_url",
              image_url: { url: "https://example.com/private.png" },
            },
            { type: "text", text: '<script>alert("test")</script>' },
          ],
        }}
      />,
    );
    expect(
      screen.getByText("https://example.com/private.png"),
    ).toBeInTheDocument();
    expect(
      screen.getByText('<script>alert("test")</script>'),
    ).toBeInTheDocument();
    expect(container.querySelector("script, img, iframe")).toBeNull();
  });
  it("keeps code and multiline content readable", () => {
    const { container } = render(
      <FormattedData data={'Use `order_id`.\n\n```json\n{"id": 1}\n```'} />,
    );
    expect(container.querySelector("code")).toHaveTextContent("order_id");
    expect(container.querySelector("pre")).toHaveTextContent('{"id": 1}');
  });
});
