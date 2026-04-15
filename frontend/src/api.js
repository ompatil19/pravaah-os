import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Request interceptor ───
api.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);

// ─── Response interceptor ───
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred';
    return Promise.reject(new Error(message));
  }
);

// ─── Call Endpoints ───
export const callsApi = {
  start: (data) => api.post('/api/calls/start', data),
  end: (sessionId, data) => api.post(`/api/calls/${sessionId}/end`, data),
  list: (params) => api.get('/api/calls', { params }),
  get: (sessionId) => api.get(`/api/calls/${sessionId}`),
};

// ─── Document Endpoints ───
export const documentsApi = {
  upload: (formData) =>
    api.post('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  get: (docId) => api.get(`/api/documents/${docId}`),
};

// ─── Analytics Endpoints ───
export const analyticsApi = {
  summary: (params) => api.get('/api/analytics/summary', { params }),
  agent: (agentId) => api.get(`/api/analytics/agent/${agentId}`),
};

// ─── Document Search ───
export const searchDocuments = (query, docIds, topK = 5) =>
  api.post('/api/documents/search', { query, doc_ids: docIds, top_k: topK });

export const getDocumentStatus = (docId) =>
  api.get(`/api/documents/${docId}/status`);

// ─── Job Endpoints ───
export const getJobStatus = (jobId) =>
  api.get(`/api/jobs/${jobId}`);

export const listJobs = (page = 1, perPage = 20) =>
  api.get('/api/jobs', { params: { page, per_page: perPage } });

// ─── Auth / User Management ───
export const createUser = (username, password, role) =>
  api.post('/api/auth/users', { username, password, role });

export default api;
