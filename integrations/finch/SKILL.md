---
name: intelliscope-research
description: Run multi-source research, structural verification, and executive insight synthesis via the IntelliScope AI MCP server (Wikipedia, arXiv, Crossref).
---

# IntelliScope AI Research Skill (Finch Desktop)

Use the connected `intelliscope-ai` MCP server tools (registered via `mcp_servers.json`) when asked to gather verified multi-source evidence or generate an analytics dashboard specification.

## Available MCP Tools

1. `intelliscope_pipeline`: Executes the complete 4-agent workflow (`Data Collector -> Research Verification -> Insight Analyst -> Dashboard Builder`) for a topic `query`, per-provider `limit` (1–10), and `sources` (`["wikipedia", "arxiv", "crossref"]`).
2. `intelliscope_research`: Queries Wikipedia, arXiv, and/or Crossref independently and returns normalized records with DOIs, authors, publication dates, and relevance classifications.
3. `intelliscope_verify`: Runs structural verification on candidate sources (HTTPS checks, allowed provider domains, DOI validation, batch deduplication).
4. `intelliscope_integrations_status`: Reports live sponsor interoperability readiness (`BAND`, `Lyzr`, `AdaL`, `Finch`, `Agent37`) without exposing secrets.

## Verification & Honesty Policy

- Never present `is_factually_verified: false` structural checks as factual proof.
- Preserve retrieved `https://` source URLs, DOIs, authors, and partial failure disclosures (`source_errors`).

