"""Prompt templates for the PlanQuality metric.

Single-stage evaluation:
- **evaluate_plan_quality** -- score the intrinsic quality of the plan.
"""

import textwrap


class PlanQualityTemplate:
    """Stateless container for prompt-building class methods."""

    @staticmethod
    def evaluate_plan_quality(user_task: str, agent_plan: str) -> str:
        """Build the prompt to score the intrinsic quality of the plan."""
        return textwrap.dedent(f"""\
            Given the user's task and the agent's plan, score the intrinsic \
            quality of the plan (0.0-1.0).

            Criteria:
            - **Completeness**: Does the plan address all aspects of the task?
            - **Logical coherence**: Are steps ordered and structured sensibly?
            - **Optimality/efficiency**: Is the plan efficient, or could it be \
            streamlined?
            - **Level of detail**: Is the plan sufficiently detailed without \
            being overly verbose?
            - **Alignment with task**: Does the plan match the user's intent?

            Scoring guide:
            - 1.0 = Excellent plan; complete, coherent, optimal.
            - 0.75 = Good plan; minor flaws or suboptimal choices.
            - 0.5 = Adequate but flawed; works but has notable gaps.
            - 0.25 = Weak plan; significant issues.
            - 0.0 = Inadequate plan; does not address the task.

            Return **only** valid JSON with two keys: `score` and `reason`.

            User task:
            {user_task}

            Agent plan:
            {agent_plan}

            JSON:
        """)
