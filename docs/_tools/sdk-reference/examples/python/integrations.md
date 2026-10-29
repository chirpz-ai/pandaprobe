```python
from pandaprobe import Client
from pandaprobe.integrations.langchain import LangChainCallbackHandler

client = Client()
handler = LangChainCallbackHandler(client=client)
invocation_config = {"callbacks": [handler]}
# Pass invocation_config as config=... to your native agent invocation.
# Keep client alive for the agent's lifetime, then call client.shutdown().
```

Full native setup examples are in the [tracing integrations](/tracing/integrations/overview) and [Reflect integrations](/reflect/frameworks).
