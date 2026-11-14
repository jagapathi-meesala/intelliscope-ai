# IntelliScope AI — 3-Minute Hackathon Demonstration Script

**Track:** Research — Data & Build  
**Platform URL:** `https://intelliscope-frontend.onrender.com`  
**API Health Check:** `https://intelliscope-backend.onrender.com/health`  
**Total Target Duration:** 3 minutes (180 seconds)

---

## Demonstration Overview & Schedule

| Timestamp | Phase / Section | Screen / UI View | Core Demonstration Focus |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:30** | Problem & Solution | Overview (`/`) | Information overload, hallucination problem, 4-agent architecture |
| **0:30 – 1:10** | Live Multi-Source Research | New Research (`/research`) | Multi-source selection (Wikipedia, arXiv, Crossref), real-time orchestration |
| **1:10 – 1:45** | Research Results & Verification | Results (`/results`) & Verification (`/verification`) | Provenance (DOIs, authors, dates), structural validation, factual disclaimers |
| **1:45 – 2:25** | Deterministic Insights & Dashboard | AI Insights (`/insights`) & Analytics (`/dashboard`) | Thematic clustering, overlapping citations, declarative Recharts visuals |
| **2:25 – 3:00** | Sponsor Interoperability & Wrap-up | Agent Activity (`/activity`) & BAND Room | BAND agent communication, Finch MCP stdio server, honest status disclosure |

---

## Detailed Demo Sequence & Spoken Narration

### Section 1: The Problem & The Four-Agent Solution (0:00 – 0:30)
**Screen to Show:** Overview (`https://intelliscope-frontend.onrender.com`)

**Action:**
1. Open the IntelliScope AI Overview page.
2. Point out the connection indicator: `Backend Online (Render Free Web Service)`.
3. Point out the KPI cards and previous research history table showing persistent historical runs.

**Spoken Script:**
> *"Welcome to IntelliScope AI, an autonomous multi-agent research intelligence platform built for the Diwali Festiverse Hackathon under the Research: Data & Build track.*  
>  
> *Modern researchers and analysts face two critical problems: information overload from disparate academic silos, and AI hallucinations from generative models that fabricate sources. IntelliScope AI solves this with a deterministic four-agent pipeline: Data Collector, Research Verification, Insight Analyst, and Dashboard Builder. Every insight is strictly grounded in verifiable source metadata, and structural validity is never confused with factual truth."*

---

### Section 2: Launching Multi-Source Research (0:30 – 1:10)
**Screen to Show:** New Research (`/research`)

**Action:**
1. Navigate to **New Research** via the sidebar.
2. In the query box, enter:  
   `"Artificial Intelligence in Healthcare"`
3. Verify all three source providers are toggled active:
   - **Wikipedia** (MediaWiki API)
   - **arXiv** (Academic preprints)
   - **Crossref** (Scholarly publication DOIs)
4. Set the limit to `6` (or `9`).
5. Click **"Start Research Pipeline"**.
6. Observe the multi-agent progress steps executing sequentially:
   - Ingesting multi-source records -> Verifying integrity -> Synthesizing insights -> Constructing dashboard spec.

**Spoken Script:**
> *"Let's run a live research query: 'Artificial Intelligence in Healthcare', querying Wikipedia, arXiv, and Crossref simultaneously. When I click Start Research, the Data Collector Agent executes asynchronous HTTP requests across all three provider APIs. Notice that if one provider experiences latency or missing abstracts, our round-robin normalizer isolates the partial error and completes with the healthy providers—preventing total pipeline failure."*

---

### Section 3: Evidence Provenance & Structural Verification (1:10 – 1:45)
**Screen to Show:** Research Results (`/results`), then click into Verification (`/verification`)

**Action:**
1. Switch to **Research Results**:
   - Point out the header badges showing **Structurally Eligible Records**, **Direct Relevance**, and **Weak Relevance** counts.
   - Expand an arXiv card to show primary authors, publication date, and canonical HTTPS link.
   - Expand a Crossref card to show the validated DOI link (`https://doi.org/...`).
2. Navigate to **Verification**:
   - Highlight the **100/100 Quality Score**.
   - Show the green checkmarks: HTTPS protocol compliance, source-aware domain whitelist, ISO 8601 timestamps, and DOI syntax checks.
   - Emphasize the prominent **Factual Accuracy Disclaimer banner**:
     `is_factually_verified = false`.

**Spoken Script:**
> *"Here on the Research Results page, we see normalized records from all three providers, complete with authors, publication dates, and DOIs. Next, our Research Verification Agent evaluates structural integrity. It enforces HTTPS protocol compliance, verifies source domains against strict allowlists, and deduplicates DOIs and URLs.*  
>  
> *Crucially, we make a transparent epistemic distinction: structural verification confirms format and protocol integrity, but it does NOT verify empirical real-world facts. Our system explicitly flags `is_factually_verified = false` with an honest disclaimer banner."*

---

### Section 4: Deterministic Insights & Safe Dashboards (1:45 – 2:25)
**Screen to Show:** AI Insights (`/insights`), then switch to Analytics Dashboard (`/dashboard`)

**Action:**
1. Navigate to **AI Insights**:
   - Point out the **Thematic Clusters** with the subtitle: *"Evidence citations (sources may support multiple overlapping themes)"*.
   - Point out the **Evidence-Backed Observations**; show that direct relevant sources get medium/high confidence, while weak relevance sources are capped at low confidence.
   - Point out the transparent **Information Gaps** and **Methodology Limitations** cards.
2. Navigate to **Analytics Dashboard**:
   - Show the **"Structurally Eligible Sources"** KPI card.
   - Show the interactive **Recharts visualizations**: Source Evidence Eligibility pie chart, Research Theme Distribution bar chart, and Keyword Frequency chart.
   - Reiterate that the dashboard specification is pure declarative JSON with zero executable JavaScript injection.

**Spoken Script:**
> *"The Insight Analyst Agent performs deterministic lexical extraction and theme clustering on verified evidence—without relying on ungrounded generative LLM extrapolation. Notice our Thematic Clusters: an individual source can support multiple topics, so we transparently label these as overlapping citations.*  
>  
> *The Dashboard Builder Agent compiles these findings into a safe, declarative JSON specification. The React frontend renders KPI cards and Recharts visualizations directly from this spec. Notice that observations from weakly relevant sources are strictly capped to low confidence so users are never misled."*

---

### Section 5: Sponsor Interoperability & Conclusion (2:25 – 3:00)
**Screen to Show:** Agent Activity / Integrations (`/activity`) & BAND Room / Finch terminal

**Action:**
1. Navigate to **Agent Activity**:
   - Point out the Sponsor Integration status cards:
     - **BAND**: Implemented / Partially Live Verified (`ready`, REST authenticated, room discovered; live roundtrip available via running host daemon)
     - **Finch**: Implemented (`ready`, MCP stdio server with 4 registered tools)
     - **Lyzr**: Partial — Not Live-Configured (`unconfigured`, modular adapter ready for API key)
     - **AdaL**: Partial — Not Live-Configured (`not_installed`, skill definition ready for host CLI)
     - **Agent37**: Partial — Not Live-Configured (`unconfigured`, optional sandbox adapter)
2. Briefly show the BAND room screenshot or live chat room where `@DataCollector research Quantum computing` received the full intelligence brief.
3. Conclude with a strong closing statement.

**Spoken Script:**
> *"Finally, IntelliScope AI is built for interoperability. Under the Diwali Festiverse Research track, we integrated with the mandatory sponsors:*  
> *• BAND: Implemented with Phoenix WebSocket daemon, REST auth, and room discovery; live room roundtrip supported via our background host worker.*  
> *• Finch: Implemented as an official Model Context Protocol (MCP) server providing research and verification tools.*  
> *• Lyzr, AdaL, and Agent37: Modular adapters implemented with clean schemas, honestly disclosed as not live-configured pending external runtime keys or host CLI installation.*  
>  
> *IntelliScope AI combines multi-agent automation with rigorous provenance and honest epistemic boundaries. Thank you!"*

---

## Backup & Contingency Notes for Recording

- **Render Cold Start**: If the free backend service has been idle for 15+ minutes, trigger a request to `https://intelliscope-backend.onrender.com/health` 60 seconds before recording so the service is hot.
- **Offline / Backup Flow**: If external APIs (such as arXiv) experience public rate limits during recording, the UI will display previous runs from the persistent history table on the Overview page (`selectRun()`). Restoring any historical run seamlessly populates all four analysis views.
- **Microphone & Screen Resolution**: Record at 1920x1080 resolution, 100% browser zoom, with system dark mode enabled for optimal contrast.

