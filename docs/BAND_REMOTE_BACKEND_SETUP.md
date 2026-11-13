# IntelliScope AI — BAND Collector Remote Backend Setup

This guide explains how to run the persistent **BAND Data Collector Agent** on your Ubuntu laptop, connected securely to your remote **Render FastAPI backend**.

---

## 1. Why Run the BAND Collector on Your Laptop?

The **BAND platform** requires an uninterrupted, active WebSocket connection:
- Endpoint: `wss://app.band.ai/api/v1/socket/websocket`
- Protocol: Phoenix WebSocket Channel (`band-sdk 6.0.1`)
- Behavior: The agent continuously listens for user `@mentions` and room events in real time.

### The Render Free Tier Limitation
- Render's **Free Web Service** automatically spins down into a sleeping state after **15 minutes of inactivity** (no incoming HTTP traffic).
- Render free tier **does not provide background worker processes**.
- If you attempted to run the WebSocket listener inside Render's free web service, the service would either shut down after 15 minutes (killing the WebSocket), or fail to receive incoming room mentions.

### The Solution: Hybrid Connectivity
By running `scripts/band_collector_agent.py` locally on your Ubuntu machine:
1. The WebSocket connection to `app.band.ai` remains **permanently connected**.
2. When a user in BAND asks for research, the collector makes an HTTPS call (`POST /pipeline`) to your **Render backend** (`https://<your-backend>.onrender.com`).
3. Your Render backend executes the four agents (Data Collector, Verification, Analyst, Builder) and returns structured intelligence back to your laptop.
4. The local collector publishes the verified results directly to the BAND room.

---

## 2. Configuration

### 2.1 Credentials Setup
Ensure your BAND agent credentials are configured in your local environment. You can use either `agent_config.yaml` or `.env`:

#### Option A: `agent_config.yaml` (Recommended)
```yaml
agent_id: "your-band-agent-uuid-here"
api_key: "your-band-agent-api-key-here"
```

#### Option B: `.env` Variables
```bash
BAND_AGENT_ID=your-band-agent-uuid-here
BAND_API_KEY=your-band-agent-api-key-here
```

### 2.2 Pointing to the Remote Render Backend
You can point to your remote Render backend using either an **environment variable** or a **command-line flag**:

#### Method 1: Environment Variable (Recommended)
Add or export `INTELLISCOPE_BACKEND_URL`:
```bash
export INTELLISCOPE_BACKEND_URL="https://<your-backend-name>.onrender.com"
```

#### Method 2: Command-Line Flag
Pass the `--backend-url` parameter directly when starting the agent:
```bash
python scripts/band_collector_agent.py --backend-url https://<your-backend-name>.onrender.com
```

---

## 3. Avoiding Duplicate Collector Processes

> [!CAUTION]
> **Never run duplicate collector processes with the same agent credentials.**
> Starting two collector daemons causes WebSocket connection thrashing (continual disconnect/reconnect loops) and duplicate replies in your BAND chat room.

### Check If a Collector Is Already Running
Before starting a new collector, verify whether an existing instance is active:

```bash
# Check running processes
ps aux | grep band_collector_agent.py | grep -v grep

# Check active lock files
ls -la /tmp/band-agent-*.lock
```

If an existing process is found (e.g. PID `57363`), do not start another one.
If you need to restart it, terminate the existing process first:
```bash
kill -TERM <PID>
```

---

## 4. Handling Render Cold Starts (Wake-Up Time)

Because Render free web services sleep after 15 minutes of inactivity:
- When the backend is sleeping, the very first request takes **30 to 50 seconds** to boot.
- If a user sends a query in BAND while the backend is asleep, the collector's built-in retry and 45-second timeout handles this gracefully.

### Pre-Warming the Remote Backend (Best Practice)
Before starting your testing session or presenting a live demo, send a quick HTTP ping to wake up your Render backend:

```bash
curl -I https://<your-backend-name>.onrender.com/health
```

Once the response returns `HTTP/2 200` (`status: healthy`), the backend is fully awake and will respond to pipeline queries in 2-4 seconds.

---

## 5. Starting the BAND Collector

### 5.1 Interactive Terminal Mode (Foreground)
Activate your Python environment and run the collector:

```bash
cd /home/jagapathi/Projects/intelliscope-ai
source .venv/bin/activate

# Start with remote backend URL
python scripts/band_collector_agent.py --backend-url https://<your-backend-name>.onrender.com
```

Expected startup output:
```text
======================================================================
INTELLISCOPE AI: BAND DATA COLLECTOR AGENT RUNTIME
======================================================================
Loaded credentials for agent ID: f00ed576...
Configured backend URL: https://<your-backend-name>.onrender.com
Verified connection to IntelliScope backend at https://<your-backend-name>.onrender.com (Health: OK)

--- BAND Diagnostic Verification ---
  [REST Auth] Status: OK (HTTP 200)
  [REST Auth] Registered Name: 'IntelliScope Collector' (@intelliscope-collector)
  [REST Auth] Registered ID:   'f00ed576-fbfe-4dfb-95a7-82f6db3c6825'
  [WebSocket] Target Endpoint: wss://app.band.ai/api/v1/socket/websocket
  [WebSocket] Reconnect Mode:  SUPERSEDE (auto-reconnect enabled)
  [WebSocket] Status: Ready
------------------------------------

Starting BAND agent listener loop for agent 'f00ed576...'. Press Ctrl+C to terminate...
```

### 5.2 Background Mode via `systemd` (Persistent Laptop Daemon)
To keep the collector running automatically in the background across reboots:

1. Create a user systemd service file:
   `~/.config/systemd/user/intelliscope-band.service`

```ini
[Unit]
Description=IntelliScope AI BAND Collector Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/jagapathi/Projects/intelliscope-ai
ExecStart=/home/jagapathi/Projects/intelliscope-ai/.venv/bin/python scripts/band_collector_agent.py --backend-url https://<your-backend-name>.onrender.com
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
```

2. Enable and start the service:
```bash
systemctl --user daemon-reload
systemctl --user enable intelliscope-band.service
systemctl --user start intelliscope-band.service
```

3. Check service status:
```bash
systemctl --user status intelliscope-band.service
```

4. View live logs:
```bash
journalctl --user -u intelliscope-band.service -f
```

---

## 6. Live Room Verification

Once your agent is running:
1. Open your BAND room at `https://app.band.ai`.
2. Post a research query mentioning your collector agent:
   ```text
   @IntelliScope Collector research Quantum computing
   ```
3. You will see:
   - Immediate reception and validation in the terminal/journalctl logs.
   - Dispatch to `POST https://<your-backend-name>.onrender.com/pipeline`.
   - Complete multi-agent pipeline execution (Data Collector -> Verification -> Analyst -> Dashboard Builder).
   - Rich, formatted markdown research report posted directly into the BAND chat room with verified sources, themes, insights, and dashboard JSON.

