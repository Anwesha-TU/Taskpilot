from typing import Any, Dict, Optional

from agent.state import AgentState


class ApprovalManager:
    """Handle human approval for product recommendations and invoices."""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"

    def request_approval(
        self,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Create an approval request for a verified invoice or recommendation."""

        invoice_fields = self._get_verified_invoice(state)

        if invoice_fields is not None:
            state.approval_required = True
            state.approval_status = self.PENDING
            state.status = "waiting_for_approval"

            return {
                "success": True,
                "status": self.PENDING,
                "message": "Human approval is required for this invoice.",
                "approval_type": "invoice",
                "invoice": {
                    "vendor": invoice_fields.get("vendor"),
                    "invoice_number": invoice_fields.get("invoice_number"),
                    "date": (
                        invoice_fields.get("date")
                        or invoice_fields.get("invoice_date")
                    ),
                    "currency": invoice_fields.get("currency"),
                    "total": invoice_fields.get("total"),
                },
            }

        recommendation = self._get_recommendation(state)

        if recommendation is None:
            message = (
                "No verified invoice or product recommendation "
                "is available for approval."
            )
            state.add_error(
                source="approval",
                message=message,
            )
            state.status = "failed"

            return {
                "success": False,
                "status": "failure",
                "message": message,
            }

        state.approval_required = True
        state.approval_status = self.PENDING
        state.status = "waiting_for_approval"

        product = recommendation.get("product", {})

        return {
            "success": True,
            "status": self.PENDING,
            "message": "Human approval is required.",
            "approval_type": "product_recommendation",
            "recommendation": {
                "product_id": product.get("product_id"),
                "name": product.get("name"),
                "brand": product.get("brand"),
                "price": product.get("price"),
                "protein_g": product.get("protein_g"),
                "added_sugar_g": product.get("added_sugar_g"),
                "score": recommendation.get("score"),
                "rank": recommendation.get("rank"),
                "reasons": recommendation.get("reasons", []),
            },
        }

    def approve(
        self,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Approve a pending invoice or product recommendation."""

        if not state.approval_required:
            return {
                "success": False,
                "status": "failure",
                "message": "No approval is currently pending.",
            }

        approval_type = self._pending_approval_type(state)

        state.approval_required = False
        state.approval_status = self.APPROVED
        state.status = "approved"

        if approval_type == "invoice":
            message = "Invoice approved by human."
        else:
            message = "Recommendation approved by human."

        state.add_observation(
            "human_approval",
            {
                "status": self.APPROVED,
                "approval_type": approval_type,
                "message": message,
            },
        )

        return {
            "success": True,
            "status": self.APPROVED,
            "message": message,
            "approval_type": approval_type,
        }

    def reject(
        self,
        state: AgentState,
        reason: str = "Request rejected by human.",
    ) -> Dict[str, Any]:
        """Reject a pending invoice or product recommendation."""

        if not state.approval_required:
            return {
                "success": False,
                "status": "failure",
                "message": "No approval is currently pending.",
            }

        approval_type = self._pending_approval_type(state)

        state.approval_required = False
        state.approval_status = self.REJECTED
        state.status = "rejected"

        state.add_observation(
            "human_approval",
            {
                "status": self.REJECTED,
                "approval_type": approval_type,
                "message": reason,
            },
        )

        return {
            "success": True,
            "status": self.REJECTED,
            "message": reason,
            "approval_type": approval_type,
        }

    @staticmethod
    def _get_verified_invoice(
        state: AgentState,
    ) -> Optional[Dict[str, Any]]:
        """Return invoice fields only when extraction and verification succeed."""

        plan = state.plan or []
        has_invoice_step = any(
            "invoice" in str(step).lower()
            for step in plan
        )

        invoice_result = None

        for observation in reversed(state.observations):
            if observation.get("type") == "invoice_fields":
                invoice_result = observation.get("data", {})
                break

        if not has_invoice_step and invoice_result is None:
            return None

        if not isinstance(invoice_result, dict):
            return None

        if not invoice_result.get("success"):
            return None

        fields = invoice_result.get("fields", {})
        if not isinstance(fields, dict) or not fields:
            return None

        verification = state.verification_result or {}

        if not verification:
            for observation in reversed(state.observations):
                if observation.get("type") == "invoice_verification":
                    verification = observation.get("data", {})
                    break

        if not verification.get("valid", False):
            return None

        if verification.get("missing_fields"):
            return None

        if verification.get("amount_valid") is not True:
            return None

        total = fields.get("total")
        if total in (None, ""):
            return None

        return fields

    @classmethod
    def _pending_approval_type(
        cls,
        state: AgentState,
    ) -> str:
        """Determine the type of request awaiting approval."""

        if cls._get_verified_invoice(state) is not None:
            return "invoice"

        if any(
            "invoice" in str(step).lower()
            for step in (state.plan or [])
        ):
            return "invoice"

        return "product_recommendation"

    @staticmethod
    def _get_recommendation(
        state: AgentState,
    ) -> Optional[Dict[str, Any]]:
        """Find the most recent product recommendation."""

        if state.final_result:
            recommendation = state.final_result.get("recommendation")
            if recommendation:
                return recommendation

        for observation in reversed(state.observations):
            if observation.get("type") == "recommendation":
                return observation.get("data")

        return None
