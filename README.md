# IntelliScope AI

### Autonomous Multi-Agent Research & Intelligence Platform

IntelliScope AI is a multi-agent research platform that collects, verifies, analyzes, and transforms information into interactive dashboards.

## Project Track
Research — Data & Build

## Agents

1. **Data Collector Agent** (Operational) — Asynchronously collects research from configurable external sources via modular clients in `backend/services/sources/`:
   - **Wikipedia** (`https://en.wikipedia.org/w/api.php`) — Default source; introductory extracts and sanitized search snippets.
   - **arXiv** (`https://export.arxiv.org/api/query`) — Academic preprints with Atom XML parsing, abstracts, authors, publication dates, and optional DOIs.
   - **Crossref** (`https://api.crossref.org/works`) — Scholarly publication metadata with DOIs, authors, publication dates, and JATS-cleaned abstracts or honest metadata fallbacks.
2. **Research Verification Agent** (Operational) — Validates structural integrity, HTTPS protocol compliance, source-aware domain whitelists (`*.wikipedia.org`, `arxiv.org`, `doi.org`), DOI syntax & cross-batch DOI deduplication, URL/title deduplication, and ISO timestamps. Computes transparent quality scores while explicitly distinguishing structural validity from factual accuracy.
3. **Insight Analyst Agent** (Operational) — Performs explainable, deterministic text analysis, keyword extraction, source-modality breakdown (`source_distribution`), and theme clustering strictly on verified evidence. Grounds all observations with source provenance (`source_name`, `source_type`, `publication_date`, `doi`, `authors`) and discloses partial source errors, information gaps, and methodology limitations without hallucination or LLM extrapolation.
4. **Dashboard Builder Agent** (Operational) — Converts the Insight Analyst Agent's structured output into a safe, validated dashboard specification JSON containing executive summaries, KPI metric cards, thematic clusters, source-distribution charts (`chart-source-distribution`), evidence citations, and chart specifications suitable for frontend rendering without executing unsafe code.

## Technology Stack

- Python 3.12+
- FastAPI & Uvicorn
- Pydantic v2
- HTTPX (Asynchronous HTTP)
- Pytest & Pytest-asyncio
- React (Frontend)
- BAND
- Lyzr
- Finch
- AdaL
- Agent37

## Core Features

- Multi-agent collaboration & pipeline orchestration
- Multi-source asynchronous research collection (Wikipedia, arXiv, Crossref) with unified record normalization & round-robin balancing
- Graceful partial-source degradation (`source_errors`) and explicit rate-limit / timeout diagnostics
- Source verification, structural integrity checking, and DOI validation / deduplication
- Domain whitelist enforcement per provider (`wikipedia`, `arxiv`, `crossref`)
- Transparent quality scoring (0–100)
- Deterministic text analysis & theme clustering
- Evidence-backed observation grounding with academic provenance
- Declarative, safe dashboard specification generation
- Interactive React dashboard with provider selection, KPIs, and chart visualizations

## Setup & Installation

### 1. Prerequisites
- Python 3.12+
- Virtual environment (`venv`)

### 2. Virtual Environment Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install required dependencies:

```bash
pip install -r requirements.txt
```

### 3. Running the Backend Server

Start the FastAPI backend with Uvicorn on port `8010`:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8010 --reload
```

Interactive API documentation (Swagger UI) is accessible at:
- `http://localhost:8010/docs`
- `http://localhost:8010/redoc`

### 4. Running Automated Tests

Run the full test suite using pytest:

```bash
pytest
```

For verbose output:

```bash
pytest -v
```

### 5. Running & Testing the React Frontend

Inside `frontend/` (assuming dependencies are already installed):

```bash
cd frontend
npm test
npm run build
npm run dev
```

---

## API Reference

### 1. Root & Health Check

#### `GET /`
Returns platform greeting and server running state.

**Response (200 OK):**
```json
{
  "project": "IntelliScope AI",
  "status": "running",
  "message": "Welcome to IntelliScope AI"
}
```

#### `GET /health`
Probing endpoint for service health monitoring.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "backend": "operational"
}
```

---

### 2. Agent Fleet Status

#### `GET /agents/status`
Returns the operational status, readiness, and implemented capabilities of platform agents. All four core agents are operational.

**Example Request:**
```bash
curl -X GET http://localhost:8010/agents/status
```

**Response (200 OK):**
```json
{
  "agents": {
    "data_collector": {
      "name": "Data Collector Agent",
      "status": "operational",
      "operational": true,
      "description": "Asynchronously collects external research data via official APIs.",
      "capabilities": [
        "wikipedia_search",
        "asynchronous_data_retrieval",
        "html_snippet_sanitization",
        "structured_metadata"
      ],
      "version": "1.0.0"
    },
    "research_verification": {
      "name": "Research Verification Agent",
      "status": "operational",
      "operational": true,
      "description": "Validates structural integrity, URL protocol, domain compliance, and deduplication of research results.",
      "capabilities": [
        "structural_schema_validation",
        "https_protocol_verification",
        "domain_whitelist_enforcement",
        "deduplication_analysis",
        "iso_timestamp_validation",
        "quality_score_calculation"
      ],
      "version": "1.0.0"
    },
    "insight_analyst": {
      "name": "Insight Analyst Agent",
      "status": "operational",
      "operational": true,
      "description": "Performs deterministic, explainable text analysis, keyword extraction, and theme clustering on verified evidence.",
      "capabilities": [
        "deterministic_text_analysis",
        "keyword_extraction",
        "theme_clustering",
        "evidence_grounding",
        "gap_identification",
        "verification_consistency_check"
      ],
      "version": "1.0.0"
    },
    "dashboard_builder": {
      "name": "Dashboard Builder Agent",
      "status": "operational",
      "operational": true,
      "description": "Generates safe, validated dashboard specification JSON including KPIs, themes, evidence citations, and chart specifications.",
      "capabilities": [
        "dashboard_specification_generation",
        "kpi_metric_synthesis",
        "chart_specification_derivation",
        "url_safety_enforcement",
        "schema_validation"
      ],
      "version": "1.0.0"
    }
  }
}
```

---

### 3. Research Collection

#### `POST /research`
Invokes the **Data Collector Agent** to perform asynchronous multi-source retrieval across selected providers (`wikipedia`, `arxiv`, `crossref`).

**Request Body Constraints:**
- `query` (string, required): 1 to 300 characters, cannot be empty or pure whitespace.
- `limit` (integer, optional): Number of results to retrieve (1 to 10, default: 5).
- `sources` (array of strings, optional): Ordered unique list of providers from `["wikipedia", "arxiv", "crossref"]` (default: `["wikipedia"]` for full backward compatibility).

**Example Request:**
```bash
curl -X POST http://localhost:8010/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Quantum Computing",
    "limit": 3,
    "sources": ["wikipedia", "arxiv", "crossref"]
  }'
```

**Response (200 OK):**
```json
{
  "agent": "Data Collector Agent",
  "agent_name": "Data Collector Agent",
  "query": "Quantum Computing",
  "result_count": 3,
  "total_results": 3,
  "sources_requested": ["wikipedia", "arxiv", "crossref"],
  "source_breakdown": {
    "wikipedia": 1,
    "arxiv": 1,
    "crossref": 1
  },
  "source_errors": {},
  "retrieved_at": "2026-11-11T18:15:00.000000+00:00",
  "results": [
    {
      "title": "Quantum computing",
      "snippet": "Quantum computing is a computer that exploits quantum mechanical phenomena.",
      "abstract": "Quantum computing is a computer that exploits quantum mechanical phenomena.",
      "source_name": "wikipedia",
      "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
      "source": "https://en.wikipedia.org/wiki/Quantum_computing",
      "publication_date": null,
      "doi": null,
      "authors": [],
      "source_type": "wikipedia_extract",
      "retrieved_at": "2026-11-11T18:15:00.000000+00:00"
    },
    {
      "title": "Fault-Tolerant Quantum Surface Codes",
      "snippet": "Analysis of threshold behavior in scalable topological qubit lattices.",
      "abstract": "Analysis of threshold behavior in scalable topological qubit lattices.",
      "source_name": "arxiv",
      "source_url": "https://arxiv.org/abs/2401.12345v1",
      "source": "https://arxiv.org/abs/2401.12345v1",
      "publication_date": "2024-01-22",
      "doi": "10.1103/PhysRevLett.132.010501",
      "authors": ["Alice Smith", "Bob Chen"],
      "source_type": "arxiv_paper",
      "retrieved_at": "2026-11-11T18:15:00.000000+00:00"
    }
  ]
}
```

#### Status Codes & Error Handling:
- `200 OK`: Successful retrieval (including queries yielding zero results, or multi-source partial failures where healthy sources still succeeded and failing providers appear in `source_errors`).
- `422 Unprocessable Entity`: Input validation failure (e.g., unsupported source name, query > 300 characters, limit out of range 1–10, empty query).
- `429 Too Many Requests`: Rate limiting enforced by all selected external providers.
- `502 Bad Gateway`: Upstream API service failure, connection error, or invalid XML/JSON upstream response across all selected providers.
- `504 Gateway Timeout`: Upstream API request timed out across all selected providers.

---

### 4. Research Verification

#### `POST /verify`
Invokes the **Research Verification Agent** to validate the output produced by the Data Collector Agent.

The verification process evaluates:
- Non-empty titles and snippets
- Secure HTTPS source URLs
- Allowed source domain whitelist per provider (Wikipedia: `*.wikipedia.org`; arXiv: `arxiv.org` / `export.arxiv.org`; Crossref: `doi.org` / `dx.doi.org`)
- DOI syntax validation (`10.xxxx/...`) and duplicate DOI detection across records
- Duplicate URLs and duplicate titles across the batch
- Valid ISO 8601 retrieval timestamps
- Missing or malformed data fields

> **Important**: This verification evaluates structural integrity, URL protocol compliance, domain whitelist adherence, timestamp validity, and deduplication. It explicitly sets `is_factually_verified: false` and includes a mandatory disclaimer distinguishing structural validity from factual correctness.

**Example Request:**
```bash
curl -X POST http://localhost:8010/verify \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Artificial Intelligence",
    "results": [
      {
        "title": "Artificial intelligence",
        "snippet": "Artificial intelligence (AI) is the intelligence of machines or software.",
        "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "retrieved_at": "2026-11-04T18:15:00.000000+00:00"
      }
    ]
  }'
```

**Response (200 OK):**
```json
{
  "agent": "Research Verification Agent",
  "agent_name": "Research Verification Agent",
  "query": "Artificial Intelligence",
  "verified_at": "2026-11-04T18:25:00.000000+00:00",
  "total_results": 1,
  "valid_results_count": 1,
  "invalid_results_count": 0,
  "quality_score": 100.0,
  "status": "passed",
  "verification_type": "structural_and_source_integrity",
  "is_factually_verified": false,
  "factual_accuracy_disclaimer": "This verification evaluates structural integrity, URL protocol compliance, domain whitelist adherence, timestamp validity, and deduplication. It does NOT assert that the factual claims within snippets are verified facts.",
  "summary": {
    "total_checks": 7,
    "passed_checks": 7,
    "failed_checks": 0,
    "warning_count": 0,
    "error_count": 0,
    "duplicate_urls_count": 0,
    "duplicate_titles_count": 0
  },
  "results": [
    {
      "index": 0,
      "title": "Artificial intelligence",
      "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "status": "valid",
      "item_score": 100.0,
      "checks": {
        "title_valid": true,
        "snippet_valid": true,
        "https_valid": true,
        "domain_allowed": true,
        "timestamp_valid": true,
        "is_duplicate_url": false,
        "is_duplicate_title": false
      },
      "errors": [],
      "warnings": []
    }
  ]
}
```

---

### 5. Insight Analysis

#### `POST /analyze`
Invokes the **Insight Analyst Agent** to synthesize structured intelligence from verified research data.

The agent:
- Validates the relational consistency between research data and verification reports (query matching, count consistency, and detection of forged verification scores or flags).
- Filters out all unverified, invalid, or duplicate sources so only eligible evidence is utilized.
- Applies explainable, deterministic lexical analysis, keyword frequency weighting, and rule-based thematic clustering without relying on external generative LLM APIs.
- Connects every evidence-backed observation directly to its supporting canonical source URL.
- Transparently discloses information gaps, actionable recommendations, and methodological limitations.

**Example Request:**
```bash
curl -X POST http://localhost:8010/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "research": {
      "query": "Artificial intelligence",
      "results": [
        {
          "title": "Artificial intelligence",
          "snippet": "Artificial intelligence is a discipline devoted to creating software and machines that model human intelligence.",
          "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
          "retrieved_at": "2026-03-01T12:00:00Z"
        }
      ]
    },
    "verification": {
      "query": "Artificial intelligence",
      "total_results": 1,
      "results": [
        {
          "index": 0,
          "title": "Artificial intelligence",
          "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
          "status": "valid",
          "checks": {
            "title_valid": true,
            "snippet_valid": true,
            "https_valid": true,
            "domain_allowed": true,
            "timestamp_valid": true,
            "is_duplicate_url": false,
            "is_duplicate_title": false
          },
          "errors": []
        }
      ]
    }
  }'
```

**Response (200 OK):**
```json
{
  "agent": "Insight Analyst Agent",
  "agent_name": "Insight Analyst Agent",
  "topic": "Artificial intelligence",
  "analyzed_at": "2026-11-05T00:15:00.000000+00:00",
  "total_sources_evaluated": 1,
  "eligible_sources_count": 1,
  "excluded_sources_count": 0,
  "executive_summary": "Synthesized research on 'Artificial intelligence' across 1 verified source(s). Primary thematic focus centers on 'Foundations & Theoretical Concepts', with recurring terminology including intelligence, discipline, software, machines, model. Initial evidence from 'Artificial intelligence' establishes that Artificial intelligence is a discipline devoted to creating software and machines that model human intelligence.",
  "key_themes": [
    {
      "theme": "Foundations & Theoretical Concepts",
      "description": "Fundamental principles, formal definitions, and theoretical underpinnings.",
      "frequency": 1,
      "sources": [
        "https://en.wikipedia.org/wiki/Artificial_intelligence"
      ]
    }
  ],
  "important_keywords": [
    "intelligence",
    "discipline",
    "software",
    "machines",
    "model"
  ],
  "evidence_backed_observations": [
    {
      "statement": "According to 'Artificial intelligence': Artificial intelligence is a discipline devoted to creating software and machines that model human intelligence.",
      "source_title": "Artificial intelligence",
      "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "confidence": "high"
    }
  ],
  "information_gaps": [
    "Limited source diversity: Only 1 eligible source(s) met verification standards.",
    "Evidence is derived from encyclopedia summary snippets rather than full primary papers.",
    "Real-time chronological updates and empirical performance metrics are unrepresented in snippets."
  ],
  "recommendations": [
    "Deepen primary literature review specifically targeting 'Foundations & Theoretical Concepts'.",
    "Expand query retrieval using specific extracted keywords: intelligence, discipline, software, machines.",
    "Conduct multi-source fact cross-referencing against peer-reviewed journals."
  ],
  "limitations": [
    "Analysis relies on deterministic lexical extraction, keyword frequency weighting, and rule-based clustering without generative LLM extrapolation.",
    "Findings are constrained strictly to text snippets verified by the Research Verification Agent.",
    "Structural validity confirms protocol and domain compliance, not infallible factual truth."
  ],
  "methodology": "Deterministic keyword extraction, frequency analysis, and rule-based theme clustering. No generative LLM extrapolation."
}
```

---

### 6. Dashboard Specification Generation

#### `POST /dashboard`
Invokes the **Dashboard Builder Agent** to transform the output of the Insight Analyst Agent into a validated, declarative JSON specification for visual rendering by the React frontend.

The specification provides:
- High-level display title and research topic.
- Executive summary narrative.
- Four core KPI cards:
  - Total Sources Evaluated (`kpi-total-sources`)
  - Eligible Verified Sources (`kpi-eligible-sources`)
  - Excluded / Duplicate Sources (`kpi-excluded-sources`)
  - Identified Research Themes (`kpi-theme-count`)
- Thematic structure breakdown and important keyword tags.
- Evidence-backed observations with audited, safe HTTPS citations.
- Structured chart specifications (`pie`, `bar`, `horizontal_bar`) derived solely from actual analysis metrics with explicit heuristic disclosures.
- Methodological limitations and research recommendations.

> **Safety Notice**: The dashboard specification is strictly declarative and static. It generates zero executable JavaScript or arbitrary HTML markup, ensuring safe hydration within frontend components.

**Example Request:**
```bash
curl -X POST http://localhost:8010/dashboard \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "Insight Analyst Agent",
    "topic": "Artificial intelligence",
    "analyzed_at": "2026-11-05T00:15:00.000000+00:00",
    "total_sources_evaluated": 1,
    "eligible_sources_count": 1,
    "excluded_sources_count": 0,
    "executive_summary": "Synthesized research on Artificial intelligence.",
    "key_themes": [
      {
        "theme": "Foundations & Theoretical Concepts",
        "description": "Fundamental principles and formal definitions.",
        "frequency": 1,
        "sources": ["https://en.wikipedia.org/wiki/Artificial_intelligence"]
      }
    ],
    "important_keywords": ["intelligence", "software", "machine"],
    "evidence_backed_observations": [
      {
        "statement": "According to Artificial intelligence: AI models cognitive tasks.",
        "source_title": "Artificial intelligence",
        "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "confidence": "high"
      }
    ],
    "information_gaps": ["Limited source depth."],
    "recommendations": ["Conduct primary literature review."],
    "limitations": ["Constrained to encyclopedia excerpts."],
    "methodology": "Deterministic text extraction."
  }'
```

**Response (200 OK):**
```json
{
  "agent": "Dashboard Builder Agent",
  "agent_name": "Dashboard Builder Agent",
  "title": "Research Intelligence Dashboard: Artificial intelligence",
  "topic": "Artificial intelligence",
  "generated_at": "2026-11-05T00:35:00.000000+00:00",
  "executive_summary": "Synthesized research on Artificial intelligence.",
  "kpi_cards": [
    {
      "id": "kpi-total-sources",
      "label": "Total Sources Evaluated",
      "value": 1,
      "unit": "sources",
      "description": "Total candidate sources gathered from data collection."
    },
    {
      "id": "kpi-eligible-sources",
      "label": "Eligible Verified Sources",
      "value": 1,
      "unit": "sources",
      "description": "Sources passing all structural, HTTPS, and domain verification checks."
    },
    {
      "id": "kpi-excluded-sources",
      "label": "Excluded / Duplicates",
      "value": 0,
      "unit": "sources",
      "description": "Sources excluded due to verification failures or duplication."
    },
    {
      "id": "kpi-theme-count",
      "label": "Identified Themes",
      "value": 1,
      "unit": "themes",
      "description": "Thematic research clusters synthesized from verified evidence."
    }
  ],
  "key_themes": [
    {
      "theme": "Foundations & Theoretical Concepts",
      "description": "Fundamental principles and formal definitions.",
      "frequency": 1,
      "sources": [
        "https://en.wikipedia.org/wiki/Artificial_intelligence"
      ]
    }
  ],
  "important_keywords": [
    "intelligence",
    "software",
    "machine"
  ],
  "observations": [
    {
      "statement": "According to Artificial intelligence: AI models cognitive tasks.",
      "source_title": "Artificial intelligence",
      "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "confidence": "high"
    }
  ],
  "information_gaps": [
    "Limited source depth."
  ],
  "recommendations": [
    "Conduct primary literature review."
  ],
  "limitations": [
    "Constrained to encyclopedia excerpts."
  ],
  "charts": [
    {
      "id": "chart-source-eligibility",
      "title": "Source Evidence Eligibility Breakdown",
      "chart_type": "pie",
      "description": "Proportion of candidate sources eligible for evidence synthesis versus excluded records.",
      "x_axis_label": null,
      "y_axis_label": null,
      "data": [
        {"label": "Eligible Sources", "value": 1.0, "color": "#10B981"},
        {"label": "Excluded / Duplicates", "value": 0.0, "color": "#EF4444"}
      ],
      "is_heuristic": false
    },
    {
      "id": "chart-theme-distribution",
      "title": "Research Theme Distribution",
      "chart_type": "horizontal_bar",
      "description": "Number of verified sources addressing each identified theme cluster.",
      "x_axis_label": "Source Count",
      "y_axis_label": "Research Theme",
      "data": [
        {"label": "Foundations & Theoretical Concepts", "value": 1.0, "color": "#3B82F6"}
      ],
      "is_heuristic": false
    },
    {
      "id": "chart-keyword-frequency",
      "title": "Prominent Keyword Occurrences in Source Evidence",
      "chart_type": "bar",
      "description": "Lexical frequency count of prominent keywords extracted across verified snippet text (heuristic text measure, not real-world demographic statistic).",
      "x_axis_label": "Extracted Keyword",
      "y_axis_label": "Snippet Term Frequency",
      "data": [
        {"label": "intelligence", "value": 1.0, "color": "#6366F1"},
        {"label": "software", "value": 1.0, "color": "#6366F1"},
        {"label": "machine", "value": 1.0, "color": "#6366F1"}
      ],
      "is_heuristic": true
    }
  ],
  "render_notice": "Safe specification format for React frontend rendering. No executable code or unsafe scripts."
}
```

#### Status Codes:
- `200 OK`: Dashboard specification successfully constructed and validated.
- `400 Bad Request`: Unsafe source URLs detected (non-HTTPS or script schemes) or malformed analyst payload attributes.
- `422 Unprocessable Entity`: Missing required payload fields or schema validation failures.
- `500 Internal Server Error`: Unexpected internal processing failure.

---

### 6. Unified Multi-Agent Pipeline

#### `POST /pipeline`
Executes the unified, end-to-end 4-agent intelligence workflow sequentially within a single request:
**Data Collector Agent** ➔ **Research Verification Agent** ➔ **Insight Analyst Agent** ➔ **Dashboard Builder Agent**.

- Single atomic invocation for the entire multi-agent pipeline.
- Precise per-agent and total execution time tracking in milliseconds (`duration_ms`).
- Resilient error isolation: if an individual agent encounters an error, upstream evidence is preserved and downstream steps are gracefully skipped.
- Zero data fabrication guarantee: if external research yields no records, the pipeline completes transparently with zero-count KPIs and explanations.

**Request Body (`PipelineRequest`):**
- `sources` (optional): list of providers from `["wikipedia", "arxiv", "crossref"]` (defaults to `["wikipedia"]`).

```json
{
  "query": "Quantum Computing",
  "limit": 3,
  "sources": ["wikipedia", "arxiv", "crossref"]
}
```

**Response (200 OK — `PipelineResponse`):**
```json
{
  "pipeline_id": "99351e34-58a3-4813-b5f7-640f8fa2667a",
  "query": "Quantum Computing",
  "status": "success",
  "total_duration_ms": 142.5,
  "agent_statuses": {
    "data_collector": {
      "agent_key": "data_collector",
      "agent_name": "Data Collector Agent",
      "status": "completed",
      "duration_ms": 48.2,
      "details": "Retrieved 2 external source(s)",
      "error": null
    },
    "research_verification": {
      "agent_key": "research_verification",
      "agent_name": "Research Verification Agent",
      "status": "completed",
      "duration_ms": 22.1,
      "details": "Quality score: 100/100 (2 valid, 0 invalid)",
      "error": null
    },
    "insight_analyst": {
      "agent_key": "insight_analyst",
      "agent_name": "Insight Analyst Agent",
      "status": "completed",
      "duration_ms": 36.4,
      "details": "Analyzed 2 eligible source(s) (0 excluded), 2 theme(s)",
      "error": null
    },
    "dashboard_builder": {
      "agent_key": "dashboard_builder",
      "agent_name": "Dashboard Builder Agent",
      "status": "completed",
      "duration_ms": 35.8,
      "details": "Generated 4 KPI card(s) and 2 chart specification(s)",
      "error": null
    }
  },
  "summary": "Quantum computing harnesses quantum mechanics to perform calculations exponentially faster than classical computers.",
  "research": { ... },
  "verification": { ... },
  "analysis": { ... },
  "dashboard": { ... },
  "executed_at": "2026-11-07T01:10:00.000000+00:00"
}
```

#### Status Codes:
- `200 OK`: Pipeline executed. Status indicates `success`, `partial_success`, or `failed` (with detailed per-agent statuses).
- `422 Unprocessable Entity`: Request validation failure (e.g., query empty, query > 300 characters, limit out of bounds 1-10).
- `500 Internal Server Error`: Unexpected unhandled orchestration failure.

---

## End-to-End Multi-Agent Pipeline & Live Verification

IntelliScope AI orchestrates four specialized agents sequentially:

```
[User Query]
     │
     ▼
┌─────────────────────────┐
│  Data Collector Agent   │  POST /research
│  (Live Wikipedia API)   │  Asynchronously searches and collects structured snippet records
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Research Verification   │  POST /verify
│        Agent            │  Validates schema, HTTPS protocol, domain whitelist, deduplication
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Insight Analyst Agent  │  POST /analyze
│ (Explainable Synthesis) │  Deterministic keyword extraction, theme clustering, evidence grounding
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Dashboard Builder Agent │  POST /dashboard
│ (Safe Specification)    │  Emits validated JSON for React UI: KPI cards, themes, charts, observations
└─────────────────────────┘
```

### Reproducible Live Pipeline Execution

To execute the entire multi-agent workflow against the live backend and official MediaWiki API:

```bash
# Ensure virtualenv is active and backend server is running on port 8010
source .venv/bin/activate

# Execute live end-to-end pipeline verification script
python scripts/live_pipeline_test.py
```

The script performs the following operations:
1. Confirms the backend server is operational on `http://127.0.0.1:8010` (or auto-launches a local instance).
2. Verifies the status of all four registered agents (`GET /agents/status`).
3. Executes `POST /research` with query `"Artificial intelligence"` against the live Wikipedia API.
4. Passes structured collector results to `POST /verify` for integrity, URL protocol, domain whitelist, and timestamp checks.
5. Feeds verified evidence to `POST /analyze` to extract key themes, prominent keywords, and evidence-backed observations.
6. Submits the analysis payload to `POST /dashboard` to generate the complete declarative dashboard specification.
7. Saves the exact live JSON responses to the `test-results/` directory:
   - `test-results/research.json`: Real MediaWiki search results with HTTPS URLs, clean text snippets, and timestamps.
   - `test-results/verification.json`: Structural integrity report, 100/100 quality score, per-result checks, and factual accuracy disclaimer.
   - `test-results/analysis.json`: Thematic clusters, lexical frequency keywords, observations with source citations, gaps, and limitations.
   - `test-results/dashboard.json`: React-ready dashboard specification with KPI cards, source eligibility pie chart, theme distribution bar chart, keyword frequency chart, and observations.
8. Validates 5 critical edge cases:
   - **Empty Research Results**: Queries returning zero items gracefully yield zero-count reports and valid empty dashboard specs with no fabricated data.
   - **Mismatched Query Payloads**: Rejects payloads where research and verification topics diverge (`HTTP 400`).
   - **Tampered Verification Reports**: Rejects forged reports claiming "valid" status when underlying checks failed (`HTTP 400`).
   - **Unsafe Citation URL Injection**: Rejects non-HTTPS schemes such as `javascript:` or `http:` in dashboard observations (`HTTP 400`).
   - **Upstream API Timeout**: Maps external service timeouts safely to `HTTP 504 Gateway Timeout`.

---

## BAND Platform Integration: Multi-Agent Intelligence Pipeline

IntelliScope AI connects its multi-agent platform directly to the **BAND** collaboration platform using the official Python SDK (`band-sdk==6.0.1`) and the documented `SimpleAdapter` pattern.

### Architecture & Connection Design

```
   ┌─────────────────────────────────────────────────────────┐
   │                  BAND Platform Room                     │
   │           Human Users & Autonomous Agents               │
   └───────────────────────────┬─────────────────────────────┘
                               │ @mention (e.g. "@DataCollector research Quantum computing")
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │      BAND Agent Runtime (scripts/band_collector_agent.py)│
   │      - SimpleAdapter[list] event loop                   │
   │      - Extracts query & parameters                      │
   │      - Dispatches to Unified Pipeline endpoint          │
   └───────────────────────────┬─────────────────────────────┘
                               │ HTTP POST /pipeline (JSON)
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │          IntelliScope FastAPI Backend (Port 8010)       │
   │  ┌───────────────────────────────────────────────────┐  │
   │  │ 1. Data Collector Agent (Wikipedia Search)        │  │
   │  │ 2. Research Verification Agent (Quality Scoring)  │  │
   │  │ 3. Insight Analyst Agent (Thematic Synthesis)     │  │
   │  │ 4. Dashboard Builder Agent (Safe Spec JSON)       │  │
   │  └───────────────────────────────────────────────────┘  │
   └───────────────────────────┬─────────────────────────────┘
                               │ HTTP 200 / PipelineResponse
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │  BAND band_send_message tool response back to chat room │
   │  - Executive Summary & Fleet Execution Timing           │
   │  - Verified Evidence Sources with HTTPS citations       │
   │  - KPI Overview & Thematic Insights                     │
   │  - Validated Dashboard Specification JSON Code Block    │
   │  - Zero fabrication guarantee                           │
   └─────────────────────────────────────────────────────────┘
```

### Configuration & Credentials

Agent credentials are read locally from `agent_config.yaml` (which is excluded from version control via `.gitignore`) or from environment variables:

1. Copy the example template:
   ```bash
   cp agent_config.yaml.example agent_config.yaml
   ```

2. Configure your platform-issued BAND agent credentials in `agent_config.yaml`:
   ```yaml
   data_collector:
     agent_id: "your-band-agent-id-here"
     api_key: "your-band-api-key-here"
   ```

   *Alternatively, set the `BAND_AGENT_ID` and `BAND_API_KEY` environment variables.*

### Startup Commands

The BAND agent runtime operates as a standalone service, independent of the FastAPI backend server:

```bash
# Terminal 1: Start the FastAPI Backend on port 8010
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8010

# Terminal 2: Start the BAND Multi-Agent Pipeline Agent
source .venv/bin/activate
python scripts/band_collector_agent.py
```

### Supported Interaction Syntax

In any BAND room where the agent is a participant, mention the agent to trigger deterministic research across all 4 agents:
- `@IntelliScope Collector Research quantum computing` *(defaults to `wikipedia`)*
- `@IntelliScope Collector Research quantum computing sources=arxiv,crossref`
- `@IntelliScope Collector Research quantum computing (sources: wikipedia, arxiv)`
- `@IntelliScope Collector Research quantum computing [arxiv, crossref] limit=6`
- `@IntelliScope Collector Research quantum computing sources=all`
- `@IntelliScope Collector Research quantum computing from arxiv and crossref`
- `@DataCollector research Artificial intelligence`
- `/intelliscope-collector Research quantum computing`
- `@DataCollector find: Graph theory (limit: 4)`

The agent extracts the original user query and optional source list, sanitizes platform mentions, handles, and leading action instructions (e.g. converting `'@IntelliScope Collector Research quantum computing'` or `'/intelliscope-collector Research quantum computing'` cleanly to `'quantum computing'`), executes the unified pipeline (`POST /pipeline`), synthesizes verified multi-source results (with provider breakdown, publication dates, authors, DOIs, and partial error notices when applicable), constructs a validated dashboard specification JSON, and posts the complete executive intelligence brief directly into the room mentioning the requester.

### Robust BAND Message Sanitization

The BAND agent runtime (`scripts/band_collector_agent.py`) implements sanitized query extraction across diverse platform message formats:
- **Multi-Word Display Names**: Strips display name mentions like `@IntelliScope Collector` and `@Data Collector Agent`.
- **Command & Path Handles**: Strips leading command slugs (`/intelliscope-collector`) and path handles (`@owner/handle`, `@/handle`, `@handle`).
- **Normalized Platform Tokens**: Resolves stored `@[[uuid]]` and `<@uuid>` mention metadata.
- **Explicit Source Modifier Extraction**: Parses optional explicit source selection modifiers while keeping source names in ordinary prose queries untouched (e.g., `Wikipedia history` or `Operations research`).
- **Action Instruction Stripping**: Strips single leading action verbs (`Research <topic>`, `search for <topic>`, `find <topic>`) into clean topic strings without stripping legitimate topic vocabulary (e.g. `Operations research`, `Search algorithms`, `Market research` remain completely intact).
- **Safe Sanitized Logging**: Logs sanitized topic queries without printing credentials, API keys, or sensitive auth headers.

### Multi-Source Architecture & Current Limitations

- **Supported Sources**: Wikipedia (`wikipedia`), arXiv preprints (`arxiv`), and Crossref publication metadata (`crossref`). All three clients use asynchronous `httpx` requests without requiring paid API keys.
- **Metadata Completeness**: arXiv entries carry optional `arxiv:doi` elements (`null` when absent). Crossref works frequently omit open `abstract` text; when unavailable, IntelliScope AI records a transparent metadata fallback noting journal and DOI instead of fabricating abstract prose.
- **API Rate Limits & Timeouts**: Public arXiv and Crossref endpoints enforce rate limits (`HTTP 429`) and occasional latency spikes. When querying multiple sources, partial provider failures are isolated and surfaced in `source_errors` while healthy provider results complete the pipeline.
- **Structural vs. Factual Verification**: Verification confirms HTTPS URLs, allowed provider domains, valid DOI format (`10.xxxx/...`), timestamps, and batch deduplication — peer-reviewed empirical fact-checking remains out of scope.

---

## Sponsor Platform Interoperability & Actual Integration Status (Diwali Festiverse Audit)

**Selected Track:** **Research — Data & Build** (Data Agent gathers & normalizes multi-source web data → Builder Agent compiles evidence-backed dashboards/widgets).

Per official Diwali Festiverse requirements for **Research — Data & Build**:
- **Mandatory Sponsors:** **BAND**, **Lyzr**, **AdaL**, and **Finch**
- **Optional Sponsor (Deployment/Credits Prize Track):** **Agent37**

IntelliScope AI implements modular, environment-configured sponsor adapters in `backend/integrations/`, official MCP / Skill / SDK artifacts, shared execution context (`ExecutionContext`), correlation IDs (`execution_id`), per-step timeouts (`PIPELINE_STEP_TIMEOUT_SECONDS`), and structured inter-agent handoffs (`AgentHandoffRecord`).

| Platform | Track Role | Status | Runtime State | What Is Actually Implemented & Observed | Remaining Prerequisites for Live E2E |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BAND (`band.ai`)** | **Mandatory** | **LIVE TESTED** | `ready` (`agent_config.yaml`) | Official `band-sdk==6.0.1` `SimpleAdapter` runtime (`scripts/band_collector_agent.py`), WS `SUPERSEDE` reconnect + `HeartbeatWatchdog`, lifecycle hooks, `@peer` A2A delegation (`delegate=@<handle>`), and live REST checks (`get_agent_me` 200 OK `@baboiiibabu/intelliscope-collector`, room `c348c418-f3a6-467d-8601-c7453bec68e1`, 10 historical User→Agent exchanges observed). Live user prompt for 'neural networks' received and 4-agent pipeline execution `221041b0` delivered back to room verified. | Live room communication verified with running host collector; automated test available via `scripts/live_band_room_test.py`. |
| **Finch (`finchwork.net`)** | **Mandatory** | **IMPLEMENTED** | `ready` (local MCP) | Official MCP JSON-RPC 2.0 `stdio` server (`scripts/intelliscope_mcp_server.py`) supporting newline + `Content-Length` framing (`intelliscope_research`, `intelliscope_verify`, `intelliscope_pipeline`, `intelliscope_integrations_status`), `integrations/finch/mcp_servers.json`, and `integrations/finch/SKILL.md`. Protocol handshake & subprocess framing tested locally (`passed`). | Launch Finch Desktop GUI with `integrations/finch/mcp_servers.json` registered for a live desktop turn. |
| **Lyzr (`lyzr.ai`)** | **Mandatory** | **PARTIAL** | `unconfigured` (missing env vars) | Modular `LyzrAdapter` (`backend/integrations/lyzr_adapter.py`) for `POST /v3/inference/chat/` and `POST /v3/workflows/{flow_id}/execute` (`x-api-key`, `session_id=execution_id`, retries, redaction, schema validation) plus opt-in `PipelineRequest.delegate_to_lyzr` / `LYZR_ENABLE_PIPELINE_DELEGATION` pipeline handoff (`insight_analyst → lyzr_studio`). Tested with HTTPX mocks. | Supply `LYZR_API_KEY` and `LYZR_AGENT_ID` / `LYZR_WORKFLOW_ID` in `.env` and run live inference verification. |
| **AdaL (`adal.sylph.ai`)** | **Mandatory** | **PARTIAL** | `not_installed` | Official project AdaL Skill (`.atskills/intelliscope-research/SKILL.md` for `@skills:intelliscope-research`) plus `AdalAdapter` (`backend/integrations/adal_adapter.py`) supporting `adal -q <prompt> -o json --workspace ... --enabled-default-tools Read,Search` and `adal_agent_sdk` (`AdalAgentOptions`, `query()`), tested with mocks. | Install `adal` CLI (`curl -fsSL https://adal.sylph.ai/install.sh | bash`) or `adal-sdk`, authenticate, and set `ADAL_ENABLED=true`. |
| **Agent37 (`agent37.com`)** | **Optional** | **PARTIAL** | `unconfigured` (missing env vars) | Modular `Agent37Adapter` (`backend/integrations/agent37_adapter.py`) implementing `X-Agent37-Key` auth, `/v1/health` checks, and bounded `POST /v1/instances/{id}/exec` calls, tested with HTTPX mocks. | Supply `AGENT37_API_KEY` and `AGENT37_INSTANCE_ID` if deploying to an Agent37 cloud sandbox later. |

### Phase 5 Interoperability & Telemetry Endpoints
- `GET /integrations/status` — Returns honest status categories (`live_tested`, `implemented`, `partial`, `not_integrated`), `mandatory_for_track` flags, runtime states, boolean `credentials_present` flags (secrets never exposed), and recent delegation telemetry.
- `POST /integrations/check/{platform_id}` — Triggers a non-mutating health or runtime/MCP handshake probe for one platform adapter.
- `POST /integrations/delegate` — Validates and dispatches structured task delegation requests (`DelegationTaskRequest` → `DelegationTaskResult`) with timeout and retry guarantees.
- **Finch MCP Server (`stdio`)**: `.venv/bin/python scripts/intelliscope_mcp_server.py` (configured via `integrations/finch/mcp_servers.json`).
- **BAND Peer Delegation Command Example**: Mention `@IntelliScope Collector Research quantum computing delegate=@analyst-peer` in a BAND room to execute the 4-agent pipeline and hand off grounded `https://` provenance URLs via `@analyst-peer` with an `intelliscope.a2a.v1` JSON payload.

---

## Project Status

- **Phase 2.1: Data Collector Agent**: Complete (Wikipedia MediaWiki API, clean HTML, Pydantic validation)
- **Phase 2.2: Research Verification Agent**: Complete (structural checks, HTTPS, domain whitelist, quality score 0–100)
- **Phase 2.3: Insight Analyst Agent**: Complete (deterministic synthesis, theme clustering, evidence citations)
- **Phase 2.4: Dashboard Builder Agent**: Complete (safe dashboard JSON spec, KPIs, charts, URL safety)
- **Phase 2.5: Live End-to-End Pipeline Verification**: Complete (`scripts/live_pipeline_test.py`, test-results saved)
- **Phase 2.6: BAND Platform Integration**: Complete (`band-sdk==6.0.1`, `SimpleAdapter` pattern)
- **Phase 3: Unified Multi-Agent Research Pipeline**: Complete (`PipelineOrchestrator`, `POST /pipeline`, 4-agent orchestration, BAND integration)
- **Phase 3.1: BAND Message Sanitization & Quality Verification**: Complete (robust mention parsing, instruction stripping, relevance verification)
- **Phase 3.2: Evidence Quality & Research Source Enhancement**: Complete (extract retrieval, markup sanitization, transparent relevance, dynamic confidence, 201 backend tests)
- **Phase 3.3: Research Relevance & Output Integrity Fix**: Complete (clean BAND mention parsing, entity/list weak relevance classification, separate verification structural vs relevance counts, heuristic dashboard labels, 205 tests).
- **Phase 3.4: Dashboard Data Consistency & Research History Fix**: Complete:
  - Fixed theme propagation in `DashboardBuilderAgent`, `DashboardResponse` (`themes`, `key_themes`, `dashboard_id`, `metadata`), BAND `format_pipeline_reply()`, and React UI so actual analyst themes, names, descriptions, and evidence counts propagate end-to-end (honestly returning `[]` when no themes exist).
  - Added shared backend pipeline run history (`PipelineHistoryStore`, `GET /pipeline/history`, `GET /pipeline/latest`, `GET /pipeline/{pipeline_id}`) and synchronized React context state (`ResearchContext`, `pipelineState.js`).
  - Ensured latest successful research (including BAND-initiated queries) replaces stale UI state automatically without double-counting Overview KPIs, allows selecting and restoring any historical run's sources/verification/insights/dashboard, and prevents failed runs from overwriting the last successful research.
  - Preserved BAND and frontend consistency across provenance (`wikipedia_extract` vs `wikipedia_search_snippet`), HTTPS URLs, verification structural/relevance counts, analyst confidence rationales, and heuristic chart flags.
- **Phase 4: Complete React Frontend**: Complete:
  - Modern, responsive Dark Navy/Indigo AI research SaaS UI using React 18, Vite, Tailwind CSS, Lucide React, and Recharts.
  - Sidebar Navigation: Overview, New Research, Research Results, Verification, AI Insights, Analytics Dashboard, Agent Activity.
  - Reusable Axios API service with `http://127.0.0.1:8010` default, environment variable override (`VITE_API_BASE_URL`), and comprehensive error handling.
  - Live interaction with `POST /pipeline`, `GET /pipeline/history`, `GET /pipeline/{pipeline_id}`, and `GET /agents/status` (zero fabricated data or simulated progress).
  - Recharts integration supporting vertical bar charts, horizontal bar charts, and pie charts with heuristic labeling.
  - Session and local state preservation across sidebar navigation plus historical run switching.
  - 9 frontend automated tests (`npm test` in `frontend/`) and production build passing (`npm run build`).
- **Phase 4 / 4.5: Multi-Source Integration & Live Validation**: Complete:
  - Added modular `arXiv` (`backend/services/sources/arxiv_client.py`) and `Crossref` (`backend/services/sources/crossref_client.py`) source clients alongside `Wikipedia`, unified record normalization, source-aware verification (domains + DOI syntax/deduplication), multi-source analyst & dashboard charts, and BAND/React source selection.
  - Verified live HTTP integration across Wikipedia, arXiv, Crossref, and combined 4-agent pipeline via opt-in `scripts/live_multisource_test.py` (reports saved in `test-results/live-multisource/`).
- **Phase 5: Sponsor Integration & Agent Interoperability**: Complete within honest scope:
  - Added `ExecutionContext` (`execution_id`), `AgentHandoffRecord`, per-step pipeline timeouts, modular `backend/integrations/` adapters, `/integrations/status`, `/integrations/check/{platform_id}`, `/integrations/delegate`, BAND lifecycle/event/A2A delegation enhancements, Agent Activity UI telemetry, and opt-in `scripts/live_integrations_test.py`.
- **Phase 6: Deployment Readiness Audit & Operational Setup**: Complete:
  - Conducted technical readiness audit across architecture, port isolation, security, history persistence, background collector requirements, and sponsor interoperability.
  - Preserved backend port `8010` (strictly isolated from separate AID-DRAS service on port `8000`).
  - Added configurable CORS security (`CORS_ALLOWED_ORIGINS`) and history storage path (`HISTORY_STORAGE_PATH`) in settings.
  - Updated [`.env.example`](file:///home/jagapathi/Projects/intelliscope-ai/.env.example) with complete, safe deployment placeholders.
  - Created [docs/DEPLOYMENT_READINESS_REPORT.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/DEPLOYMENT_READINESS_REPORT.md) and [docs/DEPLOYMENT_GUIDE.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/DEPLOYMENT_GUIDE.md).
  - Verified 257 backend tests, 12 frontend unit tests, and production build.

---

## Running the Application

### 1. Start the FastAPI Backend (Port 8010)
```bash
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8010 --reload
```

### 2. Start the React Frontend Development Server
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

### 3. Build Frontend for Production
```bash
cd frontend
VITE_API_BASE_URL="" npm run build
```

### 4. Run Test Suites & Opt-In Live Validation
- **Backend (mocked unit & integration suite)**: `.venv/bin/pytest -v` (257 passed; live network checks excluded cleanly via `pytest.ini`)
- **Frontend**: `cd frontend && npm test` (12 passed) and `npm run build`
- **Opt-In Live Multi-Source Validation**: `.venv/bin/python scripts/live_multisource_test.py`
- **Opt-In Live Sponsor Integration Probe**: `.venv/bin/python scripts/live_integrations_test.py`
- **Opt-In Live BAND Room E2E Check**: `.venv/bin/python scripts/live_band_room_test.py`

### 5. Deployment Options
- **Free Render Cloud Deployment**: Refer to [docs/RENDER_DEPLOYMENT_GUIDE.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/RENDER_DEPLOYMENT_GUIDE.md) and [render.yaml](file:///home/jagapathi/Projects/intelliscope-ai/render.yaml) for deploying the FastAPI backend (Free Web Service) and React SPA (Free Static Site with SPA rewrite rules).
- **Persistent BAND Collector Setup**: Refer to [docs/BAND_REMOTE_BACKEND_SETUP.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/BAND_REMOTE_BACKEND_SETUP.md) for connecting the local Ubuntu BAND collector daemon to your remote Render backend.
- **Single Linux Server Deployment**: Refer to [docs/DEPLOYMENT_GUIDE.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/DEPLOYMENT_GUIDE.md) and [docs/DEPLOYMENT_READINESS_REPORT.md](file:///home/jagapathi/Projects/intelliscope-ai/docs/DEPLOYMENT_READINESS_REPORT.md) for systemd services, Nginx reverse proxy, and local hosting.

Production backend invocation:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8010 --workers 1
```
Production BAND collector daemon invocation (local or remote backend):
```bash
python scripts/band_collector_agent.py --backend-url http://127.0.0.1:8010
```

---

## Evidence Quality & Verification Boundaries

IntelliScope AI enforces transparent epistemic boundaries across all research agents:

| Dimension | Verification Scope | Methodological Boundary |
|:---|:---|:---|
| **Structural Integrity** | HTTPS protocol compliance, Wikipedia domain whitelist, ISO 8601 timestamps, deduplication. | Guaranteed by automated rule checks (`is_factually_verified = False`). |
| **Source Provenance** | Distinguishes `wikipedia_extract` (introductory page extract) from `wikipedia_search_snippet`. | Provenance recorded per item. |
| **Topical Relevance** | Transparent lexical matching classifies sources as `relevant` or `weakly_relevant` with human-readable reasons. | No arbitrary statistical percentages or probabilities are fabricated. |
| **Analyst Confidence** | Rated `high`, `medium`, or `low` based on extract length, relevance status, and verification warnings. | Structural compliance alone does not entitle an observation to high confidence. |
| **Factual Truth** | Encyclopedia summary extracts represent secondary overview literature. | Does not replace primary source fact-checking or peer-reviewed empirical verification. |
