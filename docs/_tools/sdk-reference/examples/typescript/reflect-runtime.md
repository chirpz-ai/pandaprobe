This function accepts your native agent builder. It must include the tracing integration and use `reflect.agent(...)` to attach Reflect tooling; see the [framework guides](/reflect/frameworks).

```ts
import { Client } from "pandaprobe";
import { Reflect as ReflectRuntime, type NativeAgent } from "pandaprobe/reflect";

async function runSupport(
  buildAgent: (reflect: ReflectRuntime, client: Client) => Promise<NativeAgent>,
) {
  const client = new Client();
  const reflect = new ReflectRuntime(client, { config: { workspace: "./agent-memory" } });
  try {
    const agent = await buildAgent(reflect, client);
    const result = await reflect.run(agent, "Help with my return.", { sessionId: "customer-42" });
    for (const proposal of reflect.proposals()) console.log(proposal.id, proposal.status);
    return result;
  } finally {
    await reflect.close();
    await client.shutdown();
  }
}
```
