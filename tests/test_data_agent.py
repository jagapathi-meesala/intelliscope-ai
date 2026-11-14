"""
Unit tests for backend/agents/data_agent.py.
Tests the Data Collector Agent in isolation with mock HTTP clients.
"""

from unittest.mock import AsyncMock, patch
import httpx
import pytest

from backend.agents.data_agent import (
    AGENT_CAPABILITIES,
    AGENT_NAME,
    AGENT_STATUS,
    DataCollectorRateLimitError,
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
    build_wikipedia_url,
    check_source_relevance,
    clean_html_snippet,
    clean_wiki_markup_and_html,
    collect_research,
    fetch_page_extracts,
    is_navigation_or_empty,
    truncate_snippet,
)
from backend.models.research import ResearchRequest, validate_and_normalize_sources


@pytest.mark.asyncio
async def test_collect_research_success():
    """Verify collect_research returns formatted data when API succeeds."""
    mock_payload = {
        "query": {
            "search": [
                {
                    "title": "Natural Language Processing",
                    "snippet": "NLP is a subfield of <span class=\"searchmatch\">linguistics</span>.",
                    "pageid": 21652,
                }
            ]
        }
    }
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        result = await collect_research("Natural Language Processing", limit=1)

        assert result["agent"] == AGENT_NAME
        assert result["query"] == "Natural Language Processing"
        assert result["result_count"] == 1
        assert result["total_results"] == 1
        assert "retrieved_at" in result
        assert len(result["results"]) == 1

        item = result["results"][0]
        assert item["title"] == "Natural Language Processing"
        assert item["snippet"] == "NLP is a subfield of linguistics."
        assert "Natural_Language_Processing" in item["source_url"]
        assert item["source"] == item["source_url"]
        assert "retrieved_at" in item


@pytest.mark.asyncio
async def test_collect_research_empty():
    """Verify collect_research handles zero results cleanly."""
    mock_payload = {"query": {"search": []}}
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        result = await collect_research("xyz_unknown_query_99999", limit=5)

        assert result["result_count"] == 0
        assert result["total_results"] == 0
        assert result["results"] == []


@pytest.mark.asyncio
async def test_collect_research_with_provided_client():
    """Verify collect_research works with an explicitly provided AsyncClient."""
    mock_payload = {"query": {"search": []}}
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_resp

    result = await collect_research("provided client query", limit=3, client=mock_client)
    assert result["result_count"] == 0
    mock_client.get.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_query", ["", "   ", "a" * 301])
async def test_collect_research_query_validation(invalid_query):
    """Verify collect_research raises ValueError on invalid queries."""
    with pytest.raises(ValueError):
        await collect_research(invalid_query)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_limit", [0, -1, 11, 100])
async def test_collect_research_limit_validation(invalid_limit):
    """Verify collect_research raises ValueError on invalid limits."""
    with pytest.raises(ValueError):
        await collect_research("valid query", limit=invalid_limit)


@pytest.mark.asyncio
async def test_collect_research_timeout_error():
    """Verify collect_research raises DataCollectorTimeoutError on timeout."""
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectTimeout("Connection timed out")

        with pytest.raises(DataCollectorTimeoutError):
            await collect_research("Timeout query")


@pytest.mark.asyncio
async def test_collect_research_upstream_http_status_error():
    """Verify collect_research raises DataCollectorUpstreamError on 5xx."""
    mock_resp = httpx.Response(
        status_code=500,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        with pytest.raises(DataCollectorUpstreamError):
            await collect_research("500 error query")


@pytest.mark.asyncio
async def test_collect_research_upstream_request_error():
    """Verify collect_research raises DataCollectorUpstreamError on network error."""
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.NetworkError("Host unreachable")

        with pytest.raises(DataCollectorUpstreamError):
            await collect_research("Network error query")


@pytest.mark.asyncio
async def test_collect_research_mediawiki_error_payload():
    """Verify collect_research handles MediaWiki API error payload."""
    mock_payload = {
        "error": {
            "code": "badeval",
            "info": "The search parameter is invalid."
        }
    }
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        with pytest.raises(DataCollectorUpstreamError) as exc_info:
            await collect_research("Error query")
        assert "The search parameter is invalid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_collect_research_invalid_json():
    """Verify collect_research raises DataCollectorResponseError on bad JSON."""
    mock_resp = httpx.Response(
        status_code=200,
        content=b"Not valid JSON {",
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        with pytest.raises(DataCollectorResponseError):
            await collect_research("Bad JSON query")


def test_clean_html_snippet():
    """Verify HTML cleaning strips markup and unescapes entities."""
    raw = '<span class="searchmatch">Artificial</span> &quot;Intelligence&quot; &amp; Machine Learning'
    cleaned = clean_html_snippet(raw)
    assert cleaned == 'Artificial "Intelligence" & Machine Learning'

    assert clean_html_snippet("") == ""
    assert clean_html_snippet(None) == ""


def test_build_wikipedia_url():
    """Verify Wikipedia URL builder formats and escapes titles properly."""
    assert build_wikipedia_url("Deep Learning") == "https://en.wikipedia.org/wiki/Deep_Learning"
    assert build_wikipedia_url("C++") == "https://en.wikipedia.org/wiki/C%2B%2B"
    assert build_wikipedia_url("Café") == "https://en.wikipedia.org/wiki/Caf%C3%A9"


def test_metadata_constants():
    """Verify agent constants and capabilities."""
    assert AGENT_NAME == "Data Collector Agent"
    assert AGENT_STATUS == "operational"
    assert "wikipedia_search" in AGENT_CAPABILITIES
    assert "asynchronous_data_retrieval" in AGENT_CAPABILITIES


@pytest.mark.asyncio
async def test_collect_research_quantum_computing_relevance():
    """
    Verify that 'quantum computing' query returns relevant search results,
    preserves HTTPS Wikipedia URLs, and does not fabricate sources or snippets.
    """
    mock_payload = {
        "query": {
            "search": [
                {
                    "title": "Quantum computing",
                    "snippet": "<span class=\"searchmatch\">Quantum</span> computing is a rapidly-emerging technology.",
                    "pageid": 24503,
                },
                {
                    "title": "Quantum computer",
                    "snippet": "A <span class=\"searchmatch\">quantum</span> computer is a computer that exploits quantum mechanical phenomena.",
                    "pageid": 25680,
                },
            ]
        }
    }
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        result = await collect_research("quantum computing", limit=2)

        # Verify call params sent to MediaWiki API for search
        assert mock_get.await_count >= 1
        call_kwargs = mock_get.await_args_list[0].kwargs
        assert call_kwargs["params"]["srsearch"] == "quantum computing"
        assert call_kwargs["params"]["srlimit"] == 2

        # Verify structured outputs
        assert result["query"] == "quantum computing"
        assert result["result_count"] == 2
        assert len(result["results"]) == 2

        # Verify first item
        item0 = result["results"][0]
        assert item0["title"] == "Quantum computing"
        assert item0["snippet"] == "Quantum computing is a rapidly-emerging technology."
        assert item0["source_url"] == "https://en.wikipedia.org/wiki/Quantum_computing"
        assert item0["source_url"].startswith("https://en.wikipedia.org/wiki/")

        # Verify second item
        item1 = result["results"][1]
        assert item1["title"] == "Quantum computer"
        assert item1["source_url"] == "https://en.wikipedia.org/wiki/Quantum_computer"
        assert item1["source_url"].startswith("https://en.wikipedia.org/wiki/")


def test_clean_wiki_markup_and_html():
    """Verify clean_wiki_markup_and_html cleans tags, links, templates, citations, and entities."""
    raw = (
        "<b>Quantum computing</b> is a field &amp; paradigm. "
        "{{cite book}} It uses [[Qubit|qubits]] [http://example.com external] "
        "and [1][note 2] phenomena. == Overview =="
    )
    cleaned = clean_wiki_markup_and_html(raw)
    assert "<b>" not in cleaned
    assert "&amp;" not in cleaned
    assert "&" in cleaned
    assert "{{cite book}}" not in cleaned
    assert "qubits" in cleaned
    assert "[[Qubit" not in cleaned
    assert "[1]" not in cleaned
    assert "[note 2]" not in cleaned
    assert "== Overview ==" not in cleaned
    assert "Quantum computing is a field & paradigm." in cleaned


def test_is_navigation_or_empty():
    """Verify is_navigation_or_empty correctly flags stubs, jump links, and disambiguation."""
    assert is_navigation_or_empty("") is True
    assert is_navigation_or_empty("   ") is True
    assert is_navigation_or_empty("short text") is True  # < 15 chars
    assert is_navigation_or_empty("Quantum computing may refer to: physics, computer science.") is True
    assert is_navigation_or_empty("Jump to navigation Jump to search") is True
    assert is_navigation_or_empty("This is a disambiguation page for other uses, see below.") is True
    assert is_navigation_or_empty(
        "Quantum computing is a rapidly-emerging technology that harnesses the laws of quantum mechanics."
    ) is False


def test_truncate_snippet():
    """Verify snippet length truncation enforces bounds cleanly."""
    text = (
        "Quantum computing is a rapidly-emerging technology. "
        "It harnesses the laws of quantum mechanics to solve problems too complex for classical computers. "
        "Today, hardware is accessible to thousands of developers."
    )
    truncated_short = truncate_snippet(text, max_length=60)
    assert len(truncated_short) <= 60
    assert truncated_short.endswith(".") or truncated_short.endswith("...")

    # Text under limit is unchanged
    assert truncate_snippet("Short snippet", max_length=100) == "Short snippet"


def test_check_source_relevance_direct_match():
    """Verify check_source_relevance marks direct title or core term matches as relevant."""
    rel, is_weak, reason = check_source_relevance(
        query="quantum computing",
        title="Quantum computing",
        snippet="An introduction to quantum computational hardware.",
    )
    assert rel == "relevant"
    assert is_weak is False
    assert "directly matches" in reason.lower()

    # Core term in title with extract coverage
    rel, is_weak, reason = check_source_relevance(
        query="neural network",
        title="Neural network models",
        snippet="This paper reviews neural network architectures for classification.",
    )
    assert rel == "relevant"
    assert is_weak is False


def test_check_source_relevance_weak_match():
    """Verify check_source_relevance flags weakly related or peripheral sources."""
    # Only 1 of 2 terms matched
    rel, is_weak, reason = check_source_relevance(
        query="quantum cryptography",
        title="Classical cryptography",
        snippet="Historical overview of ciphers and public key algorithms.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "Weakly related" in reason

    # Zero terms matched
    rel, is_weak, reason = check_source_relevance(
        query="artificial intelligence",
        title="Baking bread",
        snippet="Flour, yeast, salt, and water are the four basic ingredients.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "Weakly related" in reason


def test_check_source_relevance_incidental_entities_and_lists():
    """
    Phase 3.3 Regression tests:
    Incidental entities/people/vendors and peripheral lists lacking query topic in title
    must be classified as weakly_relevant.
    """
    # 1. Incidental person/physicist (zero query terms in title)
    rel, is_weak, reason = check_source_relevance(
        query="quantum computing",
        title="Michael J. Biercuk",
        snippet="Michael J. Biercuk is an experimental physicist specializing in quantum computing and quantum technology.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "contains none of the query terms" in reason

    # 2. Incidental company/vendor (zero query terms in title)
    rel, is_weak, reason = check_source_relevance(
        query="quantum computing",
        title="Keysight",
        snippet="Keysight Technologies produces electronic test and measurement equipment used in quantum computing.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "contains none of the query terms" in reason

    # 3. Peripheral list article lacking core query topic in title
    rel, is_weak, reason = check_source_relevance(
        query="quantum computing",
        title="List of vacuum-tube computers",
        snippet="This is a list of vacuum-tube computers. In contrast to modern quantum computing devices...",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "index or list" in reason.lower()

    # 4. Directly relevant articles
    for directly_relevant_title in ("Quantum computing", "Quantum computer", "Quantum algorithm"):
        rel, is_weak, _ = check_source_relevance(
            query="quantum computing",
            title=directly_relevant_title,
            snippet="Overview of quantum computation and mechanical algorithms.",
        )
        assert rel == "relevant"
        assert is_weak is False


def test_check_source_relevance_phase_7c_topic_aware_matching():
    """
    Phase 7C Tests:
    1. Topic-aware matching: Handles abbreviations (AI/ML/CV), synonyms (medical/clinical for healthcare),
       and meaningful term weighting.
    2. Long queries: Avoids demanding every non-essential intent word (e.g. 'research', 'applications').
    3. Partially relevant sources: Correctly categorized as weakly_relevant with clear reasons.
    4. Unrelated sources: Correctly categorized as weakly_relevant with clear reasons.
    """
    # Case 1: Healthcare AI research (direct relevance via concept cluster & modifier handling)
    rel, is_weak, reason = check_source_relevance(
        query="healthcare AI research",
        title="Artificial Intelligence in Medicine and Healthcare: Applications and Challenges",
        snippet="This paper surveys machine learning models in clinical diagnostics, medical imaging, and patient care.",
    )
    assert rel == "relevant"
    assert is_weak is False
    assert "cover all key query terms" in reason or "substantiate core query concepts" in reason

    # Case 2: Deep learning in healthcare (synonym: deep learning for AI, healthcare in title)
    rel, is_weak, reason = check_source_relevance(
        query="healthcare artificial intelligence",
        title="Deep learning in healthcare: a review",
        snippet="Neural networks and deep learning architectures have revolutionized medical diagnostics and hospital workflows.",
    )
    assert rel == "relevant"
    assert is_weak is False

    # Case 3: Long query with intent modifiers (does not penalize missing modifier words like 'applications')
    rel, is_weak, reason = check_source_relevance(
        query="applications of artificial intelligence in healthcare",
        title="Artificial Intelligence in Healthcare: Past, Present and Future",
        snippet="We review the clinical history, current deployment, and future prospects of medical AI systems across hospitals.",
    )
    assert rel == "relevant"
    assert is_weak is False

    # Case 4: Academic paper title with domain-specific terminology (CheXNet)
    rel, is_weak, reason = check_source_relevance(
        query="healthcare artificial intelligence",
        title="CheXNet: Radiologist-Level Pneumonia Detection on Chest X-Rays with Deep Learning",
        snippet="We develop an algorithm that detects pneumonia from chest X-rays using deep convolutional neural networks.",
    )
    assert rel == "relevant"
    assert is_weak is False

    # Case 5: Long academic query (6+ words) matching core concepts without needing all modifiers
    rel, is_weak, reason = check_source_relevance(
        query="systematic literature review of deep learning approaches for healthcare diagnostics",
        title="Deep Learning for Clinical Diagnostics: A Survey",
        snippet="Neural network models applied to medical diagnostics and patient prognosis.",
    )
    assert rel == "relevant"
    assert is_weak is False

    # Case 6: Partially relevant source (mentions healthcare/spending, but zero AI/ML/computing concepts)
    rel, is_weak, reason = check_source_relevance(
        query="healthcare artificial intelligence",
        title="Healthcare expenditure in OECD countries",
        snippet="This report analyzes national health spending, hospital budgets, and public health insurance trends.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "Weakly related" in reason
    assert "lacks core query terms" in reason

    # Case 7: Partially relevant source (mentions AI/chess, but zero healthcare/medicine concepts)
    rel, is_weak, reason = check_source_relevance(
        query="healthcare artificial intelligence",
        title="A Survey of Chess-Playing Artificial Intelligence",
        snippet="An overview of minimax search algorithms, neural evaluation functions, and AlphaZero in game playing.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "Weakly related" in reason
    assert "lacks core query terms" in reason

    # Case 8: Completely unrelated source (zero concepts)
    rel, is_weak, reason = check_source_relevance(
        query="healthcare artificial intelligence",
        title="Solar Panel Photovoltaic Efficiency Trends",
        snippet="Silicon solar cells have demonstrated steady improvements in energy conversion efficiency under sunlight.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "Neither title nor extract contains query key terms" in reason


def test_check_source_relevance_phase_7d_audit_and_crossref_title_only():
    """
    Phase 7D Tests:
    1. Title-only relevant sources: Crossref records lacking open abstract metadata
       where the title substantively covers both clinical and AI concepts.
    2. Subfield hierarchy: Recognizes NLP, LLMs, Computer Vision, Transformers as AI.
    3. Specialized clinical sub-domains: Recognizes cardiovascular, oncology, surgical,
       diabetic retinopathy, chest radiography as healthcare.
    4. Directional matching: Broad parent queries accept specialized subtopics; narrow
       subtopic queries (e.g. 'pneumonia') do not cross-match sibling subtopics ('hospital').
    5. Partially relevant sources honestly identified as weakly_relevant with clear missing terms.
    6. Unrelated sources rejected.
    """
    missing_abstract_snippet = (
        "Scholarly journal article published in 'Journal of Medical Systems', DOI: 10.1007/s10916-020-01. "
        "Full abstract is not available in Crossref open metadata."
    )

    # 1. Crossref Title-only: AI + Healthcare in title with missing abstract
    crossref_cases = [
        "Artificial Intelligence in Healthcare: A Review",
        "Machine Learning in Medicine: A Practical Introduction",
        "Cardiovascular Risk Prediction Using Machine Learning Algorithms",
        "Deep Learning for Automated Detection of Diabetic Retinopathy from Fundus Photographs",
        "Large Language Models in Medicine: Hype or Hope?",
        "Computer Vision Approaches for Surgical Workflow Recognition",
        "Generative AI and Foundation Models in Healthcare: Opportunities and Challenges",
    ]
    for title in crossref_cases:
        rel, is_weak, reason = check_source_relevance(
            query="healthcare AI",
            title=title,
            snippet=missing_abstract_snippet,
        )
        assert rel == "relevant", f"Expected relevant for title '{title}', got {rel} ({reason})"
        assert is_weak is False
        assert "all query terms" in reason or "all key query terms" in reason or "core query concepts" in reason

    # 2. arXiv multi-concept coordination: Clinical task in title, AI architecture in abstract
    rel, is_weak, reason = check_source_relevance(
        query="healthcare AI",
        title="ChestX-Det: A Dataset for Chest X-ray Abnormalities Detection",
        snippet="Computer aided diagnosis using deep convolutional networks for automated detection of pulmonary diseases from radiograph scans.",
    )
    assert rel == "relevant"
    assert is_weak is False

    # 3. Directional matching: Narrow subtopic query requires that specific subtopic
    # Query 'pneumonia' should NOT match general hospital/nursing administration
    rel, is_weak, reason = check_source_relevance(
        query="pneumonia research",
        title="Hospital Nurse Shift Scheduling and Ward Management",
        snippet="A study of nursing rosters, shift duration, and bed management in an urban general hospital.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "Neither title nor extract contains query key terms" in reason

    # But query 'pneumonia' DOES match actual pneumonia research
    rel, is_weak, reason = check_source_relevance(
        query="pneumonia research",
        title="Clinical Outcomes of Pediatric Pneumonia Patients",
        snippet="A randomized trial evaluating antibiotic duration for bacterial pneumonia in hospitalized pediatric patients.",
    )
    assert rel == "relevant"
    assert is_weak is False

    # 4. Partially relevant: Pure cardiology without any AI
    rel, is_weak, reason = check_source_relevance(
        query="healthcare AI",
        title="Cardiovascular Disease Prevention and Lifestyle Intervention: Diet and Exercise in Elderly Patients",
        snippet="A prospective cohort study on dietary patterns and physical exercise for primary prevention of myocardial infarction.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "mentions 'healthcare'" in reason or "lacks core query terms 'ai'" in reason

    # 5. Partially relevant: Pure machine learning without any healthcare
    rel, is_weak, reason = check_source_relevance(
        query="healthcare AI",
        title="Recent Advances in Deep Neural Network Optimization Algorithms",
        snippet="We propose an accelerated stochastic gradient descent method for training deep transformer networks on benchmark datasets.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "mentions 'ai'" in reason or "lacks core query terms 'healthcare'" in reason

    # 6. Unrelated source: Photovoltaic solar panels
    rel, is_weak, reason = check_source_relevance(
        query="healthcare AI",
        title="Solar Panel Photovoltaic Efficiency Trends and Silicon Cell Lifespans",
        snippet="An empirical analysis of perovskite and crystalline silicon photovoltaic cells under high solar radiation.",
    )
    assert rel == "weakly_relevant"
    assert is_weak is True
    assert "Neither title nor extract contains query key terms" in reason


@pytest.mark.asyncio
async def test_fetch_page_extracts_success():
    """Verify fetch_page_extracts parses introductory extracts and resolves redirects."""
    mock_payload = {
        "query": {
            "pages": {
                "100": {
                    "pageid": 100,
                    "title": "Quantum computing",
                    "extract": "Quantum computing is a rapidly-emerging technology.",
                }
            },
            "redirects": [
                {"from": "Quantum computer", "to": "Quantum computing"}
            ]
        }
    }
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_resp

    extracts = await fetch_page_extracts(["Quantum computing", "Quantum computer"], mock_client)
    assert "quantum computing" in extracts
    assert "quantum computer" in extracts
    assert "Quantum computing is a rapidly-emerging technology." in extracts["quantum computing"]


@pytest.mark.asyncio
async def test_fetch_page_extracts_missing_page():
    """Verify fetch_page_extracts handles missing pages safely."""
    mock_payload = {
        "query": {
            "pages": {
                "-1": {
                    "ns": 0,
                    "title": "Non-existent Page",
                    "missing": "",
                }
            }
        }
    }
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_resp

    extracts = await fetch_page_extracts(["Non-existent Page"], mock_client)
    # Missing pages have empty extract string
    assert extracts.get("non-existent page", "") == ""


@pytest.mark.asyncio
async def test_fetch_page_extracts_network_error_handled():
    """Verify fetch_page_extracts returns empty dict on HTTP error without crashing."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.RequestError("Connection reset")

    extracts = await fetch_page_extracts(["Quantum computing"], mock_client)
    assert extracts == {}


@pytest.mark.asyncio
async def test_collect_research_with_extracts_and_provenance():
    """Verify collect_research merges introductory extracts and records provenance."""
    search_payload = {
        "query": {
            "search": [
                {
                    "title": "Quantum computing",
                    "snippet": "<span class=\"searchmatch\">Quantum</span> snippet...",
                    "pageid": 100,
                }
            ]
        }
    }
    extracts_payload = {
        "query": {
            "pages": {
                "100": {
                    "pageid": 100,
                    "title": "Quantum computing",
                    "extract": "Quantum computing is a rapidly-emerging technology.",
                }
            }
        }
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        httpx.Response(status_code=200, json=search_payload, request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")),
        httpx.Response(status_code=200, json=extracts_payload, request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")),
    ]

    result = await collect_research("quantum computing", limit=1, client=mock_client)
    assert result["result_count"] == 1
    item = result["results"][0]
    assert item["source_type"] == "wikipedia_extract"
    assert "rapidly-emerging technology" in item["snippet"]
    assert item["relevance"] == "relevant"
    assert item["is_weakly_relevant"] is False
    assert item["source_url"] == "https://en.wikipedia.org/wiki/Quantum_computing"
    assert "retrieved_at" in item


@pytest.mark.asyncio
async def test_collect_research_navigation_extract_fallback():
    """Verify collect_research falls back to search snippet when extract is navigation-only."""
    search_payload = {
        "query": {
            "search": [
                {
                    "title": "Quantum disambiguation",
                    "snippet": "Substantive fallback snippet describing quantum theory.",
                    "pageid": 200,
                }
            ]
        }
    }
    extracts_payload = {
        "query": {
            "pages": {
                "200": {
                    "pageid": 200,
                    "title": "Quantum disambiguation",
                    "extract": "Quantum disambiguation may refer to: jump to navigation.",
                }
            }
        }
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        httpx.Response(status_code=200, json=search_payload, request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")),
        httpx.Response(status_code=200, json=extracts_payload, request=httpx.Request("GET", "https://en.wikipedia.org/w/api.php")),
    ]

    result = await collect_research("quantum theory", limit=1, client=mock_client)
    assert result["result_count"] == 1
    item = result["results"][0]
    # Disambiguation extract filtered -> fallback to snippet
    assert item["source_type"] == "wikipedia_search_snippet"
    assert "Substantive fallback snippet" in item["snippet"]


_MULTI_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.10001v1</id>
    <published>2024-01-10T00:00:00Z</published>
    <title>Quantum Computing Algorithms</title>
    <summary>Survey of quantum computing algorithms and variational circuits.</summary>
    <author><name>Alice Quantum</name></author>
    <arxiv:doi>10.1000/arxiv.10001</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.10002v1</id>
    <published>2024-01-12T00:00:00Z</published>
    <title>Quantum Error Correction Survey</title>
    <summary>Fault-tolerant quantum computing thresholds with LDPC codes.</summary>
    <author><name>Bob Qubit</name></author>
  </entry>
</feed>
"""


def _multi_source_handler(fail_sources=None):
    fail_sources = set(fail_sources or [])

    async def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "wikipedia.org" in host:
            if "wikipedia" in fail_sources:
                return httpx.Response(503, text="Wikipedia unavailable", request=request)
            if request.url.params.get("list") == "search":
                return httpx.Response(
                    200,
                    json={
                        "query": {
                            "search": [
                                {"title": "Quantum computing", "snippet": "Quantum computing basics.", "pageid": 1},
                                {"title": "Quantum gate", "snippet": "Quantum logic gates.", "pageid": 2},
                            ]
                        }
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": {
                            "1": {"pageid": 1, "title": "Quantum computing", "extract": "Quantum computing uses qubits."},
                            "2": {"pageid": 2, "title": "Quantum gate", "extract": "Quantum gates operate on qubits."},
                        }
                    }
                },
                request=request,
            )

        if "arxiv.org" in host:
            if "arxiv" in fail_sources:
                return httpx.Response(429, headers={"Retry-After": "10"}, text="Rate limited", request=request)
            return httpx.Response(200, text=_MULTI_ARXIV_XML, request=request)

        if "crossref.org" in host:
            if "crossref" in fail_sources:
                return httpx.Response(503, text="Crossref down", request=request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "message": {
                        "items": [
                            {
                                "DOI": "10.1038/qc-2024-1",
                                "title": ["Quantum Computing Benchmarks"],
                                "abstract": "<jats:p>Benchmarking noisy intermediate-scale quantum computing devices.</jats:p>",
                                "author": [{"given": "Ada", "family": "Lovelace"}],
                                "published": {"date-parts": [[2024, 5, 1]]},
                                "URL": "https://doi.org/10.1038/qc-2024-1",
                            },
                            {
                                "DOI": "10.1038/qc-2024-2",
                                "title": ["Quantum Computing Cryogenics"],
                                "abstract": "<jats:p>Cryogenic control electronics for quantum computing.</jats:p>",
                                "author": [{"given": "Grace", "family": "Hopper"}],
                                "published": {"date-parts": [[2024, 6, 1]]},
                                "URL": "https://doi.org/10.1038/qc-2024-2",
                            },
                        ]
                    },
                },
                request=request,
            )

        raise AssertionError(f"Unexpected host in test transport: {host}")

    return handler


@pytest.mark.asyncio
async def test_collect_research_multi_source_interleaving_and_breakdown():
    """Verify multi-source collection interleaves providers round-robin and builds source_breakdown."""
    async with httpx.AsyncClient(transport=httpx.MockTransport(_multi_source_handler())) as client:
        result = await collect_research(
            "quantum computing",
            limit=4,
            client=client,
            sources=["wikipedia", "arxiv", "crossref"],
        )

    assert result["sources_requested"] == ["wikipedia", "arxiv", "crossref"]
    assert result["source_errors"] == {}
    assert result["result_count"] == 6
    providers = [item["source_name"] for item in result["results"]]
    # Round-robin order across the three sources (2 items per provider)
    assert providers == ["wikipedia", "arxiv", "crossref", "wikipedia", "arxiv", "crossref"]
    assert result["source_breakdown"] == {"wikipedia": 2, "arxiv": 2, "crossref": 2}


@pytest.mark.asyncio
async def test_collect_research_partial_source_failure():
    """Verify healthy sources still return results when one selected source fails."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_multi_source_handler(fail_sources={"crossref"}))
    ) as client:
        result = await collect_research(
            "quantum computing",
            limit=4,
            client=client,
            sources=["wikipedia", "arxiv", "crossref"],
        )

    assert result["result_count"] > 0
    assert "crossref" in result["source_errors"]
    assert "wikipedia" not in result["source_errors"]
    assert "arxiv" not in result["source_errors"]
    assert result["source_breakdown"] == {"wikipedia": 2, "arxiv": 2, "crossref": 0}


@pytest.mark.asyncio
async def test_collect_research_all_selected_sources_fail_raises():
    """Verify complete upstream failure raises the primary collector exception."""
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_multi_source_handler(fail_sources={"arxiv"}))
    ) as client:
        with pytest.raises(DataCollectorRateLimitError, match="429"):
            await collect_research("quantum computing", limit=3, client=client, sources=["arxiv"])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(_multi_source_handler(fail_sources={"wikipedia", "crossref"}))
    ) as client:
        with pytest.raises(DataCollectorUpstreamError):
            await collect_research(
                "quantum computing",
                limit=3,
                client=client,
                sources=["wikipedia", "crossref"],
            )


def test_source_selection_validation_and_normalization():
    assert validate_and_normalize_sources(None) == ["wikipedia"]
    assert validate_and_normalize_sources(["arXiv", "Wikipedia", "arxiv"]) == ["arxiv", "wikipedia"]

    with pytest.raises(ValueError, match="Unsupported"):
        validate_and_normalize_sources(["wikipedia", "unknown_db"])

    with pytest.raises(ValueError, match="Unsupported"):
        ResearchRequest(query="quantum computing", sources=["invalid_source"])


