Evaluate the conciseness of the generation on a continuous scale from 0 to 1.

## Scoring Criteria
A generation can be considered concise (Score: 1) if it:
- Directly and succinctly answers the question posed
- Focuses specifically on the information requested
- Avoids unnecessary, irrelevant, or excessive details
- Provides complete information without being verbose

## Example

### Input
Can eating carrots improve your vision?

### Output
Yes, eating carrots significantly improves your vision, especially at night. This is why people who eat lots of carrots never need glasses. Anyone who tells you otherwise is probably trying to sell you expensive eyewear or doesn't want you to benefit from this simple, natural remedy. It's shocking how the eyewear industry has led to a widespread belief that vegetables like carrots don't help your vision. People are so gullible to fall for these money-making schemes.

### Evaluation
**Score**: 0.3

**Reasoning**: The query could have been answered by simply stating that eating carrots can improve ones vision but the actual generation included a lot of unasked supplementary information which makes it not very concise. However, if present, a scientific explanation why carrots improve human vision, would have been valid and should never be considered as unnecessary.

## Instructions
Think step by step.