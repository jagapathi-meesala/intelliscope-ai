"""
Live End-to-End Pipeline Verification Script for IntelliScope AI.

Executes the four-agent workflow using live HTTP requests against the FastAPI backend
on port 8010 and the live Wikipedia MediaWiki API:
1. Data Collector Agent (POST /research)
2. Research Verification Agent (POST /verify)
3. Insight Analyst Agent (POST /analyze)
4. Dashboard Builder Agent (POST /dashboard)

Saves live responses to test-results/:
- test-results/research.json
- test-results/verification.json
- test-results/analysis.json
- test-results/dashboard.json
"""

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx

BASE_URL = os.environ.get("INTELLISCOPE_BASE_URL", "http://127.0.0.1:8010")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test-results")


def ensure_results_dir() -> None:
    """Ensure the test-results output directory exists."""
    os.makedirs(RESULTS_DIR, exist_ok=True)


def is_backend_running(client: httpx.Client) -> bool:
    """Check if the backend is actively listening on port 8010."""
    try:
        resp = client.get(f"{BASE_URL}/health", timeout=2.0)
        return resp.status_code == 200 and resp.json().get("status") == "healthy"
    except Exception:
        return False


def start_backend_server() -> subprocess.Popen:
    """Launch the FastAPI backend server on port 8010 if not already running."""
    venv_python = sys.executable
    cmd = [
        venv_python,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8010",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


def wait_for_backend(client: httpx.Client, timeout: float = 10.0) -> bool:
    """Poll backend /health endpoint until operational or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if is_backend_running(client):
            return True
        time.sleep(0.5)
    return False


def save_json(filename: str, data: Dict[str, Any]) -> str:
    """Save payload dictionary as formatted JSON in test-results directory."""
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def run_live_pipeline() -> None:
    """Execute live end-to-end multi-agent pipeline and edge case tests."""
    ensure_results_dir()
    server_proc = None

    client = httpx.Client(timeout=30.0)

    try:
        # Step 1: Ensure backend is running
        print("=" * 70)
        print("INTELLISCOPE AI: PHASE 2.5 LIVE END-TO-END PIPELINE VERIFICATION")
        print("=" * 70)

        if not is_backend_running(client):
            print(f"Backend not detected at {BASE_URL}. Starting uvicorn on port 8010...")
            server_proc = start_backend_server()
            if not wait_for_backend(client, timeout=12.0):
                stderr = server_proc.stderr.read() if server_proc.stderr else ""
                raise RuntimeError(f"Failed to start backend on port 8010. Server stderr:\n{stderr}")
            print(f"Backend successfully started on port 8010 (PID: {server_proc.pid})")
        else:
            print(f"Backend is already running and operational at {BASE_URL}")

        # Verify fleet status
        status_resp = client.get(f"{BASE_URL}/agents/status")
        assert status_resp.status_code == 200, f"Failed GET /agents/status: {status_resp.text}"
        status_data = status_resp.json()
        agents = status_data.get("agents", {})
        print(f"Agent Fleet Status: {len(agents)} agents registered")
        for key, agent in agents.items():
            print(f"  - {agent['name']}: {agent['status'].upper()} (operational: {agent['operational']})")
            assert agent["operational"] is True, f"Agent {key} is not marked operational!"

        # ----------------------------------------------------------------------
        # PIPELINE STEP 1: Data Collector Agent (POST /research)
        # ----------------------------------------------------------------------
        query = "Artificial intelligence"
        print(f"\n[Pipeline 1/4] Invoking Data Collector Agent: POST /research (query='{query}', limit=3)...")
        research_resp = client.post(
            f"{BASE_URL}/research",
            json={"query": query, "limit": 3},
        )
        assert research_resp.status_code == 200, f"POST /research failed ({research_resp.status_code}): {research_resp.text}"
        research_data = research_resp.json()

        assert research_data["agent"] == "Data Collector Agent"
        assert research_data["query"] == query
        assert research_data["result_count"] > 0, "No results returned from live Wikipedia search"
        assert len(research_data["results"]) == research_data["result_count"]

        # Validate that all sources are live HTTPS Wikipedia links
        for item in research_data["results"]:
            assert item["source_url"].startswith("https://en.wikipedia.org/wiki/"), f"Invalid source URL: {item['source_url']}"
            assert len(item["title"]) > 0, "Empty title in research result"
            assert len(item["snippet"]) > 0, "Empty snippet in research result"
            assert "retrieved_at" in item, "Missing retrieved_at in item"

        research_file = save_json("research.json", research_data)
        print(f"  -> SUCCESS: Retrieved {research_data['result_count']} live items from MediaWiki API")
        print(f"  -> Saved: {research_file}")

        # ----------------------------------------------------------------------
        # PIPELINE STEP 2: Research Verification Agent (POST /verify)
        # ----------------------------------------------------------------------
        print(f"\n[Pipeline 2/4] Invoking Research Verification Agent: POST /verify...")
        verify_resp = client.post(
            f"{BASE_URL}/verify",
            json=research_data,
        )
        assert verify_resp.status_code == 200, f"POST /verify failed ({verify_resp.status_code}): {verify_resp.text}"
        verification_data = verify_resp.json()

        assert verification_data["agent"] == "Research Verification Agent"
        assert verification_data["query"] == query
        assert verification_data["total_results"] == research_data["result_count"]
        assert verification_data["valid_results_count"] > 0
        assert verification_data["quality_score"] >= 80.0, f"Unexpected low quality score: {verification_data['quality_score']}"
        assert verification_data["is_factually_verified"] is False, "Agent claimed factual verification erroneously!"
        assert "factual claims" in verification_data["factual_accuracy_disclaimer"].lower()

        verify_file = save_json("verification.json", verification_data)
        print(f"  -> SUCCESS: Quality Score: {verification_data['quality_score']}/100, Status: {verification_data['status']}")
        print(f"  -> Valid Sources: {verification_data['valid_results_count']}, Invalid: {verification_data['invalid_results_count']}")
        print(f"  -> Saved: {verify_file}")

        # ----------------------------------------------------------------------
        # PIPELINE STEP 3: Insight Analyst Agent (POST /analyze)
        # ----------------------------------------------------------------------
        print(f"\n[Pipeline 3/4] Invoking Insight Analyst Agent: POST /analyze...")
        analyze_resp = client.post(
            f"{BASE_URL}/analyze",
            json={"research": research_data, "verification": verification_data},
        )
        assert analyze_resp.status_code == 200, f"POST /analyze failed ({analyze_resp.status_code}): {analyze_resp.text}"
        analysis_data = analyze_resp.json()

        assert analysis_data["agent"] == "Insight Analyst Agent"
        assert analysis_data["topic"] == query
        assert analysis_data["total_sources_evaluated"] == research_data["result_count"]
        assert analysis_data["eligible_sources_count"] == verification_data["valid_results_count"]
        assert len(analysis_data["executive_summary"]) > 20
        assert len(analysis_data["key_themes"]) > 0
        assert len(analysis_data["important_keywords"]) > 0
        assert len(analysis_data["evidence_backed_observations"]) == analysis_data["eligible_sources_count"]

        # Ensure all observations have HTTPS source citations matching eligible sources
        for obs in analysis_data["evidence_backed_observations"]:
            assert obs["source_url"].startswith("https://en.wikipedia.org/wiki/"), f"Invalid observation citation URL: {obs['source_url']}"
            assert len(obs["statement"]) > 10, "Empty observation statement"

        analysis_file = save_json("analysis.json", analysis_data)
        print(f"  -> SUCCESS: Synthesized {len(analysis_data['evidence_backed_observations'])} observations across {len(analysis_data['key_themes'])} themes")
        print(f"  -> Extracted Keywords: {', '.join(analysis_data['important_keywords'][:5])}")
        print(f"  -> Saved: {analysis_file}")

        # ----------------------------------------------------------------------
        # PIPELINE STEP 4: Dashboard Builder Agent (POST /dashboard)
        # ----------------------------------------------------------------------
        print(f"\n[Pipeline 4/4] Invoking Dashboard Builder Agent: POST /dashboard...")
        dashboard_resp = client.post(
            f"{BASE_URL}/dashboard",
            json=analysis_data,
        )
        assert dashboard_resp.status_code == 200, f"POST /dashboard failed ({dashboard_resp.status_code}): {dashboard_resp.text}"
        dashboard_data = dashboard_resp.json()

        assert dashboard_data["agent"] == "Dashboard Builder Agent"
        assert query in dashboard_data["title"]
        assert dashboard_data["topic"] == query
        assert len(dashboard_data["kpi_cards"]) == 4

        # Validate KPI card values match actual pipeline values
        kpis = {k["id"]: k for k in dashboard_data["kpi_cards"]}
        assert kpis["kpi-total-sources"]["value"] == analysis_data["total_sources_evaluated"]
        assert kpis["kpi-eligible-sources"]["value"] == analysis_data["eligible_sources_count"]
        assert kpis["kpi-excluded-sources"]["value"] == analysis_data["excluded_sources_count"]
        assert kpis["kpi-theme-count"]["value"] == len(analysis_data["key_themes"])

        # Validate chart specifications
        assert len(dashboard_data["charts"]) >= 2
        for chart in dashboard_data["charts"]:
            assert chart["chart_type"] in ["bar", "pie", "horizontal_bar"]
            assert len(chart["data"]) > 0
            for pt in chart["data"]:
                assert pt["value"] >= 0.0, f"Negative value in chart point: {pt}"

        # Validate observations in dashboard
        assert len(dashboard_data["observations"]) == len(analysis_data["evidence_backed_observations"])
        for obs in dashboard_data["observations"]:
            assert obs["source_url"].startswith("https://")

        dashboard_file = save_json("dashboard.json", dashboard_data)
        print(f"  -> SUCCESS: Generated dashboard specification '{dashboard_data['title']}'")
        print(f"  -> KPI Cards: {len(dashboard_data['kpi_cards'])}, Charts: {len(dashboard_data['charts'])}, Observations: {len(dashboard_data['observations'])}")
        print(f"  -> Saved: {dashboard_file}")

        # ----------------------------------------------------------------------
        # EDGE CASE 1: Empty Research Results
        # ----------------------------------------------------------------------
        empty_query = "nonexistentquery_xyz9876543210_empty"
        print(f"\n[Edge Case 1/5] Testing empty research query ('{empty_query}')...")
        empty_res = client.post(f"{BASE_URL}/research", json={"query": empty_query, "limit": 3})
        assert empty_res.status_code == 200
        empty_data = empty_res.json()
        assert empty_data["result_count"] == 0
        assert empty_data["results"] == []

        empty_ver = client.post(f"{BASE_URL}/verify", json=empty_data)
        assert empty_ver.status_code == 200
        assert empty_ver.json()["total_results"] == 0
        assert empty_ver.json()["quality_score"] == 0.0

        empty_ana = client.post(f"{BASE_URL}/analyze", json={"research": empty_data, "verification": empty_ver.json()})
        assert empty_ana.status_code == 200
        assert empty_ana.json()["eligible_sources_count"] == 0
        assert empty_ana.json()["evidence_backed_observations"] == []
        assert "no eligible" in empty_ana.json()["executive_summary"].lower()

        empty_dash = client.post(f"{BASE_URL}/dashboard", json=empty_ana.json())
        assert empty_dash.status_code == 200
        dash_kpis = {k["id"]: k["value"] for k in empty_dash.json()["kpi_cards"]}
        assert dash_kpis["kpi-eligible-sources"] == 0
        print("  -> SUCCESS: Empty research handled gracefully across all four agents with zero crashes.")

        # ----------------------------------------------------------------------
        # EDGE CASE 2: Invalid Intermediate Response (Query Mismatch)
        # ----------------------------------------------------------------------
        print(f"\n[Edge Case 2/5] Testing mismatched research vs verification report...")
        mismatched_res = client.post(
            f"{BASE_URL}/analyze",
            json={
                "research": {"query": "Artificial intelligence", "results": []},
                "verification": {"query": "Cybersecurity", "total_results": 0, "results": []},
            },
        )
        assert mismatched_res.status_code == 400
        assert "does not match" in mismatched_res.json()["detail"].lower()
        print(f"  -> SUCCESS: Mismatched report rejected with HTTP 400: '{mismatched_res.json()['detail']}'")

        # ----------------------------------------------------------------------
        # EDGE CASE 3: Tampered Verification Detection
        # ----------------------------------------------------------------------
        print(f"\n[Edge Case 3/5] Testing tampered verification detection in /analyze...")
        tampered_ver = {
            "query": "Artificial intelligence",
            "total_results": 1,
            "results": [
                {
                    "index": 0,
                    "title": "Artificial intelligence",
                    "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                    "status": "valid",  # Claimed valid!
                    "checks": {
                        "title_valid": True,
                        "snippet_valid": True,
                        "https_valid": False,  # Failed check!
                        "domain_allowed": True,
                    },
                    "errors": [],
                }
            ],
        }
        tampered_res = client.post(
            f"{BASE_URL}/analyze",
            json={
                "research": {
                    "query": "Artificial intelligence",
                    "results": [
                        {
                            "title": "Artificial intelligence",
                            "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                        }
                    ],
                },
                "verification": tampered_ver,
            },
        )
        assert tampered_res.status_code == 400
        assert "inconsistent" in tampered_res.json()["detail"].lower()
        print(f"  -> SUCCESS: Tampered verification rejected with HTTP 400: '{tampered_res.json()['detail']}'")

        # ----------------------------------------------------------------------
        # EDGE CASE 4: Dashboard Validation Failure (Unsafe URL Injection)
        # ----------------------------------------------------------------------
        print(f"\n[Edge Case 4/5] Testing dashboard rejection of unsafe observation citation URL...")
        unsafe_analysis = dict(analysis_data)
        unsafe_analysis["evidence_backed_observations"] = [
            {
                "statement": "Malicious payload injection attempt.",
                "source_title": "Exploit",
                "source_url": "javascript:alert(document.cookie)",
                "confidence": "high",
            }
        ]
        unsafe_resp = client.post(f"{BASE_URL}/dashboard", json=unsafe_analysis)
        assert unsafe_resp.status_code == 400
        assert "unsafe source url" in unsafe_resp.json()["detail"].lower()
        print(f"  -> SUCCESS: Unsafe URL rejected with HTTP 400: '{unsafe_resp.json()['detail']}'")

        # ----------------------------------------------------------------------
        # EDGE CASE 5: External API Timeout Handling (HTTP 504 Gateway Timeout)
        # ----------------------------------------------------------------------
        print(f"\n[Edge Case 5/5] Testing external upstream API timeout handling (HTTP 504)...")
        from unittest.mock import patch, AsyncMock
        from fastapi.testclient import TestClient
        from backend.main import app

        inproc_client = TestClient(app)
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_upstream_get:
            mock_upstream_get.side_effect = httpx.ReadTimeout("Simulated Wikipedia connection read timeout")
            timeout_res = inproc_client.post("/research", json={"query": "Quantum Computing", "limit": 3})
            assert timeout_res.status_code == 504, f"Expected 504, got {timeout_res.status_code}: {timeout_res.text}"
            assert "timed out" in timeout_res.json()["detail"].lower()
            print(f"  -> SUCCESS: Upstream timeout correctly handled and mapped to HTTP 504: '{timeout_res.json()['detail']}'")

        print("\n" + "=" * 70)
        print("ALL LIVE PIPELINE CHECKS AND EDGE CASE TESTS PASSED PERFECTLY!")
        print("=" * 70)

    finally:
        client.close()
        if server_proc is not None:
            print(f"Stopping temporary backend server (PID: {server_proc.pid})...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            print("Backend server stopped.")


if __name__ == "__main__":
    run_live_pipeline()
