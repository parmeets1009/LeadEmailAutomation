import os

import pytest
import requests

# E2E tests target a RUNNING backend. Default is the local bridge (backend/server.py
# on port 8001); override with REACT_APP_BACKEND_URL for staging/production runs.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
API = f"{BASE_URL}/api"


def _backend_available() -> bool:
    try:
        return requests.get(f"{API}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_backend():
    if not _backend_available():
        pytest.skip(f"backend not running at {BASE_URL} — start it or set REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def base_url():
    return API
