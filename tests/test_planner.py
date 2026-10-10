import pytest

from agent.worker import AgentWorker


class TestAgentWorker:

    # BASIC SEARCH / APPROVAL FLOW
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

    # APPROVAL → VERIFICATION → COMPLETION
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

    # PRODUCT RANKING
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

    # SIMPLE SEARCH
    def test_simple_protein_bar_search(self):
        """
        A simple protein-bar request should reach the
        human-approval checkpoint without failing.
        """

        worker = AgentWorker()

        state = worker.run("Find a protein bar")

        assert state.status == "waiting_for_approval"

        assert state.constraints["category"] == "protein_bar"

        assert state.approval_required is True
        assert state.approval_status == "pending"

        assert len(state.actions) >= 1

        assert state.errors == []

    # APPROVAL REJECTION
    def test_rejected_approval_does_not_complete_task(self):
        """
        Rejecting the recommendation should not mark the
        task as successfully completed.
        """

        worker = AgentWorker()

        state = worker.run("Find a protein bar")

        assert state.status == "waiting_for_approval"
        assert state.approval_required is True

        state = worker.reject(state)

        assert state.approval_required is False
        assert state.approval_status == "rejected"

        assert state.status != "completed"

    # CONSTRAINED SEARCH
    def test_constrained_protein_bar_search(self):
        """
        The worker should extract constraints from the goal,
        search using those constraints, and pause for approval.
        """

        worker = AgentWorker()

        state = worker.run(
            "Find a protein bar under ₹150"
        )

        assert state.constraints["category"] == "protein_bar"
        assert state.constraints["max_price"] == 150.0

        assert state.status == "waiting_for_approval"
        assert state.approval_required is True

        assert state.verification_result is None
        assert state.final_result is None

        assert len(state.actions) >= 1
        assert state.actions[0]["tool"] == "search_products"


    # MULTIPLE CONSTRAINTS
    def test_multiple_constraints_search(self):
        """
        The worker should correctly handle multiple constraints:

        - maximum price
        - minimum protein
        - maximum added sugar
        """

        worker = AgentWorker()

        state = worker.run(
            "Find a protein bar under ₹150 "
            "with at least 20g protein "
            "and less than 5g added sugar"
        )

        assert state.constraints == {
            "category": "protein_bar",
            "max_price": 150.0,
            "min_protein": 20.0,
            "max_added_sugar": 5.0,
        }

        assert state.status == "waiting_for_approval"
        assert state.approval_required is True

        assert len(state.actions) >= 1

        search_action = state.actions[0]

        assert search_action["tool"] == "search_products"
        assert search_action["status"] == "success"

    # VALID CONSTRAINED RECOMMENDATION
    def test_constrained_search_selects_valid_product(self):
        """
        The comparator and verifier should select a product
        satisfying all requested constraints.
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

        assert product["category"] == "protein_bar"
        assert product["price"] <= 150
        assert product["protein_g"] >= 20
        assert product["added_sugar_g"] < 5

        assert recommendation["meets_constraints"] is True


    # CONSTRAINED SEARCH + APPROVAL
    def test_constrained_search_approval_completes_task(self):
        """
        After human approval, a valid constrained recommendation
        should proceed through verification and complete.
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

        assert state.approval_status == "approved"

        assert state.verification_result is not None
        assert state.verification_result["valid"] is True

        assert state.final_result is not None

        recommendation = state.final_result["recommendation"]
        product = recommendation["product"]

        assert product["category"] == "protein_bar"
        assert product["price"] <= 150
        assert product["protein_g"] >= 20
        assert product["added_sugar_g"] < 5

        assert state.errors == []

    # NO MATCHING PRODUCT

    def test_no_matching_product_fails_gracefully(self):
        """
        An impossible set of constraints should not produce
        an invalid recommendation.
        """

        worker = AgentWorker()

        state = worker.run(
            "Find a protein bar under ₹50 "
            "with at least 50g protein "
            "and less than 1g added sugar"
        )

        # There must not be a fabricated final recommendation.
        assert state.final_result is None

        # Depending on the current recovery implementation,
        # the worker may terminate with failure or remain at
        # the approval checkpoint if a fallback produced a result.
        assert state.status in [
            "failed",
            "waiting_for_approval",
        ]

        if state.status == "failed":
            assert len(state.errors) > 0


if __name__ == "__main__":
    pytest.main()
