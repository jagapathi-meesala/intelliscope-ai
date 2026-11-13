# IntelliScope AI — Phase 5 Live Sponsor Integration Check

- **Generated (UTC):** `2026-11-11T20:15:26.215230+00:00`
- **Summary:** `passed=1`, `failed=0`, `external_outages=1`, `skipped=3`

| Platform | Category | Credentials | Check Type | Status | Notes / Error |
| --- | --- | --- | --- | --- | --- |
| BAND (Agentic Mesh) | `implemented` | `True` | `live_rest_auth_probe` | `EXTERNAL_OUTAGE` | ConnectError: [Errno -3] Temporary failure in name resolution |
| Agent37 Cloud Sandbox | `partial` | `False` | `live_sandbox_health` | `SKIPPED` | AGENT37_API_KEY / AGENT37_INSTANCE_ID not configured. |
| Lyzr Agent Studio | `partial` | `False` | `live_api_probe` | `SKIPPED` | LYZR_API_KEY / LYZR_AGENT_ID not configured. |
| AdaL Agent CLI / SDK | `partial` | `False` | `local_runtime_availability_probe` | `SKIPPED` | Project `.atskills/intelliscope-research/SKILL.md` present. `adal` CLI and `adal_agent_sdk` are not installed on this host; install AdaL (`curl -fsSL https://adal.sylph.ai/install.sh | bash`) and set ADAL_ENABLED=true to run live AdaL sessions. |
| Finch Desktop (MCP / Skill) | `implemented` | `True` | `local_mcp_stdio_handshake_probe` | `PASSED` | Official Finch MCP JSON-RPC stdio server (scripts/intelliscope_mcp_server.py), mcp_servers.json, and SKILL.md implemented and locally protocol-verified. Live Finch Desktop GUI turn requires opening Finch Desktop on a workstation. |
