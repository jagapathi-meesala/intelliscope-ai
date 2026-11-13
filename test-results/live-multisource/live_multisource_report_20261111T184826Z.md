# IntelliScope AI — Phase 4.5 Live Multi-Source Validation Report

- **Generated (UTC):** `2026-11-11T18:48:26.290184+00:00`
- **Query:** `quantum computing` (limit per source: `3`, polite delay: `3.0s`)
- **Execution Target:** `in-process FastAPI ASGI (live external HTTP to Wikipedia/arXiv/Crossref)`
- **Overall Outcome:** `PASSED`

## Category Breakdown (Mocked vs Live vs External Outage)

| Category | Count | Notes |
| --- | ---: | --- |
| Live Network Passed | 4 | Unmocked HTTP calls to Wikipedia, arXiv, Crossref |
| Live Network Failed | 0 | Assertion/code failures on live data |
| Live External Outages | 0 | Timeouts, HTTP 429/502/503/504, DNS/network blocks |
| Hybrid Partial-Failure Probe Passed | 1 | Live healthy sources + controlled timeout on 1 provider |
| Skipped | 0 | Explicitly skipped scenarios |

> **Verification Boundary Notice:** Structural verification checks URLs, provider domains, DOI syntax, timestamps, and duplicates (`is_factually_verified: false`). Structural validity never implies empirical or factual verification.

## Scenario Results

### Live Independent Source: wikipedia
- **ID:** `live_source_wikipedia`
- **Test Kind:** `live_network`
- **Status:** `PASSED`
- **Duration:** `1648.51 ms`
- **Source Breakdown:** `{"wikipedia": 3}`
- **Verification (Structural Only):** score=`100.0`, valid=`3`, excluded=`0`, is_factually_verified=`False`
- **Analysis:** eligible=`3`, themes=`2`, source_distribution=`{"wikipedia": 3}`
- **Dashboard:** themes=`2`, charts=`['chart-source-eligibility', 'chart-source-distribution', 'chart-theme-distribution', 'chart-keyword-frequency']`, observations=`3`
- **Sample Live Records:**
  - [Quantum computing](https://en.wikipedia.org/wiki/Quantum_computing) (source=`wikipedia`, type=`wikipedia_extract`, date=`2026-11-04`, doi=`None`, authors=`0`)
  - [Timeline of quantum computing and communication](https://en.wikipedia.org/wiki/Timeline_of_quantum_computing_and_communication) (source=`wikipedia`, type=`wikipedia_extract`, date=`2026-11-09`, doi=`None`, authors=`0`)
  - [Superconducting quantum computing](https://en.wikipedia.org/wiki/Superconducting_quantum_computing) (source=`wikipedia`, type=`wikipedia_extract`, date=`2026-10-26`, doi=`None`, authors=`0`)

### Live Independent Source: arxiv
- **ID:** `live_source_arxiv`
- **Test Kind:** `live_network`
- **Status:** `PASSED`
- **Duration:** `787.39 ms`
- **Source Breakdown:** `{"arxiv": 3}`
- **Verification (Structural Only):** score=`100.0`, valid=`3`, excluded=`0`, is_factually_verified=`False`
- **Analysis:** eligible=`3`, themes=`4`, source_distribution=`{"arxiv": 3}`
- **Dashboard:** themes=`4`, charts=`['chart-source-eligibility', 'chart-source-distribution', 'chart-theme-distribution', 'chart-keyword-frequency']`, observations=`3`
- **Sample Live Records:**
  - [Tierkreis: A Dataflow Framework for Hybrid Quantum-Classical Computing](https://arxiv.org/abs/2211.02350v1) (source=`arxiv`, type=`arxiv_paper`, date=`2022-11-04`, doi=`10.1109/QCS56647.2022.00007`, authors=`4`)
  - [Quantum Computing: Vision and Challenges](https://arxiv.org/abs/2403.02240v5) (source=`arxiv`, type=`arxiv_paper`, date=`2024-03-04`, doi=`10.1016/B978-0-443-29096-1.00008-8`, authors=`5`)
  - [Entangling Disciplines: Causality, Entropy and Time-Travel Paradoxes on a Quantum Computer](https://arxiv.org/abs/2506.15909v1) (source=`arxiv`, type=`arxiv_paper`, date=`2025-06-18`, doi=`10.1109/QCE60285.2024.20461`, authors=`1`)

### Live Independent Source: crossref
- **ID:** `live_source_crossref`
- **Test Kind:** `live_network`
- **Status:** `PASSED`
- **Duration:** `1456.21 ms`
- **Source Breakdown:** `{"crossref": 3}`
- **Verification (Structural Only):** score=`100.0`, valid=`3`, excluded=`0`, is_factually_verified=`False`
- **Analysis:** eligible=`3`, themes=`3`, source_distribution=`{"crossref": 3}`
- **Dashboard:** themes=`3`, charts=`['chart-source-eligibility', 'chart-source-distribution', 'chart-theme-distribution', 'chart-keyword-frequency']`, observations=`3`
- **Sample Live Records:**
  - [Quantum Computing I](https://doi.org/10.1093/oso/9780198854227.003.0015) (source=`crossref`, type=`crossref_abstract`, date=`2020-05-07`, doi=`10.1093/oso/9780198854227.003.0015`, authors=`1`)
  - [Quantum Computing II](https://doi.org/10.1093/oso/9780198854227.003.0016) (source=`crossref`, type=`crossref_abstract`, date=`2020-05-07`, doi=`10.1093/oso/9780198854227.003.0016`, authors=`1`)
  - [Distributed Quantum Computing – Classical and Quantum](https://doi.org/10.1002/9781394185542.ch3) (source=`crossref`, type=`crossref_work`, date=`2023-12`, doi=`10.1002/9781394185542.ch3`, authors=`0`)

### Live Combined Multi-Source Pipeline (wikipedia + arxiv + crossref)
- **ID:** `live_combined_multisource_pipeline`
- **Test Kind:** `live_network`
- **Status:** `PASSED`
- **Duration:** `2747.72 ms`
- **Source Breakdown:** `{"wikipedia": 3, "arxiv": 3, "crossref": 3}`
- **Verification (Structural Only):** score=`100.0`, valid=`9`, excluded=`0`, is_factually_verified=`False`
- **Analysis:** eligible=`9`, themes=`4`, source_distribution=`{"wikipedia": 3, "arxiv": 3, "crossref": 3}`
- **Dashboard:** themes=`4`, charts=`['chart-source-eligibility', 'chart-source-distribution', 'chart-theme-distribution', 'chart-keyword-frequency']`, observations=`9`
- **Sample Live Records:**
  - [Quantum computing](https://en.wikipedia.org/wiki/Quantum_computing) (source=`wikipedia`, type=`wikipedia_extract`, date=`2026-11-04`, doi=`None`, authors=`0`)
  - [Tierkreis: A Dataflow Framework for Hybrid Quantum-Classical Computing](https://arxiv.org/abs/2211.02350v1) (source=`arxiv`, type=`arxiv_paper`, date=`2022-11-04`, doi=`10.1109/QCS56647.2022.00007`, authors=`4`)
  - [Quantum Computing I](https://doi.org/10.1093/oso/9780198854227.003.0015) (source=`crossref`, type=`crossref_abstract`, date=`2020-05-07`, doi=`10.1093/oso/9780198854227.003.0015`, authors=`1`)
  - [Superconducting quantum computing](https://en.wikipedia.org/wiki/Superconducting_quantum_computing) (source=`wikipedia`, type=`wikipedia_extract`, date=`2026-10-26`, doi=`None`, authors=`0`)
  - [Quantum Computing: Vision and Challenges](https://arxiv.org/abs/2403.02240v5) (source=`arxiv`, type=`arxiv_paper`, date=`2024-03-04`, doi=`10.1016/B978-0-443-29096-1.00008-8`, authors=`5`)

### Controlled Partial Failure Honesty (live wikipedia+crossref + simulated arxiv timeout)
- **ID:** `controlled_partial_failure_honesty`
- **Test Kind:** `hybrid_controlled_partial_failure`
- **Status:** `PASSED`
- **Duration:** `1743.83 ms`
- **Source Breakdown:** `{"wikipedia": 3, "arxiv": 0, "crossref": 3}`
- **Source Errors:** `{"arxiv": "Controlled live validation timeout probe for arXiv"}`

## Reproduction Commands

```bash
# Ordinary mocked test suites (no live network requests):
.venv/bin/pytest -v
cd frontend && npm test && npm run build

# Opt-in live multi-source validation:
.venv/bin/python scripts/live_multisource_test.py
```
