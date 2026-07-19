"""Bridge app: mounts the outreach_mvp API under /api and serves the built
React dashboard at /.

Run: PYTHONPATH=../src uvicorn server:app --port 8001 --app-dir backend
(or via deploy/lead-email-compose.yml, which sets everything up).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="ui-assets")

    # SPA fallback: any non-API, non-asset path serves index.html so React
    # Router deep links (e.g. /review/<id>) work on refresh. Registered after
    # the /api mount, which keeps priority.
    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if candidate.is_file() and str(candidate).startswith(str(_FRONTEND_DIST.resolve())):
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"status": "ok", "service": "lead-email-automation", "api_base": "/api", "note": "frontend/dist not built"}
