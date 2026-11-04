```ts
import { Rule } from "pandaprobe/reflect";

const rule = new Rule({
  path: "refunds/standard.md",
  text: "# Standard returns\nApplies to: standard return refunds\nExclude outbound shipping.\n",
});
console.log(rule.scope, rule.applicability, rule.version);
```

Constructing a rule does not publish it. Agent-authored filesystem changes become proposals; independent validation decides acceptance.
