"""Prompt templates for the ArgumentCorrectness metric.

Three-stage evaluation:
1. **extract** -- ask the LLM to identify user input and all tool calls
   (name, input_parameters, reasoning) from the trace.
2. **verdicts** -- for each tool call, determine if parameters correctly
   address the user's task.
3. **reason** -- produce a concise overall explanation given the score
   and list of incorrect-call reasons.
"""

import json
import textwrap
from typing import Any


class ArgumentCorrectnessTemplate:
    """Stateless container for prompt-building class methods."""

    @staticmethod
    def extract_tool_calls(trace: dict[str, Any]) -> str:
        """Build the extraction prompt from a serialised trace dict."""
        return textwrap.dedent(f"""\
            Given a nested workflow trace whose spans may be of type \
            `AGENT`, `TOOL`, `LLM`, `RETRIEVER`, or `OTHER`, extract:

            1. **user_input** -- the objective expressed by the user in the \
            root span's input (trace.input or the first user message).
            2. **tool_calls** -- a list of every tool invocation. For each \
            tool call, include: `name` (tool name), `parameters` (the \
            input/arguments passed to the tool, e.g. from span.input, \
            input_parameters, or arguments), and `reasoning` (any \
            reasoning or context from the trace, if available).

            Look for spans with kind `TOOL` and any spans whose input \
            contains tool_calls, function_call, or similar structures.

            Return **only** valid JSON with two keys: `user_input` (string) \
            and `tool_calls` (array of objects with name, parameters, reasoning).

            Trace:
            {json.dumps(trace, indent=2, default=str)}

            JSON:
        """)

    @staticmethod
    def generate_verdicts(user_input: str, tool_calls: list[Any]) -> str:
        """Build the verdict prompt that scores each tool call's arguments."""
        return textwrap.dedent(f"""\
            For each tool call below, determine whether the input parameters \
            correctly address the user's task. Consider: Are the right values \
            passed? Are required parameters present? Do they match the user's \
            intent?

            Return a JSON object with a single key `verdicts`: an array of \
            objects. Each object has:
            - `verdict`: "yes" if the arguments are correct, "no" otherwise.
            - `reason`: (optional) a brief explanation when verdict is "no".

            The order of verdicts must match the order of tool_calls.

            User's task:
            {user_input}

            Tool calls:
            {json.dumps(tool_calls, indent=2, default=str)}

            JSON:
        """)

    @staticmethod
    def generate_reason(
        incorrect_reasons: list[str],
        user_input: str,
        score: float,
    ) -> str:
        """Build the reason prompt for the overall score."""
        reasons_text = "\n".join(f"- {r}" for r in incorrect_reasons) if incorrect_reasons else "(none)"
        return textwrap.dedent(f"""\
            Given the user's task, the overall argument correctness score, \
            and the reasons for any incorrect tool calls, produce a concise \
            one- or two-sentence explanation for the score.

            Return **only** valid JSON with a single key: `reason` (string).

            User's task:
            {user_input}

            Score: {score:.2f}

            Reasons for incorrect calls:
            {reasons_text}

            JSON:
        """)

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return prompt previews with sample placeholder data."""
        sample_trace = {"trace_id": "TRACE_ID", "name": "sample-trace", "spans": [{"name": "tool-call", "kind": "TOOL", "input": {"param": "value"}}]}
        return {
            "extract": cls.extract_tool_calls(sample_trace),
            "verdicts": cls.generate_verdicts(user_input="<extracted_user_input>", tool_calls=[{"name": "<tool>", "parameters": {"key": "value"}, "reasoning": "<reasoning>"}]),
            "reason": cls.generate_reason(incorrect_reasons=["<reason_for_incorrect_call>"], user_input="<extracted_user_input>", score=0.75),
        }
