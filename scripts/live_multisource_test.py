"""
Live Multi-Source Validation Script for IntelliScope AI (Phase 4.5).

Explicitly opt-in validation runner (never executed during ordinary pytest runs).
Tests real HTTP retrieval against Wikipedia, arXiv, and Crossref both independently
and combined through the complete four-agent pipeline:
    Data Collector -> Research Verification -> Insight Analyst -> Dashboard Builder

Saves timestamped JSON and Markdown execution reports under:
    test-results/live-multisource/

Usage:
    .venv/bin/python scripts/live_multisource_test.py
    .venv/bin/python scripts/live_multisource_test.py --query "quantum computing" --limit 3 --delay 3.0
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

import httpx

# Ensure project root is importable when invoked as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.main import app


DEFAULT_QUERY = "quantum computing"
DEFAULT_LIMIT = 3
DEFAULT_POLITE_DELAY_SECONDS = 3.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 25.0
REPORT_SUBDIR = PROJECT_ROOT / "test-results" / "live-multisource"

OUTAGE_INDICATORS = (
    "timed out",
    "timeout",
    "rate limit",
    "429",
    "network error",
    "connecterror",
    "temporary failure in name resolution",
    "name or service not known",
    "connection refused",
    "service unavailable",
    "502",
    "503",
    "504",
)


def is_external_outage_error(status_code: int, message: str) -> bool:
    """Classify transport/rate-limit/DNS/upstream HTTP errors as external outages."""
    if status_code in (429, 502, 503, 504):
        return True
    lower = (message or "").lower()
    return any(ind in lower for ind in OUTAGE_INDICATORS)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_provider_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize real retrieved source records without fabricating missing metadata."""
    samples: List[Dict[str, Any]] = []
    urls_https_ok = True
    doi_present_count = 0
    authors_present_count = 0
    pub_date_present_count = 0

    for item in items:
        url = str(item.get("source_url") or "")
        if not url.startswith("https://"):
            urls_https_ok = False
        doi = item.get("doi")
        authors = item.get("authors") or []
        pub_date = item.get("publication_date")
        if doi:
            doi_present_count += 1
        if authors:
            authors_present_count += 1
        if pub_date:
            pub_date_present_count += 1

        if len(samples) < 5:
            samples.append(
                {
                    "title": item.get("title"),
                    "source_name": item.get("source_name"),
                    "source_type": item.get("source_type"),
                    "source_url": url,
                    "doi": doi,
                    "authors": authors[:5],
                    "publication_date": pub_date,
                    "relevance": item.get("relevance"),
                }
            )

    return {
        "count": len(items),
        "all_urls_https": urls_https_ok,
        "items_with_doi": doi_present_count,
        "items_with_authors": authors_present_count,
        "items_with_publication_date": pub_date_present_count,
        "sample_records": samples,
    }


def _validate_four_stage_payloads(
    *,
    query: str,
    expected_sources: List[str],
    research: Dict[str, Any],
    verification: Dict[str, Any],
    analysis: Dict[str, Any],
    dashboard: Dict[str, Any],
    require_all_sources_present: bool = True,
) -> List[str]:
    """
    Validate all four agent payloads for URL integrity, attribution,
    structural vs factual boundary, source distribution, theme propagation,
    and dashboard evidence grounding.

    Returns a list of assertion failure messages (empty when all checks pass).
    """
    errors: List[str] = []

    if research.get("query") != query:
        errors.append(f"Research query mismatch: expected '{query}', got '{research.get('query')}'")

    results = research.get("results") or []
    result_count = research.get("result_count", 0)
    if result_count != len(results):
        errors.append(f"Research result_count ({result_count}) != len(results) ({len(results)})")
    if result_count == 0:
        errors.append("Research returned 0 items from live upstream source(s).")
        return errors

    source_errors = research.get("source_errors") or {}
    source_breakdown = research.get("source_breakdown") or {}
    if require_all_sources_present and source_errors:
        errors.append(f"Unexpected source_errors in full multi-source run: {source_errors}")

    # Validate each source record URL, domain whitelist match, and attribution
    retrieved_urls = set()
    for idx, item in enumerate(results):
        src_name = item.get("source_name")
        src_url = str(item.get("source_url") or "")
        if src_name not in expected_sources:
            errors.append(f"Item {idx} unexpected source_name '{src_name}' not in {expected_sources}")
        if not src_url.startswith("https://"):
            errors.append(f"Item {idx} non-HTTPS source_url '{src_url}'")
        else:
            retrieved_urls.add(src_url)
            allowed = settings.SOURCE_ALLOWED_DOMAINS.get(src_name or "", [])
            host = httpx.URL(src_url).host or ""
            if allowed and not any(host == d or host.endswith("." + d) for d in allowed):
                errors.append(f"Item {idx} host '{host}' not in allowed domains for '{src_name}': {allowed}")

        if not (item.get("title") or "").strip():
            errors.append(f"Item {idx} has empty title")
        if not (item.get("snippet") or "").strip():
            errors.append(f"Item {idx} has empty snippet")
        if not item.get("retrieved_at"):
            errors.append(f"Item {idx} missing retrieved_at timestamp")

    if require_all_sources_present:
        for src in expected_sources:
            if source_breakdown.get(src, 0) < 1:
                errors.append(f"Expected >= 1 record from '{src}', breakdown was {source_breakdown}")

    # Crossref records returned via DOI URLs should carry DOI syntax
    for idx, item in enumerate(results):
        if item.get("source_name") == "crossref" and "doi.org/" in str(item.get("source_url") or ""):
            if not item.get("doi"):
                errors.append(f"Crossref item {idx} missing 'doi' field despite doi.org URL")

    # Verification checks: strictly structural, NEVER factual
    if verification.get("is_factually_verified") is not False:
        errors.append(
            f"Verification violated boundary: is_factually_verified={verification.get('is_factually_verified')}"
        )
    disclaimer = str(verification.get("factual_accuracy_disclaimer") or "").lower()
    if "structural integrity" not in disclaimer or "verified facts" not in disclaimer:
        errors.append("Verification missing explicit structural-vs-factual disclaimer")

    valid_cnt = verification.get("structurally_valid_count", 0)
    if valid_cnt < 1:
        errors.append(f"Verification yielded 0 structurally valid sources (errors in items)")

    v_items = verification.get("results") or []
    for v_item in v_items:
        checks = v_item.get("checks") or {}
        if v_item.get("doi") and checks.get("doi_valid") is not True:
            errors.append(
                f"Verification flagged live DOI as invalid on '{v_item.get('title')}': {v_item.get('doi')}"
            )

    # Insight Analyst checks
    eligible_cnt = analysis.get("eligible_sources_count", 0)
    if eligible_cnt != valid_cnt:
        errors.append(f"Analyst eligible_sources_count ({eligible_cnt}) != Verification valid ({valid_cnt})")

    analyst_dist = analysis.get("source_distribution") or {}
    if sum(analyst_dist.values()) != eligible_cnt:
        errors.append(
            f"Analyst source_distribution sum ({sum(analyst_dist.values())}) != eligible_sources_count ({eligible_cnt})"
        )

    observations = analysis.get("evidence_backed_observations") or []
    if len(observations) != eligible_cnt:
        errors.append(
            f"Analyst observation count ({len(observations)}) != eligible_sources_count ({eligible_cnt})"
        )
    for obs in observations:
        if obs.get("source_url") not in retrieved_urls:
            errors.append(f"Analyst observation URL not grounded in retrieved sources: {obs.get('source_url')}")
        if not obs.get("source_name"):
            errors.append(f"Analyst observation missing source_name attribution for '{obs.get('source_title')}'")

    # Dashboard Builder checks: themes propagation, source distribution, chart, evidence URLs
    a_themes = analysis.get("key_themes") or []
    d_themes = dashboard.get("themes") or []
    d_key_themes = dashboard.get("key_themes") or []
    if len(d_themes) != len(a_themes):
        errors.append(f"Dashboard themes count ({len(d_themes)}) != Analyst themes count ({len(a_themes)})")
    if len(d_key_themes) != len(a_themes):
        errors.append(f"Dashboard key_themes count ({len(d_key_themes)}) != Analyst themes count ({len(a_themes)})")

    a_theme_names = [t.get("theme") for t in a_themes]
    d_theme_names = [t.get("name") or t.get("theme") for t in d_themes]
    if a_theme_names != d_theme_names:
        errors.append(f"Theme name mismatch: analyst={a_theme_names} vs dashboard={d_theme_names}")

    kpis = {k.get("id"): k.get("value") for k in (dashboard.get("kpi_cards") or [])}
    if kpis.get("kpi-theme-count") != len(a_themes):
        errors.append(f"KPI kpi-theme-count ({kpis.get('kpi-theme-count')}) != {len(a_themes)}")
    if kpis.get("kpi-eligible-sources") != eligible_cnt:
        errors.append(f"KPI kpi-eligible-sources ({kpis.get('kpi-eligible-sources')}) != {eligible_cnt}")

    d_dist = dashboard.get("source_distribution") or {}
    if d_dist != analyst_dist:
        errors.append(f"Dashboard source_distribution ({d_dist}) != Analyst ({analyst_dist})")

    charts = {c.get("id"): c for c in (dashboard.get("charts") or [])}
    if eligible_cnt > 0 and "chart-source-distribution" not in charts:
        errors.append("Dashboard missing 'chart-source-distribution' chart specification")
    elif "chart-source-distribution" in charts:
        sc = charts["chart-source-distribution"]
        if sc.get("is_heuristic") is not False:
            errors.append("'chart-source-distribution' should have is_heuristic=False")

    d_obs = dashboard.get("observations") or []
    if len(d_obs) != len(observations):
        errors.append(f"Dashboard observations ({len(d_obs)}) != Analyst observations ({len(observations)})")
    for obs in d_obs:
        url = obs.get("source_url")
        if not isinstance(url, str) or not url.startswith("https://") or url not in retrieved_urls:
            errors.append(f"Dashboard observation invalid or ungrounded URL: {url}")

    return errors


async def _run_independent_source_scenario(
    api_client: httpx.AsyncClient,
    *,
    source: str,
    query: str,
    limit: int,
) -> Dict[str, Any]:
    """Run live 4-stage pipeline (/research -> /verify -> /analyze -> /dashboard) for one provider."""
    scenario_id = f"live_source_{source}"
    t0 = time.perf_counter()

    try:
        res_resp = await api_client.post(
            "/research",
            json={"query": query, "limit": limit, "sources": [source]},
        )
    except Exception as exc:
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "id": scenario_id,
            "name": f"Live Independent Source: {source}",
            "test_kind": "live_network",
            "sources": [source],
            "status": "external_outage" if is_external_outage_error(0, str(exc)) else "failed",
            "duration_ms": dur_ms,
            "error": str(exc),
        }

    if res_resp.status_code != 200:
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        detail = res_resp.text
        try:
            detail = res_resp.json().get("detail", res_resp.text)
        except Exception:
            pass
        is_outage = is_external_outage_error(res_resp.status_code, str(detail))
        return {
            "id": scenario_id,
            "name": f"Live Independent Source: {source}",
            "test_kind": "live_network",
            "sources": [source],
            "status": "external_outage" if is_outage else "failed",
            "http_status": res_resp.status_code,
            "duration_ms": dur_ms,
            "error": f"POST /research HTTP {res_resp.status_code}: {detail}",
        }

    research_data = res_resp.json()

    ver_resp = await api_client.post("/verify", json=research_data)
    if ver_resp.status_code != 200:
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "id": scenario_id,
            "name": f"Live Independent Source: {source}",
            "test_kind": "live_network",
            "sources": [source],
            "status": "failed",
            "duration_ms": dur_ms,
            "error": f"POST /verify HTTP {ver_resp.status_code}: {ver_resp.text}",
        }
    verification_data = ver_resp.json()

    ana_resp = await api_client.post(
        "/analyze",
        json={"research": research_data, "verification": verification_data},
    )
    if ana_resp.status_code != 200:
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "id": scenario_id,
            "name": f"Live Independent Source: {source}",
            "test_kind": "live_network",
            "sources": [source],
            "status": "failed",
            "duration_ms": dur_ms,
            "error": f"POST /analyze HTTP {ana_resp.status_code}: {ana_resp.text}",
        }
    analysis_data = ana_resp.json()

    dash_resp = await api_client.post("/dashboard", json=analysis_data)
    if dash_resp.status_code != 200:
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "id": scenario_id,
            "name": f"Live Independent Source: {source}",
            "test_kind": "live_network",
            "sources": [source],
            "status": "failed",
            "duration_ms": dur_ms,
            "error": f"POST /dashboard HTTP {dash_resp.status_code}: {dash_resp.text}",
        }
    dashboard_data = dash_resp.json()

    dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    validation_errors = _validate_four_stage_payloads(
        query=query,
        expected_sources=[source],
        research=research_data,
        verification=verification_data,
        analysis=analysis_data,
        dashboard=dashboard_data,
        require_all_sources_present=True,
    )

    return {
        "id": scenario_id,
        "name": f"Live Independent Source: {source}",
        "test_kind": "live_network",
        "sources": [source],
        "status": "passed" if not validation_errors else "failed",
        "duration_ms": dur_ms,
        "validation_errors": validation_errors,
        "retrieval": _format_provider_summary(research_data.get("results") or []),
        "source_breakdown": research_data.get("source_breakdown"),
        "source_errors": research_data.get("source_errors"),
        "verification": {
            "status": verification_data.get("status"),
            "quality_score": verification_data.get("quality_score"),
            "structurally_valid_count": verification_data.get("structurally_valid_count"),
            "excluded_count": verification_data.get("excluded_count"),
            "duplicate_dois_count": verification_data.get("duplicate_dois_count"),
            "is_factually_verified": verification_data.get("is_factually_verified"),
        },
        "analysis": {
            "eligible_sources_count": analysis_data.get("eligible_sources_count"),
            "theme_count": len(analysis_data.get("key_themes") or []),
            "themes": [t.get("theme") for t in (analysis_data.get("key_themes") or [])],
            "source_distribution": analysis_data.get("source_distribution"),
        },
        "dashboard": {
            "dashboard_id": dashboard_data.get("dashboard_id"),
            "themes_count": len(dashboard_data.get("themes") or []),
            "chart_ids": [c.get("id") for c in (dashboard_data.get("charts") or [])],
            "observations_count": len(dashboard_data.get("observations") or []),
            "source_distribution": dashboard_data.get("source_distribution"),
        },
    }


async def _run_combined_pipeline_scenario(
    api_client: httpx.AsyncClient,
    *,
    query: str,
    limit: int,
) -> Dict[str, Any]:
    """Run unified POST /pipeline with combined sources: wikipedia, arxiv, crossref."""
    scenario_id = "live_combined_multisource_pipeline"
    sources = ["wikipedia", "arxiv", "crossref"]
    t0 = time.perf_counter()

    try:
        resp = await api_client.post(
            "/pipeline",
            json={"query": query, "limit": limit, "sources": sources},
        )
    except Exception as exc:
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "id": scenario_id,
            "name": "Live Combined Multi-Source Pipeline (wikipedia + arxiv + crossref)",
            "test_kind": "live_network",
            "sources": sources,
            "status": "external_outage" if is_external_outage_error(0, str(exc)) else "failed",
            "duration_ms": dur_ms,
            "error": str(exc),
        }

    dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    if resp.status_code != 200:
        return {
            "id": scenario_id,
            "name": "Live Combined Multi-Source Pipeline (wikipedia + arxiv + crossref)",
            "test_kind": "live_network",
            "sources": sources,
            "status": "external_outage" if is_external_outage_error(resp.status_code, resp.text) else "failed",
            "http_status": resp.status_code,
            "duration_ms": dur_ms,
            "error": f"POST /pipeline HTTP {resp.status_code}: {resp.text}",
        }

    pipe = resp.json()
    if pipe.get("status") == "failed":
        dc_err = ((pipe.get("agent_statuses") or {}).get("data_collector") or {}).get("error", "")
        is_outage = is_external_outage_error(0, dc_err)
        return {
            "id": scenario_id,
            "name": "Live Combined Multi-Source Pipeline (wikipedia + arxiv + crossref)",
            "test_kind": "live_network",
            "sources": sources,
            "status": "external_outage" if is_outage else "failed",
            "duration_ms": dur_ms,
            "pipeline_status": pipe.get("status"),
            "agent_statuses": pipe.get("agent_statuses"),
            "error": dc_err or pipe.get("summary"),
        }

    research_data = pipe.get("research") or {}
    verification_data = pipe.get("verification") or {}
    analysis_data = pipe.get("analysis") or {}
    dashboard_data = pipe.get("dashboard") or {}
    source_errors = research_data.get("source_errors") or {}

    # Check if an upstream partial outage occurred during combined live fetch
    partial_outage = bool(source_errors) and all(
        is_external_outage_error(0, err_msg) for err_msg in source_errors.values()
    )

    validation_errors = _validate_four_stage_payloads(
        query=query,
        expected_sources=sources,
        research=research_data,
        verification=verification_data,
        analysis=analysis_data,
        dashboard=dashboard_data,
        require_all_sources_present=not partial_outage,
    )

    # Also ensure round-robin representation if all 3 returned items
    items = research_data.get("results") or []
    breakdown = research_data.get("source_breakdown") or {}
    if all(breakdown.get(s, 0) > 0 for s in sources) and len(items) >= 3:
        first_three = [it.get("source_name") for it in items[:3]]
        if first_three != ["wikipedia", "arxiv", "crossref"]:
            validation_errors.append(f"Expected round-robin lead ['wikipedia', 'arxiv', 'crossref'], got {first_three}")

    if partial_outage and not validation_errors:
        status = "external_outage"
    elif not validation_errors:
        status = "passed"
    else:
        status = "failed"

    return {
        "id": scenario_id,
        "name": "Live Combined Multi-Source Pipeline (wikipedia + arxiv + crossref)",
        "test_kind": "live_network",
        "sources": sources,
        "status": status,
        "duration_ms": dur_ms,
        "pipeline_id": pipe.get("pipeline_id"),
        "pipeline_status": pipe.get("status"),
        "validation_errors": validation_errors,
        "agent_statuses": pipe.get("agent_statuses"),
        "retrieval": _format_provider_summary(items),
        "source_breakdown": breakdown,
        "source_errors": source_errors,
        "verification": {
            "status": verification_data.get("status"),
            "quality_score": verification_data.get("quality_score"),
            "structurally_valid_count": verification_data.get("structurally_valid_count"),
            "excluded_count": verification_data.get("excluded_count"),
            "duplicate_dois_count": verification_data.get("duplicate_dois_count"),
            "is_factually_verified": verification_data.get("is_factually_verified"),
        },
        "analysis": {
            "eligible_sources_count": analysis_data.get("eligible_sources_count"),
            "theme_count": len(analysis_data.get("key_themes") or []),
            "themes": [t.get("theme") for t in (analysis_data.get("key_themes") or [])],
            "source_distribution": analysis_data.get("source_distribution"),
            "information_gaps": analysis_data.get("information_gaps"),
        },
        "dashboard": {
            "dashboard_id": dashboard_data.get("dashboard_id"),
            "themes_count": len(dashboard_data.get("themes") or []),
            "chart_ids": [c.get("id") for c in (dashboard_data.get("charts") or [])],
            "observations_count": len(dashboard_data.get("observations") or []),
            "source_distribution": dashboard_data.get("source_distribution"),
            "sources_represented": (dashboard_data.get("metadata") or {}).get("sources_represented"),
        },
    }


async def _run_partial_failure_honesty_scenario(
    *,
    query: str,
    limit: int,
    timeout_seconds: float,
    skip_partial_probe: bool,
) -> Dict[str, Any]:
    """
    Validate honest partial failure reporting when one provider times out while
    real live Wikipedia and Crossref continue to return real data.

    Clearly labeled as 'hybrid_controlled_partial_failure' (not pure live_network).
    """
    scenario_id = "controlled_partial_failure_honesty"
    name = "Controlled Partial Failure Honesty (live wikipedia+crossref + simulated arxiv timeout)"
    sources = ["wikipedia", "arxiv", "crossref"]

    if skip_partial_probe:
        return {
            "id": scenario_id,
            "name": name,
            "test_kind": "hybrid_controlled_partial_failure",
            "sources": sources,
            "status": "skipped",
            "reason": "Skipped by --skip-partial-probe flag.",
        }

    t0 = time.perf_counter()

    async def _simulated_arxiv_timeout(*args, **kwargs):
        from backend.services.sources.base import DataCollectorTimeoutError

        raise DataCollectorTimeoutError("Controlled live validation timeout probe for arXiv")

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8010",
            timeout=timeout_seconds,
        ) as inproc_client:
            with patch("backend.agents.data_agent.search_arxiv", side_effect=_simulated_arxiv_timeout):
                resp = await inproc_client.post(
                    "/pipeline",
                    json={"query": query, "limit": limit, "sources": sources},
                )
    except Exception as exc:
        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "id": scenario_id,
            "name": name,
            "test_kind": "hybrid_controlled_partial_failure",
            "sources": sources,
            "status": "external_outage" if is_external_outage_error(0, str(exc)) else "failed",
            "duration_ms": dur_ms,
            "error": str(exc),
        }

    dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    if resp.status_code != 200:
        return {
            "id": scenario_id,
            "name": name,
            "test_kind": "hybrid_controlled_partial_failure",
            "sources": sources,
            "status": "failed",
            "http_status": resp.status_code,
            "duration_ms": dur_ms,
            "error": f"POST /pipeline HTTP {resp.status_code}: {resp.text}",
        }

    pipe = resp.json()
    research_data = pipe.get("research") or {}
    verification_data = pipe.get("verification") or {}
    analysis_data = pipe.get("analysis") or {}
    dashboard_data = pipe.get("dashboard") or {}

    if pipe.get("status") == "failed":
        dc_err = ((pipe.get("agent_statuses") or {}).get("data_collector") or {}).get("error", "")
        return {
            "id": scenario_id,
            "name": name,
            "test_kind": "hybrid_controlled_partial_failure",
            "sources": sources,
            "status": "external_outage" if is_external_outage_error(0, dc_err) else "failed",
            "duration_ms": dur_ms,
            "error": dc_err or pipe.get("summary"),
        }

    errors = _validate_four_stage_payloads(
        query=query,
        expected_sources=sources,
        research=research_data,
        verification=verification_data,
        analysis=analysis_data,
        dashboard=dashboard_data,
        require_all_sources_present=False,
    )

    src_errors = research_data.get("source_errors") or {}
    breakdown = research_data.get("source_breakdown") or {}
    gaps = analysis_data.get("information_gaps") or []

    if "arxiv" not in src_errors:
        errors.append("Partial failure probe did not record 'arxiv' in research.source_errors")
    if breakdown.get("arxiv") != 0:
        errors.append(f"Expected source_breakdown['arxiv'] == 0 on failure, got {breakdown.get('arxiv')}")
    if breakdown.get("wikipedia", 0) < 1 and breakdown.get("crossref", 0) < 1:
        errors.append(f"Expected healthy live sources to populate results, breakdown={breakdown}")
    if not any("arxiv" in g.lower() for g in gaps):
        errors.append("Insight Analyst did not disclose failed 'arxiv' source in information_gaps")

    # If live crossref/wikipedia also had an external outage alongside simulated arxiv, note honestly
    live_outage = any(k in src_errors and is_external_outage_error(0, src_errors[k]) for k in ("wikipedia", "crossref"))

    status = "external_outage" if live_outage and errors else ("passed" if not errors else "failed")

    return {
        "id": scenario_id,
        "name": name,
        "test_kind": "hybrid_controlled_partial_failure",
        "sources": sources,
        "status": status,
        "duration_ms": dur_ms,
        "validation_errors": errors,
        "source_breakdown": breakdown,
        "source_errors": src_errors,
        "information_gaps": gaps,
        "collector_details": ((pipe.get("agent_statuses") or {}).get("data_collector") or {}).get("details"),
    }


def _render_markdown_report(report: Dict[str, Any]) -> str:
    """Render concise, factual Markdown validation report with explicit test categories."""
    summary = report["summary"]
    lines = [
        "# IntelliScope AI — Phase 4.5 Live Multi-Source Validation Report",
        "",
        f"- **Generated (UTC):** `{report['generated_at']}`",
        f"- **Query:** `{report['query']}` (limit per source: `{report['limit']}`, polite delay: `{report['polite_delay_seconds']}s`)",
        f"- **Execution Target:** `{report['execution_target']}`",
        f"- **Overall Outcome:** `{report['overall_status'].upper()}`",
        "",
        "## Category Breakdown (Mocked vs Live vs External Outage)",
        "",
        "| Category | Count | Notes |",
        "| --- | ---: | --- |",
        f"| Live Network Passed | {summary['live_network_passed']} | Unmocked HTTP calls to Wikipedia, arXiv, Crossref |",
        f"| Live Network Failed | {summary['live_network_failed']} | Assertion/code failures on live data |",
        f"| Live External Outages | {summary['external_outages']} | Timeouts, HTTP 429/502/503/504, DNS/network blocks |",
        f"| Hybrid Partial-Failure Probe Passed | {summary['hybrid_passed']} | Live healthy sources + controlled timeout on 1 provider |",
        f"| Skipped | {summary['skipped']} | Explicitly skipped scenarios |",
        "",
        "> **Verification Boundary Notice:** Structural verification checks URLs, provider domains, DOI syntax, timestamps, and duplicates (`is_factually_verified: false`). Structural validity never implies empirical or factual verification.",
        "",
        "## Scenario Results",
        "",
    ]

    for sc in report["scenarios"]:
        lines.append(f"### {sc['name']}")
        lines.append(f"- **ID:** `{sc['id']}`")
        lines.append(f"- **Test Kind:** `{sc['test_kind']}`")
        lines.append(f"- **Status:** `{sc['status'].upper()}`")
        if "duration_ms" in sc:
            lines.append(f"- **Duration:** `{sc['duration_ms']} ms`")
        if sc.get("error"):
            lines.append(f"- **Error:** `{sc['error']}`")
        if sc.get("reason"):
            lines.append(f"- **Reason:** {sc['reason']}")
        if sc.get("source_breakdown") is not None:
            lines.append(f"- **Source Breakdown:** `{json.dumps(sc['source_breakdown'])}`")
        if sc.get("source_errors"):
            lines.append(f"- **Source Errors:** `{json.dumps(sc['source_errors'])}`")
        if sc.get("verification"):
            v = sc["verification"]
            lines.append(
                f"- **Verification (Structural Only):** score=`{v.get('quality_score')}`, "
                f"valid=`{v.get('structurally_valid_count')}`, excluded=`{v.get('excluded_count')}`, "
                f"is_factually_verified=`{v.get('is_factually_verified')}`"
            )
        if sc.get("analysis"):
            a = sc["analysis"]
            lines.append(
                f"- **Analysis:** eligible=`{a.get('eligible_sources_count')}`, "
                f"themes=`{a.get('theme_count')}`, source_distribution=`{json.dumps(a.get('source_distribution'))}`"
            )
        if sc.get("dashboard"):
            d = sc["dashboard"]
            lines.append(
                f"- **Dashboard:** themes=`{d.get('themes_count')}`, "
                f"charts=`{d.get('chart_ids')}`, observations=`{d.get('observations_count')}`"
            )
        if sc.get("validation_errors"):
            lines.append("- **Validation Failures:**")
            for ve in sc["validation_errors"]:
                lines.append(f"  - {ve}")
        samples = (sc.get("retrieval") or {}).get("sample_records") or []
        if samples:
            lines.append("- **Sample Live Records:**")
            for rec in samples:
                lines.append(
                    f"  - [{rec.get('title')}]({rec.get('source_url')}) "
                    f"(source=`{rec.get('source_name')}`, type=`{rec.get('source_type')}`, "
                    f"date=`{rec.get('publication_date')}`, doi=`{rec.get('doi')}`, "
                    f"authors=`{len(rec.get('authors') or [])}`)"
                )
        lines.append("")

    lines.extend(
        [
            "## Reproduction Commands",
            "",
            "```bash",
            "# Ordinary mocked test suites (no live network requests):",
            ".venv/bin/pytest -v",
            "cd frontend && npm test && npm run build",
            "",
            "# Opt-in live multi-source validation:",
            ".venv/bin/python scripts/live_multisource_test.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


async def run_live_multisource_validation(
    *,
    query: str = DEFAULT_QUERY,
    limit: int = DEFAULT_LIMIT,
    polite_delay: float = DEFAULT_POLITE_DELAY_SECONDS,
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    base_url: Optional[str] = None,
    skip_partial_probe: bool = False,
) -> Tuple[Dict[str, Any], Path, Path]:
    """Execute live independent & combined multi-source validations and save reports."""
    os.makedirs(REPORT_SUBDIR, exist_ok=True)
    generated_at = _utc_now()
    ts_slug = generated_at.strftime("%Y%m%dT%H%M%SZ")

    # Configure backend HTTP client (either explicit running server or in-process ASGI app).
    # In both modes, Data Collector outbound API calls execute REAL HTTP requests over the network.
    execution_target = "in-process FastAPI ASGI (live external HTTP to Wikipedia/arXiv/Crossref)"
    use_external_server = False
    if base_url:
        try:
            async with httpx.AsyncClient(timeout=3.0) as probe:
                h = await probe.get(f"{base_url.rstrip('/')}/health")
                if h.status_code == 200:
                    use_external_server = True
                    execution_target = f"live HTTP server {base_url.rstrip('/')} (live external HTTP)"
        except Exception:
            use_external_server = False

    client_kwargs: Dict[str, Any] = {"timeout": timeout_seconds}
    if use_external_server and base_url:
        client_kwargs["base_url"] = base_url.rstrip("/")
    else:
        client_kwargs["transport"] = httpx.ASGITransport(app=app)
        client_kwargs["base_url"] = "http://127.0.0.1:8010"

    scenarios: List[Dict[str, Any]] = []

    # Clear shared history before validation run so summary reflects this session cleanly
    from backend.services.history_store import pipeline_history_store

    pipeline_history_store.clear()

    async with httpx.AsyncClient(**client_kwargs) as api_client:
        # Step 1-3: Independent live source validations with polite rate spacing
        for idx, source in enumerate(("wikipedia", "arxiv", "crossref")):
            if idx > 0 and polite_delay > 0:
                await asyncio.sleep(polite_delay)
            print(f"[Live {idx + 1}/4] Validating independent live source '{source}' (query='{query}', limit={limit})...")
            sc = await _run_independent_source_scenario(
                api_client,
                source=source,
                query=query,
                limit=limit,
            )
            scenarios.append(sc)
            print(f"  -> {sc['status'].upper()} ({sc.get('duration_ms', 0)} ms)")

        # Step 4: Combined multi-source pipeline validation
        if polite_delay > 0:
            await asyncio.sleep(polite_delay)
        print(f"[Live 4/4] Validating combined pipeline [wikipedia, arxiv, crossref] (query='{query}', limit={limit})...")
        combined_sc = await _run_combined_pipeline_scenario(
            api_client,
            query=query,
            limit=limit,
        )
        scenarios.append(combined_sc)
        print(f"  -> {combined_sc['status'].upper()} ({combined_sc.get('duration_ms', 0)} ms)")

    # Step 5: Honest partial failure reporting verification
    if polite_delay > 0 and not skip_partial_probe:
        await asyncio.sleep(polite_delay)
    print("[Hybrid Probe] Validating honest partial failure disclosure (live wikipedia+crossref + timeout on arxiv)...")
    partial_sc = await _run_partial_failure_honesty_scenario(
        query=query,
        limit=limit,
        timeout_seconds=timeout_seconds,
        skip_partial_probe=skip_partial_probe,
    )
    scenarios.append(partial_sc)
    print(f"  -> {partial_sc['status'].upper()} ({partial_sc.get('duration_ms', 0)} ms)")

    live_scenarios = [s for s in scenarios if s.get("test_kind") == "live_network"]
    hybrid_scenarios = [s for s in scenarios if s.get("test_kind") == "hybrid_controlled_partial_failure"]

    summary = {
        "total_scenarios": len(scenarios),
        "passed": sum(1 for s in scenarios if s["status"] == "passed"),
        "failed": sum(1 for s in scenarios if s["status"] == "failed"),
        "external_outages": sum(1 for s in scenarios if s["status"] == "external_outage"),
        "skipped": sum(1 for s in scenarios if s["status"] == "skipped"),
        "live_network_passed": sum(1 for s in live_scenarios if s["status"] == "passed"),
        "live_network_failed": sum(1 for s in live_scenarios if s["status"] == "failed"),
        "live_network_outages": sum(1 for s in live_scenarios if s["status"] == "external_outage"),
        "hybrid_passed": sum(1 for s in hybrid_scenarios if s["status"] == "passed"),
        "hybrid_failed": sum(1 for s in hybrid_scenarios if s["status"] == "failed"),
        "note_on_unit_tests": (
            "This report covers live network validation only. Mocked unit/integration tests "
            "live in tests/ and run separately via '.venv/bin/pytest -v'."
        ),
    }

    if summary["failed"] > 0:
        overall_status = "failed"
    elif summary["live_network_outages"] == len(live_scenarios):
        overall_status = "external_outage"
    elif summary["external_outages"] > 0:
        overall_status = "partial_outage"
    else:
        overall_status = "passed"

    report: Dict[str, Any] = {
        "phase": "4.5",
        "title": "IntelliScope AI Live Multi-Source Validation",
        "generated_at": generated_at.isoformat(),
        "query": query,
        "limit": limit,
        "polite_delay_seconds": polite_delay,
        "timeout_seconds": timeout_seconds,
        "execution_target": execution_target,
        "overall_status": overall_status,
        "endpoints_under_test": {
            "wikipedia": settings.WIKIPEDIA_API_URL,
            "arxiv": settings.ARXIV_API_URL,
            "crossref": settings.CROSSREF_API_URL,
        },
        "summary": summary,
        "scenarios": scenarios,
    }

    json_path = REPORT_SUBDIR / f"live_multisource_report_{ts_slug}.json"
    md_path = REPORT_SUBDIR / f"live_multisource_report_{ts_slug}.md"

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2, ensure_ascii=False)
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write(_render_markdown_report(report))

    pipeline_history_store.clear()
    return report, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Opt-in Phase 4.5 live multi-source validation for IntelliScope AI."
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Research topic query (default: quantum computing)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Max results per source (1-10)")
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_POLITE_DELAY_SECONDS,
        help="Polite delay in seconds between live HTTP requests (default: 3.0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_HTTP_TIMEOUT_SECONDS,
        help="HTTP request timeout in seconds (default: 25.0)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Optional running IntelliScope FastAPI URL (e.g. http://127.0.0.1:8010); defaults to ASGI in-process",
    )
    parser.add_argument(
        "--skip-partial-probe",
        action="store_true",
        help="Skip the hybrid controlled partial-failure probe",
    )
    args = parser.parse_args()

    # Keep settings request timeout aligned with CLI timeout if higher
    report, json_path, md_path = asyncio.run(
        run_live_multisource_validation(
            query=args.query,
            limit=max(1, min(10, args.limit)),
            polite_delay=max(0.0, args.delay),
            timeout_seconds=max(1.0, args.timeout),
            base_url=args.base_url,
            skip_partial_probe=args.skip_partial_probe,
        )
    )

    print("\n" + "=" * 72)
    print(f"LIVE MULTI-SOURCE VALIDATION COMPLETE — OVERALL STATUS: {report['overall_status'].upper()}")
    print(f"Summary: {json.dumps(report['summary'])}")
    print(f"JSON Report: {json_path}")
    print(f"MD Report:   {md_path}")
    print("=" * 72)

    if report["overall_status"] == "failed":
        return 1
    if report["overall_status"] == "external_outage":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

