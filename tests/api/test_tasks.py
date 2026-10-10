import pytest
from fastapi.testclient import TestClient

from api.main import app
from agent.task_service import AgentTaskService
from agent.worker import AgentWorker
from agent_tasks.models import AgentTask

pytestmark = pytest.mark.django_db(transaction=True)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    AgentTask.objects.all().delete()


def test_create_task():
    response = client.post(
        "/api/v1/tasks",
        json={
            "goal": (
                "Find a protein bar under ₹150 with at least 20g protein "
                "and less than 5g added sugar"
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "task_id" in data
    assert data["goal"] == (
        "Find a protein bar under ₹150 with at least 20g protein "
        "and less than 5g added sugar"
    )
    assert data["status"] == "pending"
    assert data["approval_required"] is False
    assert data["approval_status"] == "pending"


def test_get_task():
    create_response = client.post(
        "/api/v1/tasks",
        json={
            "goal": "Find a protein bar under ₹150 with at least 20g protein"
        },
    )

    assert create_response.status_code == 200

    task_id = create_response.json()["task_id"]

    response = client.get(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == task_id
    assert data["goal"] == (
        "Find a protein bar under ₹150 with at least 20g protein"
    )


def test_get_unknown_task():
    response = client.get("/api/v1/tasks/does-not-exist")

    assert response.status_code == 404


def test_create_task_with_empty_goal():
    response = client.post(
        "/api/v1/tasks",
        json={"goal": ""},
    )

    assert response.status_code == 422


def test_create_task_without_goal():
    response = client.post(
        "/api/v1/tasks",
        json={},
    )

    assert response.status_code == 422


def test_approve_task():
    create_response = client.post(
        "/api/v1/tasks",
        json={
            "goal": (
                "Find a protein bar under ₹150 with at least 20g protein "
                "and less than 5g added sugar"
            )
        },
    )

    assert create_response.status_code == 200

    task_id = create_response.json()["task_id"]

    AgentTaskService().execute_task(task_id)

    task = AgentTask.objects.get(task_id=task_id)

    assert task.status == "waiting_for_approval"
    assert task.approval_required is True
    assert task.approval_status == "pending"
    assert task.started_at is not None
    assert task.completed_at is None

    response = client.post(
        f"/api/v1/tasks/{task_id}/approve"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == task_id
    assert data["status"] == "completed"
    assert data["approval_status"] == "approved"


def test_reject_task():
    create_response = client.post(
        "/api/v1/tasks",
        json={
            "goal": "Find a protein bar under ₹150 with at least 20g protein"
        },
    )

    assert create_response.status_code == 200

    task_id = create_response.json()["task_id"]

    AgentTaskService().execute_task(task_id)

    task = AgentTask.objects.get(task_id=task_id)

    assert task.status == "waiting_for_approval"
    assert task.approval_required is True
    assert task.approval_status == "pending"
    assert task.started_at is not None
    assert task.completed_at is None

    response = client.post(
        f"/api/v1/tasks/{task_id}/reject"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == task_id
    assert data["approval_status"] == "rejected"


def test_approve_unknown_task():
    response = client.post(
        "/api/v1/tasks/does-not-exist/approve"
    )

    assert response.status_code == 404


def test_reject_unknown_task():
    response = client.post(
        "/api/v1/tasks/does-not-exist/reject"
    )

    assert response.status_code == 404


def test_failed_task_persists_error(monkeypatch):
    def failing_run(self, goal):
        raise RuntimeError("Simulated worker failure")

    monkeypatch.setattr(
        AgentWorker,
        "run",
        failing_run,
    )

    task = AgentTask.objects.create(
        task_id="task_failure_test",
        goal="Find a protein bar",
        status="pending",
    )

    with pytest.raises(RuntimeError, match="Simulated worker failure"):
        AgentTaskService().execute_task(task.task_id)

    task.refresh_from_db()

    assert task.status == "failed"
    assert task.started_at is not None
    assert task.completed_at is not None
    assert len(task.errors) == 1
    assert task.errors[0]["source"] == "task_service"
    assert task.errors[0]["message"] == "Simulated worker failure"


def test_task_lifecycle_timestamps():
    task = AgentTask.objects.create(
        task_id="task_timestamp_test",
        goal=(
            "Find a protein bar under ₹150 with at least 20g protein "
            "and less than 5g added sugar"
        ),
        status="pending",
    )

    AgentTaskService().execute_task(task.task_id)

    task.refresh_from_db()

    assert task.started_at is not None
    assert task.updated_at is not None
    assert task.started_at <= task.updated_at
    assert task.status == "waiting_for_approval"


def test_approve_task_without_approval_required():
    task = AgentTask.objects.create(
        task_id="task_no_approval",
        goal="Find a protein bar",
        status="completed",
        approval_required=False,
        approval_status="pending",
    )

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/approve"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "This task does not require approval"
    )


def test_reject_task_without_approval_required():
    task = AgentTask.objects.create(
        task_id="task_no_approval_reject",
        goal="Find a protein bar",
        status="completed",
        approval_required=False,
        approval_status="pending",
    )

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/reject"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "This task does not require approval"
    )


def test_duplicate_approval_is_rejected():
    task = AgentTask.objects.create(
        task_id="task_duplicate_approval",
        goal="Find a protein bar",
        status="waiting_for_approval",
        approval_required=True,
        approval_status="approved",
    )

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/approve"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Task approval is no longer pending"
    )


def test_duplicate_rejection_is_rejected():
    task = AgentTask.objects.create(
        task_id="task_duplicate_rejection",
        goal="Find a protein bar",
        status="rejected",
        approval_required=True,
        approval_status="rejected",
    )

    response = client.post(
        f"/api/v1/tasks/{task.task_id}/reject"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Task approval is no longer pending"
    )


from datetime import timedelta

from django.utils import timezone


def test_task_response_includes_observability_fields():
    task = AgentTask.objects.create(
        task_id="task_observability_test",
        goal="Find a protein bar",
        status="waiting_for_approval",
        constraints={"category": "protein_bar"},
        plan=["search_alternatives", "verify_result"],
        current_step=1,
        observations=[{"type": "search", "data": {"count": 2}}],
        actions=[{"tool": "search_products", "status": "success"}],
        errors=[],
        retry_count=1,
        recovery_action={"action": "continue"},
        approval_required=True,
        approval_status="pending",
    )

    response = client.get(f"/api/v1/tasks/{task.task_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["observations"] == task.observations
    assert data["actions"] == task.actions
    assert data["errors"] == []
    assert data["retry_count"] == 1
    assert data["recovery_action"] == {"action": "continue"}
    assert data["execution_duration_seconds"] is None
    assert "created_at" in data
    assert "updated_at" in data


def test_task_response_calculates_execution_duration():
    started_at = timezone.now() - timedelta(seconds=12)
    completed_at = started_at + timedelta(seconds=5)

    task = AgentTask.objects.create(
        task_id="task_duration_test",
        goal="Find a protein bar",
        status="completed",
        started_at=started_at,
        completed_at=completed_at,
    )

    response = client.get(f"/api/v1/tasks/{task.task_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["execution_duration_seconds"] == 5.0
    assert data["started_at"] is not None
    assert data["completed_at"] is not None
