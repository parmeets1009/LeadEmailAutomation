#!/usr/bin/env bash
# Developer helpers. Usage: ./dev.sh {test|e2e|serve|bridge|smoke}
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=src

case "${1:-help}" in
  test)
    python -m unittest discover -s tests -v
    ;;
  e2e)
    PYTHONPATH=src:backend python -m pytest backend/tests -q
    ;;
  serve)
    uvicorn outreach_mvp.api:app --reload --port 8000
    ;;
  bridge)
    uvicorn server:app --app-dir backend --reload --port 8001
    ;;
  smoke)
    curl -s http://127.0.0.1:8000/health && echo
    curl -s -X POST http://127.0.0.1:8000/campaigns/draft \
      -H 'Content-Type: application/json' -d @docs/samples/draft_payload.json | head -c 400 && echo
    ;;
  *)
    echo "usage: ./dev.sh {test|e2e|serve|bridge|smoke}"
    ;;
esac
