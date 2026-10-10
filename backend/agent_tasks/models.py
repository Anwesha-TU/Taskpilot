from django.db import models


class AgentTask(models.Model):
    task_id = models.CharField(max_length=100, unique=True, db_index=True)
    goal = models.TextField()

    status = models.CharField(
        max_length=50,
        default="pending",
        db_index=True,
    )

    constraints = models.JSONField(default=dict, blank=True)
    plan = models.JSONField(default=list, blank=True)
    current_step = models.IntegerField(default=0)

    observations = models.JSONField(default=list, blank=True)
    actions = models.JSONField(default=list, blank=True)
    errors = models.JSONField(default=list, blank=True)

    retry_count = models.IntegerField(default=0)
    recovery_action = models.JSONField(default=dict, blank=True)

    approval_required = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=30,
        default="pending",
    )

    verification_result = models.JSONField(default=dict, blank=True)
    final_result = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.task_id}: {self.goal[:50]}"

from agent_tasks.invoice_models import InvoiceRecord