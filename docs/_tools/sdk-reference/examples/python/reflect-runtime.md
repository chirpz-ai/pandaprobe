This function wraps an already configured native agent or an async `Invocation` callback. The agent must include its tracing integration; use a [framework guide](/reflect/frameworks) to construct one with Reflect tooling.

```python
from pandaprobe import Client
from pandaprobe.reflect import Reflect, ReflectConfig


async def run_support(build_agent):
    client = Client()
    try:
        async with Reflect(client, config=ReflectConfig(workspace="./agent-memory")) as reflect:
            agent = build_agent(reflect, client)  # Your traced native factory.
            result = await reflect.run(agent, "Help with my return.", session_id="customer-42")
            for proposal in reflect.proposals():
                print(proposal.id, proposal.status)
            return result
    finally:
        client.shutdown()
```
