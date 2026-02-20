import axios from 'axios';

const api = axios.create({
  baseURL: '/', // Proxy handles /api and /auth
});

// --- JWT Token Management ---

const TOKEN_KEY = 'songshake_jwt';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Flag to prevent infinite refresh loops
let isRefreshing = false;

// Add interceptor for 401 — attempt token refresh before redirecting
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response &&
      error.response.status === 401 &&
      !originalRequest._retry &&
      !isRefreshing &&
      !originalRequest.url?.includes('/auth/refresh') &&
      !originalRequest.url?.includes('/auth/status')
    ) {
      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const res = await api.get('/auth/refresh');
        // Store the new JWT from the refresh response
        if (res.data?.token) {
          setToken(res.data.token);
        }
        isRefreshing = false;
        // Retry the original request with the refreshed token
        return api(originalRequest);
      } catch {
        isRefreshing = false;
        clearToken();
        // Refresh failed — redirect to login with expired flag
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login?expired=true';
        }
      }
    }

    // Non-401 errors or already-retried requests
    if (
      error.response &&
      error.response.status === 401 &&
      !window.location.pathname.includes('/login')
    ) {
      clearToken();
      window.location.href = '/login?expired=true';
    }

    return Promise.reject(error);
  }
);

export const checkAuth = async () => {
  const token = getToken();
  if (!token) return false;
  try {
    const res = await api.get('/auth/status');
    return res.data.authenticated;
  } catch {
    return false;
  }
};

export const getCurrentUser = async () => {
  try {
    const res = await api.get('/auth/me');
    return res.data;
  } catch {
    return null;
  }
};

export const logoutUser = async () => {
  await api.get('/auth/logout');
  clearToken();
};



export const getPlaylists = async () => {
  const res = await api.get('/api/playlists');
  return res.data;
};



export const getTags = async () => {
  const res = await api.get('/api/tags');
  return res.data;
};

export const getSongs = async (skip = 0, limit = 50, tags = null, minBpm = null, maxBpm = null) => {
  const params = { skip, limit };
  if (tags) params.tags = tags;
  if (minBpm !== null) params.min_bpm = minBpm;
  if (maxBpm !== null) params.max_bpm = maxBpm;
  const res = await api.get('/api/songs', { params });
  return res.data;  // { items, total, page, pages }
};

// --- Job System APIs ---

export const createJob = async (playlistId, apiKey = null, wipe = false, playlistName = '') => {
  const res = await api.post('/api/jobs', {
    playlist_id: playlistId,
    api_key: apiKey,
    wipe,
    playlist_name: playlistName,
  });
  return res.data;
};

export const getJobs = async (status = null) => {
  const params = {};
  if (status) params.status = status;
  const res = await api.get('/api/jobs', { params });
  return res.data;
};

export const getJob = async (jobId) => {
  const res = await api.get(`/api/jobs/${jobId}`);
  return res.data;
};

export const cancelJob = async (jobId) => {
  const res = await api.post(`/api/jobs/${jobId}/cancel`);
  return res.data;
};

export const getJobStreamUrl = (jobId) => {
  const token = getToken();
  // SSE (EventSource) doesn't support custom headers, so pass token as query param
  return `/api/jobs/${jobId}/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`;
};

export const getAIUsage = async () => {
  const res = await api.get('/api/jobs/ai-usage/current');
  return res.data;
};

export const getAIUsageStreamUrl = () => {
  const token = getToken();
  return `/api/jobs/ai-usage/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`;
};

export const retrySong = async (videoId) => {
  const res = await api.post(`/api/jobs/retry/${encodeURIComponent(videoId)}`, {});
  return res.data;
};

export default api;
