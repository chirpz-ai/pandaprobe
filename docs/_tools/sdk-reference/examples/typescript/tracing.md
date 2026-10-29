```ts
import { Client, session, user } from "pandaprobe";

const client = new Client();
try {
  await session("customer-42", () => user("user-7", async () => {
    const capture = client.captureTraces();
    await capture.run(async () => {
      await client.trace("lookup").run(async trace => {
        await trace.span("policy", { kind: "TOOL" }).run(async span => {
          span.setInput({ order_id: "ORDER-101" });
          span.setOutput({ refundable: "merchandise" });
        });
      });
    });
    console.log(capture.traceIds); // Submission IDs, not persistence confirmation.
  }));
} finally {
  await client.shutdown();
}
```
