import axios from 'axios';

/**
 * Resolves the backend API base URL with full support for:
 * 1. Build-time injected Vite environment variable (import.meta.env.VITE_API_BASE_URL)
 * 2. Process environment variable (Node.js testing / SSR)
 * 3. Browser-based runtime detection on Render (https://*.onrender.com)
 * 4. Local development fallback (http://127.0.0.1:8010)
 */
export function resolveApiBaseUrl(options = {}) {
  // Allow explicit override for unit testing
  if (options.override && typeof options.override === 'string') {
    return options.override.trim().replace(/\/+$/, '');
  }

  // 1. Build-time Vite env var
  const viteEnv = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL;
  if (viteEnv && typeof viteEnv === 'string' && viteEnv.trim()) {
    return viteEnv.trim().replace(/\/+$/, '');
  }

  // 2. Node / process env var (for unit tests / SSR)
  const procEnv = typeof process !== 'undefined' && process.env && process.env.VITE_API_BASE_URL;
  if (procEnv && typeof procEnv === 'string' && procEnv.trim()) {
    return procEnv.trim().replace(/\/+$/, '');
  }

  // 3. Browser runtime detection on Render Cloud:
  // If deployed to https://intelliscope-frontend.onrender.com and no build-time variable was baked in,
  // automatically target the corresponding Render backend service instead of dead localhost.
  const win = options.window || (typeof window !== 'undefined' ? window : null);
  if (win && win.location) {
    const { hostname, protocol } = win.location;
    if (typeof hostname === 'string' && hostname.endsWith('.onrender.com')) {
      if (hostname.includes('frontend')) {
        return `${protocol || 'https:'}//${hostname.replace('frontend', 'backend')}`;
      }
      return 'https://intelliscope-backend.onrender.com';
    }
  }

  // 4. Default for local development (port 8010 strictly preserved)
  return 'http://127.0.0.1:8010';
}

export const API_BASE_URL = resolveApiBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
  timeout: 35000, // 35s timeout to accommodate multi-agent pipeline and free tier wakeups
});

// Response interceptor for consistent error extraction
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    let errorMessage = 'An unexpected error occurred while communicating with IntelliScope AI backend.';
    let statusCode = null;
    let details = null;

    if (error.response) {
      statusCode = error.response.status;
      const data = error.response.data;

      if (data && typeof data === 'object') {
        if (data.detail) {
          if (Array.isArray(data.detail)) {
            // Pydantic 422 validation errors
            errorMessage = data.detail.map((err) => `${err.loc?.slice(1).join('.') || 'field'}: ${err.msg}`).join('; ');
            details = data.detail;
          } else if (typeof data.detail === 'string') {
            errorMessage = data.detail;
          }
        } else if (data.message) {
          errorMessage = data.message;
        }
      } else if (typeof data === 'string' && data.length < 300) {
        errorMessage = data;
      }
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      errorMessage = 'Request timed out waiting for multi-agent pipeline response. Please try again.';
      statusCode = 504;
    } else if (error.request) {
      const isLocal = API_BASE_URL.includes('127.0.0.1') || API_BASE_URL.includes('localhost');
      errorMessage = isLocal
        ? `Cannot connect to backend server at ${API_BASE_URL}. Ensure FastAPI is running on port 8010.`
        : `Cannot connect to backend server at ${API_BASE_URL}. The remote service may be waking up from sleep (cold start).`;
      statusCode = 0;
    }

    const customError = new Error(errorMessage);
    customError.statusCode = statusCode;
    customError.details = details;
    customError.raw = error;
    return Promise.reject(customError);
  }
);

export default apiClient;
