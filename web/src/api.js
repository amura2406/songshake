import axios from 'axios';

const api = axios.create({
  baseURL: '/', // Proxy handles /api and /auth
});

// Add interceptor for 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Redirect to login or dispatch cleanup
      // Check if we are already on login page to avoid loops
      if (!window.location.pathname.includes('/login')) {
         window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const checkAuth = async () => {
  try {
    const res = await api.get('/auth/status');
    return res.data.authenticated;
  } catch (error) {
    return false;
  }
};

export const getCurrentUser = async () => {
  try {
    const res = await api.get('/auth/me');
    return res.data;
  } catch (error) {
    return null;
  }
};

export const logoutUser = async () => {
  await api.get('/auth/logout');
};

export const login = async (headers_raw) => {
  await api.post('/auth/login', { headers_raw });
};

export const getPlaylists = async () => {
  const res = await api.get('/api/playlists');
  return res.data;
};

export const startEnrichment = async (playlist_id, owner = 'web_user', api_key = null) => {
  const res = await api.post('/api/enrichment', { playlist_id, owner, api_key });
  return res.data.task_id;
};

export const getAuthConfig = async () => {
  const res = await api.get('/auth/config');
  return res.data; // { use_env: boolean }
};

export const initGoogleAuth = async (clientId = null, clientSecret = null) => {
  const response = await fetch('/auth/google/init', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
  });
  if (!response.ok) throw new Error('Failed to init auth');
  return response.json();
};

export const pollGoogleAuth = async (deviceCode, clientId = null, clientSecret = null) => {
  const response = await fetch('/auth/google/poll', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_code: deviceCode, client_id: clientId, client_secret: clientSecret }),
  });
  // If 400, might be pending or error. But our API returns 200 with {status: pending} or throws 400 for real error?
  // Let's check api.py again. It catches exceptions.
  // If "pending", it returns {status: "pending"}.
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || 'Failed to poll auth');
  }
  return response.json();
};

export const getEnrichmentStatus = async (taskId) => {
  const response = await fetch(`/api/enrichment/status/${taskId}`);
  if (!response.ok) throw new Error('Failed to get status');
  return response.json();
};
// Helper to get stream URL
export const getEnrichmentStreamUrl = (taskId) => `/api/enrichment/stream/${taskId}`;

export const getSongs = async (owner = 'web_user', skip = 0, limit = 50) => {
  const res = await api.get('/api/songs', { params: { owner, skip, limit } });
  return res.data;
};

export default api;
