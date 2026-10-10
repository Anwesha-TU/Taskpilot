
from django.utils import timezone

from agent.worker import AgentWorker
from agent_tasks.models import AgentTask


class AgentTaskService:
    def __init__(self):
        self.worker = AgentWorker()

    def execute_task(self, task_id: str) -> AgentTask:
        task = AgentTask.objects.get(task_id=task_id)

        task.status = "running"
        task.started_at = timezone.now()
        task.save(
            update_fields=[
                "status",
                "started_at",
                "updated_at",
            ]
        )

        try:
            file_path = (task.constraints or {}).get("file_path")

            if file_path:
                state = self.worker.run(
                    task.goal,
                    file_path=file_path,
                )
            else:
                state = self.worker.run(task.goal)

            task.status = state.status
            task.constraints = dict(state.constraints or {})
            task.plan = list(state.plan or [])
            task.current_step = (
                state.current_step
                if state.current_step is not None
                else 0
            )
            task.observations = list(state.observations or [])
            task.actions = list(state.actions or [])
            task.errors = list(state.errors or [])
            task.retry_count = state.retry_count
            task.recovery_action = dict(state.recovery_action or {})
            task.approval_required = state.approval_required
            task.approval_status = state.approval_status or "pending"
            task.verification_result = dict(
                state.verification_result or {}
            )
            task.final_result = (
                dict(state.final_result)
                if state.final_result is not None
                else {}
            )

            if state.status in {"completed", "failed", "rejected"}:
                task.completed_at = timezone.now()

            task.save()
            return task

        except Exception as exc:
            task.status = "failed"
            task.errors = list(task.errors or []) + [
                {
                    "source": "task_service",
                    "message": str(exc),
                }
            ]
            task.completed_at = timezone.now()
            task.save()
            raise
