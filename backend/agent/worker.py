from copy import deepcopy
from typing import Any, Dict, Optional

from agent.state import AgentState
from agent.planner import initialize_plan, _classify_goal
from agent.executor import AgentExecutor
from agent.observer import AgentObserver
from agent.recovery import AgentRecovery
from agent.comparator import ProductComparator
from agent.approval import ApprovalManager
from agent.verifier import AgentVerifier
from agent.requirement_extractor import RequirementExtractor
from agent.general_executor import GeneralReasoningExecutor

import tools.product_tool
import tools.ocr_tool
import tools.invoice_tool


class AgentWorker:
    """Execute general-purpose, product-search, and invoice workflows."""

    MAX_ITERATIONS = 20

    TOOL_STEPS = {
        "inspect_product",
        "search_alternatives",
        "inspect_invoice",
        "extract_invoice_fields",
    }

    def __init__(self):
        self.requirement_extractor = RequirementExtractor()
        self.executor = AgentExecutor()
        self.observer = AgentObserver()
        self.recovery = AgentRecovery()
        self.comparator = ProductComparator()
        self.approval_manager = ApprovalManager()
        self.verifier = AgentVerifier()
        self.general_executor = GeneralReasoningExecutor()

    @staticmethod
    def _task_type(goal: str) -> str:
        return _classify_goal(goal)

    @staticmethod
    def _latest_observation(
        state: AgentState,
        observation_type: str,
    ):
        for observation in reversed(state.observations):
            if observation.get("type") == observation_type:
                return observation.get("data", {})
        return None

    def _tool_input_for_step(
        self,
        state: AgentState,
        step: Optional[str],
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if step == "inspect_invoice":
            return {"file_path": file_path} if file_path else {}

        if step == "extract_invoice_fields":
            observation = self._latest_observation(
                state,
                "invoice_ocr_text",
            )
            return {
                "text": observation.get("text", "") if observation else ""
            }

        return dict(state.constraints or {})

    def run(
        self,
        goal: str,
        file_path: Optional[str] = None,
    ) -> AgentState:
        state = AgentState(goal=goal)
        task_type = self._task_type(goal)

        state.approval_required = False
        state.approval_status = "pending"

        try:
            state.constraints = self.requirement_extractor.extract(goal)
        except Exception as exc:
            state.add_error(
                source="requirement_extractor",
                message=str(exc),
            )
            state.status = "failed"
            return state

        try:
            initialize_plan(state)
        except Exception as exc:
            state.add_error(source="planner", message=str(exc))
            state.status = "failed"
            return state

        tool_input = self._tool_input_for_step(
            state,
            state.current_plan_step,
            file_path,
        )

        for _ in range(self.MAX_ITERATIONS):
            step = state.current_plan_step

            if step is None:
                break

            if state.approval_required:
                state.status = "waiting_for_approval"
                return state

            if step == "understand_requirements":
                state.add_observation(
                    "requirements",
                    {"constraints": dict(state.constraints or {})},
                )
                state.next_step()
                continue

            if step == "reason_about_task":
                if task_type != "general_task":
                    state.add_error(
                        source="worker",
                        message="General reasoning is not valid for this workflow.",
                    )
                    state.status = "failed"
                    return state

                result = self.general_executor.execute(state.goal)

                if not result.get("success"):
                    state.add_error(
                        source="general_executor",
                        message=result.get("error", "Reasoning failed."),
                    )
                    state.status = "failed"
                    return state

                state.add_observation("general_reasoning", result)
                state.final_result = {
                    "goal": state.goal,
                    "task_type": "general_task",
                    "summary": result.get("summary", ""),
                    "answer": result.get("answer", ""),
                    "reasoning": result.get("reasoning", []),
                    "assumptions": result.get("assumptions", []),
                    "limitations": result.get("limitations", []),
                    "confidence": result.get("confidence", "medium"),
                    "model": result.get("model"),
                }
                state.next_step()
                continue

            if step in self.TOOL_STEPS:
                result = self.executor.execute_current_step(state, tool_input)
                observation = self.observer.observe(state, result)
                status = observation.get("status")

                if status == "success":
                    state.retry_count = 0

                    if step == "inspect_invoice":
                        text = (
                            result.get("text", "")
                            if isinstance(result, dict)
                            else ""
                        )
                        state.add_observation(
                            "invoice_ocr_text",
                            {"text": text},
                        )
                        tool_input = {"text": text}

                    elif step == "extract_invoice_fields":
                        state.add_observation(
                            "invoice_fields",
                            result if isinstance(result, dict) else {},
                        )

                    state.next_step()
                    continue

                if status in {"no_results", "failure"}:
                    recovery = self.recovery.recover(state, observation)
                    action = recovery.get("action")

                    if action == "relax_constraints":
                        self._relax_constraints(state)
                        tool_input = self._tool_input_for_step(
                            state, step, file_path
                        )
                        continue

                    if action == "retry":
                        tool_input = self._tool_input_for_step(
                            state, step, file_path
                        )
                        continue

                    if action == "replan":
                        self._replan(state)
                        tool_input = self._tool_input_for_step(
                            state, state.current_plan_step, file_path
                        )
                        continue

                    state.add_error(
                        source="worker",
                        message=observation.get(
                            "message",
                            "Tool execution failed.",
                        ),
                    )
                    state.status = "failed"
                    return state

                state.add_error(
                    source="worker",
                    message=f"Unexpected tool status: {status}",
                )
                state.status = "failed"
                return state

            if step == "compare_alternatives":
                if task_type != "product_recommendation":
                    state.add_error(
                        source="worker",
                        message="Product comparison is not valid for this task.",
                    )
                    state.status = "failed"
                    return state

                comparison = self._compare_products(state)

                if not comparison.get("success"):
                    state.add_error(
                        source="comparator",
                        message=comparison.get(
                            "message",
                            "Product comparison failed.",
                        ),
                    )
                    state.status = "failed"
                    return state

                state.add_observation("comparison", comparison)
                self._create_recommendation(state, comparison)
                state.next_step()
                continue

            if step == "request_human_approval":
                result = self.approval_manager.request_approval(state)

                if not result.get("success"):
                    state.add_error(
                        source="approval",
                        message=result.get(
                            "message",
                            "Approval request failed.",
                        ),
                    )
                    state.status = "failed"
                    return state

                state.status = "waiting_for_approval"
                return state

            if step == "verify_invoice":
                fields_result = self._latest_observation(
                    state,
                    "invoice_fields",
                )

                missing = (
                    fields_result.get("missing_fields", [])
                    if fields_result
                    else []
                )
                amount_valid = bool(
                    fields_result and fields_result.get("amount_valid")
                )
                valid = bool(
                    fields_result
                    and fields_result.get("success")
                    and not missing
                    and amount_valid
                )

                verification = {
                    "valid": valid,
                    "message": (
                        "Invoice fields passed basic validation."
                        if valid
                        else "Invoice needs review. Check missing fields and amount."
                    ),
                    "fields": (
                        fields_result.get("fields", {})
                        if fields_result
                        else {}
                    ),
                    "missing_fields": missing,
                    "amount_valid": amount_valid,
                }

                state.verification_result = verification
                state.add_observation("invoice_verification", verification)

                if not valid:
                    state.add_error(
                        source="invoice_verification",
                        message=verification["message"],
                    )
                    state.status = "failed"
                    return state

                state.next_step()
                continue

            if step == "verify_result":
                # Do not verify a product recommendation until the user
                # has approved it.
                if (
                    task_type == "product_recommendation"
                    and state.approval_status == "pending"
                ):
                    state.next_step()
                    continue

                if task_type == "product_recommendation":
                    verification = self._verify_result(state)

                elif task_type == "general_task":
                    result = state.final_result or {}
                    valid = bool(
                        result.get("summary")
                        and result.get("answer")
                    )
                    verification = {
                        "valid": valid,
                        "message": (
                            "General task passed verification."
                            if valid
                            else "General task result is incomplete."
                        ),
                    }

                else:
                    verification = {
                        "valid": False,
                        "message": (
                            f"No verification handler for task type '{task_type}'."
                        ),
                    }

                state.verification_result = verification

                if not verification.get("valid"):
                    state.add_error(
                        source="verification",
                        message=verification.get(
                            "message",
                            "Verification failed.",
                        ),
                    )
                    state.status = "failed"
                    return state

                state.next_step()
                continue

            if step == "complete_task":
                self._complete_task(state, task_type)
                return state

            state.add_error(
                source="worker",
                message=f"Unknown plan step: {step}",
            )
            state.status = "failed"
            return state

        if state.status not in {
            "completed",
            "waiting_for_approval",
            "failed",
            "rejected",
        }:
            state.add_error(
                source="worker",
                message="Maximum agent iterations reached or plan ended unexpectedly.",
            )
            state.status = "failed"

        return state

    def _compare_products(self, state: AgentState) -> Dict[str, Any]:
        products = []

        for observation in reversed(state.observations):
            if observation.get("type") == "execution_analysis":
                data = observation.get("data", {})
                if isinstance(data, dict) and "products" in data:
                    products = data.get("products") or []
                    break

        if not products:
            return {
                "success": False,
                "message": "No products are available for comparison.",
                "ranked_products": [],
                "best_product": None,
            }

        return self.comparator.compare(
            products,
            state.constraints or {},
        )

    def _create_recommendation(
        self,
        state: AgentState,
        comparison: Dict[str, Any],
    ) -> None:
        best_product = comparison.get("best_product")
        if best_product:
            state.add_observation(
                "recommendation",
                deepcopy(best_product),
            )

    def _verify_result(self, state: AgentState) -> Dict[str, Any]:
        recommendation = self._latest_observation(state, "recommendation")

        if recommendation is None:
            comparison = self._latest_observation(state, "comparison")
            recommendation = (
                comparison.get("best_product")
                if isinstance(comparison, dict)
                else None
            )

        if recommendation is None:
            return {
                "valid": False,
                "message": "No product recommendation is available for verification.",
            }

        product = (
            recommendation.get("product", recommendation)
            if isinstance(recommendation, dict)
            else recommendation
        )

        try:
            # Supports verifier implementations accepting product and constraints.
            return self.verifier.verify(product, state.constraints or {})
        except TypeError:
            # Supports the existing AgentVerifier implementation accepting state.
            try:
                return self.verifier.verify(state)
            except Exception as exc:
                return {"valid": False, "message": str(exc)}
        except Exception as exc:
            return {"valid": False, "message": str(exc)}

    def _complete_task(
        self,
        state: AgentState,
        task_type: str,
    ) -> None:
        result = {
            "goal": state.goal,
            "task_type": task_type,
            "constraints": deepcopy(state.constraints or {}),
        }

        if task_type == "product_recommendation":
            if state.approval_status != "approved":
                state.add_error(
                    source="completion",
                    message="Product recommendation has not been approved.",
                )
                state.status = "failed"
                return

            if not (
                state.verification_result
                and state.verification_result.get("valid")
            ):
                state.add_error(
                    source="completion",
                    message="Product recommendation failed verification.",
                )
                state.status = "failed"
                return

            result["recommendation"] = self._latest_observation(
                state, "recommendation"
            )
            result["comparison"] = self._latest_observation(
                state, "comparison"
            )
            result["verification"] = deepcopy(state.verification_result)

        elif task_type == "general_task":
            general_result = state.final_result or {}

            if not general_result.get("answer"):
                state.add_error(
                    source="completion",
                    message="No general-task answer is available.",
                )
                state.status = "failed"
                return

            result.update(general_result)
            result["verification"] = deepcopy(
                state.verification_result or {}
            )

        elif task_type == "invoice_processing":
            result["invoice"] = self._latest_observation(
                state, "invoice_fields"
            )
            result["verification"] = deepcopy(
                state.verification_result or {}
            )

        else:
            state.add_error(
                source="worker",
                message=f"No completion handler for task type '{task_type}'.",
            )
            state.status = "failed"
            return

        result["observations"] = list(state.observations)
        result["actions"] = list(state.actions)
        state.final_result = result
        state.status = "completed"

    def _relax_constraints(self, state: AgentState) -> None:
        constraints = state.constraints or {}

        if "max_price" in constraints:
            try:
                constraints["max_price"] = round(
                    float(constraints["max_price"]) * 1.20,
                    2,
                )
            except (TypeError, ValueError):
                pass

        if "min_protein" in constraints:
            try:
                constraints["min_protein"] = max(
                    0,
                    round(float(constraints["min_protein"]) * 0.90, 2),
                )
            except (TypeError, ValueError):
                pass

        if "max_added_sugar" in constraints:
            try:
                constraints["max_added_sugar"] = round(
                    float(constraints["max_added_sugar"]) * 1.20,
                    2,
                )
            except (TypeError, ValueError):
                pass

        state.add_observation(
            "constraint_relaxation",
            {"constraints": dict(constraints)},
        )

    def _replan(self, state: AgentState) -> None:
        initialize_plan(state)
        state.add_observation(
            "replanning",
            {"plan": list(state.plan)},
        )

    def approve(self, state: AgentState) -> AgentState:
        """Approve the pending recommendation and resume at verification."""
        if state.status != "waiting_for_approval":
            state.add_error(
                source="approval",
                message="The task is not waiting for approval.",
            )
            return state

        try:
            result = self.approval_manager.approve(state)
        except Exception as exc:
            state.add_error(source="approval", message=str(exc))
            state.status = "failed"
            return state

        if not result.get("success"):
            state.add_error(
                source="approval",
                message=result.get("message", "Approval failed."),
            )
            state.status = "failed"
            return state

        state.approval_required = False
        state.approval_status = "approved"

        # CRITICAL FIX:
        # Jump directly past request_human_approval. Do not rely on the
        # approval manager to advance the plan index.
        try:
            approval_index = state.plan.index("request_human_approval")
            state.current_step = approval_index + 1
        except (ValueError, AttributeError):
            state.add_error(
                source="approval",
                message="The plan does not contain a human-approval step.",
            )
            state.status = "failed"
            return state

        # Product plans include verify_result. If the plan placed verification
        # before approval, resume at verification explicitly.
        if "verify_result" in state.plan:
            verification_index = state.plan.index("verify_result")
            if verification_index < state.current_step:
                state.current_step = verification_index

        return self._continue_after_approval(state)

    def reject(self, state: AgentState) -> AgentState:
        if state.status != "waiting_for_approval":
            state.add_error(
                source="approval",
                message="The task is not waiting for approval.",
            )
            return state

        try:
            result = self.approval_manager.reject(state)
        except Exception as exc:
            state.add_error(source="approval", message=str(exc))
            state.status = "failed"
            return state

        if not result.get("success"):
            state.add_error(
                source="approval",
                message=result.get("message", "Rejection failed."),
            )
            state.status = "failed"
            return state

        state.approval_required = False
        state.approval_status = "rejected"
        state.status = "rejected"
        return state

    def _continue_after_approval(self, state: AgentState) -> AgentState:
        """Resume the existing plan after approval."""
        task_type = self._task_type(state.goal)

        for _ in range(self.MAX_ITERATIONS):
            step = state.current_plan_step

            if step is None:
                state.status = "failed"
                state.add_error(
                    source="worker",
                    message="Plan ended before task completion.",
                )
                return state

            if step == "request_human_approval":
                # Defensive handling for plans whose index was not advanced.
                try:
                    state.current_step = state.plan.index(
                        "request_human_approval"
                    ) + 1
                except (ValueError, AttributeError):
                    state.add_error(
                        source="approval",
                        message="Cannot resume past the approval step.",
                    )
                    state.status = "failed"
                    return state
                continue

            if step == "verify_result":
                if task_type == "product_recommendation":
                    verification = self._verify_result(state)
                elif task_type == "general_task":
                    result = state.final_result or {}
                    valid = bool(
                        result.get("summary") and result.get("answer")
                    )
                    verification = {
                        "valid": valid,
                        "message": (
                            "General task passed verification."
                            if valid
                            else "General task result is incomplete."
                        ),
                    }
                else:
                    verification = {
                        "valid": False,
                        "message": f"No verification handler for '{task_type}'.",
                    }

                state.verification_result = verification

                if not verification.get("valid"):
                    state.add_error(
                        source="verification",
                        message=verification.get(
                            "message",
                            "Verification failed.",
                        ),
                    )
                    state.status = "failed"
                    return state

                state.next_step()
                continue

            if step == "verify_invoice":
                fields_result = self._latest_observation(
                    state, "invoice_fields"
                )
                missing = (
                    fields_result.get("missing_fields", [])
                    if fields_result
                    else []
                )
                amount_valid = bool(
                    fields_result and fields_result.get("amount_valid")
                )
                valid = bool(
                    fields_result
                    and fields_result.get("success")
                    and not missing
                    and amount_valid
                )
                state.verification_result = {
                    "valid": valid,
                    "message": (
                        "Invoice fields passed basic validation."
                        if valid
                        else "Invoice needs review. Check missing fields and amount."
                    ),
                    "fields": (
                        fields_result.get("fields", {})
                        if fields_result
                        else {}
                    ),
                    "missing_fields": missing,
                    "amount_valid": amount_valid,
                }

                if not valid:
                    state.add_error(
                        source="invoice_verification",
                        message=state.verification_result["message"],
                    )
                    state.status = "failed"
                    return state

                state.next_step()
                continue

            if step == "complete_task":
                self._complete_task(state, task_type)
                return state

            if step == "compare_alternatives":
                comparison = self._compare_products(state)
                if not comparison.get("success"):
                    state.add_error(
                        source="comparator",
                        message=comparison.get(
                            "message",
                            "Product comparison failed.",
                        ),
                    )
                    state.status = "failed"
                    return state

                state.add_observation("comparison", comparison)
                self._create_recommendation(state, comparison)
                state.next_step()
                continue

            if step in self.TOOL_STEPS:
                tool_input = self._tool_input_for_step(state, step)
                result = self.executor.execute_current_step(state, tool_input)
                observation = self.observer.observe(state, result)

                if observation.get("status") == "success":
                    state.next_step()
                    continue

                state.add_error(
                    source="worker",
                    message=observation.get(
                        "message",
                        "Tool execution failed after approval.",
                    ),
                )
                state.status = "failed"
                return state

            state.add_error(
                source="worker",
                message=f"Unknown plan step after approval: {step}",
            )
            state.status = "failed"
            return state

        state.add_error(
            source="worker",
            message="Maximum iterations reached after approval.",
        )
        state.status = "failed"
        return state