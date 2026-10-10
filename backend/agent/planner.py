import logging
import re
from typing import List, Optional

from agent.state import AgentState
from agent.reasoning import AgentReasoner

logger = logging.getLogger(__name__)

SUPPORTED_STEPS = {
    "search_alternatives",
    "compare_alternatives",
    "inspect_invoice",
    "extract_invoice_fields",
    "verify_invoice",
    "request_human_approval",
    "reason_about_task",
    "verify_result",
    "complete_task",
}

WORKFLOW_PLANS = {
    "product_recommendation": [
        "search_alternatives",
        "compare_alternatives",
        "verify_result",
        "request_human_approval",
        "complete_task",
    ],
    "invoice_processing": [
        "inspect_invoice",
        "extract_invoice_fields",
        "verify_invoice",
        "request_human_approval",
        "complete_task",
    ],
    "general_task": [
        "reason_about_task",
        "verify_result",
        "complete_task",
    ],
}


def _contains_phrase(text: str, phrases: List[str]) -> bool:
    return any(
        re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text)
        for phrase in phrases
    )


def _classify_goal(goal: str) -> str:
    text = re.sub(r"\s+", " ", goal.lower()).strip()

    if _contains_phrase(
        text,
        [
            "invoice",
            "invoices",
            "vendor bill",
            "supplier bill",
            "process invoice",
            "extract invoice",
        ],
    ):
        return "invoice_processing"

    if _contains_phrase(
        text,
        [
            "protein bar",
            "protein bars",
            "search products",
            "find a product",
            "find products",
            "product recommendation",
            "search for products",
            "find alternatives",
        ],
    ):
        return "product_recommendation"

    return "general_task"


def _deterministic_plan(goal: str) -> List[str]:
    return list(WORKFLOW_PLANS[_classify_goal(goal)])


def create_plan(
    goal: str,
    reasoner: Optional[AgentReasoner] = None,
) -> List[str]:
    if not isinstance(goal, str) or not goal.strip():
        return list(WORKFLOW_PLANS["general_task"])

    task_type = _classify_goal(goal)

    if task_type != "invoice_processing":
        return _deterministic_plan(goal)

    try:
        active_reasoner = reasoner or AgentReasoner()
        interpretation = active_reasoner.interpret_goal(goal)

        if interpretation.get("success"):
            workflow = interpretation.get("workflow")
            candidate = WORKFLOW_PLANS.get(workflow)

            if (
                workflow == task_type
                and candidate
                and all(step in SUPPORTED_STEPS for step in candidate)
            ):
                return list(candidate)

    except Exception:
        logger.exception(
            "LLM-assisted planning failed; using deterministic planning."
        )

    return _deterministic_plan(goal)


def initialize_plan(
    state: AgentState,
    reasoner: Optional[AgentReasoner] = None,
) -> AgentState:
    state.plan = create_plan(state.goal, reasoner=reasoner)
    state.current_step = 0
    state.status = "planned"
    return state

