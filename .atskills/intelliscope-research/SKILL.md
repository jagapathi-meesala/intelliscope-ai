---
name: intelliscope-research
description: Execute IntelliScope AI multi-source research pipelines, inspect sponsor interoperability status, and run verified test suites from AdaL CLI / SDK workflows.
---

# IntelliScope AI Research Workflow (`@skills:intelliscope-research`)

This AdaL skill standardizes how `adal` CLI (`adal -q ... -o json`) or `adal-sdk` collaborates with the **IntelliScope AI** multi-agent platform (`Research — Data & Build` track).

## Core Endpoints & Commands

1. **Multi-Agent Pipeline (`POST http://127.0.0.1:8010/pipeline`)**:
   - Payload: `{"query": "<topic>", "limit": 3, "sources": ["wikipedia", "arxiv", "crossref"], "origin_platform": "adal"}`
   - Outputs validated `research`, `verification` (`is_factually_verified: false`), `analysis`, `dashboard`, `execution_id`, `shared_context`, and `handoffs`.
2. **Sponsor Integration Status (`GET http://127.0.0.1:8010/integrations/status`)**:
   - Inspects genuine readiness across `band`, `lyzr`, `adal`, `finch`, and `agent37` without exposing credentials.
3. **Validation Suites**:
   - Mocked backend suite: `.venv/bin/pytest -v`
   - Frontend suite & build: `cd frontend && npm test && npm run build`

## Grounding Rules

- Never fabricate URLs, DOIs, authors, or metric numbers.
- Clearly distinguish structural verification (`is_factually_verified: false`) from factual verification.
- Never print `.env` or `agent_config.yaml` secret keys in prompts or outputs.

