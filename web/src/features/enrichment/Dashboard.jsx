import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPlaylists, startEnrichment, getCurrentUser } from '../../api';
import { Play, Activity, ListMusic } from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';

const POLL_INTERVAL_ACTIVE = 10_000;  // 10s when something is processing
const POLL_INTERVAL_IDLE = 30_000;    // 30s when idle

const getTimeAgo = (dateString) => {
  const now = new Date();
  const date = new Date(dateString);
  const diffInMs = now - date;

  const diffInMins = Math.floor(diffInMs / (1000 * 60));
  const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
  const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));
  const diffInWeeks = Math.floor(diffInDays / 7);

  if (diffInWeeks > 0) return `${diffInWeeks}w ago`;
  if (diffInDays > 0) return `${diffInDays}d ago`;
  if (diffInHours > 0) return `${diffInHours}h ago`;
  if (diffInMins > 0) return `${diffInMins}m ago`;
  return 'just now';
};

const Dashboard = () => {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const playlistsRef = useRef(playlists);

  // Keep ref in sync with state so the poll closure always reads the latest value
  useEffect(() => {
    playlistsRef.current = playlists;
  }, [playlists]);

  const loadData = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      const [pl, u] = await Promise.all([getPlaylists(), getCurrentUser()]);
      setPlaylists(pl);
      setUser(u);
    } catch (error) {
      console.error("Failed to load data", error);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();

    // Adaptive polling: faster when enrichment is running, slower when idle
    let timeoutId;
    const poll = async () => {
      await loadData(false);
      const hasRunning = playlistsRef.current.some(p => p.is_running);
      timeoutId = setTimeout(poll, hasRunning ? POLL_INTERVAL_ACTIVE : POLL_INTERVAL_IDLE);
    };

    // Start polling after initial load
    timeoutId = setTimeout(poll, POLL_INTERVAL_IDLE);
    return () => clearTimeout(timeoutId);
  }, [loadData]);

  const handleStartEnrichment = async (playlist) => {
    try {
      if (playlist.is_running && playlist.active_task_id) {
        navigate(`/enrichment/${playlist.active_task_id}`);
        return;
      }

      const ownerId = user ? user.id : 'web_user';
      const taskId = await startEnrichment(playlist.playlistId, ownerId);
      navigate(`/enrichment/${taskId}`);
    } catch (error) {
      console.error("Failed to start enrichment", error);
    }
  };

  return (
    <div className="p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white mb-2">Select a Playlist to Enrich</h2>
          <p className="text-slate-400 text-sm">Choose a playlist from your library to start the AI enrichment process.</p>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-48 bg-surface-dark rounded-xl animate-pulse border border-white/5" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {playlists.map((playlist) => (
              <motion.div
                key={playlist.playlistId}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={{ y: -5 }}
                className="bg-surface-dark rounded-xl overflow-hidden border border-white/5 group hover:border-primary/50 transition-all shadow-lg hover:shadow-neon"
              >
                <div className="bg-surface-darker h-48 relative overflow-hidden">
                  {playlist.thumbnails?.[0]?.url ? (
                    <img
                      src={playlist.thumbnails[playlist.thumbnails.length - 1].url}
                      alt={playlist.title}
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-neutral-800">
                      <ListMusic className="w-12 h-12 text-neutral-600" />
                    </div>
                  )}
                  <div className={`absolute inset-0 bg-black/60 ${playlist.is_running ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity flex flex-col items-center justify-center backdrop-blur-sm gap-2`}>
                    <button
                      onClick={() => handleStartEnrichment(playlist)}
                      className={`${playlist.is_running ? 'bg-neutral-600 hover:bg-neutral-500 text-white' : 'bg-primary hover:bg-fuchsia-600 text-white shadow-neon'} px-6 py-3 rounded-full font-bold flex items-center gap-2 transform ${playlist.is_running ? 'scale-100' : 'scale-90 group-hover:scale-100'} transition-transform`}
                    >
                      {playlist.is_running ? (
                        <>
                          <Activity size={20} className="animate-pulse" />
                          View Progress
                        </>
                      ) : (
                        <>
                          <Play size={20} fill="currentColor" />
                          Identify Songs
                        </>
                      )}
                    </button>
                    {playlist.is_running && (
                      <span className="text-xs font-medium text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full border border-emerald-400/20 animate-pulse">
                        Currently processing
                      </span>
                    )}
                  </div>
                </div>
                <div className="p-6">
                  <div className="flex items-start justify-between mb-2 gap-2">
                    <h3 className="text-xl font-bold truncate flex-1 text-white group-hover:text-primary transition-colors" title={playlist.title}>{playlist.title}</h3>
                    {playlist.last_processed && (
                      <div className="shrink-0 flex items-center gap-1 px-2 py-0.5 bg-green-500/10 text-green-400 rounded text-[10px] border border-green-500/20 font-medium" title={`Processed: ${new Date(playlist.last_processed).toLocaleString()}`}>
                        <Activity size={10} />
                        <span>done {getTimeAgo(playlist.last_processed)}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex justify-between items-center text-slate-400 text-sm">
                    {playlist.count ? <span>{playlist.count} tracks</span> : <span>Unknown tracks</span>}
                    {playlist.description && <span className="truncate max-w-[150px]">{playlist.description}</span>}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
