
import json
import os
import re
from typing import Any, Dict, List


class GeneralReasoningExecutor:
    def __init__(self, model_name: str = "gemini-3.7-flash"):
        self.model_name = model_name

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("No JSON object found in model response.")
            result = json.loads(cleaned[start:end + 1])

        if not isinstance(result, dict):
            raise ValueError("The model response must be a JSON object.")

        return result

    @staticmethod
    def _local_proposal_comparison(goal: str) -> Dict[str, Any]:
        """Locally compare proposals when their impact, duration and cost are supplied."""
        pattern = re.compile(
            r"Proposal\s+([A-Z])\s*:\s*(.*?)"
            r"Impact\s*:\s*(High|Medium|Low)\s*\.?\s*"
            r"Implementation\s*:\s*(\d+(?:\.\d+)?)\s*weeks?\s*\.?\s*"
            r"Cost\s*:\s*(?:₹|Rs\.?\s*)?([\d,]+(?:\.\d+)?)",
            re.IGNORECASE | re.DOTALL,
        )

        proposals = []
        for match in pattern.finditer(goal):
            letter, description, impact, weeks, cost = match.groups()
            impact = impact.capitalize()
            weeks = float(weeks)
            cost_value = float(cost.replace(",", ""))

            # Transparent heuristic: prioritize impact, then lower time and cost.
            impact_score = {"High": 3, "Medium": 2, "Low": 1}[impact]
            efficiency_score = impact_score / (weeks * cost_value) if weeks and cost_value else 0

            proposals.append({
                "name": f"Proposal {letter.upper()}",
                "description": description.strip().rstrip(". "),
                "impact": impact,
                "implementation_weeks": weeks,
                "cost_inr": cost_value,
                "impact_score": impact_score,
                "efficiency_score": efficiency_score,
            })

        if len(proposals) < 2:
            return {
                "success": False,
                "error": (
                    "Gemini quota is exhausted, and this task does not contain "
                    "enough structured proposal data for local comparison."
                ),
            }

        ranked = sorted(
            proposals,
            key=lambda p: (
                -p["impact_score"],
                p["implementation_weeks"],
                p["cost_inr"],
            ),
        )

        ranking = [
            {
                "rank": index,
                **proposal,
            }
            for index, proposal in enumerate(ranked, start=1)
        ]

        best = ranked[0]
        summary = (
            f"{best['name']} is the recommended first priority: "
            f"{best['impact'].lower()} implementation impact, "
            f"{best['implementation_weeks']:g} weeks, "
            f"and ₹{best['cost_inr']:,.0f}."
        )

        details = [
            f"{p['name']}: {p['description']} — {p['impact']} impact, "
            f"{p['implementation_weeks']:g} weeks, ₹{p['cost_inr']:,.0f}."
            for p in ranking
        ]

        answer = (
            "## Ranking\n"
            + "\n".join(
                f"{p['rank']}. **{p['name']}** — {p['description']}. "
                f"Impact: {p['impact']}; duration: "
                f"{p['implementation_weeks']:g} weeks; "
                f"cost: ₹{p['cost_inr']:,.0f}."
                for p in ranking
            )
            + "\n\n## Trade-offs\n"
            + "\n".join(f"- {detail}" for detail in details)
            + "\n\n## Recommendation\n"
            + summary
            + "\n\nThis ranking prioritizes impact first, then shorter implementation "
            "time and lower cost. It is a transparent heuristic, not a financial "
            "or business-impact forecast. No additional benefits or savings were supplied."
        )

        return {
            "success": True,
            "summary": summary,
            "answer": answer,
            "reasoning": [
                "Ranked impact as High > Medium > Low.",
                "Used shorter implementation time as the second criterion.",
                "Used lower cost as the third criterion.",
            ],
            "assumptions": [
                "The supplied impact ratings are comparable.",
                "Implementation time and cost are estimates supplied by the user.",
            ],
            "limitations": [
                "The ranking does not estimate financial return or hours saved.",
                "This is a local rule-based fallback, not a Gemini-generated analysis.",
            ],
            "confidence": "medium",
            "model": "local-proposal-fallback",
            "fallback_used": True,
            "proposals": ranking,
        }

    def execute(self, goal: str) -> Dict[str, Any]:
        if not isinstance(goal, str) or not goal.strip():
            return {
                "success": False,
                "error": "A non-empty task goal is required.",
            }

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return self._local_proposal_comparison(goal)

        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.model_name)

            prompt = f"""You are the reasoning engine for an agentic operations worker.
Solve the user's task directly. Do not assume it is a product, nutrition,
or invoice task unless the user explicitly says so.

User task:
{goal}

Instructions:
- Address every part of the request.
- For comparisons, use supplied facts unless outside research is requested.
- Explain criteria, trade-offs, rankings, and recommendations.
- Do not invent facts, figures, sources, or completed actions.
- State assumptions and limitations.
- Return only valid JSON in this format:
{{"summary":"Concise direct answer","answer":"Complete response",
"reasoning":["Reasoning point"],"assumptions":[],"limitations":[],
"confidence":"high, medium, or low"}}
"""

            response = model.generate_content(prompt)
            response_text = getattr(response, "text", None)

            if not response_text or not response_text.strip():
                return {
                    "success": False,
                    "error": "Gemini returned an empty response.",
                }

            result = self._extract_json(response_text)
            summary = result.get("summary")
            answer = result.get("answer")

            if not isinstance(summary, str) or not summary.strip():
                return {
                    "success": False,
                    "error": "The response is missing a valid summary.",
                }

            if not isinstance(answer, str) or not answer.strip():
                return {
                    "success": False,
                    "error": "The response is missing a valid answer.",
                }

            return {
                "success": True,
                "summary": summary.strip(),
                "answer": answer.strip(),
                "reasoning": result.get("reasoning", []),
                "assumptions": result.get("assumptions", []),
                "limitations": result.get("limitations", []),
                "confidence": result.get("confidence", "medium"),
                "model": self.model_name,
                "fallback_used": False,
            }

        except Exception as exc:
            message = str(exc)
            if "429" in message or "quota" in message.lower():
                return self._local_proposal_comparison(goal)

            return {
                "success": False,
                "error": f"General reasoning failed: {message}",
            }
