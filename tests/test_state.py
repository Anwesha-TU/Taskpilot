from agent.state import AgentState


class TestAgentState:

    def test_default_state(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        assert state.goal == "Find a protein bar"
        assert state.constraints == {}
        assert state.plan == []
        assert state.current_step == 0
        assert state.observations == []
        assert state.actions == []
        assert state.errors == []
        assert state.retry_count == 0
        assert state.recovery_action is None
        assert state.approval_required is False
        assert state.approval_status is None
        assert state.verification_result is None
        assert state.status == "initialized"
        assert state.final_result is None

    def test_custom_state_values(self):
        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "category": "protein_bar",
                "max_price": 150
            },
            plan=[
                "search_alternatives",
                "compare_alternatives",
                "verify_result"
            ],
            current_step=1,
            retry_count=2,
            approval_required=True,
            approval_status="pending",
            status="waiting_for_approval"
        )

        assert state.constraints["category"] == "protein_bar"
        assert state.constraints["max_price"] == 150
        assert len(state.plan) == 3
        assert state.current_step == 1
        assert state.retry_count == 2
        assert state.approval_required is True
        assert state.approval_status == "pending"
        assert state.status == "waiting_for_approval"

    def test_add_observation(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        state.add_observation(
            "recommendation",
            {
                "product_id": "P002",
                "score": 45.5
            }
        )

        assert len(state.observations) == 1
        assert state.observations[0]["type"] == "recommendation"
        assert state.observations[0]["data"]["product_id"] == "P002"
        assert state.observations[0]["data"]["score"] == 45.5

    def test_multiple_observations_preserve_order(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        state.add_observation(
            "search_result",
            {"count": 2}
        )

        state.add_observation(
            "recommendation",
            {"product_id": "P002"}
        )

        assert len(state.observations) == 2
        assert state.observations[0]["type"] == "search_result"
        assert state.observations[1]["type"] == "recommendation"

    def test_add_action(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        state.add_action(
            tool="search_products",
            input_data={
                "category": "protein_bar"
            },
            output_data={
                "success": True,
                "count": 2
            }
        )

        assert len(state.actions) == 1

        action = state.actions[0]

        assert action["tool"] == "search_products"
        assert action["input"]["category"] == "protein_bar"
        assert action["output"]["success"] is True
        assert action["output"]["count"] == 2
        assert action["status"] == "success"

    def test_add_action_with_failure_status(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        state.add_action(
            tool="search_products",
            input_data={},
            output_data={
                "success": False
            },
            status="failure"
        )

        assert state.actions[0]["status"] == "failure"
        assert state.actions[0]["output"]["success"] is False

    def test_add_error(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        state.add_error(
            source="search_products",
            message="Product database unavailable."
        )

        assert len(state.errors) == 1
        assert state.errors[0]["source"] == "search_products"
        assert (
            state.errors[0]["message"]
            == "Product database unavailable."
        )

    def test_multiple_errors_preserve_order(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        state.add_error(
            source="search_products",
            message="First error"
        )

        state.add_error(
            source="recovery",
            message="Second error"
        )

        assert len(state.errors) == 2
        assert state.errors[0]["source"] == "search_products"
        assert state.errors[1]["source"] == "recovery"

    def test_next_step(self):
        state = AgentState(
            goal="Find a protein bar",
            plan=[
                "search_alternatives",
                "compare_alternatives",
                "verify_result"
            ]
        )

        assert state.current_step == 0
        assert state.current_plan_step == "search_alternatives"

        state.next_step()

        assert state.current_step == 1
        assert state.current_plan_step == "compare_alternatives"

        state.next_step()

        assert state.current_step == 2
        assert state.current_plan_step == "verify_result"

    def test_current_plan_step_returns_none_after_plan(self):
        state = AgentState(
            goal="Find a protein bar",
            plan=[
                "search_alternatives",
                "verify_result"
            ]
        )

        state.next_step()
        state.next_step()

        assert state.current_step == 2
        assert state.current_plan_step is None

    def test_current_plan_step_returns_none_for_empty_plan(self):
        state = AgentState(
            goal="Find a protein bar"
        )

        assert state.current_plan_step is None

    def test_state_collections_are_independent(self):
        state_one = AgentState(
            goal="Task one"
        )

        state_two = AgentState(
            goal="Task two"
        )

        state_one.add_observation(
            "test",
            {"value": 1}
        )

        state_one.add_error(
            "test",
            "error"
        )

        assert len(state_one.observations) == 1
        assert len(state_two.observations) == 0

        assert len(state_one.errors) == 1
        assert len(state_two.errors) == 0
