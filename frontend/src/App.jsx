
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowDownRight,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock3,
  FileText,
  ListTodo,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  ShieldCheck,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import "./styles.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const TERMINAL_STATUSES = new Set(["completed", "failed", "rejected"]);

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object"
        ? payload.detail || JSON.stringify(payload)
        : payload;

    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return payload;
}

function asObject(value) {
  if (value == null) return null;
  if (typeof value === "object") return value;

  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return { message: value };
    }
  }

  return { value };
}

function pretty(value) {
  if (value == null) return "No data recorded yet";
  return JSON.stringify(value, null, 2);
}

function humanize(value) {
  return String(value || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Number(seconds).toFixed(1)}s`;

  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function statusClass(status) {
  const normalized = String(status || "unknown").toLowerCase();

  if (["completed", "approved"].includes(normalized)) return "success";

  if (["failed", "rejected"].includes(normalized)) return "danger";

  if (
    ["waiting_for_approval", "pending", "running", "in_progress"].includes(
      normalized
    )
  ) {
    return "warning";
  }

  return "neutral";
}

function StatusPill({ status }) {
  return (
    <span className={`status-pill ${statusClass(status)}`}>
      <span className="status-dot" />
      {humanize(status)}
    </span>
  );
}

function MetricCard({ label, value, note, icon: Icon, tone }) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <span className={`metric-icon ${tone || ""}`}>
          <Icon size={18} />
        </span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{note}</div>
    </article>
  );
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <CircleDashed size={24} />
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function getGoalType(goal) {
  const text = String(goal || "").toLowerCase();

  if (
    /\b(product|products|protein bar|shopping|purchase|compare these two products|recommend a product)\b/.test(
      text
    )
  ) {
    return "product";
  }

  if (
    /\b(invoice|invoices|receipt|receipts|bill|billing document)\b/.test(text)
  ) {
    return "invoice";
  }

  return "general";
}

function getFinalResult(task) {
  return asObject(task?.final_result);
}

function findInvoiceData(task) {
  const result = getFinalResult(task);

  if (result?.invoice && typeof result.invoice === "object") {
    return result.invoice.fields || result.invoice;
  }

  const observations = Array.isArray(task?.observations)
    ? task.observations
    : [];

  for (let i = observations.length - 1; i >= 0; i -= 1) {
    const observation = observations[i];

    if (observation?.type === "invoice_fields" && observation.data) {
      return observation.data.fields || observation.data;
    }
  }

  return null;
}

/*
 * Product data is only read for product-related goals.
 * This prevents a product result from appearing on unrelated tasks.
 */
function findProduct(task) {
  if (getGoalType(task?.goal) !== "product") return null;

  const result = getFinalResult(task);
  const recommendation = asObject(result?.recommendation);

  const candidates = [
    recommendation?.product,
    result?.best_product,
    result?.selected_product,
    result?.product,
  ];

  for (const candidate of candidates) {
    if (
      candidate &&
      typeof candidate === "object" &&
      (candidate.name || candidate.product_name || candidate.product_id)
    ) {
      return candidate;
    }
  }

  return null;
}

function getGeneralSummary(result) {
  if (!result) return null;

  const candidates = [
    result.summary,
    result.message,
    result.answer,
    result.explanation,
    result.conclusion,
    result.recommendation,
    result.final_answer,
    result.output,
  ];

  for (const value of candidates) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return null;
}

function getRecommendationReasons(task, product) {
  const result = getFinalResult(task);
  const recommendation = asObject(result?.recommendation);

  const reasons =
    product?.reasons ||
    recommendation?.reasons ||
    result?.reasons;

  if (Array.isArray(reasons)) return reasons;
  if (typeof reasons === "string") return [reasons];

  return [];
}

function money(value, currency = "INR") {
  if (value == null || value === "") return "—";

  if (typeof value === "string" && /[₹$€£]/.test(value)) {
    return value;
  }

  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);

  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(number);
  } catch {
    return `${currency} ${number}`;
  }
}

function ResultField({ label, value }) {
  if (value == null || value === "") return null;

  return (
    <div className="result-field">
      <span>{label}</span>
      <strong>{String(value)}</strong>
    </div>
  );
}

function ResultSummary({ task }) {
  const result = getFinalResult(task);
  const verification = asObject(task?.verification_result);
  const goalType = getGoalType(task?.goal);

  const product = goalType === "product" ? findProduct(task) : null;
  const invoice = goalType === "invoice" ? findInvoiceData(task) : null;
  const summary = goalType === "general" ? getGeneralSummary(result) : null;

  const reasons = product ? getRecommendationReasons(task, product) : [];

  const verificationValid =
    verification?.valid === true ||
    verification?.verified === true ||
    verification?.success === true;

  const verificationInvalid =
    verification?.valid === false ||
    verification?.verified === false ||
    verification?.success === false;

  let headline = "Task in progress";
  let description = "The agent has not reported a final outcome yet.";
  let tone = "neutral";

  if (task?.status === "completed") {
    headline = "Task completed";
    description = "The agent finished processing this task.";
    tone = "success";
  } else if (task?.status === "failed") {
    headline = "Task failed";
    description = "The agent could not complete the requested task.";
    tone = "danger";
  } else if (task?.status === "rejected") {
    headline = "Task rejected";
    description = "The task was rejected during the approval process.";
    tone = "danger";
  } else if (task?.status === "waiting_for_approval") {
    headline = "Your decision is needed";
    description = "Review the available result before proceeding.";
    tone = "warning";
  }

  return (
    <section className={`result-summary result-${tone}`}>
      <div className="result-heading">
        <span className="result-icon">
          {tone === "success" ? (
            <CheckCircle2 size={23} />
          ) : tone === "danger" ? (
            <XCircle size={23} />
          ) : tone === "warning" ? (
            <ShieldCheck size={23} />
          ) : (
            <Activity size={23} />
          )}
        </span>

        <div className="result-heading-copy">
          <span className="eyebrow">TASK OUTCOME</span>
          <h3>{headline}</h3>
          <p>{description}</p>
        </div>
      </div>

      {goalType === "product" && product && (
        <div className="human-result">
          <span className="result-kicker">RECOMMENDED OPTION</span>
          <h4>
            {product.name || product.product_name || product.product_id}
          </h4>

          {product.brand && <p className="muted">{product.brand}</p>}

          <div className="product-stats">
            <div>
              <span>Protein</span>
              <strong>
                {product.protein_g ?? product.protein ?? "—"}
                {product.protein_g != null || product.protein != null
                  ? " g"
                  : ""}
              </strong>
            </div>

            <div>
              <span>Added sugar</span>
              <strong>
                {product.added_sugar_g ?? product.added_sugar ?? "—"}
                {product.added_sugar_g != null ||
                product.added_sugar != null
                  ? " g"
                  : ""}
              </strong>
            </div>

            <div>
              <span>Price</span>
              <strong>{money(product.price, product.currency || "INR")}</strong>
            </div>
          </div>

          {reasons.length > 0 && (
            <div className="reasons">
              <strong>Why it was selected</strong>
              <ul>
                {reasons.map((reason, index) => (
                  <li key={`${index}-${String(reason)}`}>
                    {String(reason)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {goalType === "invoice" && invoice && (
        <div className="human-result">
          <h4>Extracted invoice details</h4>
          <div className="result-fields">
            <ResultField label="Vendor" value={invoice.vendor} />
            <ResultField
              label="Invoice number"
              value={invoice.invoice_number}
            />
            <ResultField
              label="Invoice date"
              value={invoice.date || invoice.invoice_date}
            />
            <ResultField label="Currency" value={invoice.currency} />
            <ResultField label="Total amount" value={invoice.total} />
          </div>
        </div>
      )}

      {goalType === "general" && summary && (
        <div className="human-result">
          <h4>Result</h4>
          <p className="result-text">{summary}</p>
        </div>
      )}

      {goalType === "general" &&
        !summary &&
        task?.status === "completed" && (
          <div className="human-result">
            <h4>Result unavailable in readable format</h4>
            <p className="result-text">
              The task completed, but the backend did not provide a recognized
              text summary. Open Technical details to inspect the actual result.
              No unrelated recommendation has been substituted.
            </p>
          </div>
        )}

      {goalType === "product" && !product && task?.status === "completed" && (
        <div className="human-result">
          <h4>No structured product recommendation</h4>
          <p className="result-text">
            The task completed, but no matching product object was returned.
            Inspect the raw final result to see what the agent actually produced.
          </p>
        </div>
      )}

      {goalType === "invoice" && !invoice && task?.status === "completed" && (
        <div className="human-result">
          <h4>No extracted invoice fields</h4>
          <p className="result-text">
            The task completed, but no invoice fields were found in its result
            or observations.
          </p>
        </div>
      )}

      <div className="verification-summary">
        <span className="verification-icon">
          {verificationValid ? (
            <CheckCircle2 size={19} />
          ) : verificationInvalid ? (
            <XCircle size={19} />
          ) : (
            <ShieldCheck size={19} />
          )}
        </span>

        <div>
          <strong>
            {verificationValid
              ? "Verification passed"
              : verificationInvalid
                ? "Verification failed"
                : "Verification status unavailable"}
          </strong>

          <p>
            {verification?.message ||
              (verificationValid
                ? "The backend marked the result as valid."
                : verificationInvalid
                  ? "The backend marked the result as invalid."
                  : "The backend did not provide an explicit verification status.")}
          </p>
        </div>
      </div>
    </section>
  );
}

function InvoiceSummary({ task }) {
  if (getGoalType(task?.goal) !== "invoice") return null;

  const invoice = findInvoiceData(task);
  if (!invoice) return null;

  return (
    <section className="invoice-card">
      <div className="panel-heading">
        <div className="panel-heading-title">
          <FileText size={17} />
          <h3>Invoice fields</h3>
        </div>
        <span className="small-count">Extracted</span>
      </div>

      <div className="result-fields">
        <ResultField label="Vendor" value={invoice.vendor} />
        <ResultField label="Invoice number" value={invoice.invoice_number} />
        <ResultField
          label="Date"
          value={invoice.date || invoice.invoice_date}
        />
        <ResultField label="Currency" value={invoice.currency} />
        <ResultField label="Total" value={invoice.total} />
      </div>

      <p className="muted">
        Check these values against the original document before approval.
      </p>
    </section>
  );
}

function EvidencePanel({ title, icon: Icon, data, emptyText }) {
  const hasData = Array.isArray(data)
    ? data.length > 0
    : data && typeof data === "object"
      ? Object.keys(data).length > 0
      : Boolean(data);

  return (
    <details className="evidence-panel">
      <summary>
        <span className="evidence-title">
          <Icon size={16} />
          {title}
        </span>
        <span className="evidence-count">
          {hasData
            ? Array.isArray(data)
              ? data.length
              : "Available"
            : "Empty"}
        </span>
      </summary>

      {hasData ? (
        <pre className="json-view">{pretty(data)}</pre>
      ) : (
        <p className="empty-inline">
          {emptyText || "Nothing recorded yet."}
        </p>
      )}
    </details>
  );
}

function Timeline({ plan, actions, task }) {
  const events = [];

  const executedNames = new Set(
    actions
      .map((action) =>
        String(action?.step || action?.step_name || action?.action || "")
      )
      .filter(Boolean)
      .map((name) => name.toLowerCase().replaceAll("_", " "))
  );

  plan.forEach((step, index) => {
    const name =
      typeof step === "string"
        ? step
        : step?.name || step?.step || step?.action || `Step ${index + 1}`;

    const normalizedName = String(name).toLowerCase().replaceAll("_", " ");
    const stepStatus = typeof step === "object" ? step.status : null;

    const completed =
      ["completed", "success", "succeeded"].includes(stepStatus) ||
      executedNames.has(normalizedName);

    events.push({
      name: humanize(name),
      state: completed ? "completed" : stepStatus || "pending",
      detail: completed
        ? "Execution evidence was recorded."
        : "Planned step; completion has not been confirmed by an action record.",
    });
  });

  if (task?.status && TERMINAL_STATUSES.has(task.status)) {
    events.push({
      name: `Task ${humanize(task.status).toLowerCase()}`,
      state: task.status === "completed" ? "completed" : "failed",
      detail:
        task.status === "completed"
          ? "The backend reports that the task has finished."
          : "Inspect the errors and recovery information below.",
    });
  }

  return (
    <section className="timeline-card">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">EXECUTION TRACE</span>
          <h3>What the agent did</h3>
        </div>
        <span className="small-count">{actions.length} recorded actions</span>
      </div>

      {events.length === 0 ? (
        <p className="muted">No execution plan recorded yet.</p>
      ) : (
        <div className="timeline">
          {events.map((event, index) => (
            <div
              className={`timeline-item ${event.state}`}
              key={`${event.name}-${index}`}
            >
              <span className="timeline-marker">
                {event.state === "completed" ? (
                  <Check size={14} />
                ) : event.state === "failed" ? (
                  <X size={14} />
                ) : (
                  <CircleDashed size={14} />
                )}
              </span>

              <div className="timeline-copy">
                <strong>{event.name}</strong>
                <p>{event.detail}</p>
              </div>

              <span className="timeline-status">{humanize(event.state)}</span>
            </div>
          ))}
        </div>
      )}

      <p className="timeline-note">
        <Activity size={15} />
        Planned steps are distinguished from steps with recorded execution
        evidence.
      </p>
    </section>
  );
}

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);

  const [goal, setGoal] = useState("");
  const [filePath, setFilePath] = useState("");

  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadTasks = useCallback(
    async (preferredId = null) => {
      try {
        const response = await apiRequest("/api/v1/tasks?limit=100");
        const items = Array.isArray(response)
          ? response
          : response.items || [];

        setTasks(items);
        setLastUpdated(new Date());

        const targetId =
          preferredId ||
          selectedId ||
          (items.length ? items[0].task_id : null);

        if (targetId && items.some((task) => task.task_id === targetId)) {
          setSelectedId(targetId);

          const detail = await apiRequest(
            `/api/v1/tasks/${encodeURIComponent(targetId)}`
          );

          setSelectedTask(detail);
        } else if (!items.length) {
          setSelectedId(null);
          setSelectedTask(null);
        }

        setError("");
      } catch (requestError) {
        setError(
          `Unable to load tasks from ${API_BASE}: ${requestError.message}`
        );
      } finally {
        setLoading(false);
      }
    },
    [selectedId]
  );

  const refreshSelectedTask = useCallback(async () => {
    if (!selectedId) return;

    try {
      const detail = await apiRequest(
        `/api/v1/tasks/${encodeURIComponent(selectedId)}`
      );

      setSelectedTask(detail);
    } catch (requestError) {
      setError(requestError.message);
    }
  }, [selectedId]);

  useEffect(() => {
    loadTasks();

    const timer = window.setInterval(() => {
      loadTasks();
    }, 3000);

    return () => window.clearInterval(timer);
  }, [loadTasks]);

  useEffect(() => {
    if (!selectedId) return undefined;

    refreshSelectedTask();

    const timer = window.setInterval(refreshSelectedTask, 2500);

    return () => window.clearInterval(timer);
  }, [selectedId, refreshSelectedTask]);

  const metrics = useMemo(() => {
    return {
      total: tasks.length,
      completed: tasks.filter((task) => task.status === "completed").length,
      active: tasks.filter(
        (task) =>
          !TERMINAL_STATUSES.has(task.status) &&
          task.status !== "waiting_for_approval"
      ).length,
      approvals: tasks.filter(
        (task) =>
          task.status === "waiting_for_approval" &&
          task.approval_required &&
          task.approval_status === "pending"
      ).length,
    };
  }, [tasks]);

  async function createTask(event) {
    event.preventDefault();

    if (!goal.trim()) {
      setError("Enter a task instruction first.");
      return;
    }

    setCreating(true);
    setError("");
    setNotice("");

    try {
      const body = { goal: goal.trim() };
      if (filePath.trim()) body.file_path = filePath.trim();

      const created = await apiRequest("/api/v1/tasks", {
        method: "POST",
        body: JSON.stringify(body),
      });

      setGoal("");
      setFilePath("");
      setNotice("Task submitted. Monitoring execution.");

      await loadTasks(created.task_id);
    } catch (requestError) {
      setError(`Could not create task: ${requestError.message}`);
    } finally {
      setCreating(false);
    }
  }

  async function runApprovalAction(action) {
    if (!selectedTask) return;

    setActionBusy(true);
    setError("");
    setNotice("");

    try {
      const response = await apiRequest(
        `/api/v1/tasks/${encodeURIComponent(selectedTask.task_id)}/${action}`,
        {
          method: "POST",
          body: JSON.stringify({}),
        }
      );

      setNotice(response.message || `Task ${action} request completed.`);
      await loadTasks(selectedTask.task_id);
    } catch (requestError) {
      setError(`Could not ${action} task: ${requestError.message}`);
    } finally {
      setActionBusy(false);
    }
  }

  async function selectTask(taskId) {
    setSelectedId(taskId);
    setError("");

    try {
      const detail = await apiRequest(
        `/api/v1/tasks/${encodeURIComponent(taskId)}`
      );
      setSelectedTask(detail);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  const plan = selectedTask?.plan || [];
  const actions = selectedTask?.actions || [];
  const observations = selectedTask?.observations || [];
  const errors = selectedTask?.errors || [];

  const pendingApproval =
    selectedTask?.approval_required &&
    selectedTask?.approval_status === "pending";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Zap size={22} />
          </span>
          <div>
            <strong>Operator</strong>
            <small>Agent workspace</small>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <button className="nav-item active" type="button">
          <Activity size={18} />
          Overview
        </button>

        <button
          className="nav-item"
          type="button"
          onClick={() =>
            document
              .getElementById("task-history")
              ?.scrollIntoView({ behavior: "smooth" })
          }
        >
          <ListTodo size={18} />
          Task history
        </button>

        <button
          className="nav-item"
          type="button"
          onClick={() =>
            document
              .getElementById("task-detail")
              ?.scrollIntoView({ behavior: "smooth" })
          }
        >
          <ShieldCheck size={18} />
          Execution details
        </button>

        <div className="sidebar-bottom">
          <span className="connection-dot" />
          <div>
            <strong>API endpoint</strong>
            <span>{API_BASE}</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <ChevronRight size={14} /> <strong>Overview</strong>
          </div>

          <div className="topbar-right">
            <span className="live-indicator">
              <span />
              Auto-refresh on
            </span>
            <button
              className="icon-button"
              type="button"
              aria-label="Refresh tasks"
              onClick={() => loadTasks(selectedId)}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>

        <div className="page-container">
          <section className="page-heading">
            <div>
              <span className="eyebrow">AGENT CONTROL CENTER</span>
              <h1>Operations overview</h1>
              <p>Launch tasks, follow execution, and review outcomes.</p>
            </div>

            <span className="updated-label">
              <Clock3 size={14} />
              Updated {lastUpdated?.toLocaleTimeString() || "—"}
            </span>
          </section>

          {error && (
            <div className="alert error-alert" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={16} />
              </button>
            </div>
          )}

          {notice && (
            <div className="alert success-alert" role="status">
              <CheckCircle2 size={18} />
              <span>{notice}</span>
              <button
                type="button"
                onClick={() => setNotice("")}
                aria-label="Dismiss message"
              >
                <X size={16} />
              </button>
            </div>
          )}

          <section className="metrics-grid">
            <MetricCard
              label="Total tasks"
              value={metrics.total}
              note="Recorded in workspace"
              icon={ListTodo}
              tone="blue"
            />
            <MetricCard
              label="Completed"
              value={metrics.completed}
              note="Successfully finished"
              icon={CheckCircle2}
              tone="green"
            />
            <MetricCard
              label="In progress"
              value={metrics.active}
              note="Currently executing"
              icon={Activity}
              tone="purple"
            />
            <MetricCard
              label="Needs approval"
              value={metrics.approvals}
              note="Awaiting human decision"
              icon={ShieldCheck}
              tone="amber"
            />
          </section>

          <section className="create-card">
            <div className="section-title-row">
              <span className="section-icon">
                <Plus size={19} />
              </span>
              <div>
                <h2>Create a task</h2>
                <p>Describe the outcome you want the agent to achieve.</p>
              </div>
            </div>

            <form onSubmit={createTask}>
              <label htmlFor="goal">Task instruction</label>
              <textarea
                id="goal"
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
                placeholder="Describe the outcome you want the agent to achieve..."
                rows={3}
                required
              />

              <div className="form-bottom">
                <div className="file-path-field">
                  <label htmlFor="file-path">
                    Backend file path <span>(optional)</span>
                  </label>
                  <input
                    id="file-path"
                    value={filePath}
                    onChange={(event) => setFilePath(event.target.value)}
                    placeholder="C:\path\to\document.png"
                  />
                  <span className="field-hint">
                    The path must be accessible to the backend server.
                  </span>
                </div>

                <button
                  className="primary-button"
                  type="submit"
                  disabled={creating}
                >
                  {creating ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Play size={16} />
                  )}
                  {creating ? "Submitting..." : "Run task"}
                </button>
              </div>
            </form>
          </section>

          <div className="content-grid">
            <section className="history-card" id="task-history">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">WORKSPACE</span>
                  <h2>Task history</h2>
                  <p>Recent agent executions</p>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => loadTasks(selectedId)}
                >
                  <RefreshCw size={14} />
                  Refresh
                </button>
              </div>

              {loading ? (
                <div className="loading-state">
                  <LoaderCircle className="spin" size={21} />
                  Loading tasks...
                </div>
              ) : tasks.length === 0 ? (
                <EmptyState
                  title="No tasks yet"
                  description="Create a task above to get started."
                />
              ) : (
                <div className="task-list">
                  {tasks.map((task) => (
                    <button
                      className={`task-row ${
                        selectedId === task.task_id ? "selected" : ""
                      }`}
                      key={task.task_id}
                      type="button"
                      onClick={() => selectTask(task.task_id)}
                    >
                      <span className="task-row-icon">
                        {task.status === "completed" ? (
                          <CheckCircle2 size={18} />
                        ) : ["failed", "rejected"].includes(task.status) ? (
                          <XCircle size={18} />
                        ) : (
                          <Activity size={18} />
                        )}
                      </span>

                      <span className="task-row-main">
                        <strong>{task.goal}</strong>
                        <span>{formatDate(task.created_at)}</span>
                        <code>{task.task_id}</code>
                        <span>
                          <StatusPill status={task.status} />
                        </span>
                      </span>

                      <ChevronRight size={16} />
                    </button>
                  ))}
                </div>
              )}
            </section>

            <section className="detail-card" id="task-detail">
              {!selectedTask ? (
                <EmptyState
                  title="Select a task"
                  description="Choose a task from history to inspect its outcome and evidence."
                />
              ) : (
                <>
                  <div className="detail-heading">
                    <div>
                      <span className="eyebrow">TASK DETAILS</span>
                      <h2>{selectedTask.goal}</h2>
                      <code>{selectedTask.task_id}</code>
                    </div>
                    <StatusPill status={selectedTask.status} />
                  </div>

                  {pendingApproval && (
                    <div className="approval-banner">
                      <ShieldCheck size={23} />
                      <div className="approval-copy">
                        <strong>Human approval required</strong>
                        <p>
                          Review the outcome and evidence before proceeding.
                        </p>
                      </div>
                      <div className="approval-actions">
                        <button
                          className="reject-button"
                          type="button"
                          disabled={actionBusy}
                          onClick={() => runApprovalAction("reject")}
                        >
                          <X size={15} />
                          Reject
                        </button>
                        <button
                          className="approve-button"
                          type="button"
                          disabled={actionBusy}
                          onClick={() => runApprovalAction("approve")}
                        >
                          {actionBusy ? (
                            <LoaderCircle className="spin" size={15} />
                          ) : (
                            <Check size={15} />
                          )}
                          Approve
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="detail-stats">
                    <div>
                      <span>Plan steps</span>
                      <strong>{plan.length}</strong>
                    </div>
                    <div>
                      <span>Recorded actions</span>
                      <strong>{actions.length}</strong>
                    </div>
                    <div>
                      <span>Retries</span>
                      <strong>{selectedTask.retry_count ?? 0}</strong>
                    </div>
                    <div>
                      <span>Duration</span>
                      <strong>
                        {formatDuration(
                          selectedTask.execution_duration_seconds
                        )}
                      </strong>
                    </div>
                  </div>

                  <ResultSummary task={selectedTask} />
                  <InvoiceSummary task={selectedTask} />

                  <Timeline
                    plan={plan}
                    actions={actions}
                    task={selectedTask}
                  />

                  <section className="technical-details">
                    <div className="panel-heading">
                      <div>
                        <span className="eyebrow">FOR DEBUGGING</span>
                        <h3>Technical details</h3>
                        <p>
                          Expand a section to inspect the underlying agent
                          trace.
                        </p>
                      </div>
                    </div>

                    <div className="evidence-grid">
                      <EvidencePanel
                        title="Execution plan"
                        icon={ListTodo}
                        data={plan}
                      />
                      <EvidencePanel
                        title="Tool actions"
                        icon={Zap}
                        data={actions}
                      />
                      <EvidencePanel
                        title="Observations"
                        icon={Activity}
                        data={observations}
                      />
                      <EvidencePanel
                        title="Verification data"
                        icon={ShieldCheck}
                        data={selectedTask.verification_result}
                      />
                      <EvidencePanel
                        title="Errors"
                        icon={AlertCircle}
                        data={errors}
                      />
                      <EvidencePanel
                        title="Recovery action"
                        icon={ArrowDownRight}
                        data={selectedTask.recovery_action}
                      />
                      <EvidencePanel
                        title="Raw final result"
                        icon={FileText}
                        data={selectedTask.final_result}
                      />
                    </div>
                  </section>
                </>
              )}
            </section>
          </div>

          <footer className="page-footer">
            <span>Operator · Agent Operations</span>
            <span>FastAPI · {API_BASE}</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
