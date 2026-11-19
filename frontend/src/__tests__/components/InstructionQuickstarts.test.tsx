import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InstructionAgentQuickstart } from "@/components/features/InstructionAgentQuickstart";
import { InstructionTraceQuickstart } from "@/components/features/InstructionTraceQuickstart";

jest.mock("@/components/providers/ProjectProvider", () => ({
  useProject: () => ({ currentProject: { name: "quickstart-project" } }),
}));
jest.mock("@/hooks/useNavigation", () => ({
  useOrgId: () => "org-test",
  useProjectId: () => "project-test",
  useProjectPath: () => "/org/org-test/project/project-test",
}));
jest.mock("@/components/providers/ToastProvider", () => ({
  useToast: () => ({ toast: jest.fn() }),
}));
jest.mock("@/lib/api/traces", () => ({
  listTraces: jest.fn().mockResolvedValue({ total: 0, items: [] }),
}));
jest.mock("@/components/common/CodeBlock", () => ({
  CodeBlock: ({ code, language }: { code: string; language: string }) => (
    <pre data-testid={`code-${language}`}>{code}</pre>
  ),
}));

function renderGuide(guide: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={client}>{guide}</QueryClientProvider>,
  );
}

function step(title: string) {
  return within(
    screen.getByRole("heading", { name: title }).closest("section")!,
  );
}

it("keeps Vercel AI TypeScript-only and restores the user's language preference for other frameworks", async () => {
  const user = userEvent.setup();
  renderGuide(<InstructionAgentQuickstart />);
  const install = step("Install the SDK");
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    'pip install "pandaprobe[deepagents]" langchain-openai',
  );

  await user.click(install.getByRole("button", { name: "Vercel AI" }));
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    "npm install pandaprobe ai @ai-sdk/openai",
  );
  expect(install.getByText("TypeScript only")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Python" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Google ADK" }),
  ).not.toBeInTheDocument();
  const vercelCode = screen.getByTestId("code-typescript");
  expect(vercelCode).toHaveTextContent(
    "wrapVercelAgent(ToolLoopAgent, { client })",
  );
  expect(vercelCode).toHaveTextContent("pandaProbeMiddleware()");
  expect(vercelCode).toHaveTextContent("await client.shutdown()");
  expect(screen.getByRole("link", { name: "Open full guide" })).toHaveAttribute(
    "href",
    "https://docs.pandaprobe.com/tracing/integrations/vercel-ai",
  );

  await user.click(install.getByRole("button", { name: "LangGraph" }));
  expect(install.getByRole("button", { name: "Python" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByTestId("code-python")).toHaveTextContent(
    "LangGraphCallbackHandler",
  );
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    "langchain-openai",
  );

  await user.click(install.getByRole("button", { name: "TypeScript" }));
  await user.click(install.getByRole("button", { name: "Vercel AI" }));
  await user.click(install.getByRole("button", { name: "DeepAgents" }));
  expect(install.getByRole("button", { name: "TypeScript" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    "npm install pandaprobe deepagents",
  );
  expect(screen.getByTestId("code-typescript")).toHaveTextContent(
    "createDeepAgent",
  );
});

it("synchronizes trace installation, provider credentials, and example language from either selector", async () => {
  const user = userEvent.setup();
  renderGuide(<InstructionTraceQuickstart />);
  const install = step("Install the SDK");
  const wrap = step("Wrap your LLM client");
  const environment = step("Set environment variables");

  await user.click(wrap.getByRole("button", { name: "Google Gemini" }));
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    "pandaprobe[gemini]",
  );
  expect(environment.getByTestId("code-bash")).toHaveTextContent(
    "GOOGLE_API_KEY",
  );
  expect(wrap.getByTestId("code-python")).toHaveTextContent(
    "pandaprobe.flush()",
  );

  await user.click(wrap.getByRole("button", { name: "TypeScript" }));
  expect(install.getByRole("button", { name: "TypeScript" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    "npm install pandaprobe @google/genai",
  );
  expect(wrap.getByTestId("code-typescript")).toHaveTextContent("wrapGemini");

  await user.click(install.getByRole("button", { name: "Anthropic" }));
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    "@anthropic-ai/sdk",
  );
  expect(environment.getByTestId("code-bash")).toHaveTextContent(
    "ANTHROPIC_API_KEY",
  );
  expect(wrap.getByTestId("code-typescript")).toHaveTextContent(
    "max_tokens: 1024",
  );
  expect(wrap.getByTestId("code-typescript")).toHaveTextContent(
    "await flush()",
  );

  await user.click(install.getByRole("button", { name: "OpenAI" }));
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    "npm install pandaprobe openai",
  );
  expect(environment.getByTestId("code-bash")).toHaveTextContent(
    "OPENAI_API_KEY",
  );
  expect(wrap.getByTestId("code-typescript")).toHaveTextContent("wrapOpenAI");

  await user.click(wrap.getByRole("button", { name: "Python" }));
  expect(install.getByTestId("code-bash")).toHaveTextContent(
    'pip install "pandaprobe[openai]"',
  );
  expect(wrap.getByTestId("code-python")).toHaveTextContent("wrap_openai");
});
