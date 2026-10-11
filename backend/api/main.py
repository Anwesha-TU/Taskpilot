import os
import sys
import shutil
import uuid
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django

django.setup()

from api.routes import router
from api.dashboard_routes import router as dashboard_router
from agent.worker import AgentWorker

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NutriCoach Agentic Worker",
    description="Agentic operations and task management API.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

UPLOAD_DIR = PROJECT_ROOT / "uploads" / "invoices"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def latest_observation(observations: list, observation_type: str):
    for observation in reversed(observations or []):
        if observation.get("type") == observation_type:
            return observation.get("data", {})
    return {}


def json_safe(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]

    return str(value)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "NutriCoach Agentic Worker",
    }


@app.post("/api/v1/uploads/invoice")
async def upload_invoice(file: UploadFile = File(...)):
    """Save an invoice image and run the existing invoice agent workflow."""
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Upload an invoice image in PNG, JPG, JPEG, or TIFF format.",
        )

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file must be an image.",
        )

    saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{extension}"

    try:
        with saved_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)

        if saved_path.stat().st_size == 0:
            saved_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

    except HTTPException:
        raise
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Could not save invoice: {exc}",
        ) from exc
    finally:
        await file.close()

    try:
        worker = AgentWorker()
        state = worker.run(
            goal=(
                "Extract the invoice number, invoice date, vendor name, "
                "subtotal, tax, and total from the uploaded invoice. "
                "Flag unreadable or missing fields and verify the result."
            ),
            file_path=str(saved_path.resolve()),
        )

        observations = getattr(state, "observations", []) or []
        invoice_ocr = latest_observation(
            observations,
            "invoice_ocr_text",
        )
        invoice_fields = latest_observation(
            observations,
            "invoice_fields",
        )
        verification = (
            getattr(state, "verification_result", None) or {}
        )
        errors = getattr(state, "errors", []) or []

        return json_safe({
            "success": (
                getattr(state, "status", "failed")
                in {"completed", "waiting_for_approval"}
                and bool(invoice_fields)
            ),
            "filename": filename,
            "file_path": str(saved_path.resolve()),
            "status": getattr(state, "status", "unknown"),
            "plan": getattr(state, "plan", []) or [],
            "current_step": getattr(state, "current_step", 0),
            "ocr_text": invoice_ocr.get("text", ""),
            "invoice": invoice_fields,
            "fields": invoice_fields.get("fields", {}),
            "missing_fields": invoice_fields.get("missing_fields", []),
            "amount_valid": invoice_fields.get("amount_valid"),
            "verification": verification,
            "observations": observations,
            "actions": getattr(state, "actions", []) or [],
            "errors": errors,
            "message": (
                "Invoice processing finished."
                if getattr(state, "status", "") == "completed"
                else (
                    "Invoice extracted; approval is required."
                    if getattr(state, "status", "") == "waiting_for_approval"
                    else "Invoice processing failed. Inspect errors and OCR output."
                )
            ),
        })

    except Exception as exc:
        logger.exception("Invoice processing failed for %s", filename)
        raise HTTPException(
            status_code=500,
            detail=f"Invoice was saved, but processing failed: {exc}",
        ) from exc


app.include_router(router)
app.include_router(dashboard_router)
