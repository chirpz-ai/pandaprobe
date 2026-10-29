```ts
import { Client } from "pandaprobe";
import { LangChainCallbackHandler } from "pandaprobe/integrations/langchain";

const client = new Client();
const handler = new LangChainCallbackHandler({ client });
const invocationConfig = { callbacks: [handler] };
// Pass invocationConfig to your native agent invocation.
// Keep client alive for the agent's lifetime, then await client.shutdown().
```

Full native setup examples are in the [tracing integrations](/tracing/integrations/overview) and [Reflect integrations](/reflect/frameworks).
