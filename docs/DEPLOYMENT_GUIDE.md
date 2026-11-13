# IntelliScope AI — Production Deployment Guide

This guide details the production deployment procedures for **IntelliScope AI**.

---

## 1. Architecture & Port Allocation

IntelliScope AI consists of three cooperative runtime components:
1. **FastAPI Backend:** Multi-agent pipeline orchestrator, verification engine, and REST API. Runs on port **`8010`**.
2. **React SPA Frontend:** Built with Vite and served statically via Nginx or a static web server.
3. **BAND Collector Daemon:** Background Phoenix WebSocket client connecting to `wss://app.band.ai` and dispatching tasks to `http://127.0.0.1:8010/pipeline`.

### Port Allocation Rules
- **IntelliScope Backend:** Port **`8010`** (Preserved across all configurations).
- **IntelliScope Frontend Dev Server:** Port **`5173`** (Development only).
- **Production Web Entrypoint (Nginx):** Port **`80`** (HTTP) and **`443`** (HTTPS).
- **Reserved External Services:** Port **`8000`** is strictly reserved for the separate **AID-DRAS** project and must **never** be used or bound by IntelliScope.

---

## 2. Environment Variables Reference

Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `HOST` | Yes | `0.0.0.0` | Host IP for FastAPI/Uvicorn to bind. |
| `PORT` | Yes | `8010` | Port for FastAPI/Uvicorn. **Must remain 8010.** |
| `CORS_ALLOWED_ORIGINS` | No | `*` | Comma-separated allowed frontend origins (e.g., `https://intelliscope.yourdomain.com`). |
| `PIPELINE_STEP_TIMEOUT_SECONDS` | No | `30.0` | Execution timeout per agent step. |
| `INTELLISCOPE_BACKEND_URL` | Yes | `http://127.0.0.1:8010` | Backend API URL used by the background BAND collector and MCP server. |
| `HISTORY_STORAGE_PATH` | No | `data/processed/pipeline_history.json` | Path to persistent pipeline history JSON file. |
| `VITE_API_BASE_URL` | Yes (Build) | `http://127.0.0.1:8010` | Backend URL compiled into React frontend assets at build time. |
| `BAND_AGENT_ID` | Yes (BAND) | — | BAND Agent UUID (or configure in `agent_config.yaml`). |
| `BAND_API_KEY` | Yes (BAND) | — | BAND Agent API Key (or configure in `agent_config.yaml`). |
| `BAND_REST_URL` | No | `https://app.band.ai` | BAND platform REST endpoint. |
| `BAND_WS_URL` | No | `wss://app.band.ai/api/v1/socket/websocket` | BAND platform Phoenix WebSocket endpoint. |
| `LYZR_API_KEY` | Optional | — | Lyzr Studio API Key (optional for partial integration). |
| `LYZR_AGENT_ID` | Optional | — | Lyzr Studio Agent ID. |
| `ADAL_ENABLED` | No | `false` | Enable local AdaL CLI/SDK execution (requires `adal` binary). |
| `FINCH_ENABLED` | No | `false` | Enable Finch desktop bridge. |

---

## 3. Recommended Deployment: Single Linux Server with Systemd & Nginx

This is the simplest, most resilient deployment model for IntelliScope AI.

### Step 3.1: System Prerequisites
On a clean Ubuntu 22.04 or 24.04 LTS server:

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git nginx curl
# Install Node.js 18+ (if building frontend on the server)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### Step 3.2: Clone & Configure Application

```bash
# Clone to /var/www/intelliscope-ai (or user home)
sudo mkdir -p /var/www/intelliscope-ai
sudo chown -R $USER:$USER /var/www/intelliscope-ai
cd /var/www/intelliscope-ai

# Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Populate your BAND_AGENT_ID and BAND_API_KEY
```

### Step 3.3: Build Frontend Assets

```bash
cd /var/www/intelliscope-ai/frontend
npm install
# Set VITE_API_BASE_URL to empty string "" if using Nginx reverse proxy on same domain,
# or set to your API domain (e.g., https://api.yourdomain.com)
VITE_API_BASE_URL="" npm run build
```

### Step 3.4: Configure Systemd Service for Backend

Create `/etc/systemd/system/intelliscope-backend.service`:

```ini
[Unit]
Description=IntelliScope AI FastAPI Backend Server
After=network.target

[Service]
Type=simple
User=jagapathi
WorkingDirectory=/var/www/intelliscope-ai
EnvironmentFile=/var/www/intelliscope-ai/.env
ExecStart=/var/www/intelliscope-ai/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8010 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Step 3.5: Configure Systemd Service for BAND Collector Daemon

Create `/etc/systemd/system/intelliscope-band-collector.service`:

```ini
[Unit]
Description=IntelliScope AI BAND Collector Background Agent
After=network.target intelliscope-backend.service
Wants=intelliscope-backend.service

[Service]
Type=simple
User=jagapathi
WorkingDirectory=/var/www/intelliscope-ai
EnvironmentFile=/var/www/intelliscope-ai/.env
ExecStart=/var/www/intelliscope-ai/.venv/bin/python scripts/band_collector_agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start both services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now intelliscope-backend.service
sudo systemctl enable --now intelliscope-band-collector.service

# Verify service health
sudo systemctl status intelliscope-backend.service
sudo systemctl status intelliscope-band-collector.service
```

### Step 3.6: Configure Nginx Reverse Proxy

Create `/etc/nginx/sites-available/intelliscope`:

```nginx
server {
    listen 80;
    server_name intelliscope.yourdomain.com; # Replace with your domain or IP

    root /var/www/intelliscope-ai/frontend/dist;
    index index.html;

    # Serve static frontend SPA
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy backend API endpoints to port 8010
    location ~ ^/(health|pipeline|research|verify|analyze|dashboard|agents|integrations|docs|openapi.json) {
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Allow long-running research pipelines
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }
}
```

Enable Nginx site and test configuration:

```bash
sudo ln -s /etc/nginx/sites-available/intelliscope /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 4. Alternative Deployment: Docker & Docker Compose

For containerized environments with persistent storage volumes:

### Step 4.1: `docker-compose.yml` Architecture

```yaml
version: "3.8"

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: intelliscope-backend
    restart: unless-stopped
    ports:
      - "8010:8010"
    env_file:
      - .env
    environment:
      - HOST=0.0.0.0
      - PORT=8010
      - HISTORY_STORAGE_PATH=/app/data/processed/pipeline_history.json
    volumes:
      - intelliscope_data:/app/data/processed
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  band-collector:
    build:
      context: .
      dockerfile: Dockerfile.collector
    container_name: intelliscope-band-collector
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    env_file:
      - .env
    environment:
      - INTELLISCOPE_BACKEND_URL=http://backend:8010

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
    container_name: intelliscope-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  intelliscope_data:
```

---

## 5. Post-Deployment Verification Checklist

Verify all services immediately after deployment:

1. **Backend Health Check:**
   ```bash
   curl -s http://127.0.0.1:8010/health
   # Expected: {"status":"healthy","backend":"operational"}
   ```

2. **Agent Readiness Check:**
   ```bash
   curl -s http://127.0.0.1:8010/agents/status
   # Expected: operational=true for all 4 agents
   ```

3. **Sponsor Integrations Status:**
   ```bash
   curl -s http://127.0.0.1:8010/integrations/status | jq .summary
   # Expected: {"live_tested": 1, "implemented": 1, "partial": 3, "not_integrated": 0}
   ```

4. **Verify Process Isolation (AID-DRAS Preservation):**
   ```bash
   curl -s http://127.0.0.1:8000/health  # AID-DRAS remains active on 8000
   curl -s http://127.0.0.1:8010/health  # IntelliScope active on 8010
   ```

5. **BAND Room Live Ping:**
   Send `@IntelliScope Collector Research quantum computing` in your configured BAND room on `app.band.ai` and verify the multi-agent report is delivered.

---

## 6. Troubleshooting & Maintenance

### Inspect Logs
```bash
# Backend logs
sudo journalctl -u intelliscope-backend.service -f -n 50

# Collector daemon logs
sudo journalctl -u intelliscope-band-collector.service -f -n 50
```

### Resolving Single-Instance Lock Contention
If the collector crashes unexpectedly and leaves a stale lock file:
```bash
# Check if collector process is running
ps aux | grep band_collector_agent
# If no process is running, the lock file in /tmp is harmless (fcntl lock drops automatically).
# Do not remove the lock file while the process runs.
```

