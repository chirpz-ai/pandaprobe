```python
from pandaprobe import Client

client = Client()  # Resolves PANDAPROBE_* credentials.
try:
    with client.trace("support", input={"messages": [{"role": "user", "content": "Hello"}]}) as trace:
        trace.set_output({"messages": [{"role": "assistant", "content": "How can I help?"}]})
    client.score(trace.trace_id, "review", "1", reason="Reviewed by the application")
finally:
    client.shutdown()
```
