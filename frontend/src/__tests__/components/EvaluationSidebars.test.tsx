import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { EvaluationSidebar } from "@/components/features/EvaluationSidebar";
import { EvalRunCreateSidebar } from "@/components/features/EvalRunCreateSidebar";
import {
  createBatchTraceRun,
  createBatchSessionRun,
  createTraceRun,
  createSessionRun,
} from "@/lib/api/evaluations";

jest.mock("@/lib/api/evaluations", () => ({
  getProviders: jest.fn(),
  getTraceMetrics: jest.fn(),
  getSessionMetrics: jest.fn(),
  createBatchTraceRun: jest.fn(),
  createBatchSessionRun: jest.fn(),
  createTraceRun: jest.fn(),
  createSessionRun: jest.fn(),
}));
jest.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => ({
    data: queryKey.includes("providers")
      ? []
      : [{ name: "quality", description: "Quality metric" }],
    isPending: false,
    error: null,
  }),
}));
jest.mock("@/components/providers/ToastProvider", () => ({
  useToast: () => ({ toast: jest.fn() }),
}));
jest.mock("@/components/providers/EvalRunTrackerProvider", () => ({
  useEvalRunTracker: () => null,
}));
jest.mock("@/lib/api/client", () => ({ extractErrorMessage: String }));

describe.each([
  { mode: "trace" as const, batch: true, create: createBatchTraceRun },
  { mode: "session" as const, batch: true, create: createBatchSessionRun },
  { mode: "trace" as const, batch: false, create: createTraceRun },
  { mode: "session" as const, batch: false, create: createSessionRun },
])("$mode evaluation sidebar (batch=$batch)", ({ mode, batch, create }) => {
  beforeEach(() => {
    jest.clearAllMocks();
    (create as jest.Mock).mockResolvedValue({ id: "run-id" });
  });

  it.each(["", "   ", "  My evaluation  "])(
    "accepts optional name %j and places it after Model",
    async (name) => {
      const onClose = jest.fn();
      render(
        batch ? (
          <EvaluationSidebar
            mode={mode}
            open
            onClose={onClose}
            targetIds={["target-id"]}
          />
        ) : (
          <EvalRunCreateSidebar mode={mode} open onClose={onClose} />
        ),
      );

      const input = screen.getByPlaceholderText("Eval run name (optional)");
      const submit = screen.getByRole("button", { name: "Submit" });
      expect(input).not.toBeRequired();
      expect(
        screen.getByText("Model").compareDocumentPosition(input) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
      expect(submit).toBeDisabled(); // Metrics remain required.
      fireEvent.change(input, { target: { value: name } });
      fireEvent.click(screen.getByRole("checkbox", { name: /quality/i }));
      expect(submit).toBeEnabled();
      fireEvent.click(submit);

      await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
      const body = (create as jest.Mock).mock.calls[0][0];
      expect(body.metrics).toEqual(["quality"]);
      if (name.trim()) {
        expect(body.name).toBe("My evaluation");
      } else {
        expect(body).not.toHaveProperty("name");
      }
      await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    },
  );
});
