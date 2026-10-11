import json
import mimetypes
import os
import sys
from pathlib import Path

import requests

from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

API_BASE_URL = os.getenv(
    "NUTRICOACH_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

POLL_INTERVAL_MS = 2000

APP_STYLE = """
QWidget {
    background: #f6f8fb;
    color: #172033;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QFrame#Sidebar, QFrame#Panel, QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #e4e9f1;
    border-radius: 12px;
}
QLabel#Brand {
    font-size: 21px;
    font-weight: 700;
    color: #176b52;
}
QLabel#PageTitle {
    font-size: 23px;
    font-weight: 700;
}
QLabel#Muted {
    color: #667085;
}
QLabel#MetricValue {
    font-size: 21px;
    font-weight: 700;
}
QLabel#SectionTitle {
    font-size: 14px;
    font-weight: 700;
}
QLineEdit, QListWidget, QTabWidget::pane {
    background: #ffffff;
    border: 1px solid #dce3ed;
    border-radius: 8px;
    padding: 8px;
    selection-background-color: #d8f3e8;
    selection-color: #164e3b;
}
QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #dce3ed;
    border-radius: 8px;
    padding: 8px;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QPushButton {
    background: #edf2f7;
    color: #243247;
    border: 1px solid #dce3ed;
    border-radius: 8px;
    padding: 9px 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: #e3eaf3;
}
QPushButton#PrimaryButton {
    background: #167653;
    color: white;
    border: 1px solid #167653;
}
QPushButton#PrimaryButton:hover {
    background: #116344;
}
QPushButton#ApproveButton {
    background: #e2f7ec;
    color: #12643e;
    border: 1px solid #bce8d0;
}
QPushButton#RejectButton {
    background: #fff0f0;
    color: #a12b2b;
    border: 1px solid #f4cccc;
}
QPushButton:disabled {
    color: #98a2b3;
    background: #f2f4f7;
}
QListWidget::item {
    padding: 10px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background: #e6f5ee;
    color: #14583f;
}
QTabBar::tab {
    background: #edf2f7;
    padding: 9px 13px;
    margin-right: 3px;
    border-radius: 6px;
}
QTabBar::tab:selected {
    background: #dff3e9;
    color: #14583f;
}
"""


class ApiWorker(QThread):
    succeeded = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(
        self,
        action,
        method,
        path,
        payload=None,
        upload_path=None,
        parent=None,
    ):
        super().__init__(parent)
        self.action = action
        self.method = method
        self.path = path
        self.payload = payload
        self.upload_path = upload_path

    def run(self):
        try:
            url = f"{API_BASE_URL}{self.path}"

            if self.upload_path:
                file_path = Path(self.upload_path).expanduser().resolve()

                if not file_path.is_file():
                    self.failed.emit(
                        self.action,
                        f"File does not exist: {file_path}",
                    )
                    return

                mime_type = (
                    mimetypes.guess_type(file_path.name)[0]
                    or "application/octet-stream"
                )

                with file_path.open("rb") as image_file:
                    response = requests.post(
                        url,
                        files={
                            "file": (
                                file_path.name,
                                image_file,
                                mime_type,
                            )
                        },
                        timeout=120,
                    )
            else:
                response = requests.request(
                    self.method,
                    url,
                    json=self.payload,
                    timeout=30,
                )

            try:
                body = response.json()
            except ValueError:
                body = {
                    "detail": response.text
                    or "The API returned an empty response."
                }

            if not response.ok:
                if isinstance(body, dict):
                    message = (
                        body.get("detail")
                        or body.get("message")
                        or str(body)
                    )
                else:
                    message = str(body)

                self.failed.emit(
                    self.action,
                    f"HTTP {response.status_code}: {message}",
                )
                return

            self.succeeded.emit(self.action, body)

        except (requests.RequestException, OSError) as exc:
            self.failed.emit(
                self.action,
                f"Request to {API_BASE_URL} failed:\n{exc}",
            )


class MetricCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        label = QLabel(title)
        label.setObjectName("Muted")

        self.value = QLabel("—")
        self.value.setObjectName("MetricValue")

        layout.addWidget(label)
        layout.addWidget(self.value)


class NutriCoachDashboard(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Agent Workspace")
        self.resize(1320, 850)
        self.setMinimumSize(1050, 700)

        self.selected_task_id = None
        self.current_task = None
        self.request_busy = False
        self.polling_busy = False
        self.workers = set()

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(14)
        self.setCentralWidget(root)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter)

        self.sidebar = self.build_sidebar()
        self.workspace = self.build_workspace()

        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.workspace)
        splitter.setSizes([285, 1000])

        self.setStyleSheet(APP_STYLE)

        self.refresh_button.clicked.connect(self.refresh_history)
        self.new_task_button.clicked.connect(self.create_task)
        self.upload_invoice_button.clicked.connect(self.upload_invoice)

        self.history.itemSelectionChanged.connect(
            self.on_history_selection_changed
        )

        self.approve_button.clicked.connect(
            lambda: self.submit_decision("approve")
        )
        self.reject_button.clicked.connect(
            lambda: self.submit_decision("reject")
        )

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(POLL_INTERVAL_MS)
        self.poll_timer.timeout.connect(self.poll_task)
        self.poll_timer.start()

        self.refresh_history()

    def build_sidebar(self):
        panel = QFrame()
        panel.setObjectName("Sidebar")
        panel.setMinimumWidth(245)
        panel.setMaximumWidth(350)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(12)

        brand = QLabel("Agent Workspace")
        brand.setObjectName("Brand")

        subtitle = QLabel("AGENT CONTROL CENTER")
        subtitle.setObjectName("Muted")

        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(12)

        history_header = QHBoxLayout()

        history_title = QLabel("Task history")
        history_title.setObjectName("SectionTitle")

        self.refresh_button = QPushButton("Refresh")

        history_header.addWidget(history_title)
        history_header.addStretch()
        history_header.addWidget(self.refresh_button)
        layout.addLayout(history_header)

        self.history = QListWidget()
        self.history.setSpacing(3)
        self.history.setToolTip("Tasks loaded from the backend.")
        layout.addWidget(self.history, 1)

        note = QLabel(
            "Select a task to inspect its plan, results, "
            "verification, and approval status."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        return panel

    def build_workspace(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(12)

        top = QHBoxLayout()
        heading = QVBoxLayout()

        title = QLabel("Agent operations")
        title.setObjectName("PageTitle")

        subtitle = QLabel(
            "Create tasks, follow execution, and review outcomes."
        )
        subtitle.setObjectName("Muted")

        heading.addWidget(title)
        heading.addWidget(subtitle)
        top.addLayout(heading)
        top.addStretch()

        self.connection_label = QLabel(f"API: {API_BASE_URL}")
        self.connection_label.setObjectName("Muted")
        top.addWidget(self.connection_label, alignment=Qt.AlignTop)
        layout.addLayout(top)

        create_panel = QFrame()
        create_panel.setObjectName("Panel")
        create_layout = QVBoxLayout(create_panel)
        create_layout.setContentsMargins(16, 14, 16, 14)
        create_layout.setSpacing(9)

        create_title = QLabel("Create a task")
        create_title.setObjectName("SectionTitle")
        create_layout.addWidget(create_title)

        self.goal_input = QLineEdit()
        self.goal_input.setPlaceholderText(
            "e.g. Find available products and compare prices"
        )
        self.goal_input.returnPressed.connect(self.create_task)
        create_layout.addWidget(self.goal_input)

        create_actions = QHBoxLayout()

        create_hint = QLabel(
            "Describe the outcome you want the agent to achieve."
        )
        create_hint.setObjectName("Muted")
        create_actions.addWidget(create_hint)
        create_actions.addStretch()

        self.upload_invoice_button = QPushButton("Upload Invoice")
        self.upload_invoice_button.setToolTip(
            "Select an invoice image and run invoice extraction."
        )
        create_actions.addWidget(self.upload_invoice_button)

        self.new_task_button = QPushButton("Create task")
        self.new_task_button.setObjectName("PrimaryButton")
        create_actions.addWidget(self.new_task_button)

        create_layout.addLayout(create_actions)
        layout.addWidget(create_panel)

        self.task_heading = QLabel("Select a task to view details")
        self.task_heading.setObjectName("SectionTitle")
        layout.addWidget(self.task_heading)

        metrics = QGridLayout()
        metrics.setSpacing(10)

        self.status_card = MetricCard("STATUS")
        self.step_card = MetricCard("CURRENT STEP")
        self.retry_card = MetricCard("RETRIES")
        self.duration_card = MetricCard("EXECUTION TIME")

        metrics.addWidget(self.status_card, 0, 0)
        metrics.addWidget(self.step_card, 0, 1)
        metrics.addWidget(self.retry_card, 0, 2)
        metrics.addWidget(self.duration_card, 0, 3)
        layout.addLayout(metrics)

        approval_panel = QFrame()
        approval_panel.setObjectName("Panel")
        approval_layout = QHBoxLayout(approval_panel)
        approval_layout.setContentsMargins(14, 10, 14, 10)

        approval_text = QVBoxLayout()

        self.approval_title = QLabel("Human review")
        self.approval_title.setObjectName("SectionTitle")

        self.approval_description = QLabel(
            "Select a task to see whether review is required."
        )
        self.approval_description.setObjectName("Muted")
        self.approval_description.setWordWrap(True)

        approval_text.addWidget(self.approval_title)
        approval_text.addWidget(self.approval_description)
        approval_layout.addLayout(approval_text, 1)

        self.approve_button = QPushButton("Approve")
        self.approve_button.setObjectName("ApproveButton")

        self.reject_button = QPushButton("Reject")
        self.reject_button.setObjectName("RejectButton")

        self.approve_button.setEnabled(False)
        self.reject_button.setEnabled(False)

        approval_layout.addWidget(self.approve_button)
        approval_layout.addWidget(self.reject_button)
        layout.addWidget(approval_panel)

        self.tabs = QTabWidget()

        self.plan_view = self.make_text_view()
        self.actions_view = self.make_text_view()
        self.observations_view = self.make_text_view()
        self.errors_view = self.make_text_view()
        self.verification_view = self.make_text_view()
        self.result_view = self.make_text_view()

        self.invoice_table = QTableWidget(0, 3)
        self.invoice_table.setHorizontalHeaderLabels(
            ["Field", "Extracted Value", "Status"]
        )
        self.invoice_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.invoice_table.setAlternatingRowColors(True)
        self.invoice_table.setWordWrap(True)

        self.invoice_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.invoice_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.invoice_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )

        self.tabs.addTab(self.plan_view, "Plan")
        self.tabs.addTab(self.actions_view, "Tool logs")
        self.tabs.addTab(self.observations_view, "Observations")
        self.tabs.addTab(self.errors_view, "Errors & recovery")
        self.tabs.addTab(self.verification_view, "Verification")
        self.tabs.addTab(self.result_view, "Final result")
        self.tabs.addTab(self.invoice_table, "Invoice fields")

        layout.addWidget(self.tabs, 1)
        return panel

    @staticmethod
    def make_text_view():
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        view.setPlaceholderText("Task data will appear here.")
        return view

    def start_request(
        self,
        action,
        method,
        path,
        payload=None,
        background=False,
        upload_path=None,
    ):
        if background:
            if self.polling_busy:
                return False
            self.polling_busy = True
        else:
            if self.request_busy:
                return False
            self.request_busy = True
            self.set_controls_enabled(False)

        worker = ApiWorker(
            action,
            method,
            path,
            payload=payload,
            upload_path=upload_path,
            parent=self,
        )

        self.workers.add(worker)
        worker.succeeded.connect(self.on_request_succeeded)
        worker.failed.connect(self.on_request_failed)
        worker.finished.connect(
            lambda worker=worker, background=background:
            self.on_worker_finished(worker, background)
        )
        worker.start()
        return True

    def on_worker_finished(self, worker, background):
        self.workers.discard(worker)

        if background:
            self.polling_busy = False
        elif not self.request_busy:
            self.set_controls_enabled(True)

        worker.deleteLater()

    def release_foreground_request(self):
        self.request_busy = False
        self.set_controls_enabled(True)

    def set_controls_enabled(self, enabled):
        self.new_task_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self.goal_input.setEnabled(enabled)
        self.upload_invoice_button.setEnabled(enabled)
        self.update_approval_controls()

    def refresh_history(self):
        self.start_request(
            "list",
            "GET",
            "/api/v1/tasks?limit=100",
        )

    def create_task(self):
        goal = self.goal_input.text().strip()

        if not goal:
            QMessageBox.information(
                self,
                "Task goal required",
                "Enter a natural-language task first.",
            )
            return

        payload = {"goal": goal}

        invoice_keywords = (
            "invoice",
            "receipt",
            "bill image",
            "invoice image",
            "invoice number",
            "invoice date",
            "invoice total",
            "ocr",
        )

        is_invoice = any(
            keyword in goal.lower()
            for keyword in invoice_keywords
        )

        if is_invoice:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select invoice image",
                "",
                "Invoice images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;"
                "All files (*)",
            )

            if not file_path:
                return

            selected_path = Path(file_path).expanduser().resolve()

            if not selected_path.is_file():
                QMessageBox.warning(
                    self,
                    "Invoice image not found",
                    "Please select an existing invoice image.",
                )
                return

            payload["file_path"] = str(selected_path)

        started = self.start_request(
            "create",
            "POST",
            "/api/v1/tasks",
            payload=payload,
        )

        if started:
            self.approval_description.setText(
                "Task submitted. Waiting for the backend response..."
            )

    def upload_invoice(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select invoice image",
            "",
            "Invoice images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;"
            "All files (*)",
        )

        if not file_path:
            return

        selected_path = Path(file_path).expanduser().resolve()

        if not selected_path.is_file():
            QMessageBox.warning(
                self,
                "Invoice image not found",
                "Please select an existing invoice image.",
            )
            return

        self.start_request(
            "invoice_upload",
            "POST",
            "/api/v1/uploads/invoice",
            upload_path=str(selected_path),
        )

    def on_history_selection_changed(self):
        item = self.history.currentItem()
        if item is None:
            return

        task_id = item.data(Qt.UserRole)

        if task_id and task_id != self.selected_task_id:
            self.selected_task_id = task_id
            self.current_task = None
            self.update_approval_controls()

            self.start_request(
                "detail",
                "GET",
                f"/api/v1/tasks/{task_id}",
            )

    def poll_task(self):
        if self.polling_busy or self.request_busy:
            return

        if not self.selected_task_id:
            self.start_request(
                "poll_list",
                "GET",
                "/api/v1/tasks?limit=100",
                background=True,
            )
            return

        self.start_request(
            "poll_detail",
            "GET",
            f"/api/v1/tasks/{self.selected_task_id}",
            background=True,
        )

    def submit_decision(self, decision):
        if not self.selected_task_id:
            return

        if decision not in {"approve", "reject"}:
            return

        task_id = self.selected_task_id

        started = self.start_request(
            decision,
            "POST",
            f"/api/v1/tasks/{task_id}/{decision}",
            payload={},
        )

        if started:
            self.approval_description.setText(
                f"{decision.title()} request submitted. Updating task..."
            )

    def on_request_succeeded(self, action, data):
        if action not in {"poll_detail", "poll_list"}:
            self.release_foreground_request()

        if action in {"list", "poll_list"}:
            self.populate_history(data)
            return

        if action == "create":
            task_id = (
                data.get("task_id")
                if isinstance(data, dict)
                else None
            )

            self.goal_input.clear()

            if not task_id:
                self.approval_description.setText(
                    "The API responded, but no task ID was returned."
                )
                self.result_view.setPlainText(
                    self.human_readable_result(data)
                )
                return

            self.selected_task_id = task_id
            self.current_task = None

            self.approval_description.setText(
                "Task created. Loading its status automatically..."
            )

            self.result_view.setPlainText(
                self.human_readable_result(data)
            )

            self.start_request(
                "detail",
                "GET",
                f"/api/v1/tasks/{task_id}",
            )
            self.refresh_history()
            return

        if action in {"detail", "poll_detail"}:
            self.show_task(data)
            return

        if action in {"approve", "reject"}:
            message = (
                data.get("message")
                if isinstance(data, dict)
                else None
            )

            self.approval_description.setText(
                message or f"Task {action} accepted. Updating status..."
            )

            task_id = self.selected_task_id

            if task_id:
                self.start_request(
                    "detail",
                    "GET",
                    f"/api/v1/tasks/{task_id}",
                )
            return

        if action == "invoice_upload":
            self.result_view.setPlainText(
                self.human_readable_result(data)
            )
            self.tabs.setCurrentWidget(self.result_view)
            self.task_heading.setText("Invoice extraction result")
            self.approval_title.setText("Invoice upload")

            if isinstance(data, dict):
                status = data.get("status", "unknown")
                message = data.get(
                    "message",
                    "Invoice processing returned.",
                )

                self.approval_description.setText(
                    f"Processing status: {status}. {message}"
                )
            else:
                self.approval_description.setText(
                    "Review the invoice extraction response in Final result."
                )

            self.connection_label.setText("Invoice upload completed")
            self.connection_label.setStyleSheet("color: #167653;")
            return

    def on_request_failed(self, action, message):
        if action not in {"poll_detail", "poll_list"}:
            self.release_foreground_request()

        if action in {"poll_detail", "poll_list"}:
            self.connection_label.setText(
                "Automatic update failed; retrying..."
            )
            self.connection_label.setStyleSheet("color: #b42318;")
            return

        self.connection_label.setText("API request failed")
        self.connection_label.setStyleSheet("color: #b42318;")

        if action in {"create", "approve", "reject", "invoice_upload"}:
            QMessageBox.warning(self, "Request failed", message)
        elif action == "list":
            self.history.clear()
            self.history.addItem(
                "Could not load task history. Use Refresh to retry."
            )
        elif action == "detail":
            self.errors_view.setPlainText(message)

    def populate_history(self, tasks):
        if isinstance(tasks, dict):
            tasks = tasks.get("items", tasks.get("tasks", []))

        if not isinstance(tasks, list):
            tasks = []

        selected_id = self.selected_task_id
        selected_item = None

        self.history.blockSignals(True)
        self.history.clear()

        for task in tasks:
            if not isinstance(task, dict):
                continue

            task_id = task.get("task_id", "")
            goal = str(task.get("goal", "Untitled task")).strip()
            status = str(task.get("status", "unknown")).replace(
                "_", " "
            ).title()

            item = QListWidgetItem(
                f"{goal[:48]}\n{status}  ·  {task_id}"
            )

            item.setData(Qt.UserRole, task_id)
            item.setToolTip(
                f"{goal}\nTask ID: {task_id}\nStatus: {status}"
            )
            self.history.addItem(item)

            if task_id == selected_id:
                selected_item = item

        if selected_item is not None:
            self.history.setCurrentItem(selected_item)
        elif self.history.count() and not selected_id:
            selected_item = self.history.item(0)
            self.history.setCurrentItem(selected_item)

        self.history.blockSignals(False)

        self.connection_label.setText(
            f"Connected · {len(tasks)} tasks · auto-update enabled"
        )
        self.connection_label.setStyleSheet("color: #167653;")

        if not self.selected_task_id and selected_item is not None:
            self.selected_task_id = selected_item.data(Qt.UserRole)
            self.start_request(
                "detail",
                "GET",
                f"/api/v1/tasks/{self.selected_task_id}",
            )

    def show_task(self, task):
        if not isinstance(task, dict) or "task_id" not in task:
            return

        if task["task_id"] != self.selected_task_id:
            return

        previous_status = (
            self.current_task.get("status")
            if self.current_task
            else None
        )

        self.current_task = task
        new_status = task.get("status", "unknown")
        goal = task.get("goal", "Untitled task")

        self.task_heading.setText(
            f"{goal[:100]}  ·  {self.selected_task_id}"
        )

        self.status_card.value.setText(
            str(new_status).replace("_", " ").title()
        )

        plan = task.get("plan") or []

        self.step_card.value.setText(
            f"{task.get('current_step', 0)} / {len(plan)}"
        )

        self.retry_card.value.setText(str(task.get("retry_count", 0)))

        duration = task.get("execution_duration_seconds")

        if duration is None:
            active = new_status in {
                "pending",
                "planned",
                "running",
                "in_progress",
                "executing",
            }

            self.duration_card.value.setText(
                "In progress" if active else "—"
            )
        else:
            try:
                self.duration_card.value.setText(
                    f"{float(duration):.2f}s"
                )
            except (TypeError, ValueError):
                self.duration_card.value.setText(str(duration))

        approval_required = task.get("approval_required", False)
        approval_status = task.get("approval_status") or "not required"

        if new_status == "waiting_for_approval":
            description = (
                "The agent is waiting for your decision. "
                "Review the result, then approve or reject."
            )
        elif new_status == "completed":
            description = (
                "Task completed. The final result is available."
            )
        elif new_status == "failed":
            description = "Task failed. Check Errors & recovery."
        elif new_status == "rejected":
            description = "The task has been rejected."
        elif approval_status == "approved":
            description = "Approved. The backend is updating the task."
        else:
            description = (
                f"Approval required: "
                f"{'Yes' if approval_required else 'No'}"
                f" · Decision: "
                f"{str(approval_status).replace('_', ' ').title()}"
                f" · Status: {str(new_status).replace('_', ' ')}"
            )

        self.approval_description.setText(description)

        self.plan_view.setPlainText(self.pretty(plan))
        self.actions_view.setPlainText(
            self.pretty(task.get("actions", []))
        )
        self.observations_view.setPlainText(
            self.pretty(task.get("observations", []))
        )

        recovery = {
            "retry_count": task.get("retry_count", 0),
            "recovery_action": task.get("recovery_action", {}),
            "errors": task.get("errors", []),
        }

        self.errors_view.setPlainText(self.pretty(recovery))
        self.verification_view.setPlainText(
            self.pretty(task.get("verification_result", {}))
        )

        final_result = task.get("final_result") or {}

        # Display the final result in readable, labeled text.
        self.result_view.setPlainText(
            self.human_readable_result(final_result)
        )

        # Detect invoice tasks even when their structured output is
        # stored inside an action's output instead of final_result.
        goal_text = str(task.get("goal", "")).lower()
        task_text = self.pretty(task).lower()

        is_invoice = (
            "invoice" in goal_text
            or "invoice_processing"
            in str(task.get("task_type", "")).lower()
            or "invoice_processing"
            in str(final_result.get("task_type", "")).lower()
            or isinstance(final_result.get("invoice"), dict)
            or "suggested_subtotal" in task_text
            or "extract_invoice_fields" in task_text
        )

        if is_invoice:
            self.show_invoice_table(task)

        self.update_approval_controls()

        self.history.blockSignals(True)

        for index in range(self.history.count()):
            item = self.history.item(index)

            if item.data(Qt.UserRole) == self.selected_task_id:
                item.setText(
                    f"{goal[:48]}\n"
                    f"{str(new_status).replace('_', ' ').title()}"
                    f"  ·  {self.selected_task_id}"
                )
                break

        self.history.blockSignals(False)

        if previous_status != new_status:
            self.connection_label.setText(
                f"Task status updated: "
                f"{str(new_status).replace('_', ' ').title()}"
            )
            self.connection_label.setStyleSheet("color: #167653;")

    def show_invoice_table(self, task):
        """Find structured invoice data in final_result or recorded actions."""
        self.invoice_table.setRowCount(0)

        final_result = task.get("final_result") or {}

        verification = (
            final_result.get("verification")
            or task.get("verification_result")
            or {}
        )

        # Extraction data may be nested inside actions[*].output.
        def find_invoice_payload(node, depth=0):
            if depth > 12:
                return None

            if isinstance(node, dict):
                if (
                    isinstance(node.get("fields"), dict)
                    and any(
                        key in node
                        for key in (
                            "line_items",
                            "suggested_subtotal",
                            "vendor_suggestion",
                            "missing_fields",
                            "amount_valid",
                        )
                    )
                ):
                    return node

                for value in node.values():
                    found = find_invoice_payload(value, depth + 1)
                    if found is not None:
                        return found

            elif isinstance(node, (list, tuple)):
                for value in node:
                    found = find_invoice_payload(value, depth + 1)
                    if found is not None:
                        return found

            return None

        invoice = (
            final_result.get("invoice")
            if isinstance(final_result.get("invoice"), dict)
            else None
        )

        if not invoice or not isinstance(invoice.get("fields"), dict):
            invoice = find_invoice_payload(task)

        invoice = invoice or {}
        fields = invoice.get("fields") or {}
        missing_fields = set(invoice.get("missing_fields") or [])

        review_reasons = (
            verification.get("review_reasons")
            or invoice.get("review_reasons")
            or []
        )

        amount_valid = invoice.get("amount_valid")

        if amount_valid is None:
            amount_valid = verification.get("amount_valid")

        rows = []

        for field, value in fields.items():
            label = str(field).replace("_", " ").strip().title()

            unavailable = (
                value is None
                or (
                    isinstance(value, str)
                    and not value.strip()
                )
                or field in missing_fields
            )

            if unavailable:
                display_value = "Couldn't fetch"
                status = "Unavailable"
            else:
                display_value = (
                    self.pretty(value)
                    if isinstance(value, (dict, list))
                    else str(value)
                )

                if (
                    field in {"subtotal", "tax", "total"}
                    and amount_valid is False
                ):
                    status = "Needs review"
                else:
                    status = "Extracted"

            rows.append((label, display_value, status))

        # Never silently overwrite OCR values with calculated suggestions.
        suggested_subtotal = invoice.get("suggested_subtotal")

        if suggested_subtotal not in (None, ""):
            rows.append(
                (
                    "Suggested Subtotal (verify)",
                    str(suggested_subtotal),
                    "Suggested — verify against invoice",
                )
            )

        vendor_suggestion = invoice.get("vendor_suggestion")

        if vendor_suggestion not in (None, ""):
            rows.append(
                (
                    "Possible Vendor (inferred from email)",
                    str(vendor_suggestion),
                    "Unverified inference",
                )
            )

        line_items = (
            invoice.get("line_items")
            or fields.get("line_items")
            or []
        )

        if isinstance(line_items, list):
            for index, item in enumerate(line_items, start=1):
                if isinstance(item, dict):
                    for key, value in item.items():
                        label = (
                            f"Line item {index} — "
                            f"{str(key).replace('_', ' ').title()}"
                        )

                        unavailable = (
                            value is None or str(value).strip() == ""
                        )

                        rows.append(
                            (
                                label,
                                "Couldn't fetch"
                                if unavailable
                                else str(value),
                                "Unavailable"
                                if unavailable
                                else "Extracted",
                            )
                        )
                else:
                    rows.append(
                        (f"Line item {index}", str(item), "Extracted")
                    )

        if not rows:
            rows.append(
                ("Invoice fields", "Couldn't fetch", "Unavailable")
            )

        # If the task has no final result, expose the extracted payload
        # in the readable Final result tab too.
        if not final_result and invoice:
            self.result_view.setPlainText(
                self.human_readable_result(invoice)
            )

        for field, value, status in rows:
            row = self.invoice_table.rowCount()
            self.invoice_table.insertRow(row)

            self.invoice_table.setItem(
                row, 0, QTableWidgetItem(field)
            )
            self.invoice_table.setItem(
                row, 1, QTableWidgetItem(value)
            )
            self.invoice_table.setItem(
                row, 2, QTableWidgetItem(status)
            )

        if review_reasons:
            message = (
                "Extraction completed. Review recommended: "
                + " ".join(str(reason) for reason in review_reasons)
            )
        elif (
            verification.get("valid") is False
            or amount_valid is False
        ):
            message = (
                "Extraction completed. Some invoice values "
                "need manual review."
            )
        else:
            message = (
                "Invoice extraction completed. Review the extracted "
                "values against the source invoice."
            )

        self.approval_title.setText("Invoice extraction")
        self.approval_description.setText(message)
        self.tabs.setCurrentWidget(self.invoice_table)

    def update_approval_controls(self):
        task = self.current_task or {}

        pending = (
            task.get("approval_required", False)
            and task.get("approval_status") == "pending"
            and task.get("status") == "waiting_for_approval"
        )

        allowed = pending and not self.request_busy

        self.approve_button.setEnabled(allowed)
        self.reject_button.setEnabled(allowed)

        if pending:
            self.approval_title.setText("Human review required")
        elif task.get("approval_status") == "approved":
            self.approval_title.setText("Approval recorded")
        else:
            self.approval_title.setText("Human review")

    @staticmethod
    def human_readable_result(value, indent=0):
        """Render nested agent results as readable labeled text."""

        labels = {
            "success": "Status",
            "status": "Task Status",
            "final": "Final Answer",
            "final_result": "Final Result",
            "message": "Message",
            "error": "Error",
            "warning": "Warning",
            "goal": "Task Goal",
            "invoice_number": "Invoice Number",
            "date": "Invoice Date",
            "due_date": "Due Date",
            "vendor": "Vendor",
            "vendor_suggestion": "Possible Vendor (Unverified)",
            "vendor_gstin": "Supplier GSTIN",
            "bill_to": "Billed To",
            "bill_to_gstin": "Customer GSTIN",
            "email": "Email",
            "phone": "Phone",
            "payment_terms": "Payment Terms",
            "subtotal": "Subtotal",
            "suggested_subtotal": "Suggested Subtotal (Verify)",
            "tax": "Tax / GST",
            "total": "Total",
            "currency": "Currency",
            "amount_valid": "Financial Validation",
            "needs_review": "Manual Review Required",
            "missing_fields": "Missing Fields",
            "invalid_amount_fields": "Invalid Amount Fields",
            "review_reasons": "Review Reasons",
            "verification_message": "Verification Summary",
            "amount_reconciliation": "Subtotal and Tax Check",
            "line_items_reconciliation": "Line Items Check",
            "line_items": "Line Items",
            "item_number": "Item Number",
            "description": "Description",
            "quantity": "Quantity",
            "unit_price": "Unit Price",
            "amount": "Amount",
            "expected_total": "Expected Total",
            "extracted_total": "Extracted Total",
            "line_items_sum": "Line Items Sum",
            "extracted_subtotal": "Extracted Subtotal",
            "matches": "Values Match",
            "products": "Products",
            "name": "Name",
            "price": "Price",
            "ingredients": "Ingredients",
            "available": "Available",
            "protein_g": "Protein (g)",
            "added_sugar_g": "Added Sugar (g)",
            "count": "Number of Results",
            "observations": "Observations",
            "actions": "Actions",
            "verification_result": "Verification Result",
            "retry_count": "Retry Count",
            "recovery_action": "Recovery Action",
        }

        def readable_label(key):
            key = str(key)
            return labels.get(
                key,
                key.replace("_", " ").strip().capitalize(),
            )

        def readable_value(key, item):
            if item is None or item == "":
                return "Not available"

            if isinstance(item, bool):
                if key == "success":
                    return "Successful" if item else "Failed"

                if key == "needs_review":
                    return (
                        "Yes — manual review required"
                        if item
                        else "No"
                    )

                if key in {"amount_valid", "matches", "valid"}:
                    return "Passed" if item else "Failed"

                return "Yes" if item else "No"

            return str(item)

        def render(item, level=0, parent_key=None):
            prefix = " " * level
            lines = []

            if isinstance(item, dict):
                if not item:
                    return prefix + "No details available."

                for key, child in item.items():
                    label = readable_label(key)

                    if isinstance(child, dict):
                        lines.append(f"{prefix}{label}:")
                        lines.append(
                            render(child, level + 2, key)
                        )

                    elif isinstance(child, list):
                        lines.append(f"{prefix}{label}:")

                        if not child:
                            lines.append(f"{prefix}  None")
                            continue

                        for index, entry in enumerate(
                            child, start=1
                        ):
                            if isinstance(entry, (dict, list)):
                                lines.append(
                                    f"{prefix}  {index}."
                                )
                                lines.append(
                                    render(entry, level + 4, key)
                                )
                            else:
                                lines.append(
                                    f"{prefix}  • "
                                    f"{readable_value(key, entry)}"
                                )

                    else:
                        lines.append(
                            f"{prefix}{label}: "
                            f"{readable_value(key, child)}"
                        )

                return "\n".join(lines)

            if isinstance(item, list):
                if not item:
                    return prefix + "None"

                for index, entry in enumerate(item, start=1):
                    if isinstance(entry, (dict, list)):
                        lines.append(f"{prefix}{index}.")
                        lines.append(
                            render(entry, level + 2, parent_key)
                        )
                    else:
                        lines.append(
                            f"{prefix}• "
                            f"{readable_value(parent_key, entry)}"
                        )

                return "\n".join(lines)

            return prefix + readable_value(parent_key, item)

        return render(value, indent)

    @staticmethod
    def pretty(value):
        try:
            return json.dumps(
                value,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        except (TypeError, ValueError):
            return str(value)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = NutriCoachDashboard()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()