import axios from 'axios';

// Base URL defaults to FastAPI backend on port 8010 as per platform specification
const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== 'undefined' && process.env?.VITE_API_BASE_URL) ||
  'http://127.0.0.1:8010';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
  timeout: 30000, // 30s timeout to accommodate multi-agent pipeline
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
      errorMessage = `Cannot connect to backend server at ${API_BASE_URL}. Ensure FastAPI is running on port 8010.`;
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
