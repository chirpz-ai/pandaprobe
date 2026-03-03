"""Prompt templates for the ToolCorrectness metric.

Two-stage evaluation:
1. **extract** -- ask the LLM to extract user input, tool calls, and available
   tools from the trace.
2. **score** -- ask the LLM judge to score tool selection quality.
"""

import json
import textwrap
from typing import Any


class ToolCorrectnessTemplate:
    """Stateless container for prompt-building class methods."""

    @staticmethod
    def extract_tool_usage(trace: dict[str, Any]) -> str:
        """Build the extraction prompt from a serialised trace dict."""
        return textwrap.dedent(f"""\
            Given a nested workflow trace whose spans may be of type \
            `AGENT`, `TOOL`, `LLM`, `RETRIEVER`, or `OTHER`, extract:

            1. **user_input** -- the user's original task or goal from the \
            root span's input.
            2. **tools_called** -- a list of tool calls made during the run. \
            For each TOOL-kind span, include an object with "name" (the tool \
            name) and "parameters" (the arguments passed, from input or metadata).
            3. **available_tools** -- a list of all unique tools that were \
            available in this context. For each, include "name" and "description" \
            (infer from span metadata, tool definitions, or usage context).

            Return **only** valid JSON with keys: `user_input`, `tools_called`, \
            and `available_tools`.

            Trace:
            {json.dumps(trace, indent=2, default=str)}

            JSON:
        """)

    @staticmethod
    def score_tool_selection(
        user_input: str,
        tools_called: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
    ) -> str:
        """Build the scoring prompt for tool selection quality."""
        tools_called_str = json.dumps(tools_called, indent=2)
        available_tools_str = json.dumps(available_tools, indent=2)
        return textwrap.dedent(f"""\
            You are judging whether an AI agent selected the right tools for \
            its task. Consider:

            - **Correct selection**: Did the agent use tools that were \
            appropriate and sufficient for the user's goal?
            - **Over-selection**: Did the agent call unnecessary or redundant \
            tools?
            - **Under-selection**: Did the agent miss tools that would have \
            better served the task?
            - **Mis-selection**: Did the agent choose wrong or irrelevant tools?

            Return a JSON object with two keys:
            - `score`: a float between 0 and 1 (1 = perfect tool selection).
            - `reason`: a clear explanation of the score.

            User's task:
            {user_input}

            Tools called:
            {tools_called_str}

            Available tools:
            {available_tools_str}

            JSON:
        """)
