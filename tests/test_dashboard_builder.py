"""
Unit tests for backend/agents/dashboard_builder_agent.py.
Tests the Dashboard Builder Agent in isolation: KPI generation, chart derivations,
URL safety enforcement, and schema validation.
"""

from pydantic import ValidationError
import pytest

from backend.agents.dashboard_builder_agent import (
    AGENT_CAPABILITIES,
    AGENT_NAME,
    AGENT_STATUS,
    AGENT_VERSION,
    DashboardValidationError,
    build_dashboard,
)
from backend.models.analyst import AnalysisResponse
from backend.models.dashboard import ChartDataPoint, ChartSpec, DashboardResponse


@pytest.fixture
def sample_valid_analyst_output():
    """Fixture providing a complete, valid AnalysisResponse output."""
    return {
        "agent": "Insight Analyst Agent",
        "agent_name": "Insight Analyst Agent",
        "topic": "Renewable Energy Technologies",
        "analyzed_at": "2026-03-01T12:00:00Z",
        "total_sources_evaluated": 3,
        "eligible_sources_count": 2,
        "excluded_sources_count": 1,
        "executive_summary": "Comprehensive analysis of renewable energy across 2 eligible sources.",
        "key_themes": [
            {
                "theme": "Systems, Architectures & Methods",
                "description": "Solar photovoltaics and wind turbine generation methods.",
                "frequency": 2,
                "sources": [
                    "https://en.wikipedia.org/wiki/Solar_power",
                    "https://en.wikipedia.org/wiki/Wind_power",
                ],
            },
            {
                "theme": "Foundations & Theoretical Concepts",
                "description": "Thermodynamic energy conversion efficiency.",
                "frequency": 1,
                "sources": ["https://en.wikipedia.org/wiki/Solar_power"],
            },
        ],
        "important_keywords": ["energy", "solar", "power", "wind", "technology"],
        "evidence_backed_observations": [
            {
                "statement": "According to 'Solar power': Solar power is the conversion of energy from sunlight into electricity.",
                "source_title": "Solar power",
                "source_url": "https://en.wikipedia.org/wiki/Solar_power",
                "confidence": "high",
            },
            {
                "statement": "According to 'Wind power': Wind power is the use of wind turbines to generate electricity.",
                "source_title": "Wind power",
                "source_url": "https://en.wikipedia.org/wiki/Wind_power",
                "confidence": "high",
            },
        ],
        "information_gaps": [
            "Storage and grid integration metrics are not represented in introductory snippets."
        ],
        "recommendations": [
            "Investigate battery storage technologies in primary technical literature."
        ],
        "limitations": [
            "Analysis relies on deterministic lexical extraction from Wikipedia snippets."
        ],
        "methodology": "Deterministic keyword extraction and rule-based theme clustering.",
    }


@pytest.mark.asyncio
async def test_build_dashboard_valid(sample_valid_analyst_output):
    """Verify build_dashboard produces a complete, validated dashboard specification."""
    spec = await build_dashboard(sample_valid_analyst_output)

    assert spec["agent"] == AGENT_NAME
    assert "Renewable Energy Technologies" in spec["title"]
    assert spec["topic"] == "Renewable Energy Technologies"
    assert "2 eligible sources" in spec["executive_summary"]

    # Verify 4 KPI cards
    kpis = {k["id"]: k for k in spec["kpi_cards"]}
    assert len(kpis) == 4
    assert kpis["kpi-total-sources"]["value"] == 3
    assert kpis["kpi-eligible-sources"]["value"] == 2
    assert kpis["kpi-excluded-sources"]["value"] == 1
    assert kpis["kpi-theme-count"]["value"] == 2

    # Verify charts
    charts = {c["id"]: c for c in spec["charts"]}
    assert "chart-source-eligibility" in charts
    assert charts["chart-source-eligibility"]["chart_type"] == "pie"
    assert charts["chart-source-eligibility"]["is_heuristic"] is False

    assert "chart-theme-distribution" in charts
    assert charts["chart-theme-distribution"]["chart_type"] == "horizontal_bar"
    assert charts["chart-theme-distribution"]["is_heuristic"] is True
    assert "heuristic" in charts["chart-theme-distribution"]["description"].lower()
    assert len(charts["chart-theme-distribution"]["data"]) == 2

    assert "chart-keyword-frequency" in charts
    assert charts["chart-keyword-frequency"]["chart_type"] == "bar"
    assert charts["chart-keyword-frequency"]["is_heuristic"] is True
    assert "heuristic" in charts["chart-keyword-frequency"]["description"].lower()

    # Verify observations
    assert len(spec["observations"]) == 2
    for obs in spec["observations"]:
        assert obs["source_url"].startswith("https://")

    # Verify render notice
    assert "Safe specification" in spec["render_notice"]


@pytest.mark.asyncio
async def test_build_dashboard_with_pydantic_model_input(sample_valid_analyst_output):
    """Verify build_dashboard accepts an AnalysisResponse Pydantic instance."""
    analyst_model = AnalysisResponse(**sample_valid_analyst_output)
    spec = await build_dashboard(analyst_model)

    assert spec["topic"] == "Renewable Energy Technologies"
    assert len(spec["kpi_cards"]) == 4


@pytest.mark.asyncio
async def test_build_dashboard_empty_evidence():
    """Verify build_dashboard handles analysis with 0 eligible evidence safely."""
    payload = {
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
        "information_gaps": ["No verified data available."],
        "recommendations": ["Broaden query terms."],
        "limitations": ["Analysis halted due to lack of verified sources."],
        "methodology": "Deterministic lexical heuristics.",
    }

    spec = await build_dashboard(payload)

    kpis = {k["id"]: k for k in spec["kpi_cards"]}
    assert kpis["kpi-total-sources"]["value"] == 2
    assert kpis["kpi-eligible-sources"]["value"] == 0
    assert kpis["kpi-excluded-sources"]["value"] == 2
    assert kpis["kpi-theme-count"]["value"] == 0

    assert spec["observations"] == []
    # Keyword chart is omitted when 0 eligible sources
    chart_ids = [c["id"] for c in spec["charts"]]
    assert "chart-keyword-frequency" not in chart_ids


@pytest.mark.asyncio
async def test_build_dashboard_empty_themes(sample_valid_analyst_output):
    """Verify theme chart is safely omitted when no themes are identified."""
    sample_valid_analyst_output["key_themes"] = []
    spec = await build_dashboard(sample_valid_analyst_output)

    kpis = {k["id"]: k for k in spec["kpi_cards"]}
    assert kpis["kpi-theme-count"]["value"] == 0

    chart_ids = [c["id"] for c in spec["charts"]]
    assert "chart-theme-distribution" not in chart_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("unsafe_url", [
    "javascript:alert('xss')",
    "http://insecure.wikipedia.org/wiki/Test",
    "data:text/html;base64,PHNjcmlwdD4=",
    "ftp://wikipedia.org/file",
    "not-a-url",
    "",
])
async def test_build_dashboard_unsafe_urls(sample_valid_analyst_output, unsafe_url):
    """Verify build_dashboard rejects observations with non-HTTPS or unsafe URLs."""
    sample_valid_analyst_output["evidence_backed_observations"] = [
        {
            "statement": "An observation with an unsafe URL citation.",
            "source_title": "Unsafe Link",
            "source_url": unsafe_url,
            "confidence": "high",
        }
    ]

    with pytest.raises(DashboardValidationError) as exc:
        await build_dashboard(sample_valid_analyst_output)
    assert "unsafe source url" in str(exc.value).lower() or "missing or empty" in str(exc.value).lower() or "malformed" in str(exc.value).lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_field,invalid_value", [
    ("topic", ""),
    ("topic", "   "),
    ("executive_summary", ""),
    ("total_sources_evaluated", -1),
    ("eligible_sources_count", -5),
    ("excluded_sources_count", -1),
    ("evidence_backed_observations", "not-a-list"),
])
async def test_build_dashboard_malformed_inputs(sample_valid_analyst_output, invalid_field, invalid_value):
    """Verify build_dashboard rejects malformed analyst payload attributes."""
    sample_valid_analyst_output[invalid_field] = invalid_value

    with pytest.raises(DashboardValidationError):
        await build_dashboard(sample_valid_analyst_output)


def test_chart_spec_pydantic_validation():
    """Verify ChartSpec enforces allowed chart types and positive numeric values."""
    # Valid chart types
    for valid_type in ["bar", "pie", "horizontal_bar"]:
        chart = ChartSpec(
            id="test-chart",
            title="Valid Chart",
            chart_type=valid_type,
            description="A test description.",
            data=[ChartDataPoint(label="Point A", value=10.5)],
        )
        assert chart.chart_type == valid_type

    # Disallowed chart type
    with pytest.raises(ValidationError):
        ChartSpec(
            id="test-chart",
            title="Invalid Chart",
            chart_type="scatter",  # Disallowed
            description="A test description.",
            data=[ChartDataPoint(label="Point A", value=10.5)],
        )

    # Negative value in data point
    with pytest.raises(ValidationError):
        ChartDataPoint(label="Negative Point", value=-5.0)


def test_builder_agent_metadata():
    """Verify metadata constants of the Dashboard Builder Agent."""
    assert AGENT_NAME == "Dashboard Builder Agent"
    assert AGENT_STATUS == "operational"
    assert AGENT_VERSION == "1.0.0"
    assert "dashboard_specification_generation" in AGENT_CAPABILITIES
    assert "kpi_metric_synthesis" in AGENT_CAPABILITIES
    assert "chart_specification_derivation" in AGENT_CAPABILITIES
    assert "url_safety_enforcement" in AGENT_CAPABILITIES


@pytest.mark.asyncio
async def test_phase_3_4_three_themes_propagated_and_counts_match(sample_valid_analyst_output):
    """
    Phase 3.4 Regression test:
    Verify when analyst outputs 3 themes, dashboard propagates all 3 themes into both
    'themes' and 'key_themes' with names and evidence counts, KPI count matches,
    and chart theme distribution matches without dropping themes to [].
    """
    sample_valid_analyst_output["key_themes"] = [
        {
            "theme": "Neural Architectures",
            "description": "Deep multilayer feed-forward and recurrent architectures.",
            "frequency": 3,
            "sources": [
                "https://en.wikipedia.org/wiki/Artificial_neural_network",
                "https://en.wikipedia.org/wiki/Deep_learning",
                "https://en.wikipedia.org/wiki/Convolutional_neural_network",
            ],
        },
        {
            "theme": "Training & Optimization",
            "description": "Backpropagation and stochastic gradient descent methods.",
            "frequency": 2,
            "sources": [
                "https://en.wikipedia.org/wiki/Artificial_neural_network",
                "https://en.wikipedia.org/wiki/Backpropagation",
            ],
        },
        {
            "theme": "Hardware Acceleration",
            "description": "GPU and TPU parallel matrix processing.",
            "frequency": 1,
            "sources": ["https://en.wikipedia.org/wiki/Tensor_Processing_Unit"],
        },
    ]

    spec = await build_dashboard(sample_valid_analyst_output)

    # Dashboard must populate both 'themes' and 'key_themes' identically
    assert len(spec["themes"]) == 3
    assert len(spec["key_themes"]) == 3
    assert spec["dashboard_id"].startswith("dash-")
    assert spec["metadata"]["theme_count"] == 3

    expected = [
        ("Neural Architectures", 3),
        ("Training & Optimization", 2),
        ("Hardware Acceleration", 1),
    ]
    for item, (exp_name, exp_count) in zip(spec["themes"], expected):
        assert item["theme"] == exp_name
        assert item["name"] == exp_name
        assert item["frequency"] == exp_count
        assert item["evidence_count"] == exp_count
        assert len(item["sources"]) == exp_count

    # Overview/Dashboard KPI must match
    kpis = {k["id"]: k for k in spec["kpi_cards"]}
    assert kpis["kpi-theme-count"]["value"] == 3

    # Theme chart must reflect all 3 themes & values and retain heuristic flag
    charts = {c["id"]: c for c in spec["charts"]}
    theme_chart = charts["chart-theme-distribution"]
    assert theme_chart["is_heuristic"] is True
    assert [(d["label"], d["value"]) for d in theme_chart["data"]] == [
        ("Neural Architectures", 3.0),
        ("Training & Optimization", 2.0),
        ("Hardware Acceleration", 1.0),
    ]


@pytest.mark.asyncio
async def test_phase_3_4_empty_themes_honest_handling(sample_valid_analyst_output):
    """
    Phase 3.4 Regression test:
    Verify empty analyst themes produce themes=[], key_themes=[], KPI=0, and no fabricated theme chart.
    """
    sample_valid_analyst_output["key_themes"] = []
    spec = await build_dashboard(sample_valid_analyst_output)

    assert spec["themes"] == []
    assert spec["key_themes"] == []
    assert spec["metadata"]["theme_count"] == 0

    kpis = {k["id"]: k for k in spec["kpi_cards"]}
    assert kpis["kpi-theme-count"]["value"] == 0

    chart_ids = [c["id"] for c in spec["charts"]]
    assert "chart-theme-distribution" not in chart_ids

