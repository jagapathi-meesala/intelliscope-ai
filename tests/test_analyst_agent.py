"""
Unit tests for backend/agents/analyst_agent.py.
Tests the Insight Analyst Agent in isolation: deterministic keyword extraction,
theme clustering, evidence filtering, consistency validation, and edge cases.
"""

import pytest

from backend.agents.analyst_agent import (
    AGENT_CAPABILITIES,
    AGENT_NAME,
    AGENT_STATUS,
    AGENT_VERSION,
    AnalysisValidationError,
    analyze_research,
    assess_observation_confidence,
    build_observations,
    cluster_themes,
    extract_keywords,
    filter_eligible_evidence,
    generate_executive_summary,
    generate_recommendations,
    identify_information_gaps,
    validate_report_consistency,
)
from backend.models.analyst import AnalysisRequest


@pytest.fixture
def sample_valid_research_and_verification():
    """Fixture providing consistent, verified research and verification records."""
    research = {
        "query": "Robotics and Automation",
        "results": [
            {
                "title": "Robotics",
                "snippet": "Robotics is an engineering discipline focused on designing autonomous systems and machines.",
                "source_url": "https://en.wikipedia.org/wiki/Robotics",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Industrial automation",
                "snippet": "Industrial automation utilizes software, robotics, and control systems to optimize industry data.",
                "source_url": "https://en.wikipedia.org/wiki/Industrial_automation",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }

    verification = {
        "query": "Robotics and Automation",
        "total_results": 2,
        "results": [
            {
                "index": 0,
                "title": "Robotics",
                "source_url": "https://en.wikipedia.org/wiki/Robotics",
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
                "title": "Industrial automation",
                "source_url": "https://en.wikipedia.org/wiki/Industrial_automation",
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
        ],
    }
    return research, verification


@pytest.mark.asyncio
async def test_analyze_research_direct_success(sample_valid_research_and_verification):
    """Verify analyze_research produces complete structured analysis from valid data."""
    research, verification = sample_valid_research_and_verification

    result = await analyze_research(research, verification)

    assert result["agent"] == AGENT_NAME
    assert result["topic"] == "Robotics and Automation"
    assert result["total_sources_evaluated"] == 2
    assert result["eligible_sources_count"] == 2
    assert result["excluded_sources_count"] == 0
    assert len(result["executive_summary"]) > 20
    assert len(result["key_themes"]) > 0
    assert len(result["important_keywords"]) > 0
    assert len(result["evidence_backed_observations"]) == 2
    assert len(result["information_gaps"]) > 0
    assert len(result["recommendations"]) > 0
    assert len(result["limitations"]) > 0

    obs0 = result["evidence_backed_observations"][0]
    assert obs0["source_title"] == "Robotics"
    assert obs0["source_url"] == "https://en.wikipedia.org/wiki/Robotics"
    assert "Robotics" in obs0["statement"]


@pytest.mark.asyncio
async def test_analyze_research_with_pydantic_model(sample_valid_research_and_verification):
    """Verify analyze_research accepts an AnalysisRequest Pydantic model."""
    research, verification = sample_valid_research_and_verification
    req = AnalysisRequest(research=research, verification=verification)

    result = await analyze_research(req)
    assert result["eligible_sources_count"] == 2
    assert result["topic"] == "Robotics and Automation"


@pytest.mark.asyncio
async def test_analyze_research_empty_results():
    """Verify analyze_research handles 0 results with transparent disclosure."""
    research = {"query": "Empty Topic", "results": []}
    verification = {"query": "Empty Topic", "total_results": 0, "results": []}

    result = await analyze_research(research, verification)

    assert result["total_sources_evaluated"] == 0
    assert result["eligible_sources_count"] == 0
    assert result["evidence_backed_observations"] == []
    assert "no eligible" in result["executive_summary"].lower()
    assert any("zero eligible sources" in gap.lower() for gap in result["information_gaps"])


@pytest.mark.asyncio
async def test_analyze_research_all_ineligible():
    """Verify all items are excluded when verification flags indicate invalidity."""
    research = {
        "query": "Insecure Topic",
        "results": [
            {
                "title": "Bad Source",
                "snippet": "Insecure link snippet.",
                "source_url": "http://en.wikipedia.org/wiki/Bad",
                "retrieved_at": "2026-03-01T12:00:00Z",
            }
        ],
    }
    verification = {
        "query": "Insecure Topic",
        "total_results": 1,
        "results": [
            {
                "index": 0,
                "title": "Bad Source",
                "source_url": "http://en.wikipedia.org/wiki/Bad",
                "status": "invalid",
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": False,  # Failed check
                    "domain_allowed": True,
                    "timestamp_valid": True,
                    "is_duplicate_url": False,
                    "is_duplicate_title": False,
                },
                "errors": ["Insecure protocol"],
            }
        ],
    }

    result = await analyze_research(research, verification)

    assert result["total_sources_evaluated"] == 1
    assert result["eligible_sources_count"] == 0
    assert result["excluded_sources_count"] == 1
    assert result["evidence_backed_observations"] == []


@pytest.mark.asyncio
async def test_analyze_research_duplicate_filtering():
    """Verify duplicate records are filtered out from evidence observations."""
    research = {
        "query": "Duplicates",
        "results": [
            {
                "title": "Unique Title",
                "snippet": "First unique snippet.",
                "source_url": "https://en.wikipedia.org/wiki/First",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
            {
                "title": "Duplicate Title",
                "snippet": "Duplicate snippet.",
                "source_url": "https://en.wikipedia.org/wiki/Duplicate",
                "retrieved_at": "2026-03-01T12:00:00Z",
            },
        ],
    }
    verification = {
        "query": "Duplicates",
        "total_results": 2,
        "results": [
            {
                "index": 0,
                "title": "Unique Title",
                "source_url": "https://en.wikipedia.org/wiki/First",
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
                "title": "Duplicate Title",
                "source_url": "https://en.wikipedia.org/wiki/Duplicate",
                "status": "warning",
                "checks": {
                    "title_valid": True,
                    "snippet_valid": True,
                    "https_valid": True,
                    "domain_allowed": True,
                    "timestamp_valid": True,
                    "is_duplicate_url": True,  # Duplicate!
                    "is_duplicate_title": False,
                },
                "errors": [],
            },
        ],
    }

    result = await analyze_research(research, verification)
    assert result["eligible_sources_count"] == 1
    assert result["excluded_sources_count"] == 1
    assert len(result["evidence_backed_observations"]) == 1
    assert result["evidence_backed_observations"][0]["source_title"] == "Unique Title"


def test_validate_consistency_errors():
    """Verify validate_report_consistency raises AnalysisValidationError on mismatches."""
    # 1. Query mismatch
    with pytest.raises(AnalysisValidationError) as exc1:
        validate_report_consistency(
            {"query": "Query A", "results": []},
            {"query": "Query B", "results": []},
        )
    assert "does not match" in str(exc1.value).lower()

    # 2. Count mismatch
    with pytest.raises(AnalysisValidationError) as exc2:
        validate_report_consistency(
            {"query": "Topic", "results": [{"title": "A"}]},
            {"query": "Topic", "total_results": 0, "results": []},
        )
    assert "count mismatch" in str(exc2.value).lower()

    # 3. URL mismatch
    with pytest.raises(AnalysisValidationError) as exc3:
        validate_report_consistency(
            {
                "query": "Topic",
                "results": [{"source_url": "https://en.wikipedia.org/wiki/Alpha"}],
            },
            {
                "query": "Topic",
                "total_results": 1,
                "results": [{"source_url": "https://en.wikipedia.org/wiki/Beta"}],
            },
        )
    assert "url mismatch" in str(exc3.value).lower()

    # 4. Tampered status (valid despite failed check)
    with pytest.raises(AnalysisValidationError) as exc4:
        validate_report_consistency(
            {
                "query": "Topic",
                "results": [{"source_url": "https://en.wikipedia.org/wiki/Alpha"}],
            },
            {
                "query": "Topic",
                "total_results": 1,
                "results": [
                    {
                        "source_url": "https://en.wikipedia.org/wiki/Alpha",
                        "status": "valid",
                        "checks": {
                            "title_valid": True,
                            "snippet_valid": True,
                            "https_valid": False,  # Failed check!
                            "domain_allowed": True,
                        },
                        "errors": [],
                    }
                ],
            },
        )
    assert "inconsistent" in str(exc4.value).lower()


def test_extract_keywords():
    """Verify keyword extraction removes stopwords and orders by frequency."""
    texts = [
        "Artificial intelligence and deep learning models for data processing.",
        "Deep learning architectures are neural network models.",
    ]
    keywords = extract_keywords(texts, top_n=3)

    assert "deep" in keywords
    assert "learning" in keywords
    assert "models" in keywords
    assert "and" not in keywords
    assert "for" not in keywords


def test_cluster_themes():
    """Verify theme clustering correctly groups items based on keywords."""
    items = [
        {
            "title": "Cognitive Science",
            "snippet": "A study of intelligence and cognitive principles.",
            "source_url": "https://en.wikipedia.org/wiki/Cognitive_science",
        },
        {
            "title": "Machine Learning",
            "snippet": "Software algorithms and neural networks for computing.",
            "source_url": "https://en.wikipedia.org/wiki/Machine_learning",
        },
    ]

    themes = cluster_themes(items)
    assert len(themes) > 0
    theme_names = [t.theme for t in themes]
    assert any("Foundations" in name for name in theme_names)
    assert any("Systems" in name for name in theme_names)


def test_build_observations():
    """Verify observations are grounded in snippet and properly structured."""
    items = [
        {
            "title": "Quantum Computing",
            "snippet": "Quantum computing uses superposition to solve complex problems",
            "source_url": "https://en.wikipedia.org/wiki/Quantum_computing",
        }
    ]

    observations = build_observations(items)
    assert len(observations) == 1
    obs = observations[0]
    assert obs.source_title == "Quantum Computing"
    assert obs.source_url == "https://en.wikipedia.org/wiki/Quantum_computing"
    assert obs.statement.startswith("According to 'Quantum Computing':")
    assert obs.statement.endswith(".")


def test_analyst_agent_metadata():
    """Verify metadata constants of the Insight Analyst Agent."""
    assert AGENT_NAME == "Insight Analyst Agent"
    assert AGENT_STATUS == "operational"
    assert AGENT_VERSION == "1.0.0"
    assert "deterministic_text_analysis" in AGENT_CAPABILITIES
    assert "keyword_extraction" in AGENT_CAPABILITIES
    assert "verification_consistency_check" in AGENT_CAPABILITIES


def test_assess_observation_confidence_dynamic():
    """Verify confidence levels reflect evidence quality, extract length, and warnings."""
    # 1. Weakly relevant -> low confidence
    item_weak = {
        "title": "Bread",
        "snippet": "Bread is a staple food prepared from dough of flour and water.",
        "is_weakly_relevant": True,
        "relevance_reason": "Query was quantum computing",
    }
    conf, reason = assess_observation_confidence(item_weak)
    assert conf == "low"
    assert "Weak topical relevance" in reason

    # 2. Short snippet (< 60 chars) -> medium confidence
    item_short = {
        "title": "Quantum",
        "snippet": "A quantum is the minimum amount of any physical entity.",
        "is_weakly_relevant": False,
    }
    conf, reason = assess_observation_confidence(item_short)
    assert conf == "medium"
    assert "Brief evidence extract" in reason

    # 3. Advisory verification warning -> medium confidence
    item_warn = {
        "title": "Quantum Mechanics",
        "snippet": "Quantum mechanics is a fundamental theory in physics that describes the physical properties of nature.",
        "is_weakly_relevant": False,
    }
    v_item_warn = {
        "warnings": ["Duplicate article title: already seen"]
    }
    conf, reason = assess_observation_confidence(item_warn, v_item_warn)
    assert conf == "medium"
    assert "Verification advisory warnings present" in reason

    # 4. Direct match + substantive extract + no warnings -> high confidence
    item_strong = {
        "title": "Quantum computing",
        "snippet": "Quantum computing is a rapidly-emerging technology that harnesses the laws of quantum mechanics to solve complex problems.",
        "is_weakly_relevant": False,
    }
    conf, reason = assess_observation_confidence(item_strong, {"warnings": []})
    assert conf == "high"
    assert "Direct topical relevance" in reason


@pytest.mark.asyncio
async def test_analyst_agent_weakly_relevant_reporting():
    """Verify analyst reports transparent warnings when evidence consists of weakly relevant sources."""
    research = {
        "query": "Quantum gravity",
        "results": [
            {
                "title": "General relativity",
                "snippet": "General relativity is the geometric theory of gravitation published by Albert Einstein in 1915.",
                "source_url": "https://en.wikipedia.org/wiki/General_relativity",
                "retrieved_at": "2026-03-01T12:00:00Z",
                "is_weakly_relevant": True,
                "relevance_reason": "Mentions relativity but lacks quantum gravitational mechanics.",
            }
        ]
    }
    verification = {
        "query": "Quantum gravity",
        "total_results": 1,
        "results": [
            {
                "index": 0,
                "title": "General relativity",
                "source_url": "https://en.wikipedia.org/wiki/General_relativity",
                "status": "warning",
                "is_weakly_relevant": True,
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
                "warnings": ["Weakly related source"],
            }
        ]
    }

    report = await analyze_research(research, verification)
    assert report["eligible_sources_count"] == 1
    # Check caution in executive summary
    assert "peripheral or weakly relevant" in report["executive_summary"].lower() or "caution" in report["executive_summary"].lower()
    # Check gap reporting
    assert any("relevance" in g.lower() for g in report["information_gaps"])
    # Check observation confidence is low
    assert report["evidence_backed_observations"][0]["confidence"] == "low"


@pytest.mark.asyncio
async def test_analyst_agent_sparse_evidence_reporting():
    """Verify analyst reports information gap when evidence base is constrained to <= 1 source."""
    research = {
        "query": "Autonomous Agents",
        "results": [
            {
                "title": "Intelligent agent",
                "snippet": "An intelligent agent is an autonomous entity which acts upon an environment using sensors and actuators.",
                "source_url": "https://en.wikipedia.org/wiki/Intelligent_agent",
                "retrieved_at": "2026-03-01T12:00:00Z",
                "is_weakly_relevant": False,
            }
        ]
    }
    verification = {
        "query": "Autonomous Agents",
        "total_results": 1,
        "results": [
            {
                "index": 0,
                "title": "Intelligent agent",
                "source_url": "https://en.wikipedia.org/wiki/Intelligent_agent",
                "status": "valid",
                "is_weakly_relevant": False,
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
            }
        ]
    }

    report = await analyze_research(research, verification)
    assert report["eligible_sources_count"] == 1
    assert any("sparse" in g.lower() or "constrained" in g.lower() or "limited" in g.lower() for g in report["information_gaps"])
    assert any("structural" in lim.lower() for lim in report["limitations"])
    assert any("confidence" in lim.lower() for lim in report["limitations"])


