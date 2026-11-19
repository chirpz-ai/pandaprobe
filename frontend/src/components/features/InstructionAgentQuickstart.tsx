"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, KeyRound, Package, Settings2 } from "lucide-react";
import { useProject } from "@/components/providers/ProjectProvider";
import { useOrgId } from "@/hooks/useNavigation";
import { createAPIKey } from "@/lib/api/api-keys";
import { extractErrorMessage } from "@/lib/api/client";
import { KeyExpiration } from "@/lib/api/enums";
import { queryKeys } from "@/lib/query/keys";
import { API_URL } from "@/lib/utils/constants";
import { CodeBlock } from "@/components/common/CodeBlock";
import { useToast } from "@/components/providers/ToastProvider";
import {
  StepSection,
  ProviderTabs,
  CreateApiKeyButton,
  IssuedKeyPanel,
  NextSteps,
  SdkLanguageTabs,
  QuickstartRunHint,
  QuickstartDocsLink,
} from "./InstructionShared";
import {
  AGENT_EXAMPLES,
  getQuickstartExample,
  type AgentFramework as Framework,
  type SdkLanguage,
} from "@/components/config/quickstart-examples";

/* ── Framework snippets ───────────────────────────────────────────────── */

const FRAMEWORKS = (Object.keys(AGENT_EXAMPLES) as Framework[]).map((id) => ({
  id,
  label: AGENT_EXAMPLES[id].label,
}));

function envSnippet(projectName: string, endpoint: string) {
  return `export PANDAPROBE_API_KEY="your-api-key"
export PANDAPROBE_PROJECT_NAME="${projectName}"
export PANDAPROBE_ENDPOINT="${endpoint}"

export OPENAI_API_KEY="your-openai-key"`;
}

/* ── Body ─────────────────────────────────────────────────────────────── */

export function InstructionAgentQuickstart() {
  const { currentProject } = useProject();
  const orgId = useOrgId();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [framework, setFramework] = useState<Framework>("deepagents");
  const [language, setLanguage] = useState<SdkLanguage>("python");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [creatingKey, setCreatingKey] = useState(false);

  const projectName = currentProject?.name ?? "my-first-project";
  const guide = AGENT_EXAMPLES[framework];
  const example = getQuickstartExample(guide, language);

  async function handleCreateKey() {
    if (creatingKey) return;
    setCreatingKey(true);
    try {
      const result = await createAPIKey(orgId, {
        name: "Quickstart",
        expiration: KeyExpiration.never,
      });
      if (!result.raw_key) {
        toast({ title: "Key returned without raw value", variant: "error" });
        return;
      }
      setIssuedKey(result.raw_key);
      queryClient.invalidateQueries({
        queryKey: queryKeys.apiKeys.list(orgId),
      });
      toast({ title: "API key created", variant: "success" });
    } catch (err) {
      toast({ title: extractErrorMessage(err), variant: "error" });
    } finally {
      setCreatingKey(false);
    }
  }

  return (
    <>
      <StepSection
        number={1}
        icon={<KeyRound className="h-4 w-4" />}
        title="Create your API key"
        description="Generate a key to authenticate the SDK."
      >
        {issuedKey ? (
          <IssuedKeyPanel
            rawKey={issuedKey}
            onDismiss={() => setIssuedKey(null)}
          />
        ) : (
          <CreateApiKeyButton loading={creatingKey} onClick={handleCreateKey} />
        )}
      </StepSection>

      <StepSection
        number={2}
        icon={<Package className="h-4 w-4" />}
        title="Install the SDK"
        description="Pick the agent framework you want to instrument. You can add more later."
      >
        <ProviderTabs
          options={FRAMEWORKS}
          value={framework}
          onChange={setFramework}
        />
        <SdkLanguageTabs
          value={example.language}
          onChange={setLanguage}
          typescriptOnly={!guide.python}
        />
        {framework === "deepagents" && example.language === "python" && (
          <p className="text-xs text-text-muted">
            Requires Python 3.11 or newer.
          </p>
        )}
        {framework === "vercel-ai" && (
          <p className="text-xs text-text-muted">
            This agent example uses AI SDK 6 or 7 in Node.js.
          </p>
        )}
        <CodeBlock code={example.install} language="bash" />
      </StepSection>

      <StepSection
        number={3}
        icon={<Settings2 className="h-4 w-4" />}
        title="Set environment variables"
        description="Set these in your server-side environment. These examples use OpenAI as the model provider."
      >
        <ProviderTabs
          options={FRAMEWORKS}
          value={framework}
          onChange={setFramework}
        />
        <CodeBlock code={envSnippet(projectName, API_URL)} language="bash" />
      </StepSection>

      <StepSection
        number={4}
        icon={<Bot className="h-4 w-4" />}
        title="Build and instrument your agent"
        description={
          framework === "vercel-ai"
            ? "Wrap the native agent and add model middleware to capture the run, model steps, and tool executions."
            : "Pass the callback handler on each invocation to capture the agent run and its nested spans."
        }
      >
        <ProviderTabs
          options={FRAMEWORKS}
          value={framework}
          onChange={setFramework}
        />
        <SdkLanguageTabs
          value={example.language}
          onChange={setLanguage}
          typescriptOnly={!guide.python}
        />
        <CodeBlock
          code={example.code}
          language={example.language}
          caption={
            example.language === "python" ? "quickstart.py" : "quickstart.mts"
          }
        />
        <QuickstartRunHint language={example.language} />
        <QuickstartDocsLink href={guide.docsUrl} />
      </StepSection>

      <NextSteps />
    </>
  );
}
