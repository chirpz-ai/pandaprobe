```python
from datetime import datetime, timezone
from pandaprobe.schemas import SpanData, SpanKind, TraceData

now = datetime.now(timezone.utc)
record = TraceData(
    name="lookup", started_at=now, ended_at=now,
    spans=[SpanData(name="policy", kind=SpanKind.TOOL, started_at=now, ended_at=now)],
)
payload = record.to_api_dict()
print(payload["trace_id"])
```
