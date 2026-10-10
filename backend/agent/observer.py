from typing import Any, Dict

from agent.state import AgentState


class AgentObserver:
    """
    Interprets the outcome of an executed agent action.

    The observer does not execute tools.
    It analyzes what happened and updates the agent state.
    """

    def observe(
        self,
        state: AgentState,
        result: Any
    ) -> Dict[str, Any]:
        """
        Analyze the latest execution result.
        """

        # Unexpected result format
        if not isinstance(result, dict):

            observation = {
                "status": "unknown",
                "message": "Tool returned an unexpected result format."
            }

            state.add_observation(
                "execution_analysis",
                observation
            )

            return observation

        # Tool failure
        if result.get("success") is False:

            observation = {
                "status": "failure",
                "message": result.get(
                    "error",
                    "Tool execution failed."
                ),
                "error_type": result.get(
                    "error_type",
                    "tool_failure"
                )
            }

            state.add_observation(
                "execution_analysis",
                observation
            )

            state.status = "error"

            return observation

        # Product search
        if "products" in result:

            products = result.get("products", [])

            if len(products) == 0:

                observation = {
                    "status": "no_results",
                    "message": "No suitable products were found.",
                    "result_count": 0
                }

            else:

                observation = {
                    "status": "success",
                    "message": "Suitable products were found.",
                    "result_count": len(products),
                    "products": products
                }

            state.add_observation(
                "execution_analysis",
                observation
            )

            return observation

        # OCR result
        if "text" in result:

            text = result.get("text", "")

            if text.strip():

                observation = {
                    "status": "success",
                    "message": "Product label text extracted successfully.",
                    "text_length": len(text)
                }

            else:

                observation = {
                    "status": "failure",
                    "message": "OCR returned empty text."
                }

            state.add_observation(
                "execution_analysis",
                observation
            )

            return observation

        # Generic successful tool execution
        observation = {
            "status": "success",
            "message": "Tool executed successfully."
        }

        state.add_observation(
            "execution_analysis",
            observation
        )

        return observation
