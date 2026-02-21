import React, { useEffect, useState, useCallback } from 'react';
import { getPlaylists, getCurrentUser } from '../../api';
import { Play, Activity, ListMusic, Loader2, ChevronDown, RefreshCw } from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import { useJobs } from '../jobs/useJobs';



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
  const { createJob, jobsByPlaylistId } = useJobs();
  const [startingPlaylistId, setStartingPlaylistId] = useState(null);
  const [dropdownOpen, setDropdownOpen] = useState(null); // playlistId or null



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
  }, [loadData]);

  const handleStartEnrichment = async (playlist, wipe = false) => {
    try {
      // If already running, the job icon handles viewing progress
      if (playlist.is_running || jobsByPlaylistId[playlist.playlistId]) return;

      setStartingPlaylistId(playlist.playlistId);
      setDropdownOpen(null);
      await createJob(playlist.playlistId, wipe, playlist.title);
      // Refresh to pick up the new is_running state
      await loadData(false);
    } catch (error) {
      console.error("Failed to start enrichment", error);
    } finally {
      setStartingPlaylistId(null);
    }
  };

  const getPlaylistJob = (playlistId) => {
    return jobsByPlaylistId[playlistId] || null;
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
            {playlists.map((playlist) => {
              const job = getPlaylistJob(playlist.playlistId);
              const isActive = playlist.is_running || (job && ['pending', 'running'].includes(job.status));
              const isStarting = startingPlaylistId === playlist.playlistId;
              const progress = job && job.total > 0 ? (job.current / job.total) * 100 : 0;

              return (
                <motion.div
                  key={playlist.playlistId}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  whileHover={{ y: -5 }}
                  className={`bg-surface-dark rounded-xl overflow-hidden border group transition-all shadow-lg ${isActive
                    ? 'border-primary/30 shadow-neon'
                    : 'border-white/5 hover:border-primary/50 hover:shadow-neon'
                    }`}
                >
                  <div className="bg-surface-darker h-48 relative overflow-hidden">
                    {playlist.thumbnails?.[0]?.url ? (
                      <img
                        src={playlist.thumbnails[playlist.thumbnails.length - 1].url}
                        alt={playlist.title}
                        className={`w-full h-full object-cover transition-transform duration-500 ${isActive ? 'scale-105' : 'group-hover:scale-110'
                          }`}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-neutral-800">
                        <ListMusic className="w-12 h-12 text-neutral-600" />
                      </div>
                    )}

                    {/* Active job overlay with pulse */}
                    {isActive && (
                      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm flex flex-col items-center justify-center gap-3">
                        <div className="relative">
                          <div className="absolute inset-0 rounded-full bg-primary/30 animate-ping" style={{ animationDuration: '2s' }} />
                          <Activity size={28} className="text-primary animate-pulse relative z-10" />
                        </div>
                        <span className="text-sm font-medium text-white">
                          {job?.message || 'Processing…'}
                        </span>
                        {job && job.total > 0 && (
                          <div className="w-3/4">
                            <div className="flex justify-between text-xs text-slate-400 mb-1">
                              <span>{job.current}/{job.total} tracks</span>
                              <span>{Math.round(progress)}%</span>
                            </div>
                            <div className="h-1 bg-black/40 rounded-full overflow-hidden">
                              <motion.div
                                className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full"
                                initial={{ width: 0 }}
                                animate={{ width: `${progress}%` }}
                                transition={{ ease: 'linear', duration: 0.3 }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Hover state for inactive playlists */}
                    {!isActive && (
                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center backdrop-blur-sm gap-2">
                        <div className="relative transform scale-90 group-hover:scale-100 transition-transform">
                          {/* Split button: main action + dropdown */}
                          <div className="flex items-stretch">
                            <button
                              onClick={() => handleStartEnrichment(playlist)}
                              disabled={isStarting}
                              className="bg-primary hover:bg-fuchsia-600 text-white shadow-neon pl-5 pr-4 py-3 rounded-l-full font-bold flex items-center gap-2 disabled:opacity-50"
                            >
                              {isStarting ? (
                                <>
                                  <Loader2 size={20} className="animate-spin" />
                                  Starting…
                                </>
                              ) : (
                                <>
                                  <Play size={20} fill="currentColor" />
                                  Identify Songs
                                </>
                              )}
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setDropdownOpen(dropdownOpen === playlist.playlistId ? null : playlist.playlistId);
                              }}
                              disabled={isStarting}
                              className="bg-primary/80 hover:bg-fuchsia-600 text-white px-2.5 rounded-r-full border-l border-white/20 flex items-center disabled:opacity-50"
                            >
                              <ChevronDown size={16} />
                            </button>
                          </div>

                          {/* Dropdown menu */}
                          {dropdownOpen === playlist.playlistId && (
                            <div
                              className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-48 bg-surface-dark/95 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl py-1 z-50"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                onClick={() => handleStartEnrichment(playlist, true)}
                                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-slate-300 hover:text-white hover:bg-white/10 transition-colors rounded-xl"
                              >
                                <RefreshCw size={14} />
                                Fresh Scan
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
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
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
