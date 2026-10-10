import pytest

from agent.worker import AgentWorker


class TestAgentWorker:

    def test_find_protein_bar_requires_approval(self):
        """
        The worker should:

        1. Extract the product requirement
        2. Create a search/comparison plan
        3. Search products
        4. Compare products
        5. Stop at human approval
        """

        worker = AgentWorker()

        state = worker.run(
            "Find a protein bar under ₹150 "
            "with at least 20g protein "
            "and less than 5g added sugar"
        )

        assert state.status == "waiting_for_approval"

        assert state.constraints == {
            "category": "protein_bar",
            "max_price": 150.0,
            "min_protein": 20.0,
            "max_added_sugar": 5.0,
        }

        assert "search_alternatives" in state.plan
        assert "compare_alternatives" in state.plan
        assert "request_human_approval" in state.plan
        assert "verify_result" in state.plan
        assert "complete_task" in state.plan

        assert len(state.actions) >= 1
        assert len(state.observations) >= 2

        assert state.approval_required is True
        assert state.approval_status == "pending"

        assert state.errors == []


    def test_approval_completes_task(self):
        """
        After the recommendation is generated and approval is granted,
        the worker should continue through verification and completion.
        """

        worker = AgentWorker()

        state = worker.run(
            "Find a protein bar under ₹150 "
            "with at least 20g protein "
            "and less than 5g added sugar"
        )

        assert state.status == "waiting_for_approval"
        assert state.approval_required is True

        state = worker.approve(state)

        assert state.status == "completed"

        assert state.approval_required is False
        assert state.approval_status == "approved"

        assert state.verification_result is not None
        assert state.verification_result["valid"] is True

        assert state.final_result is not None

        assert state.final_result["recommendation"] is not None

        recommendation = state.final_result["recommendation"]

        product = recommendation["product"]

        assert product["category"] == "protein_bar"
        assert product["price"] <= 150
        assert product["protein_g"] >= 20
        assert product["added_sugar_g"] < 5

        assert state.errors == []


    def test_selected_product_is_best_valid_product(self):
        """
        The current mock product environment contains:

        P001:
            20g protein
            12g added sugar
            ₹120

        P002:
            21g protein
            3g added sugar
            ₹135

        Under the requested constraints, P002 should be preferred.
        """

        worker = AgentWorker()

        state = worker.run(
            "Find a protein bar under ₹150 "
            "with at least 20g protein "
            "and less than 5g added sugar"
        )

        assert state.status == "waiting_for_approval"

        recommendation_observations = [
            observation
            for observation in state.observations
            if observation.get("type") == "recommendation"
        ]

        assert len(recommendation_observations) >= 1

        recommendation = recommendation_observations[-1]["data"]

        product = recommendation["product"]

        assert product["product_id"] == "P002"
        assert product["name"] == "Peanut Protein Bar"
        assert product["protein_g"] == 21
        assert product["added_sugar_g"] == 3
        assert product["price"] == 135


    def test_simple_protein_bar_search(self):
        """
        Basic search should reach human approval rather than failing.
        """

        worker = AgentWorker()

        state = worker.run("Find a protein bar")

        assert state.status == "waiting_for_approval"

        assert state.constraints["category"] == "protein_bar"

        assert state.approval_required is True

        assert state.approval_status == "pending"

        assert len(state.actions) >= 1

        assert state.errors == []


    def test_rejected_approval_does_not_complete_task(self):
        """
        Rejecting the recommendation should not mark the task
        as successfully completed.
        """

        worker = AgentWorker()

        state = worker.run("Find a protein bar")

        assert state.status == "waiting_for_approval"
        assert state.approval_required is True

        state = worker.reject(state)

        assert state.approval_required is False
        assert state.approval_status == "rejected"

        assert state.status != "completed"


if __name__ == "__main__":
    pytest.main()
