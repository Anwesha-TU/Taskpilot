from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    """Store the complete working state of one agent task."""

    goal: str

    constraints: Dict[str, Any] = field(default_factory=dict)
    plan: List[str] = field(default_factory=list)
    current_step: int = 0

    observations: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    retry_count: int = 0
    recovery_action: Optional[Dict[str, Any]] = None

    approval_required: bool = False
    approval_status: Optional[str] = None

    verification_result: Optional[Dict[str, Any]] = None
    status: str = "initialized"
    final_result: Optional[Dict[str, Any]] = None

    def add_observation(
        self,
        observation_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Record information discovered during execution."""
        self.observations.append({
            "type": observation_type,
            "data": data,
        })

    def add_action(
        self,
        tool: str,
        input_data: Dict[str, Any],
        output_data: Any,
        status: str = "success",
    ) -> None:
        """Record a tool execution."""
        self.actions.append({
            "tool": tool,
            "input": input_data,
            "output": output_data,
            "status": status,
        })

    def add_error(
        self,
        source: str,
        message: str,
    ) -> None:
        """Record an execution error."""
        self.errors.append({
            "source": source,
            "message": message,
        })

    def next_step(self) -> None:
        """Advance to the next step in the plan."""
        self.current_step += 1

    @property
    def current_plan_step(self) -> Optional[str]:
        """Return the current plan step, or None when finished."""
        if 0 <= self.current_step < len(self.plan):
            return self.plan[self.current_step]

        return None