```python
from pandaprobe.reflect import Rule

rule = Rule(
    path="refunds/standard.md",
    text="# Standard returns\nApplies to: standard return refunds\nExclude outbound shipping.\n",
)
print(rule.scope, rule.applicability, rule.version)
```

Constructing a rule does not publish it. Agent-authored filesystem changes become proposals; independent validation decides acceptance.
