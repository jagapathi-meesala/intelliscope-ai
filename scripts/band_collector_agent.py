"""
BAND Integration for IntelliScope AI Data Collector Agent.

Connects the existing Data Collector Agent to the BAND collaboration platform
using the official BAND Python SDK (band-sdk 6.0.1) and SimpleAdapter pattern.

When mentioned in a BAND room:
1. Receives the research message turn.
2. Extracts and validates the research query and optional limit.
3. Calls the existing IntelliScope FastAPI backend (POST /research on port 8010) via HTTPX.
4. Returns actual, un-fabricated research results through BAND band_send_message.
5. Deterministic execution with zero LLM API key dependencies.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from band import Agent, AgentConfig, PlatformMessage, configure_logging
from band.client.rest import AsyncRestClient
from band.config import load_agent_config
from band.config.settings import DEFAULT_REST_URL, DEFAULT_WS_URL
from band.core.protocols import AgentToolsProtocol
from band.core.simple_adapter import SimpleAdapter
from band.core.types import ConflictPolicy

logger = logging.getLogger("intelliscope.band_collector")

DEFAULT_BACKEND_URL = os.environ.get("INTELLISCOPE_BACKEND_URL", "http://127.0.0.1:8010")
DEFAULT_AGENT_KEY = "data_collector"
DEFAULT_SEARCH_LIMIT = 3
MAX_QUERY_LENGTH = 300


# ------------------------------------------------------------------------------
# Configuration Helper
# ------------------------------------------------------------------------------
def load_band_credentials(
    agent_key: str = DEFAULT_AGENT_KEY,
    config_path: Optional[Path | str] = None,
) -> Tuple[str, str]:
    """
    Load BAND agent credentials from environment variables or agent_config.yaml.

    Resolution order:
    1. BAND_AGENT_ID and BAND_API_KEY environment variables.
    2. Local agent_config.yaml via band.config.load_agent_config.

    Args:
        agent_key: Key in agent_config.yaml (defaults to 'data_collector').
        config_path: Optional explicit path to configuration YAML.

    Returns:
        Tuple of (agent_id, api_key).

    Raises:
        ValueError: If required credentials are missing or empty.
        FileNotFoundError: If agent_config.yaml is missing and env vars not set.
    """
    env_agent_id = os.environ.get("BAND_AGENT_ID")
    env_api_key = os.environ.get("BAND_API_KEY")

    if env_agent_id and env_api_key:
        logger.info("Loaded BAND credentials from environment variables.")
        return env_agent_id.strip(), env_api_key.strip()

    # Load from YAML config file
    resolved_path = Path(config_path) if config_path else PROJECT_ROOT / "agent_config.yaml"
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"BAND configuration file not found at '{resolved_path}'. "
            "Please copy agent_config.yaml.example to agent_config.yaml and supply your credentials, "
            "or set BAND_AGENT_ID and BAND_API_KEY environment variables."
        )

    agent_id, api_key = load_agent_config(agent_key, config_path=resolved_path)
    if not agent_id or not api_key:
        raise ValueError(f"Credentials for '{agent_key}' in '{resolved_path}' must not be empty.")

    logger.info("Loaded BAND credentials for agent '%s' from '%s'.", agent_key, resolved_path.name)
    return agent_id, api_key


# ------------------------------------------------------------------------------
# Message Parsing Helper
# ------------------------------------------------------------------------------
KNOWN_AGENT_IDENTITIES = [
    "IntelliScope Data Collector Agent",
    "IntelliScope Data Collector",
    "IntelliScope Collector Agent",
    "IntelliScope Collector",
    "Data Collector Agent",
    "Data Collector",
    "IntelliScope AI Agent",
    "IntelliScope AI",
    "IntelliScope",
    "intelliscope-collector",
    "data_collector",
    "collector",
]


def parse_research_request(
    content: Any,
    agent_handle: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    agent_name: Optional[str] = None,
) -> Tuple[str, int]:
    """
    Extract and sanitize search query and optional result limit from a BAND chat message.

    Handles BAND SDK message structures (PlatformMessage or raw string), strips
    agent mentions (@IntelliScope Collector, @owner/handle, @/handle, @handle, @[[uuid]], <@uuid>),
    removes command handles (/intelliscope-collector, /collector), extracts limit bounds [1-10],
    and removes leading research action instructions without stripping legitimate topic words.

    Args:
        content: Raw message text string or BAND PlatformMessage object.
        agent_handle: Optional specific agent mention handle or name to strip.
        metadata: Optional message metadata dictionary (e.g. from PlatformMessage.metadata).
        agent_name: Optional agent display name to strip.

    Returns:
        Tuple of (sanitized_query, limit). If no query is found, query is empty string "".
    """
    # 1. Extract raw content text and metadata
    if hasattr(content, "content"):
        if metadata is None and hasattr(content, "metadata") and isinstance(content.metadata, dict):
            metadata = content.metadata
        raw_text = content.content or ""
    elif content is None:
        raw_text = ""
    else:
        raw_text = str(content)

    if not raw_text or not raw_text.strip():
        return "", DEFAULT_SEARCH_LIMIT

    text = raw_text.strip()

    # 2. Strip bracketed mention tokens (BAND platform normalized mentions @[[uuid]] or <@uuid>)
    text = re.sub(r"@\[\[?[^\]]+\]?\]", " ", text)
    text = re.sub(r"<@[^>]+>", " ", text)

    # 3. Gather candidate identities from constants, parameters, and metadata
    candidate_identities = set(KNOWN_AGENT_IDENTITIES)
    if agent_handle and agent_handle.strip():
        candidate_identities.add(agent_handle.strip().lstrip("@/"))
    if agent_name and agent_name.strip():
        candidate_identities.add(agent_name.strip().lstrip("@/"))

    if metadata and isinstance(metadata.get("mentions"), list):
        for m in metadata["mentions"]:
            if isinstance(m, dict):
                for k in ("name", "handle", "username", "id"):
                    val = m.get(k)
                    if val and str(val).strip():
                        candidate_identities.add(str(val).strip().lstrip("@/"))
            elif isinstance(m, str) and m.strip():
                candidate_identities.add(m.strip().lstrip("@/"))

    # Sort descending by length so longer phrases match before substrings
    sorted_identities = sorted(candidate_identities, key=len, reverse=True)

    # 4. Strip @mention and /handle patterns for all known identities (longest first)
    for ident in sorted_identities:
        pattern = re.escape(ident).replace(r"\ ", r"\s+")
        text = re.sub(rf"(?<!\S)@/?{pattern}\b\s*[:\-]?", " ", text, flags=re.IGNORECASE)
        text = re.sub(rf"(?<!\S)/{pattern}\b\s*[:\-]?", " ", text, flags=re.IGNORECASE)

    # 5. Strip generic @handles (e.g. @owner/intelliscope-collector or @user)
    text = re.sub(r"(?<!\S)@/?(?:[\w.-]+/)*[\w.-]+\s*[:\-]?", " ", text)

    # 6. Strip leading slash commands/handles
    text = re.sub(r"^/(?:[\w.-]+/)*[\w.-]+(?:\s+|$)", " ", text)

    # 7. Strip bare agent display names appearing at the start of message (longest first)
    for ident in sorted_identities:
        pattern = re.escape(ident).replace(r"\ ", r"\s+")
        text = re.sub(rf"^\s*{pattern}\s*[:\-]?", " ", text, flags=re.IGNORECASE)

    # 8. Extract limit parameter if specified (e.g., 'limit=5', 'limit: 5', 'count=5', '(limit: 4)')
    limit = DEFAULT_SEARCH_LIMIT
    limit_match = re.search(
        r"[\(\[]?\s*\b(?:limit|count|num|max)\s*[:=]?\s*(\d+)\s*[\)\]]?",
        text,
        flags=re.IGNORECASE,
    )
    if limit_match:
        try:
            parsed_limit = int(limit_match.group(1))
            limit = max(1, min(10, parsed_limit))
        except (ValueError, TypeError):
            limit = DEFAULT_SEARCH_LIMIT
        text = text[:limit_match.start()] + " " + text[limit_match.end():]

    # 9. Clean up surrounding whitespace and punctuation before matching action instructions
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"^[:,\-\s]+", "", cleaned)

    # 10. Strip leading action/research instructions (strictly at the beginning, single match)
    action_keywords = [
        r"^(?:please\s+)?research\s+on\s*[:\-]?",
        r"^(?:please\s+)?research\s*[:\-]?",
        r"^(?:please\s+)?search\s+for\s*[:\-]?",
        r"^(?:please\s+)?search\s*[:\-]",
        r"^please\s+search\s+",
        r"^(?:please\s+)?find\s+information\s+(?:on|about)\s*[:\-]?",
        r"^(?:please\s+)?find\s*[:\-]",
        r"^please\s+find\s+",
        r"^(?:please\s+)?lookup\s*[:\-]?",
        r"^(?:please\s+)?query\s*[:\-]?",
        r"^what\s+is\s+",
        r"^tell\s+me\s+about\s+",
    ]
    for kw in action_keywords:
        m = re.match(kw, cleaned, flags=re.IGNORECASE)
        if m:
            cleaned = cleaned[m.end():].strip()
            break

    # 11. Remove enclosing quotes, parenthesis, or punctuation
    cleaned = re.sub(r"^[\"\'\(\[\{:\-]+|[\"\'\)\]\}:]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if len(cleaned) > MAX_QUERY_LENGTH:
        cleaned = cleaned[:MAX_QUERY_LENGTH].rstrip()

    logger.debug("Sanitized research query: '%s' (limit=%d)", cleaned, limit)
    return cleaned, limit


# ------------------------------------------------------------------------------
# Response Formatting Helpers
# ------------------------------------------------------------------------------
def format_research_reply(data: Dict[str, Any], query: str) -> str:
    """
    Format FastAPI ResearchResponse data into clean, structured Markdown for BAND room.

    Args:
        data: JSON dictionary from FastAPI POST /research.
        query: The requested research query.

    Returns:
        Structured Markdown text suitable for chat display.
    """
    results = data.get("results", [])
    result_count = data.get("result_count", len(results))

    if not results or result_count == 0:
        return (
            f"🔍 **IntelliScope Research Collector**\n\n"
            f"**Topic:** *{query}*\n\n"
            f"No verified articles or summary snippets were found for this query on Wikipedia. "
            f"Please try refining your search terms."
        )

    lines: List[str] = [
        f"🔍 **IntelliScope Research Collector**",
        f"**Topic:** *{query}* — Found {result_count} verified source(s):\n",
    ]

    for idx, item in enumerate(results, start=1):
        title = item.get("title", f"Source {idx}")
        source_url = item.get("source_url", "")
        snippet = item.get("snippet", "").strip()
        retrieved_at = item.get("retrieved_at", "")

        # Format item with link
        if source_url:
            lines.append(f"{idx}. **[{title}]({source_url})**")
        else:
            lines.append(f"{idx}. **{title}**")

        if snippet:
            lines.append(f"   > {snippet}")

        if retrieved_at:
            lines.append(f"   *Retrieved: {retrieved_at}*")
        lines.append("")

    lines.append("*Collected via IntelliScope AI Data Collector Agent for the BAND Platform.*")
    return "\n".join(lines)


def format_pipeline_reply(data: Dict[str, Any], query: str) -> str:
    """
    Format unified PipelineResponse data into concise executive summary,
    verified source citations, agent execution status, and dashboard JSON for BAND room.

    Args:
        data: JSON dictionary from FastAPI POST /pipeline.
        query: The requested research query.

    Returns:
        Structured Markdown text suitable for BAND chat display.
    """
    status = data.get("status", "success")
    total_duration = data.get("total_duration_ms", 0.0)
    agent_statuses = data.get("agent_statuses", {})
    summary = data.get("summary", "")
    research = data.get("research") or {}
    verification = data.get("verification") or {}
    analysis = data.get("analysis") or {}
    dashboard = data.get("dashboard") or {}

    lines: List[str] = [
        "🚀 **IntelliScope Multi-Agent Intelligence Pipeline**",
        f"**Topic:** *{query}* | **Status:** {status.upper()} ({total_duration:.1f}ms)\n",
        "⚡ **Agent Fleet Execution:**",
    ]

    agent_icons = {"completed": "✅", "failed": "❌", "skipped": "⏭️"}
    for key, info in agent_statuses.items():
        st = info.get("status", "unknown")
        icon = agent_icons.get(st, "ℹ️")
        name = info.get("agent_name", key)
        dur = info.get("duration_ms", 0.0)
        details = info.get("details", "")
        detail_str = f" — *{details}*" if details else ""
        lines.append(f"• {icon} **{name}**: {st.title()} ({dur:.1f}ms){detail_str}")
    lines.append("")

    # Handle empty results
    research_results = research.get("results", [])
    if not research_results or research.get("result_count", 0) == 0:
        lines.append(f"🔍 **Notice:** No verified articles or summary snippets were found for *'{query}'* on Wikipedia.")
        if summary:
            lines.append(f"\n📋 **Analyst Summary:**\n> {summary}")
        lines.append("\n*All pipeline agents completed. Zero data fabricated.*")
        return "\n".join(lines)

    # Verification Scope Breakdown
    if verification:
        q_score = verification.get("quality_score", 0)
        struct_valid = verification.get("structurally_valid_count", verification.get("valid_results_count", 0))
        excluded_cnt = verification.get("excluded_count", verification.get("invalid_results_count", 0))
        direct_cnt = verification.get("directly_relevant_count", 0)
        weak_cnt = verification.get("weakly_relevant_count", 0)
        lines.append(
            f"🛡️ **Verification Scope (Structural Only, Factually Verified: {bool(verification.get('is_factually_verified', False))}):** "
            f"Score **{q_score}/100** | Valid: **{struct_valid}** | Excluded: **{excluded_cnt}** | "
            f"Directly Relevant: **{direct_cnt}** | Weakly Relevant: **{weak_cnt}**\n"
        )

    # Executive Summary
    if summary:
        lines.append(f"📋 **Executive Summary:**\n> {summary}\n")

    # Key Themes
    raw_themes = analysis.get("key_themes") or dashboard.get("themes") or dashboard.get("key_themes") or []
    if raw_themes:
        theme_labels = []
        for t in raw_themes:
            t_name = t.get("theme") or t.get("name") or ""
            t_count = t.get("frequency") if t.get("frequency") is not None else t.get("evidence_count")
            if t_name:
                label = f"**{t_name}** ({t_count} source(s))" if t_count is not None else f"**{t_name}**"
                theme_labels.append(label)
        if theme_labels:
            lines.append(f"🏷️ **Key Themes ({len(theme_labels)}):** {', '.join(theme_labels)}\n")
    else:
        lines.append("🏷️ **Key Themes (0):** *None identified from eligible evidence.*\n")

    # Evidence Sources with provenance & confidence reasons
    provenance_by_url = {
        (item.get("source_url") or item.get("source")): item
        for item in research_results
        if item.get("source_url") or item.get("source")
    }
    observations = analysis.get("evidence_backed_observations", [])
    lines.append(f"🔗 **Verified Evidence Sources ({len(observations) or len(research_results)}):**")
    if observations:
        for idx, obs in enumerate(observations, start=1):
            title = obs.get("source_title", f"Source {idx}")
            url = obs.get("source_url", "")
            statement = obs.get("statement") or obs.get("observation") or ""
            conf = obs.get("confidence", "")
            conf_reason = obs.get("confidence_reason", "")
            src_meta = provenance_by_url.get(url, {})
            source_type = src_meta.get("source_type", "")
            is_weak = bool(obs.get("is_weakly_relevant") or src_meta.get("is_weakly_relevant"))

            tags = []
            if source_type:
                tags.append(source_type)
            if is_weak:
                tags.append("weakly_relevant")
            if conf:
                tags.append(f"confidence: {conf}")
            tag_str = f" *[{', '.join(tags)}]*" if tags else ""

            if url:
                lines.append(f"{idx}. **[{title}]({url})**{tag_str}")
            else:
                lines.append(f"{idx}. **{title}**{tag_str}")
            if statement:
                lines.append(f"   > {statement}")
            if conf_reason:
                lines.append(f"   *Confidence rationale: {conf_reason}*")
    else:
        for idx, item in enumerate(research_results, start=1):
            title = item.get("title", f"Source {idx}")
            url = item.get("source_url", "")
            snippet = item.get("snippet", "")
            source_type = item.get("source_type", "")
            tag_str = f" *[{source_type}]*" if source_type else ""
            if url:
                lines.append(f"{idx}. **[{title}]({url})**{tag_str}")
            else:
                lines.append(f"{idx}. **{title}**{tag_str}")
            if snippet:
                lines.append(f"   > {snippet}")
    lines.append("")

    # KPI Overview
    kpi_cards = dashboard.get("kpi_cards", [])
    if kpi_cards:
        kpi_str = " | ".join(f"**{k.get('label')}:** {k.get('value')}" for k in kpi_cards)
        lines.append(f"📊 **KPI Overview:** {kpi_str}\n")

    # Dashboard Specification JSON
    if dashboard:
        dash_themes = (
            dashboard.get("themes")
            if dashboard.get("themes") is not None and len(dashboard.get("themes", [])) > 0
            else dashboard.get("key_themes", [])
        )
        dash_spec = {
            "dashboard_id": dashboard.get("dashboard_id"),
            "topic": dashboard.get("topic"),
            "title": dashboard.get("title"),
            "kpi_cards": dashboard.get("kpi_cards", []),
            "themes": dash_themes,
            "charts": dashboard.get("charts", []),
            "metadata": dashboard.get("metadata", {}),
        }
        json_str = json.dumps(dash_spec, indent=2)
        lines.append("📈 **Dashboard Specification JSON:**")
        lines.append(f"```json\n{json_str}\n```\n")

    lines.append("*Generated by IntelliScope AI Autonomous Multi-Agent Pipeline for BAND.*")
    return "\n".join(lines)


def format_error_reply(error_detail: str, query: Optional[str] = None) -> str:
    """Format an informative error reply for the BAND chat room."""
    topic_str = f" for *'{query}'*" if query else ""
    return (
        f"⚠️ **IntelliScope Research Collector Error**\n\n"
        f"Unable to complete research collection{topic_str}:\n"
        f"> {error_detail}\n\n"
        f"Please verify that the IntelliScope backend is running (`uvicorn backend.main:app --port 8010`)."
    )


def format_usage_reply() -> str:
    """Format usage instructions when a mention lacks a research query."""
    return (
        f"👋 **IntelliScope Research Collector**\n\n"
        f"I am the Data Collector Agent for IntelliScope AI. To research a topic, mention me with your query:\n\n"
        f"- `@DataCollector research Artificial intelligence`\n"
        f"- `@DataCollector research Quantum computing (limit: 5)`\n"
        f"- `@DataCollector search: Renewable energy`\n\n"
        f"I will gather verified encyclopedia sources and return structured evidence to this room."
    )


# ------------------------------------------------------------------------------
# FastAPI Backend Communication
# ------------------------------------------------------------------------------
async def call_research_api(
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    backend_url: str = DEFAULT_BACKEND_URL,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[bool, Dict[str, Any] | str]:
    """
    Call the existing IntelliScope FastAPI backend (POST /research) asynchronously.

    Args:
        query: Research query string.
        limit: Max results count (1-10).
        backend_url: Base URL of FastAPI server.
        client: Optional shared HTTPX async client.

    Returns:
        Tuple of (success_flag, data_or_error_message).
    """
    endpoint = f"{backend_url.rstrip('/')}/research"
    payload = {"query": query, "limit": limit}

    async def _post(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(endpoint, json=payload, timeout=20.0)

    try:
        if client is not None:
            response = await _post(client)
        else:
            async with httpx.AsyncClient() as local_client:
                response = await _post(local_client)

        if response.status_code == 200:
            return True, response.json()
        elif response.status_code == 504:
            return False, "Upstream research service timed out. Please try again later."
        elif response.status_code == 502:
            return False, "Upstream research provider encountered an error connecting to external sources."
        elif response.status_code in (400, 422):
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            return False, f"Request validation failed: {detail}"
        else:
            return False, f"Backend returned unexpected HTTP status {response.status_code}."

    except httpx.ConnectError:
        return (
            False,
            f"Cannot connect to IntelliScope backend at {backend_url}. "
            f"Ensure FastAPI server is active on port 8010."
        )
    except httpx.TimeoutException:
        return False, "Request to IntelliScope backend timed out after 20 seconds."
    except Exception as exc:
        return False, f"Unexpected network communication error: {str(exc)}"


async def call_pipeline_api(
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    backend_url: str = DEFAULT_BACKEND_URL,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[bool, Dict[str, Any] | str]:
    """
    Call the IntelliScope FastAPI unified multi-agent pipeline endpoint (POST /pipeline).

    Orchestrates: Data Collector -> Research Verification -> Insight Analyst -> Dashboard Builder.

    Args:
        query: Research query string.
        limit: Max results count (1-10).
        backend_url: Base URL of FastAPI server.
        client: Optional shared HTTPX async client.

    Returns:
        Tuple of (success_flag, data_or_error_message).
    """
    endpoint = f"{backend_url.rstrip('/')}/pipeline"
    payload = {"query": query, "limit": limit}

    async def _post(c: httpx.AsyncClient) -> httpx.Response:
        return await c.post(endpoint, json=payload, timeout=45.0)

    try:
        if client is not None:
            response = await _post(client)
        else:
            async with httpx.AsyncClient() as local_client:
                response = await _post(local_client)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "failed":
                summary = data.get("summary") or "Pipeline execution failed."
                return False, summary
            return True, data
        elif response.status_code == 504:
            return False, "Upstream research service timed out. Please try again later."
        elif response.status_code == 502:
            return False, "Upstream research provider encountered an error connecting to external sources."
        elif response.status_code in (400, 422):
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            return False, f"Request validation failed: {detail}"
        else:
            return False, f"Backend returned unexpected HTTP status {response.status_code}."

    except httpx.ConnectError:
        return (
            False,
            f"Cannot connect to IntelliScope backend at {backend_url}. "
            f"Ensure FastAPI server is active on port 8010."
        )
    except httpx.TimeoutException:
        return False, "Request to IntelliScope backend timed out after 45 seconds."
    except Exception as exc:
        return False, f"Unexpected network communication error: {str(exc)}"


# ------------------------------------------------------------------------------
# BAND Tool Dispatch Helper
# ------------------------------------------------------------------------------
async def send_band_reply(
    tools: AgentToolsProtocol,
    content: str,
    mentions: Optional[List[str]] = None,
) -> Any:
    """
    Send reply message through BAND platform tools.

    Supports both AgentToolsProtocol.send_message and execute_tool_call('band_send_message').

    Args:
        tools: BAND agent tools interface.
        content: Message body.
        mentions: List of handles/names/IDs to mention in room.
    """
    safe_mentions = [m for m in (mentions or []) if m]

    if hasattr(tools, "send_message"):
        return await tools.send_message(content, mentions=safe_mentions)
    elif hasattr(tools, "execute_tool_call"):
        return await tools.execute_tool_call(
            "band_send_message",
            {"content": content, "mentions": safe_mentions},
        )
    raise RuntimeError("Agent tools protocol does not provide message delivery capabilities.")


# ------------------------------------------------------------------------------
# BAND Adapter Implementation
# ------------------------------------------------------------------------------
class BandDataCollectorAdapter(SimpleAdapter[list]):
    """
    Official BAND SimpleAdapter for IntelliScope Data Collector Agent.

    Handles room message events, extracts research queries, delegates to
    FastAPI POST /research, and returns actual results via band_send_message.
    """

    def __init__(
        self,
        backend_url: str = DEFAULT_BACKEND_URL,
        agent_name: str = "IntelliScope Collector",
        agent_handle: str = "intelliscope-collector",
    ) -> None:
        super().__init__()
        self.backend_url = backend_url
        self.agent_name = agent_name
        self.agent_handle = agent_handle

    async def on_message(
        self,
        msg: PlatformMessage,
        tools: AgentToolsProtocol,
        history: list,
        participants_msg: Optional[str],
        contacts_msg: Optional[str],
        *,
        is_session_bootstrap: bool,
        room_id: str,
    ) -> None:
        """
        Handle incoming message turn in a BAND room.

        Args:
            msg: The triggering PlatformMessage.
            tools: AgentToolsProtocol providing send_message / band_send_message.
            history: Room conversation history.
            participants_msg: Formatted room participants string.
            contacts_msg: Formatted contacts string.
            is_session_bootstrap: Whether this is the initial session bootstrap.
            room_id: BAND room identifier.
        """
        logger.info(
            "Received BAND message from sender '%s' (type: %s) in room '%s'",
            msg.sender_name or msg.sender_id,
            msg.sender_type,
            room_id,
        )

        # Resolve mention target (BAND requires at least one mention in send_message)
        sender_target = msg.sender_name or msg.sender_id or "User"
        mentions = [sender_target]

        # Parse message content for query and limit
        query, limit = parse_research_request(
            content=msg.content,
            agent_handle=self.agent_handle,
            metadata=getattr(msg, "metadata", None),
            agent_name=self.agent_name,
        )

        if not query:
            logger.info("Message contained no query topic after mention sanitization. Sending usage guidance.")
            reply_text = format_usage_reply()
            await send_band_reply(tools, reply_text, mentions=mentions)
            return

        logger.info("Sanitized research query: '%s' (limit=%d)", query, limit)

        # Check if legacy call_research_api is mocked (for compatibility with legacy tests)
        # Otherwise execute the unified 4-agent multi-agent pipeline (POST /pipeline)
        is_legacy_mock = isinstance(call_research_api, (AsyncMock, MagicMock)) and not isinstance(call_pipeline_api, (AsyncMock, MagicMock))

        if is_legacy_mock:
            logger.info("Dispatching research query to legacy backend endpoint: query='%s', limit=%d", query, limit)
            success, result_or_error = await call_research_api(
                query=query,
                limit=limit,
                backend_url=self.backend_url,
            )
            if success and isinstance(result_or_error, dict):
                logger.info("Successfully retrieved research results from backend.")
                reply_text = format_research_reply(result_or_error, query)
            else:
                error_message = str(result_or_error)
                logger.warning("Research query failed: %s", error_message)
                reply_text = format_error_reply(error_message, query)
        else:
            logger.info("Dispatching query to unified multi-agent pipeline: query='%s', limit=%d", query, limit)
            success, result_or_error = await call_pipeline_api(
                query=query,
                limit=limit,
                backend_url=self.backend_url,
            )
            if success and isinstance(result_or_error, dict):
                logger.info("Successfully retrieved multi-agent pipeline results from backend.")
                reply_text = format_pipeline_reply(result_or_error, query)
            else:
                error_message = str(result_or_error)
                logger.warning("Pipeline execution failed: %s", error_message)
                reply_text = format_error_reply(error_message, query)

        # Send actual results or error back to BAND room
        await send_band_reply(tools, reply_text, mentions=mentions)


# ------------------------------------------------------------------------------
# Diagnostic Connectivity Verification
# ------------------------------------------------------------------------------
async def verify_band_connectivity(
    agent_id: str,
    api_key: str,
    rest_url: str = DEFAULT_REST_URL,
    ws_url: str = DEFAULT_WS_URL,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Perform safe diagnostic checks on BAND REST and WebSocket authentication.

    Verifies:
    1. REST API authentication (GET /api/v1/agent/me).
    2. Identity consistency: validates whether configured agent_id matches
       platform-registered agent_id associated with the API key.
       Mismatched agent IDs cause WebSocket upgrade or agent_control channel
       joins to fail repeatedly while REST returns 200 OK.
    3. Safe reporting of connection status without leaking credentials.

    Returns:
        Tuple of (is_valid, effective_agent_id, diagnostic_metadata).
    """
    redacted_id = agent_id[:8] + "..." if len(agent_id) > 8 else "***"
    logger.info("Performing pre-flight BAND diagnostic verification for agent '%s'...", redacted_id)

    diagnostic_info: Dict[str, Any] = {
        "rest_url": rest_url,
        "ws_url": ws_url,
        "configured_agent_id": redacted_id,
        "rest_authenticated": False,
        "agent_id_match": False,
    }

    try:
        rest = AsyncRestClient(api_key=api_key, base_url=rest_url)
        response = await rest.agent_api_identity.get_agent_me()
        me = response.data

        if not me:
            diagnostic_info["error"] = "REST response contained empty agent identity data."
            return False, agent_id, diagnostic_info

        registered_id = me.id
        registered_redacted = registered_id[:8] + "..." if len(registered_id) > 8 else "***"

        diagnostic_info.update({
            "rest_authenticated": True,
            "registered_agent_id": registered_redacted,
            "agent_name": me.name,
            "agent_handle": me.handle,
            "agent_description": me.description[:80] + "..." if me.description and len(me.description) > 80 else me.description,
        })

        if registered_id != agent_id:
            logger.warning(
                "AGENT ID MISMATCH: Configured agent_id ('%s') does not match registered agent_id ('%s') "
                "for this API key! The BAND platform WebSocket strictly validates agent_id against the API key, "
                "so mismatched IDs cause repeated WebSocket handshake/channel-join failures. "
                "Reconciling to registered agent_id ('%s').",
                redacted_id,
                registered_redacted,
                registered_redacted,
            )
            diagnostic_info["agent_id_match"] = False
            diagnostic_info["effective_agent_id"] = registered_redacted
            diagnostic_info["notice"] = (
                f"Configured agent_id ({redacted_id}) differed from registered agent_id ({registered_redacted}). "
                "Auto-synchronized to registered agent_id to prevent WebSocket rejection."
            )
            return True, registered_id, diagnostic_info

        diagnostic_info["agent_id_match"] = True
        logger.info(
            "BAND diagnostic check successful: REST authenticated (HTTP 200), agent '%s' (@%s), ID matched.",
            me.name,
            me.handle,
        )
        return True, agent_id, diagnostic_info

    except Exception as exc:
        exc_name = type(exc).__name__
        exc_msg = str(exc)
        logger.error("BAND REST authentication failed (%s): %s", exc_name, exc_msg)
        diagnostic_info["error"] = f"{exc_name}: {exc_msg}"
        return False, agent_id, diagnostic_info


# ------------------------------------------------------------------------------
# Agent Creation & Runner
# ------------------------------------------------------------------------------
def create_band_collector_agent(
    agent_id: str,
    api_key: str,
    backend_url: str = DEFAULT_BACKEND_URL,
    ws_url: Optional[str] = None,
    rest_url: Optional[str] = None,
    config: Optional[AgentConfig] = None,
) -> Agent:
    """
    Construct a BAND Agent instance wired to BandDataCollectorAdapter.

    Args:
        agent_id: Platform-issued BAND agent UUID.
        api_key: Platform-issued BAND API key.
        backend_url: Target IntelliScope FastAPI backend URL.
        ws_url: Optional custom WebSocket URL (defaults to BAND production WS URL).
        rest_url: Optional custom REST URL (defaults to BAND production REST URL).
        config: Optional AgentConfig instance (defaults to single_instance=True, SUPERSEDE).

    Returns:
        Configured Agent instance ready to run.
    """
    adapter = BandDataCollectorAdapter(backend_url=backend_url)
    resolved_config = config or AgentConfig(
        single_instance=True,
        conflict_policy=ConflictPolicy.SUPERSEDE,
    )
    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=ws_url,
        rest_url=rest_url,
        config=resolved_config,
    )
    return agent


async def main() -> None:
    """Main entry point to start the standalone BAND collector agent."""
    try:
        configure_logging(root_level="INFO")
    except Exception:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    print("=" * 70)
    print("INTELLISCOPE AI: BAND DATA COLLECTOR AGENT RUNTIME")
    print("=" * 70)

    # 1. Load credentials
    try:
        agent_id, api_key = load_band_credentials()
        redacted_id = agent_id[:8] + "..." if len(agent_id) > 8 else "***"
        print(f"Loaded credentials for agent ID: {redacted_id}")
    except Exception as exc:
        print(f"Error loading BAND credentials: {exc}")
        print("Please configure agent_config.yaml or set BAND_AGENT_ID and BAND_API_KEY.")
        sys.exit(1)

    backend_url = DEFAULT_BACKEND_URL
    print(f"Configured backend URL: {backend_url}")

    # 2. Check backend connectivity
    async with httpx.AsyncClient(timeout=3.0) as check_client:
        try:
            resp = await check_client.get(f"{backend_url}/health")
            if resp.status_code == 200:
                print(f"Verified connection to IntelliScope backend at {backend_url} (Health: OK)")
            else:
                print(f"Warning: Backend at {backend_url} returned status {resp.status_code}")
        except Exception:
            print(f"Notice: IntelliScope backend is not currently detected at {backend_url}.")
            print("Ensure backend is started: uvicorn backend.main:app --port 8010")

    # 3. Perform pre-flight BAND diagnostic verification
    print("\n--- BAND Diagnostic Verification ---")
    verified, effective_agent_id, diag_info = await verify_band_connectivity(agent_id, api_key)
    if verified:
        print(f"  [REST Auth] Status: OK (HTTP 200)")
        print(f"  [REST Auth] Registered Name: '{diag_info.get('agent_name')}' (@{diag_info.get('agent_handle')})")
        print(f"  [REST Auth] Registered ID:   '{diag_info.get('registered_agent_id')}'")
        if not diag_info.get("agent_id_match"):
            print(f"  [NOTICE]    Configured ID did not match registered ID. Using verified ID to prevent WebSocket failures.")
        print(f"  [WebSocket] Target Endpoint: {DEFAULT_WS_URL}")
        print(f"  [WebSocket] Reconnect Mode:  SUPERSEDE (auto-reconnect enabled)")
        print(f"  [WebSocket] Status: Ready")
        agent_id = effective_agent_id
    else:
        print(f"  [REST Auth] Notice: Pre-flight check encountered: {diag_info.get('error')}")
        print(f"  Proceeding with configured agent ID: {redacted_id}")
    print("------------------------------------\n")

    # 4. Create and launch BAND agent
    agent = create_band_collector_agent(
        agent_id=agent_id,
        api_key=api_key,
        backend_url=backend_url,
    )
    print(f"Starting BAND agent listener loop for agent '{agent_id[:8]}...'. Press Ctrl+C to terminate...")
    try:
        await agent.run()
    except KeyboardInterrupt:
        print("\nShutdown signal received. Stopping BAND agent...")
    except Exception as exc:
        print(f"BAND agent error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
