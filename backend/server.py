"""Bridge module that exposes the outreach_mvp FastAPI app under /api on port 8001.

The Emergent preview environment routes /api/* to the backend (this process) and
all other paths to the frontend (port 3000), so we mount the existing
outreach_mvp API under /api here. The HTML dashboard from outreach_mvp.frontend
is served by the separate Node frontend service.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from outreach_mvp.api import create_app as create_outreach_app

inner_app = create_outreach_app()

app = FastAPI(title="Lead Email Automation Bridge", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/api", inner_app)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "lead-email-automation", "api_base": "/api"}
