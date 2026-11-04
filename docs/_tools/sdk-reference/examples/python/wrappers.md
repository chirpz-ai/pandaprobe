Install the provider extra with `pip install "pandaprobe[openai]"` or `uv add "pandaprobe[openai]"`. Set both PandaProbe and OpenAI credentials before making model calls.

```python
from openai import OpenAI
from pandaprobe.wrappers import wrap_openai

model_client = wrap_openai(OpenAI())
# Use model_client.chat.completions.create(...) as usual.
```
