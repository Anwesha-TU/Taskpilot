
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException

from agent.state import AgentState
from agent.task_service import AgentTaskService
from agent.worker import AgentWorker
from agent_tasks.models import AgentTask, InvoiceRecord
from api.schemas import ApprovalResponse, TaskRequest, TaskResponse


router = APIRouter(prefix="/api/v1")
task_service = AgentTaskService()


def generate_task_id() -> str:
    return f"task_{uuid.uuid4().hex}"


def serialize_task(task: AgentTask) -> dict:
    duration = None

    if task.started_at is not None and task.completed_at is not None:
        duration = max(
            0.0,
            (task.completed_at - task.started_at).total_seconds(),
        )

    return {
        "task_id": task.task_id,
        "goal": task.goal,
        "status": task.status,
        "constraints": task.constraints or {},
        "plan": task.plan or [],
        "current_step": task.current_step,
        "observations": task.observations or [],
        "actions": task.actions or [],
        "errors": task.errors or [],
        "retry_count": task.retry_count,
        "recovery_action": task.recovery_action or {},
        "approval_required": task.approval_required,
        "approval_status": task.approval_status,
        "verification_result": task.verification_result or {},
        "final_result": task.final_result or {},
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "updated_at": task.updated_at,
        "execution_duration_seconds": duration,
    }


def load_state(task: AgentTask) -> AgentState:
    return AgentState(
        goal=task.goal,
        constraints=dict(task.constraints or {}),
        plan=list(task.plan or []),
        current_step=task.current_step,
        observations=list(task.observations or []),
        actions=list(task.actions or []),
        errors=list(task.errors or []),
        retry_count=task.retry_count,
        recovery_action=task.recovery_action or {},
        approval_required=task.approval_required,
        approval_status=task.approval_status or "pending",
        verification_result=task.verification_result or {},
        final_result=task.final_result or {},
        status=task.status,
    )


def save_state(task: AgentTask, state: AgentState) -> None:
    task.status = state.status
    task.constraints = dict(state.constraints or {})
    task.plan = list(state.plan or [])
    task.current_step = state.current_step
    task.observations = list(state.observations or [])
    task.actions = list(state.actions or [])
    task.errors = list(state.errors or [])
    task.retry_count = state.retry_count
    task.recovery_action = state.recovery_action or {}
    task.approval_required = state.approval_required
    task.approval_status = state.approval_status or "pending"
    task.verification_result = state.verification_result or {}
    task.final_result = state.final_result or {}

    if state.status in {"completed", "failed", "rejected"}:
        task.completed_at = task.completed_at or timezone.now()

    task.save()


def execute_background_task(task_id: str) -> None:
    try:
        task = AgentTask.objects.get(task_id=task_id)
        constraints = dict(task.constraints or {})
        file_path = constraints.get("file_path")
        is_invoice = bool(file_path) or "invoice" in task.goal.lower()

        if not is_invoice:
            task_service.execute_task(task_id)
            return

        if not file_path:
            raise ValueError(
                "Invoice image was not attached. Upload an image and "
                "submit the task again."
            )

        image_path = Path(file_path).expanduser()
        if not image_path.is_absolute():
            image_path = Path.cwd() / image_path

        if not image_path.is_file():
            raise FileNotFoundError(
                f"Invoice image was not found on the backend: {image_path}"
            )

        image_path = image_path.resolve()
        task.status = "running"
        task.started_at = timezone.now()
        task.errors = []
        task.save(
            update_fields=[
                "status",
                "started_at",
                "errors",
                "updated_at",
            ]
        )

        state = AgentWorker().run(
            goal=task.goal,
            file_path=str(image_path),
        )

        state.constraints = dict(state.constraints or {})
        state.constraints["file_path"] = str(image_path)
        save_state(task, state)

    except Exception as exc:
        try:
            task = AgentTask.objects.get(task_id=task_id)
            task.status = "failed"
            task.errors = list(task.errors or []) + [
                {
                    "source": "background_worker",
                    "message": str(exc),
                }
            ]
            task.completed_at = timezone.now()
            task.save(
                update_fields=[
                    "status",
                    "errors",
                    "completed_at",
                    "updated_at",
                ]
            )
        except AgentTask.DoesNotExist:
            pass


@router.post("/tasks", response_model=TaskResponse)
def create_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
):
    task_id = generate_task_id()

    constraints = {}
    if request.file_path:
        constraints["file_path"] = request.file_path

    task = AgentTask.objects.create(
        task_id=task_id,
        goal=request.goal,
        status="pending",
        constraints=constraints,
        plan=[],
        current_step=0,
        observations=[],
        actions=[],
        errors=[],
        retry_count=0,
        recovery_action={},
        approval_required=False,
        approval_status="pending",
        verification_result={},
        final_result={},
    )

    background_tasks.add_task(execute_background_task, task_id)
    return serialize_task(task)


@router.get("/tasks")
def list_tasks(limit: int = 100):
    limit = max(1, min(limit, 500))
    tasks = AgentTask.objects.order_by("-created_at")[:limit]
    return [serialize_task(task) for task in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str):
    try:
        task = AgentTask.objects.get(task_id=task_id)
    except AgentTask.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")

    return serialize_task(task)


def is_invoice_task(task: AgentTask, state: AgentState) -> bool:
    plan = state.plan or []
    constraints = task.constraints or {}

    return (
        bool(constraints.get("file_path"))
        or isinstance((state.final_result or {}).get("invoice"), dict)
        or any("invoice" in str(step).lower() for step in plan)
        or "invoice" in task.goal.lower()
    )


def get_invoice_result(state: AgentState):
    final_result = state.final_result or {}
    invoice_data = final_result.get("invoice")

    if isinstance(invoice_data, dict):
        return invoice_data

    for observation in reversed(state.observations or []):
        if observation.get("type") == "invoice_fields":
            data = observation.get("data", {})
            if isinstance(data, dict):
                return data

    return None


def get_invoice_fields(invoice_data: dict) -> dict:
    fields = invoice_data.get("fields")
    if isinstance(fields, dict):
        return fields
    return invoice_data


def parse_invoice_total(fields: dict):
    total_value = fields.get("total")

    if total_value in (None, ""):
        return None

    try:
        total = Decimal(str(total_value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invoice total is not a valid decimal amount",
        )

    if not total.is_finite() or total < 0:
        raise HTTPException(
            status_code=400,
            detail="Invoice total must be a finite, non-negative amount",
        )

    return total


@router.post(
    "/tasks/{task_id}/approve",
    response_model=ApprovalResponse,
)
def approve_task(task_id: str):
    try:
        task = AgentTask.objects.get(task_id=task_id)
    except AgentTask.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")

    state = load_state(task)

    if not state.approval_required:
        raise HTTPException(
            status_code=400,
            detail="This task does not require approval",
        )

    if state.approval_status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Task approval is no longer pending",
        )

    invoice_task = is_invoice_task(task, state)
    invoice_fields = {}
    verification = state.verification_result or {}
    total = None

    if invoice_task:
        invoice_data = get_invoice_result(state)

        if not isinstance(invoice_data, dict):
            raise HTTPException(
                status_code=400,
                detail="No extracted invoice data is available to approve",
            )

        if not verification.get("valid", False):
            raise HTTPException(
                status_code=400,
                detail="Invoice verification failed; approval is blocked",
            )

        invoice_fields = get_invoice_fields(invoice_data)

        if not invoice_fields:
            raise HTTPException(
                status_code=400,
                detail="Extracted invoice fields are empty",
            )

        if verification.get("missing_fields"):
            raise HTTPException(
                status_code=400,
                detail="Invoice has missing fields and cannot be approved",
            )

        if verification.get("amount_valid") is not True:
            raise HTTPException(
                status_code=400,
                detail="Invoice amount validation failed",
            )

        total = parse_invoice_total(invoice_fields)

        if total is None:
            raise HTTPException(
                status_code=400,
                detail="Invoice total is required before approval",
            )

    state = AgentWorker().approve(state)

    if state.approval_status != "approved":
        save_state(task, state)
        raise HTTPException(
            status_code=400,
            detail="The worker did not approve this task",
        )

    with transaction.atomic():
        save_state(task, state)

        if invoice_task:
            source_file = (task.constraints or {}).get("file_path", "")

            if not source_file:
                for action in state.actions or []:
                    action_input = action.get("input", {})
                    if action.get("tool") in {
                        "ocr_invoice",
                        "ocr_product_label",
                        "inspect_invoice",
                    }:
                        source_file = action_input.get("file_path", "")
                        if source_file:
                            break

            InvoiceRecord.objects.update_or_create(
                task_id=task.task_id,
                defaults={
                    "vendor": str(invoice_fields.get("vendor") or ""),
                    "invoice_number": str(
                        invoice_fields.get("invoice_number") or ""
                    ),
                    "invoice_date": str(
                        invoice_fields.get("date")
                        or invoice_fields.get("invoice_date")
                        or ""
                    ),
                    "currency": str(invoice_fields.get("currency") or ""),
                    "total": total,
                    "source_file": str(source_file or ""),
                    "verification_result": verification,
                    "approval_status": "approved",
                },
            )

    return {
        "task_id": task.task_id,
        "status": task.status,
        "approval_status": task.approval_status,
        "message": (
            "Task approved and invoice record saved"
            if invoice_task
            else "Task approved successfully"
        ),
    }


@router.post(
    "/tasks/{task_id}/reject",
    response_model=ApprovalResponse,
)
def reject_task(task_id: str):
    try:
        task = AgentTask.objects.get(task_id=task_id)
    except AgentTask.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")

    state = load_state(task)

    if not state.approval_required:
        raise HTTPException(
            status_code=400,
            detail="This task does not require approval",
        )

    if state.approval_status != "pending":
        raise HTTPException(
            status_code=400,
            detail="Task approval is no longer pending",
        )

    state = AgentWorker().reject(state)
    save_state(task, state)

    return {
        "task_id": task.task_id,
        "status": task.status,
        "approval_status": task.approval_status,
        "message": "Task rejected successfully",
    }
