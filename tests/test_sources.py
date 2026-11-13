"""
Unit tests for arXiv and Crossref research source clients.
Tests Atom XML / REST JSON parsing, normalization, error handling, rate limits,
DTD safety, and empty results using deterministic mock HTTP transports.
"""

import httpx
import pytest

from backend.services.sources import (
    DataCollectorRateLimitError,
    DataCollectorResponseError,
    DataCollectorTimeoutError,
    DataCollectorUpstreamError,
    normalize_doi,
    search_arxiv,
    search_crossref,
)


ARXIV_VALID_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title type="html">ArXiv Query: all:quantum computing</title>
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <updated>2024-02-01T12:00:00Z</updated>
    <published>2024-01-22T09:30:00Z</published>
    <title>Fault-Tolerant Quantum   Computing
      with Surface Codes</title>
    <summary>  We analyze &lt;b&gt;quantum error correction&lt;/b&gt; thresholds in
      scalable superconducting lattices [1].  </summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Chen</name></author>
    <arxiv:doi>10.1103/PhysRevLett.132.010501</arxiv:doi>
    <link href="http://arxiv.org/abs/2401.12345v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.12345v1" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.00001v1</id>
    <updated>2024-02-02T08:00:00Z</updated>
    <title>Topological Qubits in Quantum Computing</title>
    <summary></summary>
    <author><name>Carol Nguyen</name></author>
  </entry>
</feed>
"""


ARXIV_EMPTY_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>ArXiv Query: all:zzzznonexistent</title>
</feed>
"""


ARXIV_ERROR_ENTRY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format_for_abc</id>
    <title>Error</title>
    <summary>incorrect id format for abc</summary>
  </entry>
</feed>
"""


def _make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_search_arxiv_valid_atom_xml():
    """Verify valid Atom XML is parsed with HTTPS upgrade, DOI, authors, dates, and cleaned abstract."""
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search_query"] == "all:quantum computing"
        assert request.url.params["max_results"] == "5"
        return httpx.Response(200, text=ARXIV_VALID_ATOM_XML)

    async with _make_client(handler) as client:
        items = await search_arxiv(
            "quantum computing",
            limit=5,
            client=client,
            retrieved_at="2026-01-01T00:00:00+00:00",
        )

    assert len(items) == 2

    first = items[0]
    assert first["title"] == "Fault-Tolerant Quantum Computing with Surface Codes"
    assert first["source_name"] == "arxiv"
    assert first["source_type"] == "arxiv_paper"
    assert first["source_url"] == "https://arxiv.org/abs/2401.12345v1"
    assert first["source"] == first["source_url"]
    assert first["publication_date"] == "2024-01-22"
    assert first["doi"] == "10.1103/PhysRevLett.132.010501"
    assert first["authors"] == ["Alice Smith", "Bob Chen"]
    assert "quantum error correction" in first["snippet"]
    assert "<b>" not in first["snippet"]
    assert "[1]" not in first["snippet"]
    assert first["abstract"] == first["snippet"]
    assert first["retrieved_at"] == "2026-01-01T00:00:00+00:00"
    assert first["is_weakly_relevant"] is False

    second = items[1]
    # Falls back to entry <id> upgraded to https:// and synthesizes safe fallback snippet when summary empty
    assert second["source_url"] == "https://arxiv.org/abs/2402.00001v1"
    assert second["publication_date"] == "2024-02-02"
    assert second["doi"] is None
    assert second["authors"] == ["Carol Nguyen"]
    assert "Topological Qubits in Quantum Computing" in second["snippet"]


@pytest.mark.asyncio
async def test_search_arxiv_empty_feed():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ARXIV_EMPTY_ATOM_XML)

    async with _make_client(handler) as client:
        items = await search_arxiv("zzzznonexistent", limit=5, client=client)

    assert items == []


@pytest.mark.asyncio
async def test_search_arxiv_timeout():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorTimeoutError, match="timed out"):
            await search_arxiv("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_arxiv_rate_limit_429():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "15"}, text="Too Many Requests")

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorRateLimitError, match="Retry after 15s"):
            await search_arxiv("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_arxiv_http_500():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorUpstreamError, match="HTTP status 500"):
            await search_arxiv("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_arxiv_malformed_xml():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<feed><entry><title>broken")

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorResponseError, match="malformed XML"):
            await search_arxiv("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_arxiv_rejects_dtd_entity():
    dtd_payload = """<?xml version="1.0"?>
<!DOCTYPE feed [<!ENTITY xxe "boom">]>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=dtd_payload)

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorResponseError, match="DTD/ENTITY"):
            await search_arxiv("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_arxiv_api_error_entry():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ARXIV_ERROR_ENTRY_XML)

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorResponseError, match="arXiv API returned error entry"):
            await search_arxiv("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_crossref_valid_json_abstract_and_fallback():
    """Verify Crossref parses JATS abstracts, metadata fallback, DOI normalization, authors, and dates."""
    payload = {
        "status": "ok",
        "message": {
            "items": [
                {
                    "DOI": "https://doi.org/10.1038/s41586-024-07000-1",
                    "title": ["<i>Quantum Computing</i> Error Mitigation"],
                    "abstract": "<jats:p>Experimental study of quantum computing error mitigation in noisy processors.</jats:p>",
                    "author": [
                        {"given": "Ada", "family": "Lovelace"},
                        {"name": "Quantum Research Consortium"},
                    ],
                    "published": {"date-parts": [[2024, 3, 14]]},
                    "URL": "http://dx.doi.org/10.1038/s41586-024-07000-1",
                    "container-title": ["Nature"],
                    "type": "journal-article",
                },
                {
                    "DOI": "doi:10.1145/1234567.890",
                    "title": ["Quantum Computing Hardware Review"],
                    "author": [{"given": "Alan", "family": "Turing"}],
                    "issued": {"date-parts": [[2023, 11]]},
                    "container-title": ["ACM Computing Surveys"],
                    "type": "review-article",
                },
            ]
        },
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "quantum computing"
        assert request.url.params["rows"] == "5"
        return httpx.Response(200, json=payload)

    async with _make_client(handler) as client:
        items = await search_crossref(
            "quantum computing",
            limit=5,
            client=client,
            retrieved_at="2026-01-01T00:00:00+00:00",
        )

    assert len(items) == 2

    first = items[0]
    assert first["title"] == "Quantum Computing Error Mitigation"
    assert first["source_name"] == "crossref"
    assert first["source_type"] == "crossref_abstract"
    assert first["doi"] == "10.1038/s41586-024-07000-1"
    assert first["source_url"] == "https://doi.org/10.1038/s41586-024-07000-1"
    assert first["publication_date"] == "2024-03-14"
    assert first["authors"] == ["Ada Lovelace", "Quantum Research Consortium"]
    assert "<jats:p>" not in first["snippet"]
    assert "error mitigation" in first["snippet"].lower()

    second = items[1]
    assert second["source_name"] == "crossref"
    assert second["source_type"] == "crossref_work"
    assert second["doi"] == "10.1145/1234567.890"
    assert second["source_url"] == "https://doi.org/10.1145/1234567.890"
    assert second["publication_date"] == "2023-11"
    assert second["authors"] == ["Alan Turing"]
    assert "ACM Computing Surveys" in second["snippet"]
    assert "Full abstract is not available in Crossref open metadata" in second["snippet"]


@pytest.mark.asyncio
async def test_search_crossref_empty_items():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok", "message": {"items": []}})

    async with _make_client(handler) as client:
        items = await search_crossref("nonexistent", limit=5, client=client)

    assert items == []


@pytest.mark.asyncio
async def test_search_crossref_timeout():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorTimeoutError, match="timed out"):
            await search_crossref("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_crossref_rate_limit_429():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"}, text="Rate limited")

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorRateLimitError, match="Retry after 30s"):
            await search_crossref("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_crossref_http_503():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorUpstreamError, match="HTTP status 503"):
            await search_crossref("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_crossref_malformed_json():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="{not valid json")

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorResponseError, match="invalid JSON"):
            await search_crossref("quantum computing", client=client)


@pytest.mark.asyncio
async def test_search_crossref_unexpected_structure():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok", "message": {"items": "bad"}})

    async with _make_client(handler) as client:
        with pytest.raises(DataCollectorResponseError, match="not a list"):
            await search_crossref("quantum computing", client=client)


def test_normalize_doi_variants():
    assert normalize_doi("https://doi.org/10.1000/xyz123") == "10.1000/xyz123"
    assert normalize_doi("http://dx.doi.org/10.1000/xyz123") == "10.1000/xyz123"
    assert normalize_doi("doi: 10.1000/xyz123") == "10.1000/xyz123"
    assert normalize_doi("   ") is None
    assert normalize_doi(None) is None

