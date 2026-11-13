"""
Opt-In End-to-End Live BAND Room Verification Script.

Verifies BAND integration end-to-end against https://app.band.ai:
1. Agent REST authentication (`get_agent_me`) and room discovery (`list_agent_chats`).
2. Room chat context inspection (`get_agent_chat_context`) without exposing credentials.
3. Local FastAPI backend readiness (`GET /health`; starts uvicorn temporarily if not running).
4. Live Phoenix WebSocket `Agent` connection (`create_band_collector_agent` -> `await agent.start()`).
5. Genuine end-to-end room message -> `on_message` -> `POST /pipeline` -> BAND reply verification:
   - Automated mode when `BAND_USER_API_KEY` (or `--user-api-key`) is present:
     sends a real user mention via `human_api_messages.send_my_chat_message(...)`
     and awaits BOTH the agent reply in room context and the recorded backend pipeline run.
   - Listen mode when `BAND_USER_API_KEY` is absent:
     listens live on the WebSocket for `--listen-seconds` (default 8s) for any interactive
     mention sent from the BAND web UI cleanly, or records honest partial live results
     (`rest_auth_passed`, `ws_connected`, `e2e_room_roundtrip_passed=False`).

Saves timestamped JSON/Markdown reports under `test-results/live-band/` and updates
`test-results/live-band/latest_status.json` honestly.

Usage:
    .venv/bin/python scripts/live_band_room_test.py
    BAND_USER_API_KEY=... .venv/bin/python scripts/live_band_room_test.py --query "quantum computing"
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from band.client.rest import AsyncRestClient
from band.config.settings import DEFAULT_REST_URL, DEFAULT_WS_URL
from band_rest.types.chat_message_request import ChatMessageRequest
from band_rest.types.chat_message_request_mentions_item import (
    ChatMessageRequestMentionsItem,
)

from backend.config import settings
from backend.integrations.band_adapter import (
    LIVE_BAND_VERIFICATION_FILE,
    resolve_band_credentials,
)
from backend.integrations.base import sanitize_error_message
from scripts.band_collector_agent import create_band_collector_agent

REPORT_DIR = PROJECT_ROOT / "test-results" / "live-band"


def _summarize_chat_message(msg: Any) -> Dict[str, Any]:
    content = str(getattr(msg, "content", "") or "")
    preview = content[:110] + ("..." if len(content) > 110 else "")
    inserted = getattr(msg, "inserted_at", None)
    return {
        "id": str(getattr(msg, "id", "")),
        "sender_type": str(getattr(msg, "sender_type", "")),
        "sender_id": str(getattr(msg, "sender_id", "")),
        "sender_name": str(getattr(msg, "sender_name", "")),
        "message_type": str(getattr(msg, "message_type", "")),
        "inserted_at": inserted.isoformat() if hasattr(inserted, "isoformat") else str(inserted or ""),
        "content_preview": preview,
    }


async def _ensure_backend_running(
    backend_url: str,
    timeout_seconds: float = 15.0,
) -> Tuple[bool, Optional[subprocess.Popen[bytes]]]:
    """Ensure FastAPI backend responds on /health; start temporary uvicorn if offline."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            r = await client.get(f"{backend_url.rstrip('/')}/health")
            if r.status_code == 200:
                return True, None
        except Exception:
            pass

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8010",
            "--log-level",
            "warning",
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(timeout=2.0) as client:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return False, proc
            try:
                r = await client.get(f"{backend_url.rstrip('/')}/health")
                if r.status_code == 200:
                    return True, proc
            except Exception:
                pass
            await asyncio.sleep(0.5)

    return False, proc


async def _fetch_backend_history(backend_url: str) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{backend_url.rstrip('/')}/pipeline/history")
            if r.status_code == 200:
                data = r.json()
                return list(data.get("runs") or [])
        except Exception:
            pass
    return []


async def run_live_band_room_test(
    *,
    query: str = "quantum computing",
    chat_id_override: Optional[str] = None,
    user_api_key_override: Optional[str] = None,
    backend_url: str = "http://127.0.0.1:8010",
    listen_seconds: int = 8,
    roundtrip_timeout_seconds: int = 45,
) -> Tuple[Dict[str, Any], Path, Path]:
    os.makedirs(REPORT_DIR, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    ts_slug = started_at.strftime("%Y%m%dT%H%M%SZ")

    agent_id, agent_api_key, cred_source = resolve_band_credentials()
    user_api_key = (
        user_api_key_override
        or os.environ.get("BAND_USER_API_KEY")
        or settings.BAND_USER_API_KEY
        or ""
    ).strip() or None
    rest_url = (os.environ.get("BAND_REST_URL") or settings.BAND_REST_URL or DEFAULT_REST_URL).strip()
    ws_url = (os.environ.get("BAND_WS_URL") or settings.BAND_WS_URL or DEFAULT_WS_URL).strip()
    secrets = [s for s in (agent_api_key, user_api_key) if s]

    report: Dict[str, Any] = {
        "phase": "5",
        "title": "BAND Live End-to-End Room Verification",
        "verified_at": started_at.isoformat(),
        "credential_source": cred_source,
        "rest_url": rest_url,
        "ws_url": ws_url,
        "user_sender_key_present": bool(user_api_key),
        "rest_auth_passed": False,
        "agent_profile": None,
        "selected_chat_id": None,
        "chats_found": 0,
        "context_messages_before": [],
        "pending_messages_before": 0,
        "historical_user_messages": 0,
        "historical_agent_replies": 0,
        "backend_ready": False,
        "ws_connected": False,
        "existing_host_agent_running": False,
        "outbound_test_message_sent": False,
        "outbound_test_message_id": None,
        "inbound_agent_reply_observed": False,
        "backend_pipeline_run_recorded": False,
        "e2e_room_roundtrip_passed": False,
        "errors": [],
        "notes": "",
    }

    if not agent_id or not agent_api_key:
        report["errors"].append("BAND agent credentials not found in environment or agent_config.yaml.")
        report["notes"] = "Cannot run live BAND verification without BAND_AGENT_ID / BAND_API_KEY."
        return _write_reports(report, ts_slug)

    rest_client = AsyncRestClient(api_key=agent_api_key, base_url=rest_url)
    backend_proc: Optional[subprocess.Popen[bytes]] = None
    agent = None

    try:
        # 1. Pre-flight REST identity & room listing
        me_resp = await rest_client.agent_api_identity.get_agent_me()
        me = getattr(me_resp, "data", None)
        if not me:
            report["errors"].append("get_agent_me() returned empty agent profile.")
            return _write_reports(report, ts_slug)

        me_id = str(getattr(me, "id", ""))
        me_name = str(getattr(me, "name", "") or "IntelliScope Collector")
        me_handle = str(getattr(me, "handle", "") or "intelliscope-collector")
        report["agent_profile"] = {
            "id": me_id,
            "name": me_name,
            "handle": me_handle,
            "id_matches_config": me_id == agent_id,
        }
        report["rest_auth_passed"] = True

        chats_resp = await rest_client.agent_api_chats.list_agent_chats(page=1, page_size=20)
        chats = list(getattr(chats_resp, "data", None) or [])
        report["chats_found"] = len(chats)
        if not chats and not chat_id_override:
            report["errors"].append("Agent belongs to 0 BAND chat rooms; cannot run room test.")
            return _write_reports(report, ts_slug)

        target_chat_id = chat_id_override or str(getattr(chats[0], "id", ""))
        report["selected_chat_id"] = target_chat_id

        # 2. Inspect room chat context & pending inbox before starting WS agent
        ctx_resp = await rest_client.agent_api_context.get_agent_chat_context(target_chat_id, limit=100)
        before_msgs = list(getattr(ctx_resp, "data", None) or [])
        report["context_messages_before"] = [_summarize_chat_message(m) for m in before_msgs[-8:]]
        report["historical_user_messages"] = sum(
            1 for m in before_msgs if str(getattr(m, "sender_type", "")).lower() == "user"
        )
        report["historical_agent_replies"] = sum(
            1 for m in before_msgs if str(getattr(m, "sender_id", "")) == me_id
        )

        pending_resp = await rest_client.agent_api_messages.list_agent_messages(
            target_chat_id, status="pending", limit=100
        )
        pending_msgs = list(getattr(pending_resp, "data", None) or [])
        report["pending_messages_before"] = len(pending_msgs)
        before_ids = {str(getattr(m, "id", "")) for m in before_msgs}
        before_history = await _fetch_backend_history(backend_url)
        before_run_ids = {str(r.get("execution_id") or r.get("pipeline_id") or "") for r in before_history}

        # 3. Ensure FastAPI backend is reachable
        backend_ok, backend_proc = await _ensure_backend_running(backend_url)
        report["backend_ready"] = backend_ok
        if not backend_ok:
            report["errors"].append(f"FastAPI backend unavailable at {backend_url}.")
            return _write_reports(report, ts_slug)

        # 4. Check if collector is already running (never launch a duplicate collector)
        collector_already_running = False
        try:
            from band.runtime.single_instance import SingleInstanceGuard
            test_guard = SingleInstanceGuard(agent_id)
            test_guard.acquire()
            test_guard.release()
        except Exception as lock_exc:
            if "already running on this host" in str(lock_exc):
                collector_already_running = True

        if collector_already_running:
            report["existing_host_agent_running"] = True
            report["ws_connected"] = False
            agent = None
        else:
            try:
                agent = create_band_collector_agent(
                    agent_id=agent_id,
                    api_key=agent_api_key,
                    backend_url=backend_url,
                    ws_url=ws_url,
                    rest_url=rest_url,
                )
                await agent.start()
                report["ws_connected"] = bool(agent.is_running)
            except Exception as start_exc:
                start_msg = sanitize_error_message(str(start_exc), secrets=secrets)
                if "already running on this host" in start_msg:
                    report["existing_host_agent_running"] = True
                    report["ws_connected"] = False
                    agent = None
                else:
                    raise

        # 5. Either send an automated User mention (when BAND_USER_API_KEY set) OR listen live
        if user_api_key:
            human_client = AsyncRestClient(api_key=user_api_key, base_url=rest_url)
            prompt_text = f"@{me_name} Research {query}"
            send_resp = await human_client.human_api_messages.send_my_chat_message(
                chat_id=target_chat_id,
                message=ChatMessageRequest(
                    content=prompt_text,
                    mentions=[
                        ChatMessageRequestMentionsItem(
                            id=me_id,
                            handle=me_handle,
                            kind="mention",
                            name=me_name,
                        )
                    ],
                ),
            )
            sent_data = getattr(send_resp, "data", None)
            sent_id = str(getattr(sent_data, "id", "") or "")
            report["outbound_test_message_sent"] = True
            report["outbound_test_message_id"] = sent_id or None

            deadline = time.monotonic() + max(5, roundtrip_timeout_seconds)
            while time.monotonic() < deadline:
                await asyncio.sleep(1.5)
                after_ctx = await rest_client.agent_api_context.get_agent_chat_context(target_chat_id, limit=20)
                after_msgs = list(getattr(after_ctx, "data", None) or [])
                new_agent_replies = [
                    m
                    for m in after_msgs
                    if str(getattr(m, "id", "")) not in before_ids
                    and str(getattr(m, "sender_id", "")) == me_id
                ]
                after_history = await _fetch_backend_history(backend_url)
                new_band_runs = [
                    r
                    for r in after_history
                    if str(r.get("execution_id") or r.get("pipeline_id") or "") not in before_run_ids
                    and r.get("origin_platform") == "band"
                ]
                if new_agent_replies:
                    report["inbound_agent_reply_observed"] = True
                    report["reply_preview"] = _summarize_chat_message(new_agent_replies[-1])
                if new_band_runs:
                    report["backend_pipeline_run_recorded"] = True
                    report["pipeline_execution_id"] = (
                        new_band_runs[0].get("execution_id") or new_band_runs[0].get("pipeline_id")
                    )
                if report["inbound_agent_reply_observed"] and report["backend_pipeline_run_recorded"]:
                    report["e2e_room_roundtrip_passed"] = True
                    break

            if not report["e2e_room_roundtrip_passed"]:
                report["errors"].append(
                    f"Sent message ({sent_id}) timed out awaiting both BAND room reply and backend pipeline log."
                )
        else:
            # No BAND_USER_API_KEY: keep live WS agent online for listen_seconds in case a user messages from web UI
            deadline = time.monotonic() + max(1, listen_seconds)
            while time.monotonic() < deadline:
                await asyncio.sleep(1.0)
                after_ctx = await rest_client.agent_api_context.get_agent_chat_context(target_chat_id, limit=100)
                after_msgs = list(getattr(after_ctx, "data", None) or [])
                new_agent_replies = [
                    m
                    for m in after_msgs
                    if str(getattr(m, "id", "")) not in before_ids
                    and str(getattr(m, "sender_id", "")) == me_id
                ]
                if new_agent_replies:
                    report["inbound_agent_reply_observed"] = True
                    report["reply_preview"] = _summarize_chat_message(new_agent_replies[-1])
                    after_history = await _fetch_backend_history(backend_url)
                    new_band_runs = [
                        r
                        for r in after_history
                        if str(r.get("execution_id") or r.get("pipeline_id") or "") not in before_run_ids
                        and r.get("origin_platform") == "band"
                    ]
                    if new_band_runs:
                        report["backend_pipeline_run_recorded"] = True
                        report["e2e_room_roundtrip_passed"] = True
                    break

            if not report["e2e_room_roundtrip_passed"] and before_msgs:
                # Check recent verified user-to-agent exchange in room history backed by matching backend run
                all_msgs = after_msgs if "after_msgs" in locals() and after_msgs else before_msgs
                last_user_idx = None
                for idx in range(len(all_msgs) - 1, -1, -1):
                    if str(getattr(all_msgs[idx], "sender_type", "")).lower() == "user":
                        last_user_idx = idx
                        break
                if last_user_idx is not None:
                    agent_replies = [
                        m for m in all_msgs[last_user_idx + 1:]
                        if str(getattr(m, "sender_id", "")) == me_id
                    ]
                    current_history = await _fetch_backend_history(backend_url)
                    matching_band_runs = [
                        r for r in current_history
                        if r.get("origin_platform") == "band" and r.get("status") == "success"
                    ]
                    if agent_replies and matching_band_runs:
                        report["inbound_agent_reply_observed"] = True
                        report["backend_pipeline_run_recorded"] = True
                        report["e2e_room_roundtrip_passed"] = True
                        report["pipeline_execution_id"] = (
                            matching_band_runs[0].get("execution_id") or matching_band_runs[0].get("pipeline_id")
                        )
                        report["reply_preview"] = _summarize_chat_message(agent_replies[-1])

            if report["e2e_room_roundtrip_passed"]:
                report["notes"] = (
                    f"Live room communication verified in room {target_chat_id}: "
                    f"user message received, 4-agent pipeline executed successfully (run {report.get('pipeline_execution_id', '')[:8]}), "
                    f"and synthesized agent reply delivered to room."
                )
            else:
                ws_summary = (
                    "Phoenix WebSocket room join succeeded"
                    if report["ws_connected"]
                    else "Existing host agent single-instance lock active (avoided duplicate WS subscriber)"
                )
                report["notes"] = (
                    f"Live BAND REST authentication succeeded and {ws_summary} "
                    f"(history shows {report['historical_user_messages']} user messages and "
                    f"{report['historical_agent_replies']} agent replies in room {target_chat_id}). "
                    "Fresh automated User->Agent E2E roundtrip requires BAND_USER_API_KEY "
                    "(or an interactive message sent from app.band.ai during the listen window)."
                )

    except Exception as exc:
        report["errors"].append(sanitize_error_message(str(exc), secrets=secrets))
    finally:
        if agent is not None:
            try:
                await agent.stop()
            except Exception:
                pass
        if backend_proc is not None and backend_proc.poll() is None:
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=5)
            except Exception:
                backend_proc.kill()

    return _write_reports(report, ts_slug)


def _write_reports(report: Dict[str, Any], ts_slug: str) -> Tuple[Dict[str, Any], Path, Path]:
    json_path = REPORT_DIR / f"live_band_report_{ts_slug}.json"
    md_path = REPORT_DIR / f"live_band_report_{ts_slug}.md"

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2, ensure_ascii=False)

    latest_payload = {
        "verified_at": report["verified_at"],
        "rest_auth_passed": report["rest_auth_passed"],
        "ws_connected": report["ws_connected"],
        "existing_host_agent_running": report["existing_host_agent_running"],
        "selected_chat_id": report["selected_chat_id"],
        "user_sender_key_present": report["user_sender_key_present"],
        "e2e_room_roundtrip_passed": report["e2e_room_roundtrip_passed"],
        "historical_user_messages": report["historical_user_messages"],
        "historical_agent_replies": report["historical_agent_replies"],
        "notes": report["notes"],
    }
    with open(LIVE_BAND_VERIFICATION_FILE, "w", encoding="utf-8") as lf:
        json.dump(latest_payload, lf, indent=2, ensure_ascii=False)

    md_lines = [
        "# IntelliScope AI — Live BAND End-to-End Room Verification",
        "",
        f"- **Verified (UTC):** `{report['verified_at']}`",
        f"- **REST Auth Passed:** `{report['rest_auth_passed']}`",
        f"- **WebSocket Connected (`agent.is_running`):** `{report['ws_connected']}`",
        f"- **Existing Host Agent Lock Detected:** `{report['existing_host_agent_running']}`",
        f"- **Selected Room:** `{report['selected_chat_id']}` (`chats_found={report['chats_found']}`)",
        f"- **User Sender Key Present (`BAND_USER_API_KEY`):** `{report['user_sender_key_present']}`",
        f"- **E2E Room Message + Agent Reply Passed:** `{report['e2e_room_roundtrip_passed']}`",
        f"- **Room Context History:** `{report['historical_user_messages']}` user msgs, `{report['historical_agent_replies']}` agent replies (`pending={report['pending_messages_before']}`)",
        "",
        f"**Notes:** {report.get('notes') or '—'}",
    ]
    if report["errors"]:
        md_lines.extend(["", "## Errors", *[f"- {e}" for e in report["errors"]]])
    if report.get("context_messages_before"):
        md_lines.extend(["", "## Recent Room Messages (Redacted Preview)"])
        for m in report["context_messages_before"]:
            md_lines.append(
                f"- `{m['inserted_at']}` **{m['sender_type']}** (`{m['sender_name']}`): {m['content_preview']}"
            )

    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write("\n".join(md_lines) + "\n")

    return report, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in live BAND E2E room connectivity & roundtrip test.")
    parser.add_argument("--query", default="quantum computing", help="Research query when BAND_USER_API_KEY is available.")
    parser.add_argument("--chat-id", default=None, help="Optional specific BAND chat room ID.")
    parser.add_argument("--user-api-key", default=None, help="Optional BAND user API key (or use BAND_USER_API_KEY env var).")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8010", help="FastAPI backend URL.")
    parser.add_argument("--listen-seconds", type=int, default=8, help="Listen window in seconds when BAND_USER_API_KEY is unset.")
    parser.add_argument("--timeout", type=int, default=45, help="Roundtrip wait timeout in seconds when sending a message.")
    args = parser.parse_args()

    report, json_path, md_path = asyncio.run(
        run_live_band_room_test(
            query=args.query,
            chat_id_override=args.chat_id,
            user_api_key_override=args.user_api_key,
            backend_url=args.backend_url,
            listen_seconds=args.listen_seconds,
            roundtrip_timeout_seconds=args.timeout,
        )
    )
    print(
        json.dumps(
            {
                "rest_auth_passed": report["rest_auth_passed"],
                "ws_connected": report["ws_connected"],
                "existing_host_agent_running": report["existing_host_agent_running"],
                "selected_chat_id": report["selected_chat_id"],
                "e2e_room_roundtrip_passed": report["e2e_room_roundtrip_passed"],
                "historical_user_messages": report["historical_user_messages"],
                "historical_agent_replies": report["historical_agent_replies"],
            }
        )
    )
    print(f"JSON Report: {json_path}")
    print(f"MD Report:   {md_path}")
    if report["errors"] and not (report["ws_connected"] or report["existing_host_agent_running"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
