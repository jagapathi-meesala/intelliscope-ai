# IntelliScope AI — Final Hackathon Submission Checklist

**Event:** Diwali Festiverse Hackathon  
**Track:** Research — Data & Build  
**Date / Timestamp:** November 2026

Use this checklist to ensure all project deliverables, platform links, documentation files, and sponsor integration disclosures are complete, honest, and ready for submission.

---

## 1. Repository & Codebase Readiness

- [x] **Repository Cleanliness**:
  - No secret tokens, credentials, or API keys committed to Git.
  - Sensitive files (`.env`, `agent_config.yaml`, `runtime_data/`, `__pycache__/`) excluded via `.gitignore`.
  - `.env.example` and `agent_config.yaml.example` updated with safe placeholders.
- [x] **Port & Environment Hygiene**:
  - Backend default port set to `8010` (strictly preserving port `8000` for external developer services).
  - Dynamic port binding supported (`$PORT` for Render deployment, `0.0.0.0` host interface).
- [x] **Four-Agent Core Architecture Intact**:
  - `DataCollectorAgent`: Asynchronous multi-source ingestion (Wikipedia, arXiv, Crossref).
  - `ResearchVerificationAgent`: Structural checks, HTTPS protocol, domain allowlists, DOI syntax.
  - `InsightAnalystAgent`: Deterministic text extraction, theme clustering, evidence citations.
  - `DashboardBuilderAgent`: Safe declarative JSON specifications (KPIs, Recharts specs).

---

## 2. Live Deployment URLs

| Service | Environment | URL / Endpoint | Status |
| :--- | :--- | :--- | :--- |
| **Frontend Web App** | Render Static Site | `https://intelliscope-frontend.onrender.com` | Deployed & Operational |
| **FastAPI Backend** | Render Free Web Service | `https://intelliscope-backend.onrender.com` | Deployed & Operational |
| **API Health Check** | Render Free Web Service | `https://intelliscope-backend.onrender.com/health` | Returns `200 OK` (`healthy`) |
| **Interactive Docs** | Render Free Web Service | `https://intelliscope-backend.onrender.com/docs` | Swagger UI Operational |
| **Alternative Docs** | Render Free Web Service | `https://intelliscope-backend.onrender.com/redoc` | ReDoc Operational |

> **Note on Free Tier Sleep**: Render Free Web Services sleep after 15 minutes of inactivity. Send an initial ping to `/health` ~60 seconds before demonstrations or evaluator reviews to warm up the instance.

---

## 3. Demo Video Deliverables

- [x] **Demonstration Script**: Fully documented in [docs/DEMO_SCRIPT.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/DEMO_SCRIPT.md).
- [ ] **Video Recording Completed**: (To be recorded following `docs/DEMO_SCRIPT.md`).
  - **Target Length**: Under 3 minutes (180 seconds).
  - **Resolution**: 1080p (1920x1080).
  - **Audio**: Clear commentary explaining problem, solution, multi-source pipeline, evidence grounding, and sponsor interoperability.
- [ ] **Hosted Video Link**: Uploaded to YouTube (Unlisted) or Loom, link added to final submission form.

---

## 4. Documentation Deliverables

| Document | File Path | Purpose |
| :--- | :--- | :--- |
| **Project README** | [README.md](file:///home/jagapathi/Projects/intelliscope-ai/README.md) | Comprehensive overview, setup instructions, API reference, limitations. |
| **System Architecture** | [docs/ARCHITECTURE.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/ARCHITECTURE.md) | Mermaid diagrams, data flow schemas, epistemic separation, sponsor adapters. |
| **Demo Script** | [docs/DEMO_SCRIPT.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/DEMO_SCRIPT.md) | 3-minute narration script, sequence of pages, expected outputs. |
| **Render Deployment Guide** | [docs/RENDER_DEPLOYMENT_GUIDE.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/RENDER_DEPLOYMENT_GUIDE.md) | Hybrid deployment topology, environment variables, SPA routing rules. |
| **BAND Remote Setup** | [docs/BAND_REMOTE_BACKEND_SETUP.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/BAND_REMOTE_BACKEND_SETUP.md) | Setup instructions for persistent BAND background worker on host machine. |
| **Submission Checklist** | [docs/SUBMISSION_CHECKLIST.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/SUBMISSION_CHECKLIST.md) | Final verification audit and submission fields template. |

---

## 5. Sponsor Integration Evidence (Diwali Festiverse)

| Sponsor | Category | Status Disclosed | Verification Evidence & Required Proof |
| :--- | :--- | :--- | :--- |
| **BAND (`band.ai`)** | Mandatory | **IMPLEMENTED / PARTIALLY LIVE VERIFIED** | **Verified Evidence:** `band-sdk==6.0.1` runtime (`scripts/band_collector_agent.py`), live REST auth (`get_agent_me` 200 OK `@baboiiibabu/intelliscope-collector`), room discovery (`c348c418-f3a6-467d-8601-c7453bec68e1`), and 10 historical message exchanges.<br><br>**Evidence Required for LIVE TESTED:** Active background daemon running on host connected via WebSocket with a fresh inbound room prompt triggering 4-agent execution and posting back an outbound room reply in real time (`scripts/live_band_room_test.py`). |
| **Finch (`finchwork.net`)** | Mandatory | **IMPLEMENTED** | Official MCP JSON-RPC 2.0 `stdio` server (`scripts/intelliscope_mcp_server.py`) implementing 4 tools (`intelliscope_research`, `intelliscope_verify`, `intelliscope_pipeline`, `intelliscope_integrations_status`). Configured via `integrations/finch/mcp_servers.json` and `integrations/finch/SKILL.md`. Subprocess protocol framing tested locally (`passed`). |
| **Lyzr (`lyzr.ai`)** | Mandatory | **PARTIAL (Not Live-Configured)** | Modular adapter `backend/integrations/lyzr_adapter.py` implementing `POST /v3/inference/chat/` and workflow execution. Tested with HTTPX mocks. Explicitly disclosed as not live-configured because `LYZR_API_KEY` and `LYZR_AGENT_ID` are not present in the environment. |
| **AdaL (`adal.sylph.ai`)** | Mandatory | **PARTIAL (Not Live-Configured)** | Project AdaL skill defined in `.atskills/intelliscope-research/SKILL.md` and CLI runner in `backend/integrations/adal_adapter.py`. Explicitly disclosed as not live-configured because the `adal` CLI is not installed on this host (`ADAL_ENABLED=false`). |
| **Agent37 (`agent37.com`)** | Optional Prize Track | **PARTIAL (Not Live-Configured)** | Modular adapter `backend/integrations/agent37_adapter.py` for cloud execution. Tested with HTTPX mocks. Explicitly disclosed as not live-configured because `AGENT37_API_KEY` and `AGENT37_INSTANCE_ID` are not set. |

---

## 6. Test Suite & Verification Results

| Test Suite | Execution Command | Result | Notes |
| :--- | :--- | :--- | :--- |
| **Backend Unit & Integration** | `.venv/bin/pytest tests/` | **260 passed, 0 failed** (2.7s) | Full coverage of agents, API endpoints, BAND collector, multi-source clients, and integration adapters. |
| **Frontend Unit Tests** | `npm --prefix frontend test` | **17 passed, 0 failed** (340ms) | Node test runner validating API client resolution, URL safety, state mapping, and dashboard integrity. |
| **Frontend Production Build** | `npm --prefix frontend run build` | **Successful build** (4.4s) | Precompiled Vite SPA assets in `frontend/dist/`. |
| **Live Multi-Source Validation** | `python scripts/live_multisource_test.py` | **Passed** | Verified live HTTP ingestion from Wikipedia, arXiv, and Crossref (`test-results/live-multisource/`). |
| **Live Sponsor Probe** | `python scripts/live_integrations_test.py` | **Passed (2 passed, 3 skipped)** | Verified BAND REST auth and Finch MCP handshake; skipped unconfigured sponsors honestly. |
| **Live BAND Room Test** | `python scripts/live_band_room_test.py` | **Opt-In Script Available** | Automated script to demonstrate fresh inbound-to-outbound room roundtrip when host collector is active. |

---

## 7. Submission Form Template Fields

When filling out the hackathon submission portal, use the following standardized fields:

- **Project Title:** IntelliScope AI
- **Tagline:** Autonomous Multi-Agent Research & Intelligence Platform
- **Track:** Research — Data & Build
- **Short Description (1-2 sentences):**  
  *IntelliScope AI is a collaborative 4-agent intelligence platform that gathers academic research across Wikipedia, arXiv, and Crossref, enforces structural integrity, deterministically clusters themes, and generates safe interactive dashboards with verifiable source provenance.*
- **Problem Statement:**  
  *Researchers, technical analysts, and engineers waste hours manually cross-referencing papers across fragmented repositories, while modern generative AI summarizers hallucinate citations and present speculative assertions as facts.*
- **Solution:**  
  *IntelliScope AI decouples the intelligence workflow into four specialized agents: Data Collector (multi-source retrieval), Research Verification (structural checks and DOI deduplication), Insight Analyst (deterministic theme clustering and evidence citations), and Dashboard Builder (declarative, safe JSON specifications). Every insight is traceable to its canonical source, and structural validity is strictly separated from factual claims.*
- **Key Technologies:**  
  *Python 3.12, FastAPI, Pydantic v2, HTTPX, React 18, Vite, Tailwind CSS, Recharts, BAND SDK, Model Context Protocol (MCP).*
- **Sponsor Tracks Applied For:**
  - **BAND**: Phoenix WebSocket runtime, multi-agent pipeline orchestration, inter-agent delegation.
  - **Finch**: Official MCP JSON-RPC 2.0 stdio server with 4 research and verification tools.
  - **Lyzr**: Modular workflow adapter with typed schemas.
  - **AdaL**: Project AdaL skill and CLI execution adapter.
- **Repository URL:** https://github.com/jagapathi-meesala/intelliscope-ai
- **Live Demo URL:** `https://intelliscope-frontend.onrender.com`
- **Backend API URL:** `https://intelliscope-backend.onrender.com`
- **Demo Video URL:** *(Insert YouTube/Loom video link)*

