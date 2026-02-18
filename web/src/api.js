import axios from 'axios';

const api = axios.create({
  baseURL: '/', // Proxy handles /api and /auth
});

// Add interceptor for 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
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
};

export const login = async (headers_raw) => {
  await api.post('/auth/login', { headers_raw });
};

export const getPlaylists = async () => {
  const res = await api.get('/api/playlists');
  return res.data;
};

export const getAuthConfig = async () => {
  const res = await api.get('/auth/config');
  return res.data; // { use_env: boolean }
};

export const initGoogleAuth = async (clientId = null, clientSecret = null) => {
  const res = await api.post('/auth/google/init', {
    client_id: clientId,
    client_secret: clientSecret,
  });
  return res.data;
};

export const pollGoogleAuth = async (deviceCode, clientId = null, clientSecret = null) => {
  const res = await api.post('/auth/google/poll', {
    device_code: deviceCode,
    client_id: clientId,
    client_secret: clientSecret,
  });
  return res.data;
};

export const getTags = async (owner) => {
  const res = await api.get('/api/tags', { params: { owner } });
  return res.data;
};

export const getSongs = async (owner, skip = 0, limit = 50, tags = null, minBpm = null, maxBpm = null) => {
  const params = { owner, skip, limit };
  if (tags) params.tags = tags;
  if (minBpm !== null) params.min_bpm = minBpm;
  if (maxBpm !== null) params.max_bpm = maxBpm;
  const res = await api.get('/api/songs', { params });
  return res.data;
};

// --- Job System APIs ---

export const createJob = async (playlistId, owner = 'web_user', apiKey = null, wipe = false, playlistName = '') => {
  const res = await api.post('/api/jobs', {
    playlist_id: playlistId,
    owner,
    api_key: apiKey,
    wipe,
    playlist_name: playlistName,
  });
  return res.data;
};

export const getJobs = async (status = null, owner = null) => {
  const params = {};
  if (status) params.status = status;
  if (owner) params.owner = owner;
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

export const getJobStreamUrl = (jobId) => `/api/jobs/${jobId}/stream`;

export const getAIUsage = async (owner = 'web_user') => {
  const res = await api.get('/api/jobs/ai-usage/current', { params: { owner } });
  return res.data;
};

export const getAIUsageStreamUrl = (owner = 'web_user') =>
  `/api/jobs/ai-usage/stream?owner=${encodeURIComponent(owner)}`;

export default api;
