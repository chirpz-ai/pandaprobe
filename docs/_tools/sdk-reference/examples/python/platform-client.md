This creates a real evaluation run for an existing trace. `trace_id` is a persisted task trace UUID from the same project.

```python
from pandaprobe import Client
from pandaprobe.api import PlatformClient


async def evaluate(trace_id: str):
    client = Client()
    try:
        async with PlatformClient(client) as api:
            await api.traces.wait_visible(trace_id)
            run = await api.evaluations.create([trace_id], ["task_completion"])
            return await api.evaluations.wait(
                run.id, trace_ids=[trace_id], metrics=["task_completion"],
            )
    finally:
        client.shutdown()
```
