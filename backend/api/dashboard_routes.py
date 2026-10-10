from fastapi import APIRouter, HTTPException
from agent_tasks.models import AgentTask

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


@router.get("/tasks")
def list_tasks(limit: int = 50, offset: int = 0):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="offset cannot be negative",
        )

    queryset = AgentTask.objects.order_by("-created_at")
    total = queryset.count()
    tasks = queryset[offset:offset + limit]

    return {
        "items": [
            {
                "task_id": task.task_id,
                "goal": task.goal,
                "status": task.status,
                "approval_required": task.approval_required,
                "approval_status": task.approval_status,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }
            for task in tasks
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }