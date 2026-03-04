"""Prompt templates for the StepEfficiency metric.

Two-stage evaluation:
1. **extract_task_from_trace** -- identify the user's original goal from the trace.
2. **get_execution_efficiency** -- score how efficiently the agent executed the task.
"""

import json
import textwrap
from typing import Any


class StepEfficiencyTemplate:
    """Stateless container for prompt-building class methods."""

    @staticmethod
    def extract_task_from_trace(trace: dict[str, Any]) -> str:
        """Build the extraction prompt to identify the user's original goal from the trace."""
        return textwrap.dedent(f"""\
            Given a nested workflow trace whose spans may be of type \
            `AGENT`, `TOOL`, `LLM`, `RETRIEVER`, or `OTHER`, identify the \
            user's original goal.

            Focus on the root-level input. Extract what the user explicitly \
            asked for or wanted to achieve. Be agent-agnostic: express the \
            goal from the user's perspective, not the agent's actions.

            Do NOT describe what the agent did. Only describe what the user \
            wanted.

            IMPORTANT: Return **only** valid JSON with a single key: `task`.

            Trace:
            {json.dumps(trace, indent=2, default=str)}

            JSON:
        """)

    @staticmethod
    def get_execution_efficiency(task: str, trace: dict[str, Any]) -> str:
        """Build the prompt to score how efficiently the agent executed the task."""
        return textwrap.dedent(f"""\
            Given the user's task and the full trace of how an agent executed it, \
            score how efficiently (minimally) the agent accomplished the task.

            Evaluate:
            - Unnecessary actions: Did the agent take steps that were not needed?
            - Redundant steps: Did the agent repeat or duplicate work?
            - Minimal action principle: Could the task have been done with fewer steps?
            - Resource economy: Did the agent use more tools, calls, or iterations than necessary?

            Scoring guide:
            - 1.0 = Perfectly efficient; minimal steps, no redundancy.
            - 0.75 = Mostly efficient with minor redundancy.
            - 0.5 = Noticeable inefficiency; some unnecessary steps.
            - 0.25 = Multiple unnecessary actions; clearly inefficient.
            - 0.0 = Highly inefficient; many redundant or superfluous steps.

            Return **only** valid JSON with two keys: `score` and `reason`.

            Task:
            {task}

            Trace:
            {json.dumps(trace, indent=2, default=str)}

            JSON:
        """)

    @classmethod
    def get_prompt_preview(cls) -> dict[str, str]:
        """Return prompt previews with sample placeholder data."""
        sample_trace = {
            "trace_id": "TRACE_ID",
            "name": "sample-trace",
            "spans": [
                {
                    "name": "agent",
                    "kind": "AGENT",
                    "input": {"task": "USER_TASK"},
                    "output": {"result": "AGENT_OUTPUT"},
                }
            ],
        }
        return {
            "extract_task": cls.extract_task_from_trace(sample_trace),
            "score": cls.get_execution_efficiency(task="<extracted_task>", trace=sample_trace),
        }
