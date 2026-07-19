# LeadEmailAutomation — agent instructions

Before doing ANY work in this repo, read `docs/JUNIOR-IMPLEMENTATION-PLAYBOOK.md` in full. It is the authoritative build plan: current state, 6 confirmed bugs, 4 implementation phases, prompts, tests, and acceptance checklists. Execute phases in order; do not skip Phase 0.

Hard rules (from the playbook, §0):

- Never break the safety invariants: no email leaves without human approval; suppression list is absolute; no secrets in git; every outbound email has a working opt-out + truthful sender identity.
- Test-first: every fix gets its named failing test before the code change. Run the full suite after every change: `PYTHONPATH=src python -m unittest discover -s tests -v` (must only ever go up from 33 passing).
- Verify end-to-end with the smoke flow in playbook §0.4, not just unit tests.
- Never guess LLM model IDs. Claude models used here: `claude-opus-4-8` (default), `claude-haiku-4-5` (cost lever, owner's call). Use the official `anthropic` SDK, not OpenAI-compatible shims.
- Never swallow exceptions (`except: pass/return {}` is banned). Log, surface, and record provenance (`generated_by: llm|fallback`).
- Small commits with meaningful messages. Update `ROADMAP.md` checkboxes + Decision Log as you go. Record playbook ambiguities under a "Playbook errata" heading in `ROADMAP.md` instead of silently working around them.

Repo quick facts:

- Core app: `src/outreach_mvp/` (FastAPI + agents). Bridge: `backend/server.py` mounts it under `/api`. React UI: `frontend/`. Deploy: `deploy/lead-email-compose.yml` (NOT yet deployed anywhere; has no auth yet — see playbook §7.1 before deploying).
- Tests: `tests/` (unit, must stay green), `backend/tests/` (E2E, hit a live server; being repointed to localhost in Phase 0 §3.7).
- The default LLM path without `ANTHROPIC_API_KEY` is a deterministic template fallback — that is expected and must stay working.
