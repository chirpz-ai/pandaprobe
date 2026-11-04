```ts
import { Client } from "pandaprobe";

const client = new Client(); // Resolves PANDAPROBE_* credentials.
try {
  const trace = client.trace("support", {
    input: { messages: [{ role: "user", content: "Hello" }] },
  });
  await trace.run(async current => {
    current.setOutput({ messages: [{ role: "assistant", content: "How can I help?" }] });
  });
  client.score(trace.traceId, "review", "1", { reason: "Reviewed by the application" });
} finally {
  await client.shutdown();
}
```
