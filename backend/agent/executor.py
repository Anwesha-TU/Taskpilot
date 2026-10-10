from typing import Any, Dict, Optional

from agent.state import AgentState
from tools.registry import registry

import tools.product_tool  # noqa: F401
import tools.ocr_tool  # noqa: F401
import tools.invoice_tool  # noqa: F401


class AgentExecutor:
    """Execute registered product-search and invoice tools."""

    STEP_TO_TOOL = {
        "search_alternatives": "search_products",
        "inspect_invoice": "ocr_invoice",
        "extract_invoice_fields": "extract_invoice_fields",
    }

    def execute_current_step(
        self,
        state: AgentState,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        step = state.current_plan_step
        tool_name = self.STEP_TO_TOOL.get(step)

        if tool_name is None:
            message = f"No supported tool mapping exists for plan step: {step}"
            state.add_error(source="executor", message=message)
            state.status = "failed"
            return {
                "success": False,
                "error": message,
                "error_type": "unknown_plan_step",
            }

        inputs = dict(tool_input or {})

        required_inputs = {
            "ocr_invoice": ("file_path",),
            "extract_invoice_fields": ("text",),
        }

        missing = [
            key for key in required_inputs.get(tool_name, ())
            if not inputs.get(key)
        ]

        if missing:
            message = (
                f"Tool '{tool_name}' requires input: "
                + ", ".join(missing)
            )
            output = {
                "success": False,
                "error": message,
                "error_type": "missing_input",
            }
            state.add_action(
                tool=tool_name,
                input_data=inputs,
                output_data=output,
                status="failed",
            )
            state.add_error(source=tool_name, message=message)
            state.status = "failed"
            return output

        try:
            result = registry.execute(tool_name, **inputs)
        except Exception as exc:
            message = str(exc)
            state.add_action(
                tool=tool_name,
                input_data=inputs,
                output_data=None,
                status="failed",
            )
            state.add_error(source=tool_name, message=message)
            state.status = "failed"
            return {
                "success": False,
                "error": message,
                "error_type": "tool_failure",
            }

        success = (
            result.get("success", True)
            if isinstance(result, dict)
            else True
        )

        state.add_action(
            tool=tool_name,
            input_data=inputs,
            output_data=result,
            status="success" if success else "failed",
        )

        if not success:
            message = (
                result.get("error", "Tool execution failed.")
                if isinstance(result, dict)
                else "Tool execution failed."
            )
            state.add_error(source=tool_name, message=message)
            state.status = "failed"
            return {
                "success": False,
                "error": message,
                "error_type": (
                    result.get("error_type", "tool_failure")
                    if isinstance(result, dict)
                    else "tool_failure"
                ),
            }

        state.status = "running"
        return result
