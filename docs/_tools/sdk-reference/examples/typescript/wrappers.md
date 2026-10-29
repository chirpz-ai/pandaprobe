Install `pandaprobe` and `openai` with npm, yarn, or pnpm. Set both PandaProbe and OpenAI credentials before making model calls.

```ts
import OpenAI from "openai";
import { wrapOpenAI } from "pandaprobe/wrappers/openai";

const modelClient = wrapOpenAI(new OpenAI());
// Use modelClient.chat.completions.create(...) as usual.
```
