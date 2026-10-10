from agent.state import AgentState
from agent.approval import ApprovalManager


class TestApprovalManager:

    def setup_method(self):
        self.approval = ApprovalManager()

        self.product = {
            "product_id": "P002",
            "name": "Peanut Protein Bar",
            "brand": "NutriFit",
            "price": 135,
            "protein_g": 21,
            "added_sugar_g": 3
        }

        self.recommendation = {
            "product": self.product,
            "score": 45.5,
            "rank": 1,
            "reasons": [
                "Meets the requested nutritional constraints."
            ]
        }

    def create_state_with_recommendation(self):
        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "category": "protein_bar",
                "max_price": 150,
                "min_protein": 20,
                "max_added_sugar": 5
            }
        )

        state.add_observation(
            "recommendation",
            self.recommendation
        )

        return state

    def test_request_approval_creates_pending_request(self):
        state = self.create_state_with_recommendation()

        result = self.approval.request_approval(state)

        assert result["success"] is True
        assert result["status"] == ApprovalManager.PENDING
        assert state.approval_required is True
        assert state.approval_status == ApprovalManager.PENDING
        assert state.status == "waiting_for_approval"

    def test_approval_request_contains_recommendation_details(self):
        state = self.create_state_with_recommendation()

        result = self.approval.request_approval(state)

        recommendation = result["recommendation"]

        assert recommendation["product_id"] == "P002"
        assert recommendation["name"] == "Peanut Protein Bar"
        assert recommendation["brand"] == "NutriFit"
        assert recommendation["price"] == 135
        assert recommendation["protein_g"] == 21
        assert recommendation["added_sugar_g"] == 3
        assert recommendation["score"] == 45.5
        assert recommendation["rank"] == 1

    def test_request_approval_without_recommendation_fails(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        result = self.approval.request_approval(state)

        assert result["success"] is False
        assert result["status"] == "failure"
        assert state.status == "failed"
        assert state.approval_required is False
        assert len(state.errors) > 0

    def test_approve_pending_recommendation(self):
        state = self.create_state_with_recommendation()

        self.approval.request_approval(state)

        result = self.approval.approve(state)

        assert result["success"] is True
        assert result["status"] == ApprovalManager.APPROVED
        assert state.approval_required is False
        assert state.approval_status == ApprovalManager.APPROVED
        assert state.status == "approved"

    def test_approval_adds_human_approval_observation(self):
        state = self.create_state_with_recommendation()

        self.approval.request_approval(state)
        self.approval.approve(state)

        approval_observations = [
            observation
            for observation in state.observations
            if observation.get("type") == "human_approval"
        ]

        assert len(approval_observations) == 1
        assert approval_observations[0]["data"]["status"] == "approved"

    def test_reject_pending_recommendation(self):
        state = self.create_state_with_recommendation()

        self.approval.request_approval(state)

        result = self.approval.reject(
            state,
            reason="I prefer a different product."
        )

        assert result["success"] is True
        assert result["status"] == ApprovalManager.REJECTED
        assert state.approval_required is False
        assert state.approval_status == ApprovalManager.REJECTED
        assert state.status == "rejected"

    def test_rejection_preserves_reason(self):
        state = self.create_state_with_recommendation()

        self.approval.request_approval(state)

        reason = "The price is too high."

        result = self.approval.reject(
            state,
            reason=reason
        )

        assert result["message"] == reason

        approval_observations = [
            observation
            for observation in state.observations
            if observation.get("type") == "human_approval"
        ]

        assert len(approval_observations) == 1
        assert approval_observations[0]["data"]["message"] == reason

    def test_approve_without_pending_request_fails(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        result = self.approval.approve(state)

        assert result["success"] is False
        assert result["status"] == "failure"
        assert state.approval_status is None

    def test_reject_without_pending_request_fails(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        result = self.approval.reject(state)

        assert result["success"] is False
        assert result["status"] == "failure"
        assert state.approval_status is None

    def test_cannot_approve_twice(self):
        state = self.create_state_with_recommendation()

        self.approval.request_approval(state)

        first_result = self.approval.approve(state)
        second_result = self.approval.approve(state)

        assert first_result["success"] is True
        assert second_result["success"] is False
        assert second_result["status"] == "failure"

    def test_cannot_reject_twice(self):
        state = self.create_state_with_recommendation()

        self.approval.request_approval(state)

        first_result = self.approval.reject(state)
        second_result = self.approval.reject(state)

        assert first_result["success"] is True
        assert second_result["success"] is False
        assert second_result["status"] == "failure"

    def test_final_result_recommendation_is_used(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        state.final_result = {
            "recommendation": self.recommendation
        }

        result = self.approval.request_approval(state)

        assert result["success"] is True
        assert result["status"] == ApprovalManager.PENDING
        assert result["recommendation"]["product_id"] == "P002"
