```python
import pandaprobe
from pandaprobe import Client

client = Client()
try:
    with pandaprobe.session("customer-42"), pandaprobe.user("user-7"):
        with client.capture_traces() as capture:
            with client.trace("lookup") as trace:
                with trace.span("policy", kind="TOOL") as span:
                    span.set_input({"order_id": "ORDER-101"})
                    span.set_output({"refundable": "merchandise"})
        print(capture.trace_ids)  # Submission IDs, not a persistence confirmation.
finally:
    client.shutdown()
```
