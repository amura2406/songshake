import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPlaylists, startEnrichment, getEnrichmentStatus, getEnrichmentStreamUrl, getCurrentUser, logoutUser } from '../api';
import { Play, Activity, ListMusic, LogOut, Search, User } from 'lucide-react';
import { motion } from 'framer-motion';

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
  const [processing, setProcessing] = useState(null);
  const [logs, setLogs] = useState([]);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const logContainerRef = useRef(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [pl, u] = await Promise.all([getPlaylists(), getCurrentUser()]);
      setPlaylists(pl);
      setUser(u);
    } catch (error) {
      console.error("Failed to load data", error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await logoutUser();
    window.location.href = '/';
  };

  const handleStartEnrichment = async (playlistId) => {
    try {
      const ownerId = user ? user.id : 'web_user';
      console.log("Starting enrichment for owner:", ownerId);
      const taskId = await startEnrichment(playlistId, ownerId);
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
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
                    <button
                      onClick={() => handleStartEnrichment(playlist.playlistId)}
                      className="bg-primary hover:bg-fuchsia-600 text-white px-6 py-3 rounded-full font-bold flex items-center gap-2 transform scale-90 group-hover:scale-100 transition-transform shadow-neon"
                    >
                      <Play size={20} fill="currentColor" />
                      Idenfity Songs
                    </button>
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
