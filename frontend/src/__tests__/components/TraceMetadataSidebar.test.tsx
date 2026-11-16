import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TraceMetadataSidebar } from "@/components/features/TraceMetadataSidebar";
import { formatDateTime } from "@/lib/utils/format";
import { makeTrace } from "../fixtures/trace";

it("opens trace metadata, copies the ID, and restores focus after keyboard dismissal", async () => {
  const user = userEvent.setup();
  const onCopyId = jest.fn();
  const trace = makeTrace({
    session_id: "support-session",
    user_id: "customer-1",
    environment: "staging",
    release: "v0.7.0",
    tags: ["support", "regression"],
  });
  render(
    <TraceMetadataSidebar trace={trace} copiedId={false} onCopyId={onCopyId} />,
  );
  const trigger = screen.getByRole("button", { name: "Metadata" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  await user.click(trigger);
  const details = within(screen.getByRole("dialog", { name: "Metadata" }));
  for (const value of [
    trace.name,
    trace.trace_id,
    formatDateTime(trace.started_at),
    formatDateTime(trace.ended_at),
    "support-session",
    "customer-1",
    "staging",
    "v0.7.0",
    "support",
    "regression",
  ]) {
    expect(details.getByText(value)).toBeInTheDocument();
  }
  await user.click(details.getByRole("button", { name: "Copy trace ID" }));
  expect(onCopyId).toHaveBeenCalledTimes(1);

  await user.keyboard("{Escape}");
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(trigger).toHaveFocus();
});
