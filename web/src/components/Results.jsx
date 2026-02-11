import React, { useEffect, useState } from 'react';
import { getSongs } from '../api';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Music, Disc, User, Tag, ChevronLeft, ChevronRight, Play, X } from 'lucide-react';

const Results = () => {
  const [songs, setSongs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [currentSong, setCurrentSong] = useState(null);
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
    <div className="min-h-screen bg-neutral-900 text-neutral-200 p-8 pb-32">
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
                  className="bg-neutral-800 p-4 rounded-xl border border-neutral-700 hover:border-neutral-600 transition-colors flex flex-col md:flex-row gap-6 items-start md:items-center group"
                >
                  <div className="relative w-24 h-24 md:w-20 md:h-20 shrink-0 rounded-lg overflow-hidden bg-neutral-900">
                    {song.thumbnails?.[0]?.url ? (
                      <img src={song.thumbnails[0].url} alt={song.title} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Music size={24} className="text-neutral-500" />
                      </div>
                    )}
                    <button
                      onClick={() => setCurrentSong(song)}
                      className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                    >
                      <Play size={32} className="text-white fill-white" />
                    </button>
                  </div>

                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2 truncate">
                       {song.title}
                       {song.url && (
                        <a href={song.url} target="_blank" rel="noopener noreferrer" className="text-neutral-500 hover:text-purple-400 shrink-0">
                           <ExternalLink size={14} />
                         </a>
                       )}
                    </h3>
                    <div className="flex flex-wrap gap-4 text-sm text-neutral-400">
                      <div className="flex items-center gap-1">
                        <User size={14} />
                        <span className="truncate max-w-[200px]">{song.artists}</span>
                      </div>
                      {song.album && (
                        <div className="flex items-center gap-1">
                          <Disc size={14} />
                          <span className="truncate max-w-[200px]">{song.album}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 min-w-[200px]">
                    <div className="flex flex-wrap gap-2">
                      {song.genres?.map((genre, i) => (
                        <span key={i} className="px-2 py-1 bg-purple-900/30 text-purple-300 text-xs rounded-md border border-purple-500/20 whitespace-nowrap">
                          {genre}
                        </span>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {song.moods?.map((mood, i) => (
                        <span key={i} className="px-2 py-1 bg-pink-900/30 text-pink-300 text-xs rounded-md border border-pink-500/20 whitespace-nowrap">
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

      {/* Fixed Player */}
      {currentSong && (
        <div className="fixed bottom-0 left-0 right-0 bg-neutral-950 border-t border-neutral-800 p-4 shadow-2xl z-50 animate-in slide-in-from-bottom duration-300">
          <div className="max-w-7xl mx-auto flex items-center gap-6">
            <div className="hidden md:block relative w-16 h-16 rounded-md overflow-hidden shrink-0">
              {currentSong.thumbnails?.[0]?.url ? (
                <img src={currentSong.thumbnails[0].url} alt={currentSong.title} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-neutral-800 flex items-center justify-center">
                  <Music size={20} className="text-neutral-500" />
                </div>
              )}
            </div>

            <div className="flex-1 min-w-0 hidden md:block">
              <h4 className="font-bold text-white truncate">{currentSong.title}</h4>
              <p className="text-sm text-neutral-400 truncate">{currentSong.artists}</p>
            </div>

            <div className="flex-1 max-w-2xl">
              <iframe
                width="100%"
                height="80"
                src={`https://www.youtube.com/embed/${currentSong.videoId}?autoplay=1&enablejsapi=1`}
                title="YouTube video player"
                frameBorder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="rounded-lg bg-black"
              ></iframe>
            </div>

            <button
              onClick={() => setCurrentSong(null)}
              className="p-2 hover:bg-neutral-800 rounded-full text-neutral-400 hover:text-white transition-colors"
            >
              <X size={24} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Results;
