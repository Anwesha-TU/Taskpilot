
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "backend.settings",
)

import django

django.setup()

from api.routes import router
from api.dashboard_routes import router as dashboard_router

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

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "NutriCoach Agentic Worker",
    }

app.include_router(router)
app.include_router(dashboard_router)
