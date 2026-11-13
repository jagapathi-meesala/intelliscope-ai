# IntelliScope AI — Phase 4.5 Live Multi-Source Validation Report

- **Generated (UTC):** `2026-11-11T18:40:12.357923+00:00`
- **Query:** `quantum computing` (limit per source: `3`, polite delay: `3.0s`)
- **Execution Target:** `in-process FastAPI ASGI (live external HTTP to Wikipedia/arXiv/Crossref)`
- **Overall Outcome:** `EXTERNAL_OUTAGE`

## Category Breakdown (Mocked vs Live vs External Outage)

| Category | Count | Notes |
| --- | ---: | --- |
| Live Network Passed | 0 | Unmocked HTTP calls to Wikipedia, arXiv, Crossref |
| Live Network Failed | 0 | Assertion/code failures on live data |
| Live External Outages | 5 | Timeouts, HTTP 429/502/503/504, DNS/network blocks |
| Hybrid Partial-Failure Probe Passed | 0 | Live healthy sources + controlled timeout on 1 provider |
| Skipped | 0 | Explicitly skipped scenarios |

> **Verification Boundary Notice:** Structural verification checks URLs, provider domains, DOI syntax, timestamps, and duplicates (`is_factually_verified: false`). Structural validity never implies empirical or factual verification.

## Scenario Results

### Live Independent Source: wikipedia
- **ID:** `live_source_wikipedia`
- **Test Kind:** `live_network`
- **Status:** `EXTERNAL_OUTAGE`
- **Duration:** `41.75 ms`
- **Error:** `POST /research HTTP 502: Upstream research provider encountered an error.`

### Live Independent Source: arxiv
- **ID:** `live_source_arxiv`
- **Test Kind:** `live_network`
- **Status:** `EXTERNAL_OUTAGE`
- **Duration:** `16.13 ms`
- **Error:** `POST /research HTTP 502: Upstream research provider encountered an error.`

### Live Independent Source: crossref
- **ID:** `live_source_crossref`
- **Test Kind:** `live_network`
- **Status:** `EXTERNAL_OUTAGE`
- **Duration:** `13.71 ms`
- **Error:** `POST /research HTTP 502: Upstream research provider encountered an error.`

### Live Combined Multi-Source Pipeline (wikipedia + arxiv + crossref)
- **ID:** `live_combined_multisource_pipeline`
- **Test Kind:** `live_network`
- **Status:** `EXTERNAL_OUTAGE`
- **Duration:** `18.42 ms`
- **Error:** `Network error while connecting to upstream search service: [Errno -3] Temporary failure in name resolution`

### Controlled Partial Failure Honesty (live wikipedia+crossref + simulated arxiv timeout)
- **ID:** `controlled_partial_failure_honesty`
- **Test Kind:** `hybrid_controlled_partial_failure`
- **Status:** `EXTERNAL_OUTAGE`
- **Duration:** `15.86 ms`
- **Error:** `Network error while connecting to upstream search service: [Errno -3] Temporary failure in name resolution`

## Reproduction Commands

```bash
# Ordinary mocked test suites (no live network requests):
.venv/bin/pytest -v
cd frontend && npm test && npm run build

# Opt-in live multi-source validation:
.venv/bin/python scripts/live_multisource_test.py
```
