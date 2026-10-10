from typing import Any, Dict

from agent.state import AgentState


class AgentRecovery:
    """
    Handles failures and unexpected outcomes during execution.

    Recovery decides whether the worker should:

        - continue
        - retry the same action
        - modify the action
        - re-plan
        - stop execution
    """

    MAX_RETRIES = 2

    def recover(
        self,
        state: AgentState,
        observation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Decide what the agent should do after observing
        the result of an executed action.
        """

        status = observation.get("status")

        # SUCCESS
        if status == "success":

            recovery = {
                "action": "continue",
                "reason": "The previous action succeeded."
            }

            state.recovery_action = recovery

            return recovery

        # NO RESULTS
        if status == "no_results":

            # Maximum retry limit reached
            if state.retry_count >= self.MAX_RETRIES:

                state.add_error(
                    source="recovery",
                    message=(
                        "Maximum retries reached while searching "
                        "for suitable products."
                    )
                )

                state.status = "failed"

                recovery = {
                    "action": "stop",
                    "reason": "Maximum recovery attempts reached."
                }

                state.recovery_action = recovery

                return recovery

            # Allow another attempt
            state.retry_count += 1

            recovery = {
                "action": "relax_constraints",
                "reason": (
                    "No suitable products were found. "
                    "The search constraints should be relaxed."
                )
            }

            state.recovery_action = recovery

            return recovery

        # TOOL FAILURE
        if status == "failure":

            # Maximum retry limit reached
            if state.retry_count >= self.MAX_RETRIES:

                state.add_error(
                    source="recovery",
                    message="Maximum tool retries reached."
                )

                state.status = "failed"

                recovery = {
                    "action": "stop",
                    "reason": "Maximum retry attempts reached."
                }

                state.recovery_action = recovery

                return recovery

            # Retry failed tool
            state.retry_count += 1

            recovery = {
                "action": "retry",
                "reason": "The tool failed and should be retried."
            }

            state.recovery_action = recovery

            return recovery

        # UNKNOWN RESULT
        state.add_error(
            source="recovery",
            message=(
                "Unable to determine an appropriate "
                "recovery strategy."
            )
        )

        state.status = "failed"

        recovery = {
            "action": "stop",
            "reason": "Unknown execution outcome."
        }

        state.recovery_action = recovery

        return recovery
