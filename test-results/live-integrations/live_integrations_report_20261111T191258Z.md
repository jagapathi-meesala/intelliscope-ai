# IntelliScope AI — Phase 5 Live Sponsor Integration Check

- **Generated (UTC):** `2026-11-11T19:12:58.393742+00:00`
- **Summary:** `passed=1`, `failed=0`, `external_outages=0`, `skipped=4`

| Platform | Category | Credentials | Check Type | Status | Notes / Error |
| --- | --- | --- | --- | --- | --- |
| BAND (Agentic Mesh) | `implemented` | `True` | `live_rest_auth_probe` | `PASSED` | connected |
| Agent37 Cloud Sandbox | `partial` | `False` | `live_sandbox_health` | `SKIPPED` | AGENT37_API_KEY / AGENT37_INSTANCE_ID not configured. |
| Lyzr Agent Studio | `partial` | `False` | `live_api_probe` | `SKIPPED` | LYZR_API_KEY / LYZR_AGENT_ID not configured. |
| AdaL Agent CLI / SDK | `partial` | `False` | `local_runtime_availability_probe` | `SKIPPED` | AdaL CLI (`adal`) and `adal_agent_sdk` are not installed in this environment. Install AdaL CLI & set ADAL_ENABLED=true to enable local CLI delegation. |
| Finch Desktop (MCP / Mini-Tools) | `not_integrated` | `False` | `local_runtime_availability_probe` | `SKIPPED` | Not integrated for live execution: Finch (`finchwork.app`) is a desktop agent host using npm mini-tools (`@finchtoys/minitools`) and local MCP servers rather than an external REST delegation endpoint. |
