import React, { useEffect, useState } from 'react';
import { getSongs } from '../api';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Music, Disc, User, Tag, ChevronLeft, ChevronRight } from 'lucide-react';

const Results = () => {
  const [songs, setSongs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 50;
  const navigate = useNavigate();

  useEffect(() => {
    loadSongs();
  }, [page]);

  const loadSongs = async () => {
    setLoading(true);
    try {
      const data = await getSongs('web_user', page * limit, limit);
      setSongs(data);
    } catch (error) {
      console.error("Failed to load songs", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-200 p-8">
      <header className="max-w-7xl mx-auto mb-8 flex items-center justify-between">
        <button 
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-neutral-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={20} />
          Back to Dashboard
        </button>
        <h1 className="text-2xl font-bold">Enriched Collection</h1>
        <div className="w-24"></div> {/* Spacer */}
      </header>

      <div className="max-w-7xl mx-auto">
        {loading ? (
             <div className="space-y-4">
               {[1,2,3,4,5].map(i => (
                 <div key={i} className="h-20 bg-neutral-800 rounded-xl animate-pulse" />
               ))}
             </div>
        ) : (
          <>
            <div className="grid gap-4">
              {songs.map((song) => (
                <div 
                  key={song.videoId} 
                  className="bg-neutral-800 p-6 rounded-xl border border-neutral-700 hover:border-neutral-600 transition-colors flex flex-col md:flex-row gap-6 items-start md:items-center"
                >
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
                       {song.title}
                       {song.url && (
                         <a href={song.url} target="_blank" rel="noopener noreferrer" className="text-neutral-500 hover:text-purple-400">
                           <ExternalLink size={14} />
                         </a>
                       )}
                    </h3>
                    <div className="flex flex-wrap gap-4 text-sm text-neutral-400">
                      <div className="flex items-center gap-1">
                        <User size={14} />
                        {song.artists}
                      </div>
                      {song.album && (
                        <div className="flex items-center gap-1">
                          <Disc size={14} />
                          {song.album}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 min-w-[200px]">
                    <div className="flex flex-wrap gap-2">
                      {song.genres?.map((genre, i) => (
                        <span key={i} className="px-2 py-1 bg-purple-900/30 text-purple-300 text-xs rounded-md border border-purple-500/20">
                          {genre}
                        </span>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {song.moods?.map((mood, i) => (
                        <span key={i} className="px-2 py-1 bg-pink-900/30 text-pink-300 text-xs rounded-md border border-pink-500/20">
                          {mood}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-center items-center gap-4 mt-8">
              <button 
                disabled={page === 0}
                onClick={() => setPage(p => Math.max(0, p - 1))}
                className="p-2 rounded-lg bg-neutral-800 border border-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-neutral-700 transition-colors"
              >
                <ChevronLeft />
              </button>
              <span className="text-sm text-neutral-400">Page {page + 1}</span>
              <button 
                disabled={songs.length < limit}
                onClick={() => setPage(p => p + 1)}
                className="p-2 rounded-lg bg-neutral-800 border border-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-neutral-700 transition-colors"
              >
                <ChevronRight />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default Results;
