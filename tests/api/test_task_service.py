import pytest

from agent_tasks.models import AgentTask
from agent.task_service import AgentTaskService


@pytest.mark.django_db
def test_execute_task():
    task = AgentTask.objects.create(
        task_id="service-test-001",
        goal="Find a protein bar under ₹150 with at least 20g protein and less than 5g added sugar",
        status="pending",
    )

    service = AgentTaskService()

    result = service.execute_task(task.task_id)

    assert result.task_id == task.task_id
    assert result.status == "waiting_for_approval"
    assert result.approval_required is True
    assert result.approval_status == "pending"


@pytest.mark.django_db
def test_execute_unknown_task():
    service = AgentTaskService()

    with pytest.raises(AgentTask.DoesNotExist):
        service.execute_task("does-not-exist")
