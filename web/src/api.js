import axios from 'axios';

const api = axios.create({
  baseURL: '/', // Proxy handles /api and /auth
});

export const checkAuth = async () => {
  try {
    const res = await api.get('/auth/status');
    return res.data.authenticated;
  } catch (error) {
    return false;
  }
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

export const getEnrichmentStatus = async (task_id) => {
  const res = await api.get(`/api/enrichment/${task_id}`);
  return res.data;
};

export const getSongs = async (owner = 'web_user', skip = 0, limit = 50) => {
  const res = await api.get('/api/songs', { params: { owner, skip, limit } });
  return res.data;
};

export default api;
