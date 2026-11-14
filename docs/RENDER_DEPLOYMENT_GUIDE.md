# IntelliScope AI — Render Free Tier Deployment Guide

This guide provides step-by-step instructions for deploying **IntelliScope AI** on Render's free tier, combined with your local Ubuntu machine for persistent background agent connectivity.

---

## 1. System Architecture

Deploying an autonomous multi-agent intelligence platform on Render's free tier utilizes a **hybrid deployment topology**:

```
                                  +---------------------------------------+
                                  |         Render Free Static Site       |
                                  |         (React / Vite SPA)            |
                                  |  https://intelliscope.onrender.com    |
                                  +-------------------+-------------------+
                                                      |
                                          HTTP REST   |  (POST /pipeline)
                                          CORS Auth   v
                                  +---------------------------------------+
                                  |        Render Free Web Service        |
                                  |         (FastAPI / Uvicorn)           |
                                  |  https://intelliscope-api.onrender.com|
                                  +-------------------+-------------------+
                                                      ^
                                          HTTPS REST  |  (POST /pipeline)
                                                      |
                        +-----------------------------+-------------------------------+
                        |                                                             |
+-----------------------+-----------------------+     +-------------------------------+-----------------------+
|                 Ubuntu Host                   |     |                     BAND                      |
|       Persistent BAND Collector Agent         | <-> |               Platform Cloud                  |
|        (scripts/band_collector_agent.py)      | WS  |     (wss://app.band.ai/api/v1/socket)         |
+-----------------------------------------------+     +-----------------------------------------------+
```

### Why This Hybrid Model?
1. **Render Free Web Service**: Runs the FastAPI multi-agent pipeline orchestrator, data verification agent, insight analyst agent, and dashboard builder agent.
2. **Render Free Static Site**: Builds and hosts the React 18 / Tailwind CSS dashboard with fast global CDN delivery and automatic SSL.
3. **Local Ubuntu Host for BAND**: Render's free tier **does not provide persistent background workers**. Free web services spin down after 15 minutes of inactivity and terminate active WebSocket connections. The BAND Data Collector Agent requires an uninterrupted Phoenix WebSocket connection to `wss://app.band.ai`. Running the BAND agent on your Ubuntu laptop connects it to the cloud room while delegating heavy pipeline research to the Render backend over HTTPS.

---

## 2. Prerequisites

1. A free account on [Render.com](https://render.com).
2. A GitHub repository containing the IntelliScope AI project.
3. Your BAND Agent credentials (`BAND_AGENT_ID` and `BAND_API_KEY`).

---

## 3. Deployment Method A: Render Blueprint (`render.yaml`)

The repository includes a ready-to-use `render.yaml` blueprint that configures both services automatically.

1. Log in to the [Render Dashboard](https://dashboard.render.com).
2. Click **New +** in the top navigation bar and select **Blueprint**.
3. Connect your IntelliScope AI GitHub repository.
4. Render will parse `render.yaml` and show:
   - `intelliscope-backend` (Web Service, Free tier, Python runtime)
   - `intelliscope-frontend` (Static Site, Free tier, SPA routing)
5. Review the plan and click **Apply**.
6. Once the backend finishes deploying, copy its public URL:
   `https://<your-backend-name>.onrender.com`
7. Update the frontend environment variable `VITE_API_BASE_URL` with this backend URL (see Section 4.2).

---

## 4. Deployment Method B: Manual Dashboard Setup

If you prefer to configure each service manually in the Render dashboard, follow these steps.

### Step 4.1: Deploy the FastAPI Backend (Render Web Service)

1. On the Render Dashboard, click **New +** -> **Web Service**.
2. Select your `intelliscope-ai` GitHub repository.
3. Configure the following service settings:

| Field | Value | Notes |
| :--- | :--- | :--- |
| **Name** | `intelliscope-backend` | Or any unique name you prefer |
| **Region** | `Oregon (US West)` | Select closest to you or standard |
| **Branch** | `main` | Production branch |
| **Root Directory** | *(Leave blank)* | Uses project root |
| **Runtime** | `Python 3` | Python 3.12 runtime |
| **Build Command** | `pip install -r requirements.txt` | Installs FastAPI, Uvicorn, httpx, etc. |
| **Start Command** | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1` | Binds dynamic `$PORT` |
| **Instance Type** | `Free` | 512 MB RAM / 0.1 CPU |

4. Under **Advanced**, configure:
   - **Health Check Path**: `/health`
   - **Auto-Deploy**: `Yes`

5. Add the following **Environment Variables**:

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Binds to all interfaces |
| `CORS_ALLOWED_ORIGINS` | `https://intelliscope-frontend.onrender.com,http://localhost:5173,http://127.0.0.1:5173` | Production frontend + local dev |
| `PIPELINE_STEP_TIMEOUT_SECONDS` | `30.0` | Step execution timeout |
| `PYTHON_VERSION` | `3.12.3` | Matches tested environment |
| `DEFAULT_USER_AGENT` | `IntelliScopeAI/1.0 (dev@intelliscope.ai) httpx/0.28.1` | Polite headers for arXiv/Crossref |

6. Click **Create Web Service**.
7. Wait for the build and deployment to complete (approx. 2-3 minutes).
8. Verify backend health by running in your terminal:
   ```bash
   curl -s https://<your-backend-name>.onrender.com/health
   # Expected output: {"status":"healthy","backend":"operational"}
   ```

---

### Step 4.2: Deploy the React Frontend (Render Static Site)

1. On the Render Dashboard, click **New +** -> **Static Site**.
2. Select your `intelliscope-ai` GitHub repository.
3. Configure the following site settings:

| Field | Value | Notes |
| :--- | :--- | :--- |
| **Name** | `intelliscope-frontend` | Or any unique name |
| **Branch** | `main` | Production branch |
| **Root Directory** | `frontend` | Points to React codebase |
| **Build Command** | `npm install && npm run build` | Compiles Vite production bundle |
| **Publish Directory** | `dist` | Relative to `rootDir` (`frontend/dist`) |

4. **CRITICAL: Set the Environment Variable BEFORE Building**:
   Under **Environment Variables**, add:

| Key | Value | Notes |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `https://<your-backend-name>.onrender.com` | **Do not omit.** Vite embeds this at build time. |

5. **CRITICAL: Configure SPA Routing Rewrite Rule**:
   Under **Redirects / Rewrites**, click **Add Rule**:
   - **Type**: `Rewrite`
   - **Source**: `/*`
   - **Destination**: `/index.html`

> [!IMPORTANT]
> **Why the rewrite rule is required:**
> IntelliScope AI uses client-side routing via React Router (`/`, `/new-research`, `/results`, `/verification`, `/insights`, `/dashboard`, `/activity`).
> Without this rewrite rule, refreshing any deep link or sharing a direct URL will trigger a `404 Not Found` error from Render's static file server.

6. Click **Create Static Site**.
7. Wait for the build to finish (approx. 1-2 minutes).
8. Open `https://<your-frontend-name>.onrender.com` in your browser. Verify the dashboard loads, agent status badges show healthy, and navigation works.

---

## 5. Free Tier Constraints & Operational Guidance

### 5.1 Cold Starts (Instance Sleeping)
Render free web services automatically spin down after **15 minutes of inactivity** (no incoming HTTP requests).
- **Wake-up time**: When a new request arrives, Render spins up the container, taking **30 to 50 seconds** to complete the cold start.
- **Pre-warming**: Before initiating research via BAND or testing the frontend, send a quick ping to wake the service:
  ```bash
  curl -I https://<your-backend-name>.onrender.com/health
  ```
- The frontend client includes an extended 30-second timeout and displays clear connection notices if the backend is waking up.

### 5.2 Ephemeral Filesystem
Render free web services operate on an **ephemeral container filesystem**.
- When the container spins down or restarts, newly created local files (such as `data/processed/pipeline_history.json`) are reset to the state in the repository.
- **For persistent history across reboots**, configure an external database (e.g. Supabase, Render PostgreSQL) or pass storage via an external S3-compatible service if upgrading beyond the free tier.

### 5.3 Single Worker Limit
The backend start command strictly uses `--workers 1`:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1
```
This ensures memory consumption remains well within Render's 512 MB free tier RAM quota, preventing out-of-memory (OOM) termination during multi-source concurrent data retrieval.

---

## 6. End-to-End Verification Checklist

| Step | Verification Command / Action | Expected Result |
| :---: | :--- | :--- |
| 1 | `curl https://<backend>/health` | HTTP 200: `{"status":"healthy","backend":"operational"}` |
| 2 | `curl https://<backend>/agents/status` | HTTP 200: 4 agents operational (`data_collector`, `verification`, `analyst`, `dashboard_builder`) |
| 3 | Visit `https://<frontend>/` in browser | Overview page displays with system KPI metrics and active navigation |
| 4 | Visit `https://<frontend>/verification` directly | Page renders correctly without 404 error (verifies SPA rewrite rule) |
| 5 | Run research in browser: "Quantum computing" | Full multi-agent pipeline completes: sources gathered, verified, analyzed, and dashboard rendered |
| 6 | Connect local BAND collector (see `docs/BAND_REMOTE_BACKEND_SETUP.md`) | Room mentions trigger live pipeline runs and post structured results back to BAND room |

