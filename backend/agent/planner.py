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
        re.search(
            r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
            text,
        )
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
            "bill processing",
        ],
    ):
        return "invoice_processing"

    product_intent = _contains_phrase(
        text,
        [
            "product",
            "products",
            "product catalog",
            "product catalogue",
            "item",
            "items",
            "inventory",
            "stock",
            "shopping",
            "purchase",
            "buy ",
            "price comparison",
            "compare prices",
            "compare their prices",
            "compare the price",
            "compare price",
            "cheapest",
            "lowest price",
            "most affordable",
            "available chocolate",
            "available protein",
            "available bars",
            "chocolate bar",
            "chocolate bars",
            "protein bar",
            "protein bars",
            "find alternatives",
            "search alternatives",
            "search for",
            "find available",
            "show available",
            "compare alternatives",
            "compare products",
            "find a product",
            "find products",
            "search products",
            "search for products",
            "product recommendation",
            "recommend a product",
            "recommend products",
            "which product",
            "which one should i buy",
        ],
    )

    if product_intent:
        return "product_recommendation"

    return "general_task"


def _deterministic_plan(goal: str) -> List[str]:
    task_type = _classify_goal(goal)
    return list(WORKFLOW_PLANS[task_type])


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
