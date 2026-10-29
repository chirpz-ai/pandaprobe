"""Prompt templates for the TaskCompletion metric.

Two-stage evaluation:
1. **extract** -- ask the LLM to identify the task and factual outcome
   from the trace.
2. **verdict** -- ask the LLM to compare task vs. outcome and score it.
"""

import json
import textwrap
from typing import Any

from app.core.evals.metrics.utils import REFLECT_TOOL_GUIDANCE


class TaskCompletionTemplate:
    """Stateless container for prompt-building class methods."""

    @staticmethod
    def extract_task_and_outcome(trace: dict[str, Any]) -> str:
        """Build the extraction prompt from a serialised trace dict."""
        return textwrap.dedent(f"""\
            Given a nested workflow trace whose spans may be of type \
            `AGENT`, `TOOL`, `LLM`, `RETRIEVER`, or `OTHER`, identify:

            1. **task** -- the objective expressed by the user in the \
            root span's input.
            2. **outcome** -- a strictly factual description of what the \
            system did, derived only from the trace.

            Do **not** include subjective language such as "successfully" \
            or "efficiently".  Enumerate each relevant action the trace \
            shows, in plain language.

            {REFLECT_TOOL_GUIDANCE}
            Report Reflect rule and memory operations separately from task actions;
            preserve failed task attempts.

            IMPORTANT: Return **only** valid JSON with two keys: \
            `task` and `outcome`.

            Trace:
            {json.dumps(trace, indent=2, default=str)}

            JSON:
        """)

    @staticmethod
    def generate_verdict(task: str, actual_outcome: str) -> str:
        """Build the verdict prompt that scores task completion."""
        return textwrap.dedent(f"""\
            Given the task (desired outcome) and the actual achieved \
            outcome, score how well the actual outcome fulfils the task.

            A trace may cover only part of a longer, multi-step effort. Score the \
            progress the outcome actually shows toward the task; reserve 0.0 for \
            an outcome that shows no progress or contradicts the task, not for one \
            that is merely incomplete.

            Reflect rule and memory operations alone show no task progress. A proposed
            rule is not proof that a task failure was corrected.

            Return a JSON object with two keys:
            - `verdict`: a float between 0 and 1 (1 = perfectly achieved).
            - `reason`: a one-sentence explanation for the score.

            Example:
            {{
                "verdict": 0.85,
                "reason": "The system addressed flights and hotels but \
            did not include sightseeing options."
            }}

            Task:
            {task}

            Actual outcome:
            {actual_outcome}

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
            "extract": cls.extract_task_and_outcome(sample_trace),
            "score": cls.generate_verdict(task="<extracted_task>", actual_outcome="<extracted_outcome>"),
        }
