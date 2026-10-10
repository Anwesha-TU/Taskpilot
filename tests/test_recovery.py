from agent.state import AgentState
from agent.recovery import AgentRecovery


class TestAgentRecovery:

    def test_success_continues(self):
        state = AgentState(goal="Find a protein bar")
        recovery = AgentRecovery()

        result = recovery.recover(
            state,
            {"status": "success"}
        )

        assert result["action"] == "continue"
        assert state.retry_count == 0
        assert state.recovery_action == result

    def test_no_results_relaxes_constraints(self):
        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "category": "protein_bar",
                "max_price": 100
            }
        )

        recovery = AgentRecovery()

        result = recovery.recover(
            state,
            {"status": "no_results"}
        )

        assert result["action"] == "relax_constraints"
        assert state.retry_count == 1
        assert state.recovery_action == result
        assert state.status != "failed"

    def test_failure_retries(self):
        state = AgentState(goal="Find a protein bar")
        recovery = AgentRecovery()

        result = recovery.recover(
            state,
            {"status": "failure"}
        )

        assert result["action"] == "retry"
        assert state.retry_count == 1
        assert state.recovery_action == result
        assert state.status != "failed"

    def test_failure_stops_after_max_retries(self):
        state = AgentState(goal="Find a protein bar")
        state.retry_count = AgentRecovery.MAX_RETRIES

        recovery = AgentRecovery()

        result = recovery.recover(
            state,
            {"status": "failure"}
        )

        assert result["action"] == "stop"
        assert state.status == "failed"
        assert state.recovery_action == result
        assert len(state.errors) > 0

    def test_no_results_stops_after_max_retries(self):
        state = AgentState(goal="Find a protein bar")
        state.retry_count = AgentRecovery.MAX_RETRIES

        recovery = AgentRecovery()

        result = recovery.recover(
            state,
            {"status": "no_results"}
        )

        assert result["action"] == "stop"
        assert state.status == "failed"
        assert state.recovery_action == result
        assert len(state.errors) > 0

    def test_unknown_status_fails_safely(self):
        state = AgentState(goal="Find a protein bar")
        recovery = AgentRecovery()

        result = recovery.recover(
            state,
            {"status": "unknown_status"}
        )

        assert result["action"] == "stop"
        assert state.status == "failed"
        assert state.recovery_action == result
        assert len(state.errors) > 0
