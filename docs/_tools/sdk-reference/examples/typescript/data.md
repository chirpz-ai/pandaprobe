```ts
import { SpanData, SpanKind, TraceData } from "pandaprobe";

const now = new Date();
const record = new TraceData({
  name: "lookup", startedAt: now, endedAt: now,
  spans: [new SpanData({ name: "policy", kind: SpanKind.TOOL, startedAt: now, endedAt: now })],
});
const payload = record.toApiDict();
console.log(payload.trace_id);
```
