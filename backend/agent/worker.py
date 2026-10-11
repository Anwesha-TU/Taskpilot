

from copy import deepcopy

from pathlib import Path

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

    """Run general, product-search, and invoice-processing tasks."""



    MAX_ITERATIONS = 20

    MAX_TOOL_RETRIES = 3



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

    def _latest_observation(state: AgentState, observation_type: str):

        for observation in reversed(state.observations or []):

            if observation.get("type") == observation_type:

                return observation.get("data", {})

        return None



    @staticmethod

    def _add_error(state: AgentState, source: str, message: str) -> None:

        state.add_error(source=source, message=message)



    def _tool_input_for_step(

        self,

        state: AgentState,

        step: Optional[str],

        file_path: Optional[str] = None,

    ) -> Dict[str, Any]:

        constraints = dict(state.constraints or {})



        if step == "inspect_invoice":

            path = file_path or constraints.get("file_path")

            if not path:

                return {}

            return {"file_path": str(path)}



        if step == "extract_invoice_fields":

            observation = self._latest_observation(

                state, "invoice_ocr_text"

            )

            return {

                "text": observation.get("text", "")

                if observation

                else ""

            }



        if step in {"inspect_product", "search_alternatives"}:

            allowed = {

                "category",

                "query",

                "max_price",

                "min_price",

                "min_protein",

                "max_added_sugar",

                "available",

                "min_ram_gb",

                "min_storage_gb",

                "brand",

            }

            return {

                key: value

                for key, value in constraints.items()

                if key in allowed and value is not None

            }



        return constraints



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

            extracted = self.requirement_extractor.extract(goal)

            state.constraints = dict(extracted or {})

        except Exception as exc:

            self._add_error(

                state, "requirement_extractor", str(exc)

            )

            state.status = "failed"

            return state



        if file_path:

            state.constraints["file_path"] = str(file_path)



        if task_type == "invoice_processing":

            path = file_path or state.constraints.get("file_path")

            if not path:

                self._add_error(

                    state,

                    "worker",

                    "No invoice image was attached. Upload an invoice image "

                    "and submit the task again.",

                )

                state.status = "failed"

                return state



            if not Path(path).is_file():

                self._add_error(

                    state,

                    "worker",

                    f"Invoice image does not exist: {path}",

                )

                state.status = "failed"

                return state



            file_path = str(Path(path).resolve())

            state.constraints["file_path"] = file_path



        try:

            initialize_plan(state)

        except Exception as exc:

            self._add_error(state, "planner", str(exc))

            state.status = "failed"

            return state



        retries_by_step: Dict[str, int] = {}

        last_tool_result: Dict[str, Any] = {}



        for _ in range(self.MAX_ITERATIONS):

            step = state.current_plan_step



            if step is None:

                if state.status not in {

                    "failed",

                    "rejected",

                    "waiting_for_approval",

                }:

                    state.status = "completed"

                return state



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

                    self._add_error(

                        state,

                        "worker",

                        "General reasoning is not valid for this workflow.",

                    )

                    state.status = "failed"

                    return state



                result = self.general_executor.execute(state.goal)



                if not isinstance(result, dict) or not result.get("success"):

                    self._add_error(

                        state,

                        "general_executor",

                        (

                            result.get("error", "Reasoning failed.")

                            if isinstance(result, dict)

                            else "The reasoning executor returned an invalid result."

                        ),

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

                tool_input = self._tool_input_for_step(

                    state, step, file_path

                )



                if step == "inspect_invoice" and not tool_input.get(

                    "file_path"

                ):

                    self._add_error(

                        state,

                        "worker",

                        "Invoice inspection requires a valid image path.",

                    )

                    state.status = "failed"

                    return state



                if step == "extract_invoice_fields" and not tool_input.get(

                    "text"

                ):

                    self._add_error(

                        state,

                        "worker",

                        "No OCR text is available to extract invoice fields from.",

                    )

                    state.status = "failed"

                    return state



                print(f"[AgentWorker] Goal: {state.goal}")

                print(f"[AgentWorker] Task type: {task_type}")

                print(f"[AgentWorker] Step: {step}")

                print(f"[AgentWorker] Tool input: {tool_input}")



                try:

                    result = self.executor.execute_current_step(

                        state, tool_input

                    )

                except Exception as exc:

                    result = {

                        "success": False,

                        "error": str(exc),

                        "message": str(exc),

                    }



                if not isinstance(result, dict):

                    result = {

                        "success": False,

                        "error": "Tool returned an invalid result.",

                        "message": "Tool returned an invalid result.",

                    }



                last_tool_result = result

                observation = self.observer.observe(state, result)



                if not isinstance(observation, dict):

                    observation = {

                        "status": "failure",

                        "message": "Observer returned an invalid result.",

                    }



                status = observation.get("status", "failure")

                print(f"[AgentWorker] Tool result: {result}")

                print(f"[AgentWorker] Observation: {observation}")



                if status == "success":

                    retries_by_step[step] = 0

                    state.retry_count = 0



                    if step == "inspect_invoice":

                        text = result.get("text", "")

                        state.add_observation(

                            "invoice_ocr_text", {"text": text}

                        )



                    elif step == "extract_invoice_fields":

                        state.add_observation("invoice_fields", result)



                    state.next_step()

                    continue



                if status in {"no_results", "failure"}:

                    retry_count = retries_by_step.get(step, 0)



                    if retry_count >= self.MAX_TOOL_RETRIES:

                        self._add_error(

                            state,

                            "recovery",

                            f"Maximum retries reached for step '{step}'. "

                            f"Last result: {result.get('error') or result.get('message') or result}",

                        )

                        state.status = "failed"

                        return state



                    try:

                        recovery = self.recovery.recover(

                            state, observation

                        )

                    except Exception as exc:

                        self._add_error(

                            state, "recovery", str(exc)

                        )

                        state.status = "failed"

                        return state



                    if not isinstance(recovery, dict):

                        recovery = {"action": "stop"}



                    action = recovery.get("action", "stop")

                    state.retry_count = retry_count + 1

                    retries_by_step[step] = retry_count + 1



                    print(

                        f"[AgentWorker] Recovery action: {recovery}"

                    )



                    if action == "relax_constraints":

                        self._relax_constraints(state)

                        continue



                    if action == "retry":

                        continue



                    if action == "replan":

                        try:

                            self._replan(state)

                        except Exception as exc:

                            self._add_error(

                                state, "replanning", str(exc)

                            )

                            state.status = "failed"

                            return state

                        continue



                    message = (

                        observation.get("message")

                        or result.get("error")

                        or result.get("message")

                        or "No suitable results were found."

                    )

                    self._add_error(state, "worker", message)

                    state.status = "failed"

                    return state



                self._add_error(

                    state,

                    "worker",

                    f"Unexpected tool status '{status}'.",

                )

                state.status = "failed"

                return state



            if step == "compare_alternatives":

                if task_type != "product_recommendation":

                    self._add_error(

                        state,

                        "worker",

                        "Product comparison is not valid for this task.",

                    )

                    state.status = "failed"

                    return state



                comparison = self._compare_products(state)



                if not comparison.get("success"):

                    self._add_error(

                        state,

                        "comparator",

                        comparison.get(

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

                try:

                    result = self.approval_manager.request_approval(state)

                except Exception as exc:

                    self._add_error(state, "approval", str(exc))

                    state.status = "failed"

                    return state



                if not result.get("success"):

                    self._add_error(

                        state,

                        "approval",

                        result.get("message", "Approval request failed."),

                    )

                    state.status = "failed"

                    return state



                state.status = "waiting_for_approval"

                return state



            if step == "verify_invoice":

                fields_result = self._latest_observation(

                    state, "invoice_fields"

                )

                verification = self._verify_invoice_fields(fields_result)

                state.verification_result = verification

                state.add_observation(

                    "invoice_verification", verification

                )



                if not verification["valid"]:
                    # Extraction completed; preserve validation warnings but do
                    # not fail the task solely because fields are missing or
                    # monetary values do not reconcile.
                    state.add_observation(
                        "invoice_review_required",
                        {
                            "message": verification.get(
                                "message", "Invoice needs manual review."
                            ),
                            "missing_fields": verification.get(
                                "missing_fields", []
                            ),
                            "review_reasons": verification.get(
                                "review_reasons", []
                            ),
                            "amount_valid": verification.get(
                                "amount_valid", False
                            ),
                            "amount_reconciliation": verification.get(
                                "amount_reconciliation"
                            ),
                        },
                    )

                state.next_step()
                continue



            if step == "verify_result":

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

                        "message": (

                            f"No verification handler for task type '{task_type}'."

                        ),

                    }



                state.verification_result = verification



                if not verification.get("valid"):

                    self._add_error(

                        state,

                        "verification",

                        verification.get(

                            "message", "Verification failed."

                        ),

                    )

                    state.status = "failed"

                    return state



                state.next_step()

                continue



            if step == "complete_task":

                self._complete_task(state, task_type)

                return state



            self._add_error(

                state, "worker", f"Unknown plan step: {step}"

            )

            state.status = "failed"

            return state



        self._add_error(

            state,

            "worker",

            "Maximum agent iterations reached.",

        )

        state.status = "failed"

        return state



    @staticmethod

    def _verify_invoice_fields(fields_result: Any) -> Dict[str, Any]:

        """Validate invoice extraction without inventing missing values."""

        if not isinstance(fields_result, dict):

            fields_result = {}



        fields = fields_result.get("fields", {})

        if not isinstance(fields, dict):

            fields = {}



        missing = fields_result.get("missing_fields", [])

        if not isinstance(missing, list):

            missing = []



        invalid_amounts = fields_result.get("invalid_amount_fields", [])

        if not isinstance(invalid_amounts, list):

            invalid_amounts = []



        amount_valid = fields_result.get("amount_valid") is True

        reconciliation = fields_result.get("amount_reconciliation")

        reasons = []



        if missing:

            reasons.append(

                "Missing or unreadable fields: "

                + ", ".join(str(field) for field in missing)

                + "."

            )



        if invalid_amounts:

            reasons.append(

                "Invalid monetary values: "

                + ", ".join(str(field) for field in invalid_amounts)

                + "."

            )



        if not amount_valid:

            if (

                isinstance(reconciliation, dict)

                and reconciliation.get("matches") is False

            ):

                reasons.append(

                    "Subtotal plus tax does not equal the extracted total."

                )

            elif "tax" in missing:

                reasons.append(

                    "Tax is missing. Confirm whether tax is zero or whether "

                    "the tax amount is unreadable."

                )

            else:

                reasons.append(

                    "The invoice amounts could not be fully verified."

                )



        if not fields_result.get("success"):

            reasons.append(

                fields_result.get("error")

                or "Invoice field extraction was unsuccessful."

            )



        valid = bool(

            fields_result.get("success")

            and not missing

            and not invalid_amounts

            and amount_valid

        )



        return {

            "valid": valid,

            "message": (

                "Invoice fields passed basic validation."

                if valid

                else "Invoice needs review. " + " ".join(reasons)

            ),

            "fields": fields,

            "missing_fields": missing,

            "invalid_amount_fields": invalid_amounts,

            "amount_valid": amount_valid,

            "amount_reconciliation": reconciliation,

            "review_reasons": reasons,

        }



    def _compare_products(self, state: AgentState) -> Dict[str, Any]:

        products = []



        for observation in reversed(state.observations or []):

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

            products, state.constraints or {}

        )



    def _create_recommendation(

        self,

        state: AgentState,

        comparison: Dict[str, Any],

    ) -> None:

        best_product = comparison.get("best_product")

        if best_product:

            state.add_observation(

                "recommendation", deepcopy(best_product)

            )



    def _verify_result(self, state: AgentState) -> Dict[str, Any]:

        recommendation = self._latest_observation(

            state, "recommendation"

        )



        if recommendation is None:

            comparison = self._latest_observation(

                state, "comparison"

            )

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

            result = self.verifier.verify(

                product, state.constraints or {}

            )

            return result if isinstance(result, dict) else {

                "valid": bool(result),

                "message": "Verifier returned a non-dictionary result.",

            }

        except TypeError:

            try:

                result = self.verifier.verify(state)

                return result if isinstance(result, dict) else {

                    "valid": bool(result),

                    "message": "Verifier returned a non-dictionary result.",

                }

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

                self._add_error(

                    state,

                    "completion",

                    "Product recommendation has not been approved.",

                )

                state.status = "failed"

                return



            if not (

                state.verification_result

                and state.verification_result.get("valid")

            ):

                self._add_error(

                    state,

                    "completion",

                    "Product recommendation failed verification.",

                )

                state.status = "failed"

                return



            result["recommendation"] = self._latest_observation(

                state, "recommendation"

            )

            result["comparison"] = self._latest_observation(

                state, "comparison"

            )

            result["verification"] = deepcopy(

                state.verification_result

            )



        elif task_type == "general_task":

            general_result = state.final_result or {}

            if not general_result.get("answer"):

                self._add_error(

                    state,

                    "completion",

                    "No general-task answer is available.",

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

            self._add_error(

                state,

                "worker",

                f"No completion handler for task type '{task_type}'.",

            )

            state.status = "failed"

            return



        result["observations"] = list(state.observations or [])

        result["actions"] = list(state.actions or [])

        state.final_result = result

        state.status = "completed"



    def _relax_constraints(self, state: AgentState) -> None:

        constraints = dict(state.constraints or {})



        if "max_price" in constraints:

            try:

                constraints["max_price"] = round(

                    float(constraints["max_price"]) * 1.20, 2

                )

            except (TypeError, ValueError):

                pass



        if "min_price" in constraints:

            constraints.pop("min_price", None)



        if "min_protein" in constraints:

            try:

                constraints["min_protein"] = max(

                    0, round(float(constraints["min_protein"]) * 0.90, 2)

                )

            except (TypeError, ValueError):

                pass



        if "max_added_sugar" in constraints:

            try:

                constraints["max_added_sugar"] = round(

                    float(constraints["max_added_sugar"]) * 1.20, 2

                )

            except (TypeError, ValueError):

                pass



        state.constraints = constraints

        state.add_observation(

            "constraint_relaxation",

            {"constraints": dict(constraints)},

        )



    def _replan(self, state: AgentState) -> None:

        initialize_plan(state)

        state.add_observation(

            "replanning", {"plan": list(state.plan or [])}

        )



    def approve(self, state: AgentState) -> AgentState:

        if state.status != "waiting_for_approval":

            self._add_error(

                state, "approval", "The task is not waiting for approval."

            )

            return state



        try:

            result = self.approval_manager.approve(state)

        except Exception as exc:

            self._add_error(state, "approval", str(exc))

            state.status = "failed"

            return state



        if not result.get("success"):

            self._add_error(

                state,

                "approval",

                result.get("message", "Approval failed."),

            )

            state.status = "failed"

            return state



        state.approval_required = False

        state.approval_status = "approved"



        try:

            approval_index = state.plan.index("request_human_approval")

            state.current_step = approval_index + 1

        except (ValueError, AttributeError):

            self._add_error(

                state,

                "approval",

                "The plan does not contain a human-approval step.",

            )

            state.status = "failed"

            return state



        if "verify_result" in state.plan:

            verification_index = state.plan.index("verify_result")

            if verification_index < state.current_step:

                state.current_step = verification_index



        return self._continue_after_approval(state)



    def reject(self, state: AgentState) -> AgentState:

        if state.status != "waiting_for_approval":

            self._add_error(

                state, "approval", "The task is not waiting for approval."

            )

            return state



        try:

            result = self.approval_manager.reject(state)

        except Exception as exc:

            self._add_error(state, "approval", str(exc))

            state.status = "failed"

            return state



        if not result.get("success"):

            self._add_error(

                state,

                "approval",

                result.get("message", "Rejection failed."),

            )

            state.status = "failed"

            return state



        state.approval_required = False

        state.approval_status = "rejected"

        state.status = "rejected"

        return state



    def _continue_after_approval(

        self, state: AgentState

    ) -> AgentState:

        task_type = self._task_type(state.goal)



        for _ in range(self.MAX_ITERATIONS):

            step = state.current_plan_step



            if step is None:

                self._add_error(

                    state, "worker", "Plan ended before task completion."

                )

                state.status = "failed"

                return state



            if step == "request_human_approval":

                try:

                    state.current_step = (

                        state.plan.index("request_human_approval") + 1

                    )

                except (ValueError, AttributeError):

                    self._add_error(

                        state,

                        "approval",

                        "Cannot resume past the approval step.",

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

                    self._add_error(

                        state,

                        "verification",

                        verification.get(

                            "message", "Verification failed."

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

                verification = self._verify_invoice_fields(fields_result)

                state.verification_result = verification

                state.add_observation(

                    "invoice_verification", verification

                )



                if not verification["valid"]:
                    # Extraction completed; preserve validation warnings but do
                    # not fail the task solely because fields are missing or
                    # monetary values do not reconcile.
                    state.add_observation(
                        "invoice_review_required",
                        {
                            "message": verification.get(
                                "message", "Invoice needs manual review."
                            ),
                            "missing_fields": verification.get(
                                "missing_fields", []
                            ),
                            "review_reasons": verification.get(
                                "review_reasons", []
                            ),
                            "amount_valid": verification.get(
                                "amount_valid", False
                            ),
                            "amount_reconciliation": verification.get(
                                "amount_reconciliation"
                            ),
                        },
                    )

                state.next_step()
                continue



            if step == "compare_alternatives":

                comparison = self._compare_products(state)

                if not comparison.get("success"):

                    self._add_error(

                        state,

                        "comparator",

                        comparison.get(

                            "message", "Product comparison failed."

                        ),

                    )

                    state.status = "failed"

                    return state



                state.add_observation("comparison", comparison)

                self._create_recommendation(state, comparison)

                state.next_step()

                continue



            if step == "complete_task":

                self._complete_task(state, task_type)

                return state



            if step in self.TOOL_STEPS:

                tool_input = self._tool_input_for_step(state, step)

                result = self.executor.execute_current_step(

                    state, tool_input

                )

                observation = self.observer.observe(state, result)



                if observation.get("status") == "success":

                    state.next_step()

                    continue



                self._add_error(

                    state,

                    "worker",

                    observation.get(

                        "message",

                        "Tool execution failed after approval.",

                    ),

                )

                state.status = "failed"

                return state



            self._add_error(

                state,

                "worker",

                f"Unknown plan step after approval: {step}",

            )

            state.status = "failed"

            return state



        self._add_error(

            state,

            "worker",

            "Maximum iterations reached after approval.",

        )

        state.status = "failed"

        return state
