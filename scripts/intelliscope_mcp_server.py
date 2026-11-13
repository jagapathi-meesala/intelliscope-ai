"""
Model Context Protocol (MCP) JSON-RPC 2.0 Stdio Server for IntelliScope AI.

Official transport bridge enabling Finch Desktop (`mcpServers` configuration),
AdaL CLI/IDE MCP clients, or any standard MCP host to invoke IntelliScope's
multi-source research, verification, and 4-agent pipeline tools locally.

Supports both newline-delimited JSON-RPC 2.0 messages and Content-Length framed
JSON-RPC messages over stdin/stdout.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.data_agent import collect_research
from backend.agents.verification_agent import verify_research
from backend.integrations import integration_registry
from backend.models.pipeline import PipelineRequest
from backend.services.pipeline_orchestrator import run_pipeline

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "intelliscope-ai-mcp",
    "version": "1.0.0",
}

MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "intelliscope_research",
        "description": "Retrieve normalized research sources across Wikipedia, arXiv, and Crossref with transparent relevance and provenance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research topic query (1-300 chars)"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["wikipedia", "arxiv", "crossref"]},
                    "default": ["wikipedia"],
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "intelliscope_verify",
        "description": "Run structural verification (HTTPS, domain whitelist, DOI validation, timestamps, duplicates). Structural only; never factual verification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "results": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["query", "results"],
        },
    },
    {
        "name": "intelliscope_pipeline",
        "description": "Execute the full 4-agent IntelliScope research pipeline (Collector -> Verifier -> Analyst -> Dashboard Builder) with handoff telemetry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research topic query"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["wikipedia", "arxiv", "crossref"]},
                    "default": ["wikipedia"],
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "intelliscope_integrations_status",
        "description": "Inspect honest live readiness & configuration status across BAND, Lyzr, AdaL, Finch, and Agent37 (never exposes secrets).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


async def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch an MCP tools/call invocation to the genuine IntelliScope backend."""
    args = arguments or {}
    if name == "intelliscope_research":
        data = await collect_research(
            query=str(args.get("query") or ""),
            limit=int(args.get("limit") or 5),
            sources=args.get("sources"),
        )
        return {
            "content": [{"type": "text", "text": json.dumps(data, indent=2)}],
            "isError": False,
        }

    if name == "intelliscope_verify":
        report = await verify_research(
            {"query": str(args.get("query") or ""), "results": args.get("results") or []}
        )
        return {
            "content": [{"type": "text", "text": json.dumps(report, indent=2)}],
            "isError": False,
        }

    if name == "intelliscope_pipeline":
        req = PipelineRequest(
            query=str(args.get("query") or ""),
            limit=int(args.get("limit") or 3),
            sources=args.get("sources") or ["wikipedia"],
            origin_platform="finch_mcp",
        )
        res = await run_pipeline(req)
        return {
            "content": [{"type": "text", "text": json.dumps(res.model_dump(), indent=2)}],
            "isError": res.status == "failed",
        }

    if name == "intelliscope_integrations_status":
        status_resp = integration_registry.get_status_response()
        return {
            "content": [{"type": "text", "text": json.dumps(status_resp.model_dump(), indent=2)}],
            "isError": False,
        }

    return {
        "content": [{"type": "text", "text": f"Unknown MCP tool '{name}'."}],
        "isError": True,
    }


async def handle_jsonrpc_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process one parsed MCP JSON-RPC 2.0 request or notification."""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}

    # Notifications have no id and expect no reply
    if method == "notifications/initialized" or msg_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": MCP_TOOLS},
        }

    if method == "tools/call":
        tool_name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        try:
            call_res = await handle_tool_call(tool_name, arguments)
            return {"jsonrpc": "2.0", "id": msg_id, "result": call_res}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool execution error: {exc}"}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method '{method}' not found"},
    }


async def serve_stdio() -> None:
    """Run MCP stdio loop accepting newline-delimited or Content-Length JSON-RPC frames."""
    while True:
        line = await asyncio.to_thread(sys.stdin.buffer.readline)
        if not line:
            break

        raw_str = line.decode("utf-8", errors="replace").strip()
        if not raw_str:
            continue

        payload_text = raw_str
        if raw_str.lower().startswith("content-length:"):
            try:
                content_length = int(raw_str.split(":", 1)[1].strip())
            except ValueError:
                continue
            # Consume blank header separator lines
            while True:
                hdr = await asyncio.to_thread(sys.stdin.buffer.readline)
                if not hdr or hdr in (b"\r\n", b"\n"):
                    break
            body = await asyncio.to_thread(sys.stdin.buffer.read, content_length)
            payload_text = body.decode("utf-8", errors="replace")

        try:
            msg = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()
            continue

        reply = await handle_jsonrpc_message(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(serve_stdio())

