"""
Unit tests for backend/agents/verification_agent.py.
Tests the Research Verification Agent in isolation across all structural checks,
scoring rules, and edge cases.
"""

import pytest

from backend.agents.verification_agent import (
    AGENT_CAPABILITIES,
    AGENT_NAME,
    AGENT_STATUS,
    AGENT_VERSION,
    FACTUAL_ACCURACY_DISCLAIMER,
    _calculate_item_score,
    _validate_snippet,
    _validate_timestamp,
    _validate_title,
    _validate_url,
    verify_research,
)
from backend.models.verification import VerificationRequest


@pytest.mark.asyncio
async def test_verify_research_perfect_batch():
    """Verify verify_research returns 100 quality score on well-formed items."""
    data = {
        "query": "Neural Networks",
        "results": [
            {
                "title": "Artificial neural network",
                "snippet": "Artificial neural networks (ANNs) are computing systems inspired by biology.",
                "source_url": "https://en.wikipedia.org/wiki/Artificial_neural_network",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Deep learning",
                "snippet": "Deep learning is part of a broader family of machine learning methods.",
                "source_url": "https://en.wikipedia.org/wiki/Deep_learning",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
        ],
    }

    report = await verify_research(data)

    assert report["agent"] == AGENT_NAME
    assert report["agent_name"] == AGENT_NAME
    assert report["query"] == "Neural Networks"
    assert report["total_results"] == 2
    assert report["valid_results_count"] == 2
    assert report["invalid_results_count"] == 0
    assert report["quality_score"] == 100.0
    assert report["status"] == "passed"
    assert report["is_factually_verified"] is False
    assert report["factual_accuracy_disclaimer"] == FACTUAL_ACCURACY_DISCLAIMER

    summary = report["summary"]
    assert summary["error_count"] == 0
    assert summary["warning_count"] == 0
    assert summary["duplicate_urls_count"] == 0
    assert summary["duplicate_titles_count"] == 0


@pytest.mark.asyncio
async def test_verify_research_empty_batch():
    """Verify verify_research handles empty results gracefully."""
    report = await verify_research({"query": "Empty", "results": []})

    assert report["total_results"] == 0
    assert report["valid_results_count"] == 0
    assert report["invalid_results_count"] == 0
    assert report["quality_score"] == 0.0
    assert report["status"] == "failed"
    assert report["is_factually_verified"] is False
    assert report["results"] == []


@pytest.mark.asyncio
async def test_verify_research_with_pydantic_model_input():
    """Verify verify_research accepts a VerificationRequest instance."""
    req = VerificationRequest(
        query="Robotics",
        results=[
            {
                "title": "Robotics",
                "snippet": "Robotics is an interdisciplinary branch of computer science and engineering.",
                "source_url": "https://en.wikipedia.org/wiki/Robotics",
                "retrieved_at": "2026-03-01T10:00:00Z",
            }
        ],
    )

    report = await verify_research(req)
    assert report["total_results"] == 1
    assert report["valid_results_count"] == 1
    assert report["quality_score"] == 100.0


@pytest.mark.asyncio
async def test_verify_research_missing_fields():
    """Verify items with missing title, snippet, URL, or timestamp are flagged."""
    data = {
        "query": "Missing Fields",
        "results": [
            {
                # Missing title
                "snippet": "A snippet with missing title.",
                "source_url": "https://en.wikipedia.org/wiki/Test1",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                # Missing snippet
                "title": "Missing Snippet",
                "source_url": "https://en.wikipedia.org/wiki/Test2",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                # Missing source_url
                "title": "Missing URL",
                "snippet": "A snippet with missing source link.",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                # Missing retrieved_at
                "title": "Missing Timestamp",
                "snippet": "A snippet with missing timestamp.",
                "source_url": "https://en.wikipedia.org/wiki/Test4",
            },
        ],
    }

    report = await verify_research(data)

    assert report["total_results"] == 4
    assert report["invalid_results_count"] == 4
    assert report["status"] == "failed"

    res = report["results"]
    assert res[0]["checks"]["title_valid"] is False
    assert res[1]["checks"]["snippet_valid"] is False
    assert res[2]["checks"]["https_valid"] is False
    assert res[3]["checks"]["timestamp_valid"] is False


@pytest.mark.asyncio
async def test_verify_research_invalid_types():
    """Verify non-string types and non-dictionary items are detected safely."""
    data = {
        "query": "Type Validation",
        "results": [
            {
                "title": 12345,  # Non-string title
                "snippet": "Valid snippet content string.",
                "source_url": "https://en.wikipedia.org/wiki/Test",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            "not-a-dictionary-item",  # Invalid item shape
        ],
    }

    report = await verify_research(data)
    assert report["total_results"] == 2
    assert report["invalid_results_count"] == 2

    # Check non-string title error
    assert report["results"][0]["checks"]["title_valid"] is False
    assert any("must be a string" in err for err in report["results"][0]["errors"])

    # Check non-dict item error
    assert report["results"][1]["status"] == "invalid"
    assert report["results"][1]["item_score"] == 0.0
    assert any("not a valid dictionary" in err for err in report["results"][1]["errors"])


@pytest.mark.asyncio
async def test_verify_research_url_protocols_and_domains():
    """Verify URL scheme checking and domain whitelist enforcement."""
    data = {
        "query": "URL Testing",
        "results": [
            {
                "title": "Insecure HTTP",
                "snippet": "Valid snippet content describing HTTP item.",
                "source_url": "http://en.wikipedia.org/wiki/Test",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Disallowed Domain",
                "snippet": "Valid snippet pointing to disallowed domain.",
                "source_url": "https://random-site.com/wiki/Test",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Allowed Subdomain",
                "snippet": "Valid snippet pointing to German Wikipedia subdomain.",
                "source_url": "https://de.wikipedia.org/wiki/Test",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
        ],
    }

    report = await verify_research(data)

    res = report["results"]
    # Item 0: Insecure HTTP
    assert res[0]["checks"]["https_valid"] is False
    assert res[0]["checks"]["domain_allowed"] is True

    # Item 1: Disallowed domain
    assert res[1]["checks"]["https_valid"] is True
    assert res[1]["checks"]["domain_allowed"] is False

    # Item 2: Allowed subdomain
    assert res[2]["checks"]["https_valid"] is True
    assert res[2]["checks"]["domain_allowed"] is True
    assert res[2]["status"] == "valid"


@pytest.mark.asyncio
async def test_verify_research_duplicates():
    """Verify duplicate URLs and titles are identified and penalized."""
    data = {
        "query": "Duplicate Detection",
        "results": [
            {
                "title": "Quantum computing",
                "snippet": "Quantum computing is a rapidly-emerging technology.",
                "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                # Duplicate title & duplicate URL
                "title": "QUANTUM COMPUTING",
                "snippet": "Second snippet referring to the exact same article.",
                "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
        ],
    }

    report = await verify_research(data)

    assert report["summary"]["duplicate_urls_count"] == 1
    assert report["summary"]["duplicate_titles_count"] == 1

    item0 = report["results"][0]
    assert item0["checks"]["is_duplicate_url"] is False
    assert item0["checks"]["is_duplicate_title"] is False
    assert item0["item_score"] == 100.0

    item1 = report["results"][1]
    assert item1["checks"]["is_duplicate_url"] is True
    assert item1["checks"]["is_duplicate_title"] is True
    # Penalty: title duplicate (-10), url duplicate (-15) -> 75.0
    assert item1["item_score"] < item0["item_score"]


@pytest.mark.asyncio
async def test_verify_research_timestamps():
    """Verify timestamp parsing and validation across formats."""
    data = {
        "query": "Timestamp Check",
        "results": [
            {
                "title": "Valid UTC with Z",
                "snippet": "Valid snippet content text.",
                "source_url": "https://en.wikipedia.org/wiki/Test1",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Valid Offset",
                "snippet": "Valid snippet content text.",
                "source_url": "https://en.wikipedia.org/wiki/Test2",
                "retrieved_at": "2026-03-01T10:00:00+05:30",
            },
            {
                "title": "Malformed Timestamp",
                "snippet": "Valid snippet content text.",
                "source_url": "https://en.wikipedia.org/wiki/Test3",
                "retrieved_at": "not-a-timestamp",
            },
            {
                "title": "Year Out of Bounds",
                "snippet": "Valid snippet content text.",
                "source_url": "https://en.wikipedia.org/wiki/Test4",
                "retrieved_at": "1850-01-01T00:00:00Z",
            },
        ],
    }

    report = await verify_research(data)

    res = report["results"]
    assert res[0]["checks"]["timestamp_valid"] is True
    assert res[1]["checks"]["timestamp_valid"] is True
    assert res[2]["checks"]["timestamp_valid"] is False
    assert res[3]["checks"]["timestamp_valid"] is False


@pytest.mark.asyncio
async def test_verify_research_custom_allowed_domains():
    """Verify allowed_domains parameter overrides default whitelist."""
    data = {
        "query": "Custom Domains",
        "results": [
            {
                "title": "Custom Source",
                "snippet": "Snippet from an approved custom domain.",
                "source_url": "https://docs.intelliscope.ai/article",
                "retrieved_at": "2026-03-01T10:00:00Z",
            }
        ],
    }

    # Pass custom allowed domain
    report = await verify_research(data, allowed_domains=["intelliscope.ai"])
    assert report["results"][0]["checks"]["domain_allowed"] is True
    assert report["results"][0]["status"] == "valid"


def test_helper_validate_title():
    """Test _validate_title helper function."""
    assert _validate_title("Valid Title") == (True, None)
    assert _validate_title("")[0] is False
    assert _validate_title("   ")[0] is False
    assert _validate_title(None)[0] is False
    assert _validate_title(123)[0] is False


def test_helper_validate_snippet():
    """Test _validate_snippet helper function."""
    ok, err, warn = _validate_snippet("A comprehensive snippet exceeding minimum length.")
    assert ok is True and err is None and warn is None

    # Short snippet generates warning
    ok, err, warn = _validate_snippet("Short snippet")
    assert ok is True and err is None and warn is not None

    # Empty snippet generates error
    ok, err, warn = _validate_snippet("")
    assert ok is False and err is not None


def test_helper_validate_url():
    """Test _validate_url helper function."""
    allowed = ["wikipedia.org"]
    https_ok, domain_ok, err, canonical = _validate_url(
        "https://en.wikipedia.org/wiki/AI", allowed
    )
    assert https_ok is True
    assert domain_ok is True
    assert err is None
    assert canonical == "https://en.wikipedia.org/wiki/AI"

    # Insecure HTTP
    https_ok, domain_ok, err, _ = _validate_url("http://en.wikipedia.org/wiki/AI", allowed)
    assert https_ok is False
    assert domain_ok is True
    assert "insecure protocol" in err.lower()

    # Disallowed domain
    https_ok, domain_ok, err, _ = _validate_url("https://malicious.org/wiki/AI", allowed)
    assert https_ok is True
    assert domain_ok is False
    assert "allowed domains" in err.lower()


def test_helper_validate_timestamp():
    """Test _validate_timestamp helper function."""
    assert _validate_timestamp("2026-03-01T12:00:00Z")[0] is True
    assert _validate_timestamp("invalid-date")[0] is False
    assert _validate_timestamp("")[0] is False
    assert _validate_timestamp(None)[0] is False


def test_helper_calculate_item_score_bounds():
    """Test _calculate_item_score maintains 0.0 to 100.0 bounds."""
    # Perfect score
    score = _calculate_item_score(
        title_valid=True,
        snippet_valid=True,
        has_snippet_warning=False,
        https_valid=True,
        domain_allowed=True,
        timestamp_valid=True,
        is_duplicate_url=False,
        is_duplicate_title=False,
    )
    assert score == 100.0

    # Minimum score
    score_min = _calculate_item_score(
        title_valid=False,
        snippet_valid=False,
        has_snippet_warning=False,
        https_valid=False,
        domain_allowed=False,
        timestamp_valid=False,
        is_duplicate_url=True,
        is_duplicate_title=True,
    )
    assert score_min == 0.0


def test_verification_agent_metadata():
    """Test agent metadata constants."""
    assert AGENT_NAME == "Research Verification Agent"
    assert AGENT_VERSION == "1.0.0"
    assert AGENT_STATUS == "operational"
    assert "structural_schema_validation" in AGENT_CAPABILITIES
    assert "https_protocol_verification" in AGENT_CAPABILITIES
    assert "domain_whitelist_enforcement" in AGENT_CAPABILITIES
    assert "quality_score_calculation" in AGENT_CAPABILITIES


@pytest.mark.asyncio
async def test_verify_research_weakly_relevant_warning():
    """Verify that weakly relevant sources receive an advisory warning."""
    data = {
        "query": "quantum computing",
        "results": [
            {
                "title": "Baking bread",
                "snippet": "Flour, water, yeast, and salt are the basic ingredients.",
                "source_url": "https://en.wikipedia.org/wiki/Bread",
                "retrieved_at": "2026-03-01T10:00:00Z",
                "is_weakly_relevant": True,
                "relevance_reason": "Neither title nor extract contains query key terms.",
            }
        ],
    }

    report = await verify_research(data)
    assert report["total_results"] == 1
    item = report["results"][0]
    assert item["is_weakly_relevant"] is True
    assert item["status"] == "warning"
    assert any("Weakly related source" in w for w in item["warnings"])
    assert report["status"] == "passed_with_warnings"


@pytest.mark.asyncio
async def test_verify_research_structural_vs_factual_disclaimers():
    """Verify that structural verification explicitly disclaims factual verification."""
    data = {
        "query": "Artificial intelligence",
        "results": [
            {
                "title": "Artificial intelligence",
                "snippet": "AI is intelligence demonstrated by machines.",
                "source_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "retrieved_at": "2026-03-01T10:00:00Z",
            }
        ],
    }

    report = await verify_research(data)
    assert report["is_factually_verified"] is False
    assert report["verification_type"] == "structural_and_source_integrity"
    assert "factual claims within snippets are verified facts" in report["factual_accuracy_disclaimer"]
    assert "structural integrity" in report["factual_accuracy_disclaimer"].lower()


@pytest.mark.asyncio
async def test_phase_3_3_verification_reporting_counts_and_separation():
    """
    Phase 3.3 Regression test:
    Verify explicit reporting of:
    - structurally_valid_count
    - directly_relevant_count
    - weakly_relevant_count
    - excluded_count
    - separation of structural quality score from topical relevance.
    """
    data = {
        "query": "quantum computing",
        "results": [
            {
                # Item 0: Directly relevant and structurally valid
                "title": "Quantum computing",
                "snippet": "Quantum computing is a rapidly-emerging technology.",
                "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
                "retrieved_at": "2026-03-01T10:00:00Z",
                "is_weakly_relevant": False,
            },
            {
                # Item 1: Weakly relevant entity, but structurally valid
                "title": "Michael J. Biercuk",
                "snippet": "Michael J. Biercuk is an experimental physicist specializing in quantum computing.",
                "source_url": "https://en.wikipedia.org/wiki/Michael_J._Biercuk",
                "retrieved_at": "2026-03-01T10:00:00Z",
                "is_weakly_relevant": True,
                "relevance_reason": "Article title 'Michael J. Biercuk' contains none of the query terms.",
            },
            {
                # Item 2: Structurally invalid (insecure http) -> excluded
                "title": "Insecure source",
                "snippet": "Some snippet text for an insecure source.",
                "source_url": "http://en.wikipedia.org/wiki/Insecure",
                "retrieved_at": "2026-03-01T10:00:00Z",
                "is_weakly_relevant": False,
            },
        ],
    }

    report = await verify_research(data)

    assert report["total_results"] == 3
    assert report["structurally_valid_count"] == 2
    assert report["excluded_count"] == 1
    assert report["directly_relevant_count"] == 1
    assert report["weakly_relevant_count"] == 1

    # Check summary contains matching explicit fields
    summary = report["summary"]
    assert summary["structurally_valid_count"] == 2
    assert summary["excluded_count"] == 1
    assert summary["directly_relevant_count"] == 1
    assert summary["weakly_relevant_count"] == 1

    # Check structural score separation:
    # Item 1 (weakly relevant) has full structural points (100.0) despite weak relevance
    res = report["results"]
    assert res[1]["item_score"] == 100.0
    assert res[1]["status"] == "warning"
    assert res[1]["is_weakly_relevant"] is True

    # Item 2 is excluded (status = invalid)
    assert res[2]["status"] == "invalid"

    # Factual accuracy disclaimer
    assert report["is_factually_verified"] is False
    assert "factual claims within snippets are verified facts" in report["factual_accuracy_disclaimer"]


@pytest.mark.asyncio
async def test_verify_research_multi_source_domains_and_valid_doi():
    """Verify arXiv and Crossref domains and valid DOIs pass structural verification."""
    data = {
        "query": "quantum computing",
        "results": [
            {
                "title": "Quantum computing",
                "snippet": "Quantum computing relies on quantum mechanical phenomena.",
                "source_name": "wikipedia",
                "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Fault-Tolerant Quantum Codes",
                "snippet": "Surface codes protect logical qubits in scalable quantum processors.",
                "source_name": "arxiv",
                "source_url": "https://arxiv.org/abs/2401.12345v1",
                "doi": "10.1103/PhysRevLett.132.010501",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Error Mitigation in Practice",
                "snippet": "Zero-noise extrapolation reduces circuit bias across superconducting hardware.",
                "source_name": "crossref",
                "source_url": "https://doi.org/10.1038/s41586-024-07000-1",
                "doi": "10.1038/s41586-024-07000-1",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
        ],
    }

    report = await verify_research(data)
    assert report["status"] == "passed"
    assert report["structurally_valid_count"] == 3
    for item in report["results"]:
        assert item["checks"]["https_valid"] is True
        assert item["checks"]["domain_allowed"] is True
    assert report["results"][1]["checks"]["doi_valid"] is True
    assert report["results"][2]["checks"]["doi_valid"] is True
    assert report["summary"]["duplicate_dois_count"] == 0


@pytest.mark.asyncio
async def test_verify_research_invalid_source_domain_bad_doi_and_duplicate_doi():
    """Verify source-specific domain checks, invalid DOI flagging, and duplicate DOI detection."""
    data = {
        "query": "quantum computing",
        "results": [
            {
                "title": "Paper One",
                "snippet": "First paper discussing quantum computing error thresholds.",
                "source_name": "crossref",
                "source_url": "https://doi.org/10.1000/shared-doi-1",
                "doi": "10.1000/shared-doi-1",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Paper Two Duplicate DOI",
                "snippet": "Second record sharing the same DOI via an alternate link.",
                "source_name": "arxiv",
                "source_url": "https://arxiv.org/abs/2401.99999v1",
                "doi": "10.1000/shared-doi-1",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Malformed DOI Paper",
                "snippet": "Preprint carrying a syntactically invalid DOI string.",
                "source_name": "arxiv",
                "source_url": "https://arxiv.org/abs/2401.88888v1",
                "doi": "invalid-doi-format",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
            {
                "title": "Untrusted Crossref Spoof",
                "snippet": "Crossref item pointing outside doi.org.",
                "source_name": "crossref",
                "source_url": "https://untrusted.example.com/paper",
                "doi": "10.1000/other",
                "retrieved_at": "2026-03-01T10:00:00Z",
            },
        ],
    }

    report = await verify_research(data)
    res = report["results"]

    assert res[0]["checks"]["doi_valid"] is True
    assert res[0]["checks"]["is_duplicate_doi"] is False

    assert res[1]["checks"]["is_duplicate_doi"] is True
    assert report["summary"]["duplicate_dois_count"] == 1

    assert res[2]["checks"]["doi_valid"] is False
    assert any("doi" in msg.lower() for msg in (res[2]["warnings"] + res[2]["errors"]))

    assert res[3]["checks"]["domain_allowed"] is False
    assert res[3]["status"] == "invalid"


