
from django.db import models


class InvoiceRecord(models.Model):
    task_id = models.CharField(max_length=100, unique=True, db_index=True)
    vendor = models.CharField(max_length=255, blank=True, default="")
    invoice_number = models.CharField(max_length=100, blank=True, default="")
    invoice_date = models.CharField(max_length=30, blank=True, default="")
    currency = models.CharField(max_length=10, blank=True, default="")
    total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    source_file = models.CharField(max_length=255, blank=True, default="")
    verification_result = models.JSONField(default=dict, blank=True)
    approval_status = models.CharField(max_length=30, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice_number or self.task_id}: {self.vendor}"
