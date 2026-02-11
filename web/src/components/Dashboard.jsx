import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPlaylists, startEnrichment, getSongs } from '../api';
import { Play, Activity, ListMusic, LogOut, Search } from 'lucide-react';
import { motion } from 'framer-motion';

const Dashboard = () => {
  const [playlists, setPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadPlaylists();
  }, []);

  const loadPlaylists = async () => {
    try {
      const data = await getPlaylists();
      setPlaylists(data);
    } catch (error) {
      console.error("Failed to load playlists", error);
    } finally {
      setLoading(false);
    }
  };

  const handleStartEnrichment = async (playlistId) => {
    try {
      const taskId = await startEnrichment(playlistId);
      navigate(`/enrichment/${taskId}`);
    } catch (error) {
      console.error("Failed to start enrichment", error);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-white p-8">
      <header className="flex justify-between items-center mb-12">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-gradient-to-tr from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
            <Activity className="text-white" />
          </div>
          <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400">Song Shake</h1>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={() => navigate('/results')}
            className="flex items-center gap-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors border border-neutral-700"
          >
            <ListMusic size={18} />
            <span>View Library</span>
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto">
        <h2 className="text-3xl font-bold mb-8">Select a Playlist to Enrich</h2>
        
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-48 bg-neutral-800 rounded-xl animate-pulse" />
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
                className="bg-neutral-800 rounded-xl overflow-hidden border border-neutral-700 group hover:border-purple-500/50 transition-all shadow-lg hover:shadow-purple-500/10"
              >
                <div className="bg-neutral-700 h-48 relative overflow-hidden">
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
                      className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-full font-bold flex items-center gap-2 transform scale-90 group-hover:scale-100 transition-transform"
                    >
                      <Play size={20} fill="currentColor" />
                      Idenfity Songs
                    </button>
                  </div>
                </div>
                <div className="p-6">
                  <h3 className="text-xl font-bold truncate mb-2" title={playlist.title}>{playlist.title}</h3>
                  <div className="flex justify-between items-center text-neutral-400 text-sm">
                    {playlist.count ? <span>{playlist.count}</span> : <span>Unknown tracks</span>}
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
