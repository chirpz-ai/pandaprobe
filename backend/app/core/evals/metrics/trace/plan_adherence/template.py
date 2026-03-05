"""Prompt templates for the PlanAdherence metric.

Two-stage evaluation:
1. **extract_plan_from_trace** -- extract the explicit or implied plan from trace.
2. **evaluate_adherence** -- score how strictly execution followed the plan.
"""

import json
import textwrap
from typing import Any


class PlanAdherenceTemplate:
    """Stateless container for prompt-building class methods."""

    @staticmethod
    def extract_plan_from_trace(trace: dict[str, Any]) -> str:
        """Build the extraction prompt to get the plan the agent followed from trace.

        Extract the explicit or implied plan from trace reasoning/thought fields.
        Rules: every step must be supported by trace evidence, no hallucination,
        focus on intent. Return JSON with "plan" (list of strings).
        Return empty list if no plan found.
        """
        return textwrap.dedent(f"""\
            Given a nested workflow trace whose spans may be of type \
            `AGENT`, `TOOL`, `LLM`, `RETRIEVER`, or `OTHER`, extract the \
            explicit or implied plan the agent followed.

            Rules:
            - Every step must be supported by trace evidence (reasoning, thought, \
            or action fields). Do NOT hallucinate steps.
            - Focus on intent: what did the agent plan to do, in order?
            - If no plan can be inferred from the trace, return an empty list.
            - Return **only** valid JSON with a single key: `plan` (list of strings).

            Trace:
            {json.dumps(trace, indent=2, default=str)}

            JSON:
        """)

    @staticmethod
    def evaluate_adherence(
        user_task: str,
        agent_plan: str,
        execution_trace: dict[str, Any],
    ) -> str:
        """Build the prompt to score how strictly execution followed the plan."""
        return textwrap.dedent(f"""\
            Given the user's task, the agent's plan, and the full execution trace, \
            score how strictly the execution followed the plan (0.0-1.0).

            Rules:
            - Verify each plan step was executed.
            - Check for extraneous actions not in the plan.
            - Assess order consistency: were steps followed in the intended order?
            - Assess completeness: were all planned steps addressed?

            Scoring guide:
            - 1.0 = Perfect adherence; execution matches plan exactly.
            - 0.75 = Nearly all steps in order; minor deviations.
            - 0.5 = Partial adherence; some steps skipped or reordered.
            - 0.25 = Weak adherence; significant deviation from plan.
            - 0.0 = No adherence; execution bears little relation to plan.

            Return **only** valid JSON with two keys: `score` and `reason`.

            User task:
            {user_task}

            Agent plan:
            {agent_plan}

            Execution trace:
            {json.dumps(execution_trace, indent=2, default=str)}

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
            "extract_plan": cls.extract_plan_from_trace(sample_trace),
            "score": cls.evaluate_adherence(
                user_task="<extracted_task>", agent_plan="<extracted_plan>", execution_trace=sample_trace
            ),
        }
