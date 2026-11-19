// Runnable examples aligned with the tracing quickstart and framework guides.
// Keep install commands and examples together when updating SDK integrations.
import { DOCS_QUICKSTART_URL, DOCS_URL } from "@/lib/utils/constants";

export type SdkLanguage = "python" | "typescript";
export type TraceProvider = "openai" | "anthropic" | "gemini";
export type AgentFramework = "deepagents" | "langgraph" | "vercel-ai";

interface QuickstartExample {
  install: string;
  code: string;
}

interface QuickstartGuide {
  label: string;
  docsUrl: string;
  python?: QuickstartExample;
  typescript: QuickstartExample;
}

export function getQuickstartExample(
  guide: QuickstartGuide,
  preferred: SdkLanguage,
) {
  if (preferred === "python" && guide.python) {
    return { ...guide.python, language: "python" as const };
  }
  return { ...guide.typescript, language: "typescript" as const };
}

export const TRACE_EXAMPLES: Record<TraceProvider, QuickstartGuide> = {
  openai: {
    label: "OpenAI",
    docsUrl: DOCS_QUICKSTART_URL,
    python: {
      install: `pip install "pandaprobe[openai]"`,
      code: `import pandaprobe
from pandaprobe.wrappers import wrap_openai
from openai import OpenAI

client = wrap_openai(OpenAI())

response = client.chat.completions.create(
    model="gpt-5.4",
    messages=[{"role": "user", "content": "What is agent engineering?"}],
)

print(response.choices[0].message.content)

pandaprobe.flush()`,
    },
    typescript: {
      install: `npm install pandaprobe openai`,
      code: `import OpenAI from "openai";
import { flush } from "pandaprobe";
import { wrapOpenAI } from "pandaprobe/wrappers/openai";

const client = wrapOpenAI(new OpenAI());
const response = await client.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: "What is PandaProbe?" }],
});

console.log(response.choices[0]?.message.content);
await flush();`,
    },
  },
  anthropic: {
    label: "Anthropic",
    docsUrl: DOCS_QUICKSTART_URL,
    python: {
      install: `pip install "pandaprobe[anthropic]"`,
      code: `import pandaprobe
from pandaprobe.wrappers import wrap_anthropic
from anthropic import Anthropic

client = wrap_anthropic(Anthropic())

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "What is agent engineering?"}],
)

print(response.content[0].text)

pandaprobe.flush()`,
    },
    typescript: {
      install: `npm install pandaprobe @anthropic-ai/sdk`,
      code: `import Anthropic from "@anthropic-ai/sdk";
import { flush } from "pandaprobe";
import { wrapAnthropic } from "pandaprobe/wrappers/anthropic";

const client = wrapAnthropic(new Anthropic());
const response = await client.messages.create({
  model: "claude-sonnet-5",
  max_tokens: 1024,
  messages: [{ role: "user", content: "What is PandaProbe?" }],
});

const text = response.content.find((block) => block.type === "text");
console.log(text?.type === "text" ? text.text : "");
await flush();`,
    },
  },
  gemini: {
    label: "Google Gemini",
    docsUrl: DOCS_QUICKSTART_URL,
    python: {
      install: `pip install "pandaprobe[gemini]"`,
      code: `import pandaprobe
from pandaprobe.wrappers import wrap_gemini
from google import genai

client = wrap_gemini(genai.Client())

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="What is agent engineering?",
)

print(response.text)

pandaprobe.flush()`,
    },
    typescript: {
      install: `npm install pandaprobe @google/genai`,
      code: `import { GoogleGenAI } from "@google/genai";
import { flush } from "pandaprobe";
import { wrapGemini } from "pandaprobe/wrappers/gemini";

const client = wrapGemini(new GoogleGenAI({ apiKey: process.env.GOOGLE_API_KEY }));
const response = await client.models.generateContent({
  model: "gemini-3.8-flash",
  contents: "What is PandaProbe?",
});

console.log(response.text);
await flush();`,
    },
  },
};

export const AGENT_EXAMPLES: Record<AgentFramework, QuickstartGuide> = {
  deepagents: {
    label: "DeepAgents",
    docsUrl: `${DOCS_URL}/tracing/integrations/deepagents`,
    python: {
      install: `pip install "pandaprobe[deepagents]" langchain-openai`,
      code: `from deepagents import create_deep_agent
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
    },
    typescript: {
      install: `npm install pandaprobe deepagents langchain @langchain/core @langchain/openai @langchain/langgraph @langchain/langgraph-checkpoint @langchain/langgraph-sdk langsmith`,
      code: `import { ChatOpenAI } from "@langchain/openai";
import { createDeepAgent } from "deepagents";
import { flush } from "pandaprobe";
import { DeepAgentsCallbackHandler } from "pandaprobe/integrations/deepagents";

const agent = createDeepAgent({
  model: new ChatOpenAI({ model: "gpt-5.6-terra", useResponsesApi: true }),
  tools: [],
  systemPrompt: "You are a helpful research assistant. Be concise.",
});

const handler = new DeepAgentsCallbackHandler({ tags: ["deepagents"] });
const result = await agent.invoke(
  { messages: [{ role: "user", content: "What is the capital of France?" }] },
  { callbacks: [handler] },
);

console.log(result.messages.at(-1)?.content);
await flush();`,
    },
  },
  langgraph: {
    label: "LangGraph",
    docsUrl: `${DOCS_URL}/tracing/integrations/langgraph`,
    python: {
      install: `pip install "pandaprobe[langgraph]" langchain-openai`,
      code: `from typing import Annotated

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
    },
    typescript: {
      install: `npm install pandaprobe @langchain/langgraph @langchain/openai @langchain/core`,
      code: `import { END, MessagesAnnotation, START, StateGraph } from "@langchain/langgraph";
import { ChatOpenAI } from "@langchain/openai";
import { flush } from "pandaprobe";
import { LangGraphCallbackHandler } from "pandaprobe/integrations/langgraph";

const llm = new ChatOpenAI({ model: "gpt-4o-mini" });
const graph = new StateGraph(MessagesAnnotation)
  .addNode("chatbot", async (state) => ({ messages: [await llm.invoke(state.messages)] }))
  .addEdge(START, "chatbot")
  .addEdge("chatbot", END)
  .compile();

const handler = new LangGraphCallbackHandler({ tags: ["chatbot", "example"] });
const result = await graph.invoke(
  { messages: [{ role: "user", content: "What is the capital of France?" }] },
  { callbacks: [handler] },
);

console.log(result.messages.at(-1)?.content);
await flush();`,
    },
  },
  "vercel-ai": {
    label: "Vercel AI",
    docsUrl: `${DOCS_URL}/tracing/integrations/vercel-ai`,
    typescript: {
      install: `npm install pandaprobe ai @ai-sdk/openai`,
      code: `import { openai } from "@ai-sdk/openai";
import { jsonSchema, tool, ToolLoopAgent, wrapLanguageModel } from "ai";
import { Client } from "pandaprobe";
import {
  pandaProbeMiddleware,
  wrapVercelAgent,
} from "pandaprobe/integrations/vercel-ai";

const client = new Client();
const model = wrapLanguageModel({
  model: openai("gpt-5.6-terra"),
  middleware: pandaProbeMiddleware(),
});
const TracedAgent = wrapVercelAgent(ToolLoopAgent, { client });

try {
  const agent = new TracedAgent({
    model,
    instructions: "Use the weather tool to answer. Explain that its data is a demo.",
    tools: {
      getWeather: tool({
        description: "Get example weather for a city (demo data).",
        inputSchema: jsonSchema<{ city: string }>({
          type: "object",
          properties: { city: { type: "string" } },
          required: ["city"],
          additionalProperties: false,
        }),
        execute: async ({ city }) => ({ city, forecast: "Sunny, 22°C (demo data)" }),
      }),
    },
  });
  const result = await agent.generate({ prompt: "What is the weather in London?" });
  console.log(result.text);
} finally {
  await client.shutdown();
}`,
    },
  },
};
