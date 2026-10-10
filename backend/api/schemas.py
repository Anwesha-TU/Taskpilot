from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    file_path: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    goal: str
    status: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    plan: List[Any] = Field(default_factory=list)
    current_step: int = 0
    observations: List[Any] = Field(default_factory=list)
    actions: List[Any] = Field(default_factory=list)
    errors: List[Any] = Field(default_factory=list)
    retry_count: int = 0
    recovery_action: Dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = False
    approval_status: str = "pending"
    verification_result: Dict[str, Any] = Field(default_factory=dict)
    final_result: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime
    execution_duration_seconds: Optional[float] = None


class ApprovalResponse(BaseModel):
    task_id: str
    status: str
    approval_status: str
    message: str