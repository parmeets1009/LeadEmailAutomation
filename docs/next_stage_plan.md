# LeadEmailAutomation Next-Stage Implementation Plan

> For Hermes: execute with TDD and keep draft-first/no-send safety intact.

Goal: Move the app beyond MVP by adding the first durable intelligence layer: a response-event ledger and lead-response graph analytics.

Architecture: Keep the current stdlib/FastAPI/JSON architecture. Store response events as append-only JSONL in `campaign_runs/response_events.jsonl`, build graph exports dynamically from saved campaigns plus events, and expose manual API endpoints for recording replies/bounces/unsubscribes/conversions before any live inbox sync exists.

Tech Stack: Python dataclasses, JSON/JSONL, FastAPI, unittest.

## Deep MVP-to-next-stage analysis

Current MVP strengths:
- Draft-first campaign generation is implemented and tested.
- Company profiling, lead scoring, Apollo sourcing, optional website enrichment, compliance checks, approval-gated draft creation, OAuth setup, and browser review UI exist.
- Gmail/Outlook integrations create drafts only and do not send.
- Campaign JSON persistence and review workflow are in place.

Primary gaps before next-stage product readiness:
1. No persistent response/outcome intelligence layer.
2. No reply/bounce/unsubscribe event capture or analytics.
3. Suppression is still request-scoped, not a durable consent/suppression ledger.
4. Follow-up sequences cannot safely exist until reply/bounce/unsubscribe stop conditions are persisted.
5. Deliverability checks and campaign simulation are not implemented.
6. Prompt/template lineage is campaign-level only, not per-variant/per-outcome.

Chosen implementation slice:
- Add `ResponseEvent` dataclass plus JSON-safe graph node/edge dictionaries and metrics.
- Add `ResponseEventStore` using JSONL for append-only auditability.
- Add `LeadResponseGraphBuilder` to produce nodes, edges, and metrics by country/title/industry.
- Add APIs:
  - `POST /campaigns/{campaign_id}/drafts/{draft_id}/events`
  - `GET /campaigns/{campaign_id}/drafts/{draft_id}/events`
  - `GET /campaigns/{campaign_id}/response-graph`
- Update docs to describe the new response intelligence foundation.

## Tasks

### Task 1: Add response graph domain tests

Files:
- Create: `tests/test_response_graph.py`

Write failing tests for:
- JSONL event store append/load/filter behavior.
- Graph node/edge generation from a campaign result and events.
- Metrics: reply/bounce/unsubscribe/conversion rates and segment metrics.

### Task 2: Implement response graph domain module

Files:
- Create: `src/outreach_mvp/response_graph.py`
- Modify: `src/outreach_mvp/models.py`

Implement dataclasses, event validation, JSONL event storage, graph building, and metrics.

### Task 3: Add API tests for response event and graph endpoints

Files:
- Modify: `tests/test_api.py`

Write failing tests for recording a manual reply event, listing draft events, loading graph metrics, unknown draft 404, and unsupported event type 400.

### Task 4: Implement API endpoints

Files:
- Modify: `src/outreach_mvp/api.py`

Wire `ResponseEventStore` into `create_app()`, validate draft existence and event types, append events, list events, and return graph data.

### Task 5: Update docs and verify

Files:
- Modify: `README.md`
- Modify: `docs/mvp_plan.md`

Run:
`PYTHONPATH=src python3 -m unittest discover -s tests -v`

Expected: all tests pass.
