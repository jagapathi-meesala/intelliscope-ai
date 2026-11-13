"""
Opt-In Live Sponsor Integration Probe Script (Phase 5).

Explicitly opt-in CLI script (never executed during ordinary pytest runs).
Safely probes sponsor platform adapters where local credentials/runtimes exist
without exposing secrets or triggering paid LLM inference unless approved.

Saves timestamped reports under test-results/live-integrations/.

Usage:
    .venv/bin/python scripts/live_integrations_test.py
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.integrations import (
    DelegationTaskRequest,
    IntegrationRegistry,
    sanitize_error_message,
)


REPORT_DIR = PROJECT_ROOT / "test-results" / "live-integrations"
OUTAGE_MARKERS = (
    "timed out",
    "timeout",
    "network error",
    "temporary failure in name resolution",
    "connecterror",
    "connection refused",
    "502",
    "503",
    "504",
    "429",
)


def _is_outage(msg: str) -> bool:
    lower = (msg or "").lower()
    return any(m in lower for m in OUTAGE_MARKERS)


async def run_live_integrations_check(*, allow_paid_lyzr: bool = False) -> Tuple[Dict[str, Any], Path, Path]:
    os.makedirs(REPORT_DIR, exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    ts_slug = generated_at.strftime("%Y%m%dT%H%M%SZ")

    registry = IntegrationRegistry()
    results: List[Dict[str, Any]] = []

    # 1. BAND live REST authentication probe (non-paid, uses local agent_config.yaml or env)
    band_adapter = registry.get_adapter("band")
    assert band_adapter is not None
    if band_adapter.is_configured():
        band_info = await band_adapter.check_connectivity(timeout_seconds=12.0)
        if band_info.last_check_status == "connected" and not band_info.last_check_error:
            b_status = "passed"
        elif band_info.last_check_error and _is_outage(band_info.last_check_error):
            b_status = "external_outage"
        elif band_info.last_check_status == "connected" and band_info.last_check_error:
            # e.g., ID mismatch warning but REST 200 succeeded
            b_status = "failed"
        else:
            b_status = "failed"
        results.append(
            {
                "platform_id": "band",
                "display_name": band_info.display_name,
                "category": band_info.status,
                "credentials_present": band_info.credentials_present,
                "test_kind": "live_rest_auth_probe",
                "status": b_status,
                "probe_status": band_info.last_check_status,
                "error": sanitize_error_message(band_info.last_check_error or "") if band_info.last_check_error else None,
                "notes": band_info.notes,
            }
        )
    else:
        results.append(
            {
                "platform_id": "band",
                "display_name": band_adapter.display_name,
                "category": band_adapter.integration_category(),
                "credentials_present": False,
                "test_kind": "live_rest_auth_probe",
                "status": "skipped",
                "reason": "Missing BAND credentials in environment or agent_config.yaml.",
            }
        )

    # 2. Agent37 live probe (only when configured)
    a37_adapter = registry.get_adapter("agent37")
    assert a37_adapter is not None
    if a37_adapter.is_configured():
        a37_info = await a37_adapter.check_connectivity(timeout_seconds=12.0)
        err_msg = a37_info.last_check_error or ""
        a37_status = (
            "passed"
            if a37_info.last_check_status == "completed"
            else ("external_outage" if _is_outage(err_msg) else "failed")
        )
        results.append(
            {
                "platform_id": "agent37",
                "display_name": a37_info.display_name,
                "category": a37_info.status,
                "credentials_present": True,
                "test_kind": "live_sandbox_health",
                "status": a37_status,
                "error": sanitize_error_message(err_msg) if err_msg else None,
            }
        )
    else:
        results.append(
            {
                "platform_id": "agent37",
                "display_name": a37_adapter.display_name,
                "category": a37_adapter.integration_category(),
                "credentials_present": False,
                "test_kind": "live_sandbox_health",
                "status": "skipped",
                "reason": "AGENT37_API_KEY / AGENT37_INSTANCE_ID not configured.",
            }
        )

    # 3. Lyzr probe (respects paid-API approval gate)
    lyzr_adapter = registry.get_adapter("lyzr")
    assert lyzr_adapter is not None
    if not lyzr_adapter.is_configured():
        results.append(
            {
                "platform_id": "lyzr",
                "display_name": lyzr_adapter.display_name,
                "category": lyzr_adapter.integration_category(),
                "credentials_present": False,
                "test_kind": "live_api_probe",
                "status": "skipped",
                "reason": "LYZR_API_KEY / LYZR_AGENT_ID not configured.",
            }
        )
    elif not allow_paid_lyzr:
        results.append(
            {
                "platform_id": "lyzr",
                "display_name": lyzr_adapter.display_name,
                "category": lyzr_adapter.integration_category(),
                "credentials_present": True,
                "test_kind": "config_only_no_paid_inference",
                "status": "skipped",
                "reason": "Skipped live token inference unless --allow-paid-lyzr is supplied.",
            }
        )
    else:
        del_res = await lyzr_adapter.delegate_task(
            DelegationTaskRequest(
                target_platform="lyzr",
                action="chat_inference",
                payload={"message": "Health probe: reply OK."},
                timeout_seconds=15.0,
                max_retries=0,
            )
        )
        results.append(
            {
                "platform_id": "lyzr",
                "display_name": lyzr_adapter.display_name,
                "category": lyzr_adapter.integration_category(),
                "credentials_present": True,
                "test_kind": "live_inference_probe",
                "status": (
                    "passed"
                    if del_res.status == "completed"
                    else ("external_outage" if _is_outage(del_res.error or "") else "failed")
                ),
                "error": del_res.error,
            }
        )

    # 4. AdaL & Finch honest local runtime checks
    for pid in ("adal", "finch"):
        adp = registry.get_adapter(pid)
        assert adp is not None
        info = await adp.check_connectivity()
        if pid == "finch":
            f_status = (
                "passed"
                if info.last_check_status == "ready"
                else ("skipped" if info.last_check_status == "not_integrated" else "failed")
            )
            results.append(
                {
                    "platform_id": pid,
                    "display_name": info.display_name,
                    "category": info.status,
                    "mandatory_for_track": info.mandatory_for_track,
                    "credentials_present": info.credentials_present,
                    "runtime_state": info.runtime_state,
                    "test_kind": "local_mcp_stdio_handshake_probe",
                    "status": f_status,
                    "reason": info.last_check_error or info.notes,
                }
            )
        else:
            results.append(
                {
                    "platform_id": pid,
                    "display_name": info.display_name,
                    "category": info.status,
                    "mandatory_for_track": info.mandatory_for_track,
                    "credentials_present": info.credentials_present,
                    "runtime_state": info.runtime_state,
                    "test_kind": "local_runtime_availability_probe",
                    "status": "passed" if info.credentials_present else "skipped",
                    "reason": None if info.credentials_present else info.notes,
                }
            )

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "external_outages": sum(1 for r in results if r["status"] == "external_outage"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
    }

    report = {
        "phase": "5",
        "title": "IntelliScope AI Live Sponsor Integration Check",
        "generated_at": generated_at.isoformat(),
        "summary": summary,
        "platforms": results,
    }

    json_path = REPORT_DIR / f"live_integrations_report_{ts_slug}.json"
    md_path = REPORT_DIR / f"live_integrations_report_{ts_slug}.md"

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2, ensure_ascii=False)

    md_lines = [
        "# IntelliScope AI — Phase 5 Live Sponsor Integration Check",
        "",
        f"- **Generated (UTC):** `{report['generated_at']}`",
        f"- **Summary:** `passed={summary['passed']}`, `failed={summary['failed']}`, `external_outages={summary['external_outages']}`, `skipped={summary['skipped']}`",
        "",
        "| Platform | Category | Credentials | Check Type | Status | Notes / Error |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        note = r.get("error") or r.get("reason") or r.get("probe_status") or "—"
        md_lines.append(
            f"| {r['display_name']} | `{r['category']}` | `{r['credentials_present']}` | `{r['test_kind']}` | `{r['status'].upper()}` | {note} |"
        )
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write("\n".join(md_lines) + "\n")

    return report, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in live sponsor integration probe for IntelliScope AI.")
    parser.add_argument(
        "--allow-paid-lyzr",
        action="store_true",
        help="Explicitly allow live inference call to Lyzr if LYZR_API_KEY & LYZR_AGENT_ID are set.",
    )
    args = parser.parse_args()

    report, json_path, md_path = asyncio.run(
        run_live_integrations_check(allow_paid_lyzr=args.allow_paid_lyzr)
    )
    print(f"Live integrations summary: {json.dumps(report['summary'])}")
    print(f"JSON Report: {json_path}")
    print(f"MD Report:   {md_path}")
    if report["summary"]["failed"] > 0:
        return 1
    if report["summary"]["external_outages"] > 0 and report["summary"]["passed"] == 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

