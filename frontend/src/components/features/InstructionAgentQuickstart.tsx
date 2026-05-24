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
} from "./InstructionShared";

/* ── Framework snippets ───────────────────────────────────────────────── */

type Framework = "deepagents" | "langgraph" | "google-adk";

const FRAMEWORKS: { id: Framework; label: string }[] = [
  { id: "deepagents", label: "DeepAgents" },
  { id: "langgraph", label: "LangGraph" },
  { id: "google-adk", label: "Google ADK" },
];

const INSTALL_SNIPPETS: Record<Framework, string> = {
  deepagents: 'pip install "pandaprobe[deepagents]"',
  langgraph: 'pip install "pandaprobe[langgraph]"',
  "google-adk": 'pip install "pandaprobe[google-adk]"',
};

const FRAMEWORK_KEY_EXPORTS: Record<Framework, string> = {
  deepagents: 'export OPENAI_API_KEY="your-openai-key"',
  langgraph: 'export OPENAI_API_KEY="your-openai-key"',
  "google-adk": 'export GOOGLE_API_KEY="your-google-key"',
};

function envSnippet(
  framework: Framework,
  projectName: string,
  endpoint: string,
) {
  return `export PANDAPROBE_API_KEY="your-api-key"
export PANDAPROBE_PROJECT_NAME="${projectName}"
export PANDAPROBE_ENDPOINT="${endpoint}"

${FRAMEWORK_KEY_EXPORTS[framework]}`;
}

const AGENT_SNIPPETS: Record<Framework, string> = {
  deepagents: `from deepagents import create_deep_agent
from langchain.tools import tool

import pandaprobe
from pandaprobe.integrations.deepagents import DeepAgentsCallbackHandler

@tool
def search_papers(topic: str) -> str:
    """Return a short list of recent papers on a topic."""
    return (
        f"Top 3 recent papers on {topic}:\\n"
        "1. Smith et al., 2024 — A survey of advances\\n"
        "2. Lee & Kumar, 2024 — Empirical comparisons\\n"
        "3. Garcia, 2023 — Foundations and theory"
    )

researcher_subagent = {
    "name": "researcher",
    "description": (
        "Searches for and summarizes recent academic papers on a given topic. "
        "Use this when the user asks for a literature overview."
    ),
    "system_prompt": (
        "You are a research assistant. When given a topic, call search_papers, "
        "then return a concise 2-sentence summary of what you found."
    ),
    "tools": [search_papers],
    "model": "openai:gpt-5.4-nano",
}

agent = create_deep_agent(
    model="openai:gpt-5.4-nano",
    tools=[],
    system_prompt=(
        "You are a senior research lead. For any literature/research request, "
        "delegate to the 'researcher' sub-agent via the task tool, then "
        "synthesize the result into a final answer."
    ),
    subagents=[researcher_subagent],
)

handler = DeepAgentsCallbackHandler(tags=["research-agent", "subagents"])

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Give me a brief summary of recent research on retrieval-augmented generation.",
            }
        ]
    },
    config={"callbacks": [handler]},
)

final_message = result["messages"][-1]
print(f"Agent: {final_message.content}")

pandaprobe.flush()
pandaprobe.shutdown()`,

  langgraph: `from typing import Annotated

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

import pandaprobe
from pandaprobe.integrations.langgraph import LangGraphCallbackHandler

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    weather_data = {
        "london": "Cloudy, 15°C, 70% humidity",
        "tokyo": "Sunny, 28°C, 45% humidity",
        "new york": "Partly cloudy, 22°C, 55% humidity",
        "paris": "Rainy, 12°C, 85% humidity",
    }
    return weather_data.get(city.lower(), f"Weather data not available for {city}")

@tool
def get_population(city: str) -> str:
    """Get the approximate population of a city."""
    populations = {
        "london": "8.8 million",
        "tokyo": "13.9 million",
        "new york": "8.3 million",
        "paris": "2.2 million",
    }
    return populations.get(city.lower(), f"Population data not available for {city}")

tools = [get_weather, get_population]
llm = ChatOpenAI(model="gpt-5.4-nano").bind_tools(tools)

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

def agent_node(state: AgentState) -> dict:
    system = SystemMessage(content="You are a helpful assistant with access to weather and population tools.")
    messages = [system, *state["messages"]]
    return {"messages": [llm.invoke(messages)]}

def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", ToolNode(tools))
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "agent")
app = graph.compile()

handler = LangGraphCallbackHandler(tags=["tool-agent", "example"])

result = app.invoke(
    {"messages": [("user", "What's the weather like in London and what's its population?")]},
    config={"callbacks": [handler]},
)

final_message = result["messages"][-1]
print(f"Agent: {final_message.content}")

pandaprobe.flush()
pandaprobe.shutdown()`,

  "google-adk": `import asyncio
import uuid

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

import pandaprobe
from pandaprobe.integrations.google_adk import GoogleADKAdapter

def get_weather(city: str) -> dict:
    """Get the current weather for a city."""
    weather_data = {
        "london": {"condition": "Cloudy", "temp": "15°C", "humidity": "70%"},
        "tokyo": {"condition": "Sunny", "temp": "28°C", "humidity": "45%"},
        "new york": {"condition": "Partly cloudy", "temp": "22°C", "humidity": "55%"},
        "paris": {"condition": "Rainy", "temp": "12°C", "humidity": "85%"},
    }
    return weather_data.get(city.lower(), {"error": f"No data for {city}"})

def get_population(city: str) -> dict:
    """Get the approximate population of a city."""
    populations = {
        "london": {"population": "8.8 million"},
        "tokyo": {"population": "13.9 million"},
        "new york": {"population": "8.3 million"},
        "paris": {"population": "2.2 million"},
    }
    return populations.get(city.lower(), {"error": f"No data for {city}"})

agent = LlmAgent(
    name="city_info_agent",
    model="gemini-3.1-flash-lite",
    instruction=(
        "You are a helpful assistant with access to weather and population tools. "
        "Use the tools to answer questions about cities."
    ),
    tools=[get_weather, get_population],
)

APP_NAME = "tool_agent"
USER_ID = "user_1"
SESSION_ID = str(uuid.uuid4())

async def main():
    adapter = GoogleADKAdapter(
        session_id=SESSION_ID,
        user_id=USER_ID,
        tags=["tool-agent", "example"],
    )
    adapter.instrument()

    session_service = InMemorySessionService()
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    user_message = Content(
        role="user",
        parts=[Part(text="What's the weather like in London and what's its population?")],
    )

    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=user_message):
        if event.is_final_response():
            text = " ".join(p.text for p in event.content.parts if p.text)
            print(f"Agent: {text}")

    pandaprobe.flush()
    pandaprobe.shutdown()
    print("\\nTrace sent to PandaProbe backend.")

if __name__ == "__main__":
    asyncio.run(main())`,
};

/* ── Body ─────────────────────────────────────────────────────────────── */

export function InstructionAgentQuickstart() {
  const { currentProject } = useProject();
  const orgId = useOrgId();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [framework, setFramework] = useState<Framework>("deepagents");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [creatingKey, setCreatingKey] = useState(false);

  const projectName = currentProject?.name ?? "my-first-project";

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
          <CreateApiKeyButton
            loading={creatingKey}
            onClick={handleCreateKey}
          />
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
        <CodeBlock code={INSTALL_SNIPPETS[framework]} language="bash" />
      </StepSection>

      <StepSection
        number={3}
        icon={<Settings2 className="h-4 w-4" />}
        title="Set environment variables"
        description="Point the SDK at your project and paste the API key you just created."
      >
        <ProviderTabs
          options={FRAMEWORKS}
          value={framework}
          onChange={setFramework}
        />
        <CodeBlock
          code={envSnippet(framework, projectName, API_URL)}
          language="bash"
        />
      </StepSection>

      <StepSection
        number={4}
        icon={<Bot className="h-4 w-4" />}
        title="Build and instrument your agent"
        description="Wire up the callback handler or adapter. The full agent run becomes one trace."
      >
        <ProviderTabs
          options={FRAMEWORKS}
          value={framework}
          onChange={setFramework}
        />
        <CodeBlock code={AGENT_SNIPPETS[framework]} language="python" />
      </StepSection>

      <NextSteps />
    </>
  );
}
