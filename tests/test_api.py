"""
Integration tests for IntelliScope AI FastAPI endpoints.
Tests endpoints using FastAPI TestClient with mocked external HTTP calls.
"""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# Sample MediaWiki API response for testing
MOCK_WIKIPEDIA_SEARCH_RESPONSE = {
    "batchcomplete": "",
    "continue": {"sroffset": 2, "continue": "-||"},
    "query": {
        "searchinfo": {"totalhits": 450},
        "search": [
            {
                "ns": 0,
                "title": "Artificial intelligence",
                "pageid": 1164,
                "size": 142000,
                "wordcount": 14500,
                "snippet": "<b>Artificial intelligence</b> (AI) is intelligence demonstrated by machines.",
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "ns": 0,
                "title": "Machine learning",
                "pageid": 233488,
                "size": 89000,
                "wordcount": 9200,
                "snippet": "Machine learning is a field of <span class=\"searchmatch\">study</span> &amp; research.",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        ],
    },
}

MOCK_EMPTY_SEARCH_RESPONSE = {
    "batchcomplete": "",
    "query": {
        "searchinfo": {"totalhits": 0},
        "search": [],
    },
}


def test_home_endpoint():
    """Verify GET / returns project metadata and status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "IntelliScope AI"
    assert data["status"] == "running"
    assert "message" in data


def test_health_endpoint():
    """Verify GET /health returns operational status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["backend"] == "operational"


def test_cors_headers_for_render_frontend():
    """Verify CORS headers correctly allow deployed Render frontend origin."""
    response = client.get(
        "/health",
        headers={"Origin": "https://intelliscope-frontend.onrender.com"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://intelliscope-frontend.onrender.com"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_agents_status_endpoint():
    """
    Verify GET /agents/status accurately reflects agent statuses:
    - Data Collector, Research Verification, and Insight Analyst Agents are operational.
    - Dashboard Builder remains planned and not operational.
    """
    response = client.get("/agents/status")
    assert response.status_code == 200
    data = response.json()
    agents = data.get("agents", {})

    # Data Collector Agent must be operational
    assert "data_collector" in agents
    dc = agents["data_collector"]
    assert dc["status"] == "operational"
    assert dc["operational"] is True
    assert "wikipedia_search" in dc["capabilities"]
    assert len(dc["capabilities"]) > 0
    assert dc["version"] == "1.0.0"

    # Research Verification Agent must be operational
    assert "research_verification" in agents
    va = agents["research_verification"]
    assert va["status"] == "operational"
    assert va["operational"] is True
    assert "structural_schema_validation" in va["capabilities"]
    assert len(va["capabilities"]) > 0
    assert va["version"] == "1.0.0"

    # Insight Analyst Agent must be operational
    assert "insight_analyst" in agents
    ia = agents["insight_analyst"]
    assert ia["status"] == "operational"
    assert ia["operational"] is True
    assert "deterministic_text_analysis" in ia["capabilities"]
    assert len(ia["capabilities"]) > 0
    assert ia["version"] == "1.0.0"

    # Dashboard Builder Agent must be operational
    assert "dashboard_builder" in agents
    db = agents["dashboard_builder"]
    assert db["status"] == "operational"
    assert db["operational"] is True
    assert "dashboard_specification_generation" in db["capabilities"]
    assert len(db["capabilities"]) > 0
    assert db["version"] == "1.0.0"


def test_research_success():
    """Verify POST /research successfully collects and formats search results."""
    mock_response = httpx.Response(
        status_code=200,
        json=MOCK_WIKIPEDIA_SEARCH_RESPONSE,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        response = client.post(
            "/research",
            json={"query": "Artificial intelligence", "limit": 2}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["query"] == "Artificial intelligence"
        assert data["agent"] == "Data Collector Agent"
        assert data["result_count"] == 2
        assert data["total_results"] == 2
        assert "retrieved_at" in data
        assert len(data["results"]) == 2

        first_item = data["results"][0]
        assert first_item["title"] == "Artificial intelligence"
        assert "<b>" not in first_item["snippet"]  # HTML tags stripped
        assert "Artificial intelligence" in first_item["snippet"]
        assert "https://en.wikipedia.org/wiki/Artificial_intelligence" in first_item["source_url"]
        assert first_item["source"] == first_item["source_url"]
        assert "retrieved_at" in first_item

        second_item = data["results"][1]
        assert second_item["title"] == "Machine learning"
        assert "&amp;" not in second_item["snippet"]  # Entities unescaped
        assert "& research" in second_item["snippet"]


def test_research_empty_results():
    """Verify POST /research safely handles queries with zero results."""
    mock_response = httpx.Response(
        status_code=200,
        json=MOCK_EMPTY_SEARCH_RESPONSE,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        response = client.post(
            "/research",
            json={"query": "NonexistentRandomQueryXYZ999", "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "NonexistentRandomQueryXYZ999"
        assert data["result_count"] == 0
        assert data["total_results"] == 0
        assert data["results"] == []


@pytest.mark.parametrize("invalid_payload", [
    {"query": "", "limit": 5},                         # Empty query
    {"query": "   ", "limit": 5},                      # Pure whitespace
    {"query": "a" * 301, "limit": 5},                  # Exceeds 300 chars
    {"query": "valid query", "limit": 0},              # Limit < 1
    {"query": "valid query", "limit": 11},             # Limit > 10
    {"limit": 5},                                      # Missing query
])
def test_research_invalid_input(invalid_payload):
    """Verify POST /research rejects invalid input with 422 Unprocessable Entity."""
    response = client.post("/research", json=invalid_payload)
    assert response.status_code == 422


def test_research_upstream_timeout():
    """Verify POST /research returns 504 when upstream request times out."""
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ReadTimeout("Connection read timed out")

        response = client.post(
            "/research",
            json={"query": "Quantum Computing", "limit": 3}
        )

        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()


def test_research_upstream_http_error():
    """Verify POST /research returns 502 when upstream server returns an HTTP error."""
    mock_response = httpx.Response(
        status_code=503,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        response = client.post(
            "/research",
            json={"query": "Quantum Computing", "limit": 3}
        )

        assert response.status_code == 502
        assert "upstream research provider" in response.json()["detail"].lower()


def test_research_upstream_network_error():
    """Verify POST /research returns 502 when network connection to upstream fails."""
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        response = client.post(
            "/research",
            json={"query": "Quantum Computing", "limit": 3}
        )

        assert response.status_code == 502
        assert "upstream research provider" in response.json()["detail"].lower()


def test_research_upstream_invalid_json():
    """Verify POST /research returns 502 when upstream returns unparseable content."""
    mock_response = httpx.Response(
        status_code=200,
        content=b"<!DOCTYPE html><html><body>Error</body></html>",
        headers={"Content-Type": "text/html"},
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        response = client.post(
            "/research",
            json={"query": "Quantum Computing", "limit": 3}
        )

        assert response.status_code == 502


# ==============================================================================
# POST /verify Endpoint Tests
# ==============================================================================

def test_verify_success_valid_results():
    """Verify POST /verify successfully validates a well-formed research payload."""
    payload = {
        "agent": "Data Collector Agent",
        "agent_name": "Data Collector Agent",
        "query": "Artificial Intelligence",
        "result_count": 2,
        "total_results": 2,
        "retrieved_at": "2026-03-01T12:00:00Z",
        "results": [
            {
                "title": "Artificial intelligence",
                "snippet": "Artificial intelligence (AI) is the intelligence of machines or software.",
                "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "source": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Machine learning",
                "snippet": "Machine learning is a field of inquiry devoted to understanding systems.",
                "source_url": "https://en.wikipedia.org/wiki/Machine_learning",
                "source": "https://en.wikipedia.org/wiki/Machine_learning",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["agent"] == "Research Verification Agent"
    assert data["query"] == "Artificial Intelligence"
    assert data["total_results"] == 2
    assert data["valid_results_count"] == 2
    assert data["invalid_results_count"] == 0
    assert data["quality_score"] == 100.0
    assert data["status"] == "passed"
    assert data["is_factually_verified"] is False
    assert "factual claims" in data["factual_accuracy_disclaimer"].lower()

    # Verify summary
    summary = data["summary"]
    assert summary["error_count"] == 0
    assert summary["warning_count"] == 0
    assert summary["duplicate_urls_count"] == 0
    assert summary["duplicate_titles_count"] == 0

    # Verify per-item reports
    results = data["results"]
    assert len(results) == 2
    for item in results:
        assert item["status"] == "valid"
        assert item["item_score"] == 100.0
        assert item["checks"]["title_valid"] is True
        assert item["checks"]["snippet_valid"] is True
        assert item["checks"]["https_valid"] is True
        assert item["checks"]["domain_allowed"] is True
        assert item["checks"]["timestamp_valid"] is True
        assert item["checks"]["is_duplicate_url"] is False
        assert item["checks"]["is_duplicate_title"] is False


def test_verify_empty_results():
    """Verify POST /verify handles empty results list safely."""
    payload = {
        "query": "Empty Results Query",
        "results": [],
    }

    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_results"] == 0
    assert data["quality_score"] == 0.0
    assert data["status"] == "failed"
    assert data["is_factually_verified"] is False
    assert data["results"] == []


def test_verify_empty_input():
    """Verify POST /verify handles completely empty JSON payload gracefully."""
    response = client.post("/verify", json={})
    assert response.status_code == 200
    data = response.json()

    assert data["total_results"] == 0
    assert data["quality_score"] == 0.0
    assert data["status"] == "failed"


def test_verify_invalid_urls():
    """Verify POST /verify detects HTTP (insecure) and disallowed domains."""
    payload = {
        "query": "URL Protocol Test",
        "results": [
            {
                "title": "Insecure Article",
                "snippet": "This article uses insecure HTTP protocol instead of HTTPS.",
                "source_url": "http://en.wikipedia.org/wiki/Insecure",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Disallowed Domain Article",
                "snippet": "This article points to an untrusted external third-party domain.",
                "source_url": "https://untrusted-domain.com/wiki/Disallowed",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_results"] == 2
    assert data["invalid_results_count"] == 2
    assert data["status"] == "failed"

    item0 = data["results"][0]
    assert item0["checks"]["https_valid"] is False
    assert item0["checks"]["domain_allowed"] is True
    assert any("insecure protocol" in err.lower() for err in item0["errors"])

    item1 = data["results"][1]
    assert item1["checks"]["https_valid"] is True
    assert item1["checks"]["domain_allowed"] is False
    assert any("allowed domains" in err.lower() for err in item1["errors"])


def test_verify_missing_fields():
    """Verify POST /verify flags items missing required title, snippet, or URL."""
    payload = {
        "query": "Missing Fields Test",
        "results": [
            {
                # Missing title
                "snippet": "A snippet without any article title provided.",
                "source_url": "https://en.wikipedia.org/wiki/Test1",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Missing Snippet Article",
                # Missing snippet
                "source_url": "https://en.wikipedia.org/wiki/Test2",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Missing URL Article",
                "snippet": "A snippet that lacks any source URL link reference.",
                # Missing source_url
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["total_results"] == 3
    assert data["invalid_results_count"] == 3

    assert data["results"][0]["checks"]["title_valid"] is False
    assert data["results"][1]["checks"]["snippet_valid"] is False
    assert data["results"][2]["checks"]["https_valid"] is False


def test_verify_duplicate_detection():
    """Verify POST /verify detects duplicate source URLs and duplicate titles."""
    payload = {
        "query": "Deduplication Test",
        "results": [
            {
                "title": "Duplicate Article",
                "snippet": "First occurrence of this article snippet.",
                "source_url": "https://en.wikipedia.org/wiki/Duplicate_Article",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Duplicate Article",
                "snippet": "Second occurrence of the exact same title and URL.",
                "source_url": "https://en.wikipedia.org/wiki/Duplicate_Article",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["summary"]["duplicate_urls_count"] == 1
    assert data["summary"]["duplicate_titles_count"] == 1

    first_item = data["results"][0]
    assert first_item["checks"]["is_duplicate_url"] is False
    assert first_item["checks"]["is_duplicate_title"] is False

    second_item = data["results"][1]
    assert second_item["checks"]["is_duplicate_url"] is True
    assert second_item["checks"]["is_duplicate_title"] is True


def test_verify_malformed_timestamps():
    """Verify POST /verify detects invalid ISO 8601 timestamps."""
    payload = {
        "query": "Malformed Timestamp Test",
        "results": [
            {
                "title": "Bad Timestamp Article",
                "snippet": "This article has an unparseable timestamp string.",
                "source_url": "https://en.wikipedia.org/wiki/Test",
                "retrieved_at": "invalid-date-string-12345",
            }
        ],
    }

    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["results"][0]["checks"]["timestamp_valid"] is False
    assert any("iso 8601" in err.lower() for err in data["results"][0]["errors"])


def test_verify_invalid_request_shape():
    """Verify POST /verify rejects non-list results or excessive query length with 422."""
    # results is not a list
    resp1 = client.post("/verify", json={"query": "Test", "results": "not-a-list"})
    assert resp1.status_code == 422

    # query exceeds 300 characters
    resp2 = client.post("/verify", json={"query": "a" * 301, "results": []})
    assert resp2.status_code == 422


# ==============================================================================
# POST /analyze Endpoint Tests
# ==============================================================================

def test_analyze_success_valid_input():
    """Verify POST /analyze produces structured intelligence from valid evidence."""
    research_payload = {
        "agent": "Data Collector Agent",
        "query": "Artificial intelligence",
        "result_count": 2,
        "total_results": 2,
        "retrieved_at": "2026-03-01T12:00:00Z",
        "results": [
            {
                "title": "Artificial intelligence",
                "snippet": "Artificial intelligence is a discipline devoted to creating software and machines that model human intelligence.",
                "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "source": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Machine learning",
                "snippet": "Machine learning is an algorithmic technology that enables computational systems to learn from data.",
                "source_url": "https://en.wikipedia.org/wiki/Machine_learning",
                "source": "https://en.wikipedia.org/wiki/Machine_learning",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    # Corresponding consistent verification report
    verification_payload = {
        "agent": "Research Verification Agent",
        "query": "Artificial intelligence",
        "verified_at": "2026-03-01T12:05:00Z",
        "total_results": 2,
        "valid_results_count": 2,
        "invalid_results_count": 0,
        "quality_score": 100.0,
        "status": "passed",
        "verification_type": "structural_and_source_integrity",
        "is_factually_verified": False,
        "factual_accuracy_disclaimer": "Structural verification only.",
        "summary": {
            "total_checks": 14,
            "passed_checks": 14,
            "failed_checks": 0,
            "warning_count": 0,
            "error_count": 0,
            "duplicate_urls_count": 0,
            "duplicate_titles_count": 0,
        },
        "results": [
            {
                "index": 0,
                "title": "Artificial intelligence",
                "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "status": "valid",
                "item_score": 100.0,
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": True,
                    "domain_allowed": True,
                    "timestamp_valid": True,
                    "is_duplicate_url": False,
                    "is_duplicate_title": False,
                },
                "errors": [],
                "warnings": [],
            },
            {
                "index": 1,
                "title": "Machine learning",
                "source_url": "https://en.wikipedia.org/wiki/Machine_learning",
                "status": "valid",
                "item_score": 100.0,
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": True,
                    "domain_allowed": True,
                    "timestamp_valid": True,
                    "is_duplicate_url": False,
                    "is_duplicate_title": False,
                },
                "errors": [],
                "warnings": [],
            },
        ],
    }

    response = client.post("/analyze", json={
        "research": research_payload,
        "verification": verification_payload,
    })

    assert response.status_code == 200
    data = response.json()

    assert data["agent"] == "Insight Analyst Agent"
    assert data["topic"] == "Artificial intelligence"
    assert data["total_sources_evaluated"] == 2
    assert data["eligible_sources_count"] == 2
    assert data["excluded_sources_count"] == 0
    assert len(data["executive_summary"]) > 20
    assert len(data["key_themes"]) > 0
    assert len(data["important_keywords"]) > 0
    assert len(data["evidence_backed_observations"]) == 2
    assert len(data["information_gaps"]) > 0
    assert len(data["recommendations"]) > 0
    assert len(data["limitations"]) > 0

    # Every observation must have supporting source URL and source title
    for obs in data["evidence_backed_observations"]:
        assert obs["source_url"].startswith("https://en.wikipedia.org")
        assert len(obs["statement"]) > 10
        assert obs["source_title"] in ["Artificial intelligence", "Machine learning"]


def test_analyze_empty_research():
    """Verify POST /analyze handles empty research and verification safely."""
    payload = {
        "research": {
            "query": "Quantum Computing",
            "results": [],
        },
        "verification": {
            "query": "Quantum Computing",
            "total_results": 0,
            "results": [],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["topic"] == "Quantum Computing"
    assert data["total_sources_evaluated"] == 0
    assert data["eligible_sources_count"] == 0
    assert data["evidence_backed_observations"] == []
    assert "no eligible" in data["executive_summary"].lower()


def test_analyze_all_invalid_evidence():
    """Verify POST /analyze excludes all items when verification checks fail."""
    research_payload = {
        "query": "Untrusted Query",
        "results": [
            {
                "title": "Bad Protocol",
                "snippet": "Insecure HTTP source.",
                "source_url": "http://en.wikipedia.org/wiki/Bad1",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Bad Domain",
                "snippet": "Disallowed domain source.",
                "source_url": "https://malicious-domain.com/wiki/Bad2",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    verification_payload = {
        "query": "Untrusted Query",
        "total_results": 2,
        "results": [
            {
                "index": 0,
                "title": "Bad Protocol",
                "source_url": "http://en.wikipedia.org/wiki/Bad1",
                "status": "invalid",
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": False,
                    "domain_allowed": True,
                    "timestamp_valid": True,
                    "is_duplicate_url": False,
                    "is_duplicate_title": False,
                },
                "errors": ["Insecure protocol"],
            },
            {
                "index": 1,
                "title": "Bad Domain",
                "source_url": "https://malicious-domain.com/wiki/Bad2",
                "status": "invalid",
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": True,
                    "domain_allowed": False,
                    "timestamp_valid": True,
                    "is_duplicate_url": False,
                    "is_duplicate_title": False,
                },
                "errors": ["Disallowed domain"],
            },
        ],
    }

    response = client.post("/analyze", json={
        "research": research_payload,
        "verification": verification_payload,
    })

    assert response.status_code == 200
    data = response.json()

    assert data["eligible_sources_count"] == 0
    assert data["excluded_sources_count"] == 2
    assert data["evidence_backed_observations"] == []
    assert "no eligible" in data["executive_summary"].lower()


def test_analyze_duplicate_evidence():
    """Verify POST /analyze filters out duplicate records from evidence."""
    research_payload = {
        "query": "Deduplication Query",
        "results": [
            {
                "title": "Primary Record",
                "snippet": "First unique record for analysis.",
                "source_url": "https://en.wikipedia.org/wiki/Unique1",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Primary Record",
                "snippet": "Duplicate record snippet.",
                "source_url": "https://en.wikipedia.org/wiki/Unique1",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    verification_payload = {
        "query": "Deduplication Query",
        "total_results": 2,
        "results": [
            {
                "index": 0,
                "title": "Primary Record",
                "source_url": "https://en.wikipedia.org/wiki/Unique1",
                "status": "valid",
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": True,
                    "domain_allowed": True,
                    "timestamp_valid": True,
                    "is_duplicate_url": False,
                    "is_duplicate_title": False,
                },
                "errors": [],
            },
            {
                "index": 1,
                "title": "Primary Record",
                "source_url": "https://en.wikipedia.org/wiki/Unique1",
                "status": "warning",
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": True,
                    "domain_allowed": True,
                    "timestamp_valid": True,
                    "is_duplicate_url": True,
                    "is_duplicate_title": True,
                },
                "errors": [],
                "warnings": ["Duplicate URL", "Duplicate title"],
            },
        ],
    }

    response = client.post("/analyze", json={
        "research": research_payload,
        "verification": verification_payload,
    })

    assert response.status_code == 200
    data = response.json()

    assert data["eligible_sources_count"] == 1
    assert data["excluded_sources_count"] == 1
    assert len(data["evidence_backed_observations"]) == 1


def test_analyze_mismatched_query():
    """Verify POST /analyze returns 400 when research query does not match verification query."""
    payload = {
        "research": {"query": "Machine Learning", "results": []},
        "verification": {"query": "Cybersecurity", "total_results": 0, "results": []},
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"].lower()


def test_analyze_mismatched_counts():
    """Verify POST /analyze returns 400 when result counts differ."""
    payload = {
        "research": {
            "query": "Quantum",
            "results": [
                {
                    "title": "Q1",
                    "snippet": "Snippet 1",
                    "source_url": "https://en.wikipedia.org/wiki/Q1",
                    "retrieved_at": "2026-03-01T12:00:00Z",
                }
            ],
        },
        "verification": {
            "query": "Quantum",
            "total_results": 0,
            "results": [],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 400
    assert "count mismatch" in response.json()["detail"].lower()


def test_analyze_mismatched_urls():
    """Verify POST /analyze returns 400 when URLs at corresponding indexes diverge."""
    payload = {
        "research": {
            "query": "Divergent URLs",
            "results": [
                {
                    "title": "Article A",
                    "snippet": "Snippet A",
                    "source_url": "https://en.wikipedia.org/wiki/Article_A",
                    "retrieved_at": "2026-03-01T12:00:00Z",
                }
            ],
        },
        "verification": {
            "query": "Divergent URLs",
            "total_results": 1,
            "results": [
                {
                    "index": 0,
                    "title": "Article A",
                    "source_url": "https://en.wikipedia.org/wiki/Article_B_DIFFERENT",
                    "status": "valid",
                    "checks": {
                        "title_valid": True,
                        "snippet_valid": True,
                        "https_valid": True,
                        "domain_allowed": True,
                        "timestamp_valid": True,
                        "is_duplicate_url": False,
                        "is_duplicate_title": False,
                    },
                    "errors": [],
                }
            ],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()


def test_analyze_tampered_verification():
    """Verify POST /analyze catches a forged 'valid' status when checks actually failed."""
    payload = {
        "research": {
            "query": "Tampering Test",
            "results": [
                {
                    "title": "Insecure Article",
                    "snippet": "Insecure source.",
                    "source_url": "http://en.wikipedia.org/wiki/Insecure",
                    "retrieved_at": "2026-03-01T12:00:00Z",
                }
            ],
        },
        "verification": {
            "query": "Tampering Test",
            "total_results": 1,
            "results": [
                {
                    "index": 0,
                    "title": "Insecure Article",
                    "source_url": "http://en.wikipedia.org/wiki/Insecure",
                    # User maliciously set status to valid despite https_valid=False
                    "status": "valid",
                    "checks": {
                        "title_valid": True,
                        "snippet_valid": True,
                        "https_valid": False,
                        "domain_allowed": True,
                        "timestamp_valid": True,
                        "is_duplicate_url": False,
                        "is_duplicate_title": False,
                    },
                    "errors": [],
                }
            ],
        },
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 400
    assert "inconsistent" in response.json()["detail"].lower()


def test_analyze_invalid_payload_shape():
    """Verify POST /analyze returns 422 on missing sub-payloads or malformed types."""
    # Missing verification
    resp1 = client.post("/analyze", json={"research": {"query": "Test", "results": []}})
    assert resp1.status_code == 422

    # Research is not a dictionary
    resp2 = client.post("/analyze", json={"research": "not-a-dict", "verification": {}})
    assert resp2.status_code == 422


def test_full_pipeline_collector_to_verifier_to_analyst():
    """Verify complete multi-agent pipeline: Data Collector -> Verifier -> Analyst."""
    mock_response = httpx.Response(
        status_code=200,
        json=MOCK_WIKIPEDIA_SEARCH_RESPONSE,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    # 1. Collect
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        collect_resp = client.post("/research", json={"query": "Artificial intelligence", "limit": 2})
        assert collect_resp.status_code == 200
        research_data = collect_resp.json()

    # 2. Verify
    verify_resp = client.post("/verify", json=research_data)
    assert verify_resp.status_code == 200
    verification_data = verify_resp.json()

    # 3. Analyze
    analyze_resp = client.post("/analyze", json={
        "research": research_data,
        "verification": verification_data,
    })
    assert analyze_resp.status_code == 200
    analysis = analyze_resp.json()

    assert analysis["agent"] == "Insight Analyst Agent"
    assert analysis["eligible_sources_count"] == 2
    assert len(analysis["evidence_backed_observations"]) == 2
    assert len(analysis["key_themes"]) > 0
    assert len(analysis["important_keywords"]) > 0


# ==============================================================================
# POST /dashboard Endpoint Tests
# ==============================================================================

def test_dashboard_endpoint_success():
    """Verify POST /dashboard returns a validated dashboard specification JSON."""
    analysis_payload = {
        "agent": "Insight Analyst Agent",
        "agent_name": "Insight Analyst Agent",
        "topic": "Quantum Computing",
        "analyzed_at": "2026-03-01T12:00:00Z",
        "total_sources_evaluated": 2,
        "eligible_sources_count": 2,
        "excluded_sources_count": 0,
        "executive_summary": "Synthesized quantum computing research across 2 verified sources.",
        "key_themes": [
            {
                "theme": "Systems, Architectures & Methods",
                "description": "Quantum circuit architectures and supercomputing.",
                "frequency": 2,
                "sources": [
                    "https://en.wikipedia.org/wiki/Quantum_computing",
                ],
            }
        ],
        "important_keywords": ["quantum", "qubit", "computing", "superposition"],
        "evidence_backed_observations": [
            {
                "statement": "According to 'Quantum computing': Quantum computing uses qubits in superposition.",
                "source_title": "Quantum computing",
                "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
                "confidence": "high",
            }
        ],
        "information_gaps": ["Error correction thresholds remain unrepresented."],
        "recommendations": ["Investigate topological quantum computing."],
        "limitations": ["Constrained to encyclopedia snippets."],
        "methodology": "Deterministic keyword extraction.",
    }

    response = client.post("/dashboard", json=analysis_payload)
    assert response.status_code == 200
    spec = response.json()

    assert spec["agent"] == "Dashboard Builder Agent"
    assert "Quantum Computing" in spec["title"]
    assert spec["topic"] == "Quantum Computing"
    assert len(spec["kpi_cards"]) == 4

    # Verify KPI card IDs and values
    kpis = {k["id"]: k for k in spec["kpi_cards"]}
    assert kpis["kpi-total-sources"]["value"] == 2
    assert kpis["kpi-eligible-sources"]["value"] == 2
    assert kpis["kpi-excluded-sources"]["value"] == 0
    assert kpis["kpi-theme-count"]["value"] == 1

    # Verify charts
    assert len(spec["charts"]) >= 2
    chart_types = [c["chart_type"] for c in spec["charts"]]
    assert "pie" in chart_types
    assert "horizontal_bar" in chart_types

    # Verify observations
    assert len(spec["observations"]) == 1
    assert spec["observations"][0]["source_url"] == "https://en.wikipedia.org/wiki/Quantum_computing"


def test_dashboard_endpoint_empty_evidence():
    """Verify POST /dashboard handles analysis containing 0 eligible evidence."""
    analysis_payload = {
        "agent": "Insight Analyst Agent",
        "topic": "Empty Topic",
        "analyzed_at": "2026-03-01T12:00:00Z",
        "total_sources_evaluated": 2,
        "eligible_sources_count": 0,
        "excluded_sources_count": 2,
        "executive_summary": "Zero eligible evidence records were available.",
        "key_themes": [],
        "important_keywords": [],
        "evidence_backed_observations": [],
        "information_gaps": ["No verified data."],
        "recommendations": ["Broaden query."],
        "limitations": ["Analysis halted due to unverified sources."],
        "methodology": "Deterministic lexical heuristics.",
    }

    response = client.post("/dashboard", json=analysis_payload)
    assert response.status_code == 200
    spec = response.json()

    assert spec["topic"] == "Empty Topic"
    kpis = {k["id"]: k for k in spec["kpi_cards"]}
    assert kpis["kpi-eligible-sources"]["value"] == 0
    assert kpis["kpi-excluded-sources"]["value"] == 2
    assert spec["observations"] == []


def test_dashboard_endpoint_unsafe_url_rejected():
    """Verify POST /dashboard rejects analyst payloads with unsafe observation URLs."""
    analysis_payload = {
        "agent": "Insight Analyst Agent",
        "topic": "XSS Attempt",
        "analyzed_at": "2026-03-01T12:00:00Z",
        "total_sources_evaluated": 1,
        "eligible_sources_count": 1,
        "excluded_sources_count": 0,
        "executive_summary": "Testing unsafe link injection.",
        "key_themes": [],
        "important_keywords": [],
        "evidence_backed_observations": [
            {
                "statement": "Malicious script link injection.",
                "source_title": "Exploit Title",
                "source_url": "javascript:alert('malicious_code')",
                "confidence": "high",
            }
        ],
        "information_gaps": [],
        "recommendations": [],
        "limitations": [],
        "methodology": "Test.",
    }

    response = client.post("/dashboard", json=analysis_payload)
    assert response.status_code == 400
    assert "unsafe source url" in response.json()["detail"].lower()


def test_dashboard_endpoint_invalid_payload_422():
    """Verify POST /dashboard returns 422 on missing required fields or type errors."""
    # Missing topic
    resp1 = client.post("/dashboard", json={"executive_summary": "No topic provided"})
    assert resp1.status_code == 422

    # Negative total sources count
    resp2 = client.post("/dashboard", json={
        "topic": "Valid Topic",
        "executive_summary": "Valid summary",
        "total_sources_evaluated": -5,
    })
    assert resp2.status_code == 422


def test_complete_four_agent_pipeline():
    """
    Verify complete autonomous multi-agent pipeline:
    1. Data Collector Agent (POST /research)
    2. Research Verification Agent (POST /verify)
    3. Insight Analyst Agent (POST /analyze)
    4. Dashboard Builder Agent (POST /dashboard)
    """
    mock_response = httpx.Response(
        status_code=200,
        json=MOCK_WIKIPEDIA_SEARCH_RESPONSE,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    # Step 1: Collect research
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        collect_resp = client.post("/research", json={"query": "Artificial intelligence", "limit": 2})
        assert collect_resp.status_code == 200
        research_data = collect_resp.json()

    # Step 2: Verify research
    verify_resp = client.post("/verify", json=research_data)
    assert verify_resp.status_code == 200
    verification_data = verify_resp.json()

    # Step 3: Analyze verified evidence
    analyze_resp = client.post("/analyze", json={
        "research": research_data,
        "verification": verification_data,
    })
    assert analyze_resp.status_code == 200
    analysis_data = analyze_resp.json()

    # Step 4: Build dashboard specification
    dashboard_resp = client.post("/dashboard", json=analysis_data)
    assert dashboard_resp.status_code == 200
    dashboard_spec = dashboard_resp.json()

    # Verify final dashboard specification
    assert dashboard_spec["agent"] == "Dashboard Builder Agent"
    assert "Artificial intelligence" in dashboard_spec["title"]
    assert dashboard_spec["topic"] == "Artificial intelligence"
    assert len(dashboard_spec["kpi_cards"]) == 4

    kpis = {k["id"]: k for k in dashboard_spec["kpi_cards"]}
    assert kpis["kpi-total-sources"]["value"] == 2
    assert kpis["kpi-eligible-sources"]["value"] == 2
    assert kpis["kpi-excluded-sources"]["value"] == 0

    assert len(dashboard_spec["charts"]) >= 2
    assert len(dashboard_spec["observations"]) == 2
    for obs in dashboard_spec["observations"]:
        assert obs["source_url"].startswith("https://en.wikipedia.org")
    assert "Safe specification format" in dashboard_spec["render_notice"]


def test_complete_four_agent_pipeline_empty_results():
    """
    Verify complete 4-agent pipeline handles zero search results gracefully:
    Collector (0 results) -> Verifier (0 valid, 0 invalid) -> Analyst (0 eligible, empty observations) -> Builder (valid spec, 0 KPIs).
    """
    mock_response = httpx.Response(
        status_code=200,
        json=MOCK_EMPTY_SEARCH_RESPONSE,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        collect_resp = client.post("/research", json={"query": "Nonexistent Topic", "limit": 3})
        assert collect_resp.status_code == 200
        research_data = collect_resp.json()
        assert research_data["result_count"] == 0

    verify_resp = client.post("/verify", json=research_data)
    assert verify_resp.status_code == 200
    verification_data = verify_resp.json()
    assert verification_data["total_results"] == 0
    assert verification_data["valid_results_count"] == 0

    analyze_resp = client.post("/analyze", json={
        "research": research_data,
        "verification": verification_data,
    })
    assert analyze_resp.status_code == 200
    analysis_data = analyze_resp.json()
    assert analysis_data["eligible_sources_count"] == 0
    assert analysis_data["evidence_backed_observations"] == []
    assert "no eligible" in analysis_data["executive_summary"].lower()

    dashboard_resp = client.post("/dashboard", json=analysis_data)
    assert dashboard_resp.status_code == 200
    dashboard_spec = dashboard_resp.json()
    kpis = {k["id"]: k["value"] for k in dashboard_spec["kpi_cards"]}
    assert kpis["kpi-total-sources"] == 0
    assert kpis["kpi-eligible-sources"] == 0
    assert len(dashboard_spec["observations"]) == 0
    assert len(dashboard_spec["charts"]) == 0


def test_complete_four_agent_pipeline_with_excluded_sources():
    """
    Verify 4-agent pipeline correctly filters out invalid sources and propagates KPI counts:
    Collector -> Verifier (detects invalid URL) -> Analyst (excludes invalid record) -> Builder (accurate KPIs & charts).
    """
    research_data = {
        "agent": "Data Collector Agent",
        "agent_name": "Data Collector Agent",
        "query": "Quantum Computing",
        "result_count": 2,
        "total_results": 2,
        "retrieved_at": "2026-01-01T00:00:00Z",
        "results": [
            {
                "title": "Quantum computing",
                "snippet": "Quantum computing is a rapidly-emerging technology.",
                "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
                "source": "https://en.wikipedia.org/wiki/Quantum_computing",
                "retrieved_at": "2026-01-01T00:00:00Z",
            },
            {
                "title": "Insecure Link",
                "snippet": "This result has an insecure HTTP URL.",
                "source_url": "http://en.wikipedia.org/wiki/Insecure_link",
                "source": "http://en.wikipedia.org/wiki/Insecure_link",
                "retrieved_at": "2026-01-01T00:00:00Z",
            },
        ],
    }

    # Step 2: Verifier detects insecure URL
    verify_resp = client.post("/verify", json=research_data)
    assert verify_resp.status_code == 200
    verification_data = verify_resp.json()
    assert verification_data["total_results"] == 2
    assert verification_data["valid_results_count"] == 1
    assert verification_data["invalid_results_count"] == 1

    # Step 3: Analyst excludes insecure URL from evidence
    analyze_resp = client.post("/analyze", json={
        "research": research_data,
        "verification": verification_data,
    })
    assert analyze_resp.status_code == 200
    analysis_data = analyze_resp.json()
    assert analysis_data["total_sources_evaluated"] == 2
    assert analysis_data["eligible_sources_count"] == 1
    assert analysis_data["excluded_sources_count"] == 1
    assert len(analysis_data["evidence_backed_observations"]) == 1
    assert analysis_data["evidence_backed_observations"][0]["source_url"] == "https://en.wikipedia.org/wiki/Quantum_computing"

    # Step 4: Dashboard builder reflects exact counts in KPIs and charts
    dash_resp = client.post("/dashboard", json=analysis_data)
    assert dash_resp.status_code == 200
    dash_spec = dash_resp.json()
    kpis = {k["id"]: k["value"] for k in dash_spec["kpi_cards"]}
    assert kpis["kpi-total-sources"] == 2
    assert kpis["kpi-eligible-sources"] == 1
    assert kpis["kpi-excluded-sources"] == 1

    # Eligibility chart reflects 1 eligible and 1 excluded
    eligibility_chart = next(c for c in dash_spec["charts"] if c["id"] == "chart-source-eligibility")
    chart_data = {pt["label"]: pt["value"] for pt in eligibility_chart["data"]}
    assert chart_data["Eligible Sources"] == 1.0
    assert chart_data["Excluded / Duplicates"] == 1.0


# ==============================================================================
# Unified Pipeline Endpoint (POST /pipeline) Tests
# ==============================================================================
def test_pipeline_endpoint_success():
    """Verify POST /pipeline executes end-to-end 4-agent intelligence pipeline."""
    mock_wiki_response = {
        "query": {
            "search": [
                {
                    "title": "Quantum computing",
                    "snippet": "<span>Quantum</span> computing is an emerging field that harnesses the laws of quantum mechanics.",
                },
                {
                    "title": "Quantum supremacy",
                    "snippet": "Quantum supremacy is the goal of demonstrating that a programmable quantum device can solve a problem.",
                },
            ]
        }
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=mock_wiki_response,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        response = client.post(
            "/pipeline",
            json={"query": "Quantum Computing", "limit": 2}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["query"] == "Quantum Computing"
        assert data["total_duration_ms"] > 0
        assert "pipeline_id" in data

        # Check all 4 agents completed
        agent_statuses = data["agent_statuses"]
        assert len(agent_statuses) == 4
        assert agent_statuses["data_collector"]["status"] == "completed"
        assert agent_statuses["research_verification"]["status"] == "completed"
        assert agent_statuses["insight_analyst"]["status"] == "completed"
        assert agent_statuses["dashboard_builder"]["status"] == "completed"

        # Check agent details
        assert "Retrieved 2" in agent_statuses["data_collector"]["details"]
        assert "Quality score: 100/100" in agent_statuses["research_verification"]["details"]

        # Check Data Collector results
        research = data["research"]
        assert research["result_count"] == 2
        assert len(research["results"]) == 2

        # Check Verification results
        verification = data["verification"]
        assert verification["quality_score"] == 100
        assert verification["valid_results_count"] == 2
        assert verification["invalid_results_count"] == 0

        # Check Insight Analyst results
        analysis = data["analysis"]
        assert analysis["total_sources_evaluated"] == 2
        assert analysis["eligible_sources_count"] == 2
        assert len(analysis["evidence_backed_observations"]) == 2
        assert data["summary"] == analysis["executive_summary"]

        # Check Dashboard Builder results
        dashboard = data["dashboard"]
        assert dashboard["topic"] == "Quantum Computing"
        kpis = {k["id"]: k["value"] for k in dashboard["kpi_cards"]}
        assert kpis["kpi-total-sources"] == 2
        assert kpis["kpi-eligible-sources"] == 2
        assert kpis["kpi-excluded-sources"] == 0
        assert len(dashboard["charts"]) >= 1


def test_pipeline_endpoint_empty_results():
    """Verify POST /pipeline handles zero results cleanly without fabricating data."""
    mock_empty_wiki = {"query": {"search": []}}
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_empty_wiki,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        response = client.post(
            "/pipeline",
            json={"query": "NonexistentXYZTopic12345", "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["research"]["result_count"] == 0
        assert data["verification"]["valid_results_count"] == 0
        assert data["analysis"]["eligible_sources_count"] == 0
        assert data["dashboard"]["observations"] == []
        assert data["dashboard"]["charts"] == []

        # All 4 agents completed
        for agent_key in ("data_collector", "research_verification", "insight_analyst", "dashboard_builder"):
            assert data["agent_statuses"][agent_key]["status"] == "completed"


@pytest.mark.parametrize("invalid_payload", [
    {"query": "", "limit": 5},                          # Empty query
    {"query": "   ", "limit": 5},                       # Whitespace query
    {"query": "a" * 301, "limit": 5},                   # Query > 300 chars
    {"query": "Valid topic", "limit": 0},               # Limit < 1
    {"query": "Valid topic", "limit": 11},              # Limit > 10
    {"limit": 5},                                       # Missing query
])
def test_pipeline_endpoint_invalid_input(invalid_payload):
    """Verify POST /pipeline rejects invalid inputs with 422 Unprocessable Entity."""
    response = client.post("/pipeline", json=invalid_payload)
    assert response.status_code == 422


def test_pipeline_endpoint_upstream_timeout():
    """Verify POST /pipeline records failed status when upstream times out."""
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ReadTimeout("Upstream read timed out")

        response = client.post(
            "/pipeline",
            json={"query": "Timeout Topic", "limit": 3}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "failed"
        assert "timed out" in data["summary"].lower()
        assert data["agent_statuses"]["data_collector"]["status"] == "failed"
        assert data["agent_statuses"]["research_verification"]["status"] == "skipped"
        assert data["agent_statuses"]["insight_analyst"]["status"] == "skipped"
        assert data["agent_statuses"]["dashboard_builder"]["status"] == "skipped"
        assert data["research"] is None


def test_phase_3_4_pipeline_history_latest_and_themes_endpoints():
    """
    Phase 3.4 API Regression test:
    - GET /pipeline/latest and GET /pipeline/history track runs across callers
    - 3+ analyst themes appear properly in dashboard.themes and dashboard.key_themes
    - Newer 'neural networks' run becomes latest successful run while retaining 'quantum computing'
    - Failed run is recorded in history but does NOT overwrite latest successful run
    - GET /pipeline/{pipeline_id} restores an older run's complete output
    """
    from backend.services.history_store import pipeline_history_store

    pipeline_history_store.clear()

    # Fresh state checks
    empty_hist = client.get("/pipeline/history")
    assert empty_hist.status_code == 200
    assert empty_hist.json()["total_runs"] == 0
    assert empty_hist.json()["latest_successful_run"] is None

    empty_latest = client.get("/pipeline/latest")
    assert empty_latest.status_code == 200
    assert empty_latest.json() is None

    quantum_search = {
        "query": {
            "search": [
                {
                    "title": "Quantum computing",
                    "snippet": "Quantum computing systems and algorithms enable research applications with scientific impact.",
                },
                {
                    "title": "Qubit theory",
                    "snippet": "Theoretical history methodology and challenge risks in quantum computation.",
                },
            ]
        }
    }
    nn_search = {
        "query": {
            "search": [
                {
                    "title": "Artificial neural network",
                    "snippet": "Neural networks use layered optimization models and hardware systems for machine learning.",
                }
            ]
        }
    }

    # 1. Execute older Quantum Computing run
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(
            status_code=200,
            json=quantum_search,
            request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php"),
        )
        r1 = client.post("/pipeline", json={"query": "quantum computing", "limit": 2})
        assert r1.status_code == 200
        q_data = r1.json()
        assert q_data["status"] == "success"
        # Verify themes propagated cleanly
        assert len(q_data["dashboard"]["themes"]) == len(q_data["analysis"]["key_themes"])
        assert len(q_data["dashboard"]["themes"]) >= 3

    # 2. Execute latest Neural Networks run
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(
            status_code=200,
            json=nn_search,
            request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php"),
        )
        r2 = client.post("/pipeline", json={"query": "neural networks", "limit": 1})
        assert r2.status_code == 200
        nn_data = r2.json()
        assert nn_data["status"] == "success"

    # 3. Execute failed run -> must NOT overwrite Neural Networks as latest
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ReadTimeout("Simulated failure")
        r3 = client.post("/pipeline", json={"query": "failed run query", "limit": 1})
        assert r3.status_code == 200
        assert r3.json()["status"] == "failed"

    # GET /pipeline/latest returns Neural Networks
    latest_resp = client.get("/pipeline/latest")
    assert latest_resp.status_code == 200
    assert latest_resp.json()["pipeline_id"] == nn_data["pipeline_id"]
    assert latest_resp.json()["query"] == "neural networks"

    # GET /pipeline/history returns 3 runs newest-first and latest_successful_run == Neural Networks
    hist_resp = client.get("/pipeline/history")
    assert hist_resp.status_code == 200
    hist_json = hist_resp.json()
    assert hist_json["total_runs"] == 3
    assert hist_json["latest_successful_pipeline_id"] == nn_data["pipeline_id"]
    assert hist_json["latest_successful_run"]["query"] == "neural networks"
    assert [entry["query"] for entry in hist_json["runs"]] == [
        "failed run query",
        "neural networks",
        "quantum computing",
    ]

    # GET /pipeline/{quantum_id} restores complete Quantum Computing run
    restore_resp = client.get(f"/pipeline/{q_data['pipeline_id']}")
    assert restore_resp.status_code == 200
    restored = restore_resp.json()
    assert restored["query"] == "quantum computing"
    assert restored["research"]["results"][0]["title"] == "Quantum computing"
    assert len(restored["dashboard"]["themes"]) == len(q_data["dashboard"]["themes"])

    # Nonexistent ID returns 404
    missing_resp = client.get("/pipeline/nonexistent-id-0000")
    assert missing_resp.status_code == 404

    pipeline_history_store.clear()


_API_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2402.11111v1</id>
    <published>2024-02-15T00:00:00Z</published>
    <title>Quantum Computing Error Mitigation</title>
    <summary>Quantum computing noise mitigation techniques and circuit folding strategies.</summary>
    <author><name>Alice Smith</name></author>
    <arxiv:doi>10.1000/arxiv.2402.11111</arxiv:doi>
  </entry>
</feed>
"""


def _api_multi_source_side_effect(rate_limit_arxiv: bool = False):
    async def _mock_get(url, params=None, headers=None, **kwargs):
        url_str = str(url)
        if "wikipedia.org" in url_str:
            if params and params.get("list") == "search":
                return httpx.Response(
                    200,
                    json={
                        "query": {
                            "search": [
                                {
                                    "title": "Quantum computing",
                                    "snippet": "Quantum computing algorithms and qubit architectures.",
                                    "pageid": 1,
                                }
                            ]
                        }
                    },
                    request=httpx.Request("GET", url_str),
                )
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": {
                            "1": {
                                "pageid": 1,
                                "title": "Quantum computing",
                                "extract": "Quantum computing uses quantum mechanics for computation.",
                            }
                        }
                    }
                },
                request=httpx.Request("GET", url_str),
            )
        if "arxiv.org" in url_str:
            if rate_limit_arxiv:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "20"},
                    text="Rate limited",
                    request=httpx.Request("GET", url_str),
                )
            return httpx.Response(200, text=_API_ARXIV_XML, request=httpx.Request("GET", url_str))
        if "crossref.org" in url_str:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "message": {
                        "items": [
                            {
                                "DOI": "10.1038/s41586-024-07000-1",
                                "title": ["Quantum Computing Hardware"],
                                "abstract": "<jats:p>Experimental superconducting quantum computing processors.</jats:p>",
                                "author": [{"given": "Ada", "family": "Lovelace"}],
                                "published": {"date-parts": [[2024, 4, 1]]},
                                "URL": "https://doi.org/10.1038/s41586-024-07000-1",
                            }
                        ]
                    },
                },
                request=httpx.Request("GET", url_str),
            )
        raise AssertionError(f"Unexpected URL: {url_str}")

    return _mock_get


def test_phase_4_research_multi_source_and_default_compatibility():
    """Verify POST /research preserves default wikipedia and supports multi-source requests."""
    with patch.object(
        httpx.AsyncClient, "get", side_effect=_api_multi_source_side_effect()
    ):
        default_resp = client.post("/research", json={"query": "quantum computing", "limit": 1})
        assert default_resp.status_code == 200
        d_json = default_resp.json()
        assert d_json["sources_requested"] == ["wikipedia"]
        assert d_json["source_breakdown"] == {"wikipedia": 1}

        multi_resp = client.post(
            "/research",
            json={
                "query": "quantum computing",
                "limit": 3,
                "sources": ["wikipedia", "arxiv", "crossref"],
            },
        )
        assert multi_resp.status_code == 200
        m_json = multi_resp.json()
        assert m_json["sources_requested"] == ["wikipedia", "arxiv", "crossref"]
        assert m_json["source_breakdown"] == {"wikipedia": 1, "arxiv": 1, "crossref": 1}
        assert m_json["source_errors"] == {}
        for item in m_json["results"]:
            assert "source_name" in item
            assert "abstract" in item


def test_phase_4_research_invalid_source_422_and_rate_limit_429():
    """Verify invalid source yields 422 and upstream HTTP 429 maps to 429."""
    bad_resp = client.post(
        "/research",
        json={"query": "quantum computing", "sources": ["wikipedia", "nonexistent_db"]},
    )
    assert bad_resp.status_code == 422

    with patch.object(
        httpx.AsyncClient,
        "get",
        side_effect=_api_multi_source_side_effect(rate_limit_arxiv=True),
    ):
        rate_resp = client.post(
            "/research",
            json={"query": "quantum computing", "limit": 2, "sources": ["arxiv"]},
        )
        assert rate_resp.status_code == 429


def test_phase_4_pipeline_multi_source_and_history_summary():
    """Verify POST /pipeline and GET /pipeline/history track multi-source breakdowns."""
    from backend.services.history_store import pipeline_history_store

    pipeline_history_store.clear()
    with patch.object(
        httpx.AsyncClient, "get", side_effect=_api_multi_source_side_effect()
    ):
        resp = client.post(
            "/pipeline",
            json={
                "query": "quantum computing",
                "limit": 3,
                "sources": ["wikipedia", "arxiv", "crossref"],
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["research"]["sources_requested"] == ["wikipedia", "arxiv", "crossref"]
    assert data["research"]["source_breakdown"] == {"wikipedia": 1, "arxiv": 1, "crossref": 1}
    assert data["dashboard"]["source_distribution"] == {"wikipedia": 1, "arxiv": 1, "crossref": 1}

    hist = client.get("/pipeline/history").json()
    assert hist["total_runs"] == 1
    assert hist["runs"][0]["sources_requested"] == ["wikipedia", "arxiv", "crossref"]
    assert hist["runs"][0]["source_breakdown"] == {"wikipedia": 1, "arxiv": 1, "crossref": 1}

    pipeline_history_store.clear()


def test_phase_5_integrations_status_check_and_delegate_endpoints(monkeypatch, tmp_path):
    """Verify GET /integrations/status, POST /integrations/check, and POST /integrations/delegate."""
    from types import SimpleNamespace
    from backend.integrations import integration_registry

    monkeypatch.setattr(
        "backend.integrations.band_adapter.LIVE_BAND_VERIFICATION_FILE",
        tmp_path / "missing_live_band.json",
    )
    integration_registry.clear_delegations()

    status_resp = client.get("/integrations/status")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert set(body["platforms"].keys()) == {"band", "lyzr", "agent37", "adal", "finch"}
    assert set(body["summary"].keys()) == {"live_tested", "implemented", "partial", "not_integrated"}
    assert body["platforms"]["band"]["status"] == "implemented"
    assert body["platforms"]["finch"]["status"] == "implemented"
    assert body["platforms"]["band"]["mandatory_for_track"] is True
    assert body["platforms"]["lyzr"]["mandatory_for_track"] is True
    assert body["platforms"]["adal"]["mandatory_for_track"] is True
    assert body["platforms"]["finch"]["mandatory_for_track"] is True
    assert body["platforms"]["agent37"]["mandatory_for_track"] is False
    # Ensure secret keys are never leaked in status response
    raw_text = status_resp.text.lower()
    assert "sk_live_" not in raw_text

    finch_chk = client.post("/integrations/check/finch")
    assert finch_chk.status_code == 200
    assert finch_chk.json()["last_check_status"] == "ready"

    assert client.post("/integrations/check/unknown_platform").status_code == 404

    monkeypatch.setenv("BAND_AGENT_ID", "band-id-test")
    monkeypatch.setenv("BAND_API_KEY", "band-key-test")
    mock_rest = MagicMock = AsyncMock()
    mock_rest.agent_api_identity.get_agent_me = AsyncMock(
        return_value=SimpleNamespace(
            data=SimpleNamespace(id="band-id-test", handle="intelliscope-collector", name="Collector")
        )
    )
    with patch("backend.integrations.band_adapter.AsyncRestClient", return_value=mock_rest):
        chk = client.post("/integrations/check/band")
        assert chk.status_code == 200
        assert chk.json()["last_check_status"] == "connected"

    # Validation check -> 422 for unknown target platform or empty action
    bad_del = client.post(
        "/integrations/delegate",
        json={"target_platform": "invalid_platform", "action": "test"},
    )
    assert bad_del.status_code == 422

    # Valid delegation via BAND prepare_peer_handoff records telemetry
    good_del = client.post(
        "/integrations/delegate",
        json={
            "execution_id": "exec-api-del-1",
            "target_platform": "band",
            "action": "prepare_peer_handoff",
            "payload": {
                "peer_handle": "@analyst-peer",
                "query": "quantum computing",
                "source_urls": ["https://arxiv.org/abs/2401.12345v1"],
            },
        },
    )
    assert good_del.status_code == 200
    del_data = good_del.json()
    assert del_data["status"] == "completed"
    assert del_data["output_valid"] is True

    after_status = client.get("/integrations/status").json()
    assert len(after_status["recent_delegations"]) == 1
    assert after_status["recent_delegations"][0]["execution_id"] == "exec-api-del-1"

    integration_registry.clear_delegations()


def test_cors_configuration_and_headers():
    """Verify CORS headers respond to browser origins correctly."""
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173")







