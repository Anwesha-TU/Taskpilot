
import json
import os
from typing import Any, Dict, Optional


class AgentReasoner:
    """Uses an LLM to interpret business goals and identify supported workflows."""

    SUPPORTED_WORKFLOWS = {
        "invoice_processing",
        "product_recommendation",
        "ingredient_analysis",
        "unsupported",
    }

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = (
            model_name
            or os.getenv("AGENT_REASONING_MODEL")
            or os.getenv("GEMINI_MODEL")
            or "gemini-2.5-flash"
        )
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    def interpret_goal(self, goal: str) -> Dict[str, Any]:
        """Interpret a goal using Gemini, with a safe fallback on failure."""
        if not isinstance(goal, str) or not goal.strip():
            return self._fallback("The task goal is empty.")

        if not self.api_key:
            return self._fallback("Gemini API key is not configured.")

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=(
                    "You are the reasoning component of an autonomous business "
                    "operator. Interpret the user's intended outcome. Do not "
                    "execute actions or invent capabilities. Classify the task "
                    "into exactly one supported workflow: invoice_processing, "
                    "product_recommendation, ingredient_analysis, or unsupported. "
                    "Invoice processing means extracting and validating invoice "
                    "data from a provided file. Product recommendation means "
                    "searching and comparing available products. Ingredient "
                    "analysis means analyzing product ingredients. If the task "
                    "requires an unavailable tool or workflow, select unsupported. "
                    "Return only valid JSON with keys workflow, reasoning, and "
                    "missing_information. workflow must be one of the four exact "
                    "allowed values. reasoning must be a short explanation. "
                    "missing_information must be a JSON array of strings."
                ),
            )

            response = model.generate_content(
                f"Interpret this user goal:\n{goal.strip()}",
                generation_config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                },
                request_options={"timeout": 20},
            )

            result = json.loads(response.text)
            workflow = result.get("workflow")
            reasoning = result.get("reasoning", "")
            missing_information = result.get("missing_information", [])

            if workflow not in self.SUPPORTED_WORKFLOWS:
                return self._fallback("Gemini returned an unsupported workflow.")

            if not isinstance(missing_information, list):
                missing_information = []

            return {
                "success": True,
                "workflow": workflow,
                "reasoning": str(reasoning),
                "missing_information": [
                    str(item) for item in missing_information
                ],
                "source": "gemini",
            }

        except Exception as exc:
            return self._fallback(
                f"Gemini interpretation failed: {type(exc).__name__}."
            )

    @staticmethod
    def _fallback(reason: str) -> Dict[str, Any]:
        """Signal the planner to use its existing deterministic rules."""
        return {
            "success": False,
            "workflow": None,
            "reasoning": reason,
            "missing_information": [],
            "source": "fallback",
        }
