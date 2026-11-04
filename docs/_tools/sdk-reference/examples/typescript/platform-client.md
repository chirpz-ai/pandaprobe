This creates a real evaluation run for an existing trace. `traceId` is a persisted task trace UUID from the same project.

```ts
import { Client } from "pandaprobe";
import { PlatformClient } from "pandaprobe/api";

async function evaluate(traceId: string) {
  const client = new Client();
  const api = new PlatformClient(client);
  try {
    await api.traces.waitVisible(traceId);
    const run = await api.evaluations.create([traceId], ["task_completion"]);
    return await api.evaluations.wait(run.id, {
      traceIds: [traceId], metrics: ["task_completion"],
    });
  } finally {
    await api.close();
    await client.shutdown();
  }
}
```
