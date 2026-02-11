import React, { useEffect, useState, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getSongs, getCurrentUser, getTags } from '../api';
import { Play, Pause, FastForward, Rewind, Volume2 } from 'lucide-react';
import YouTube from 'react-youtube';
import { motion, AnimatePresence } from 'framer-motion';

const Results = () => {
  const [songs, setSongs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [currentSong, setCurrentSong] = useState(null);
  const [tags, setTags] = useState([]);
  const [selectedTags, setSelectedTags] = useState([]);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [filteredSongs, setFilteredSongs] = useState([]);
  const [playerContext, setPlayerContext] = useState(null);
  const [playbackProgress, setPlaybackProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const limit = 50;

  const location = useLocation();
  const navigate = useNavigate();

  // Parse URL query parameter
  const queryTags = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const ts = params.get('tags');
    return ts ? ts.split(',') : [];
  }, [location.search]);

  // Sync initial state from URL on mount/url change
  useEffect(() => {
    setSelectedTags(queryTags);
    setPage(0); // Reset page on filter change
  }, [queryTags]);


  useEffect(() => {
    loadData();
    loadTags();
  }, [page, queryTags]); // Reload when page or tags query change

  useEffect(() => {
    let interval;
    if (playerContext && isPlaying) {
      interval = setInterval(() => {
        try {
          const currentTime = playerContext.getCurrentTime();
          setPlaybackProgress(currentTime);
          const dur = playerContext.getDuration();
          if (dur > 0 && duration === 0) setDuration(dur);

        } catch { /* ignore */ }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [playerContext, isPlaying]);

  const loadTags = async () => {
    try {
      const u = await getCurrentUser();
      if (u) {
        const fetchedTags = await getTags(u.id);
        const transformedTags = fetchedTags.map(t => ({ type: t.type, value: t.name, count: t.count }));

        // Ensure that URL tags are also present, even if count is 0
        queryTags.forEach(qt => {
          if (!transformedTags.some(t => t.value === qt)) {
            transformedTags.push({ type: 'unknown', value: qt });
          }
        });
        setTags(transformedTags);
      }
    } catch (error) {
      console.error("Failed to fetch available filter tags", error);
    }
  };

  const loadData = async () => {
    try {
      setLoading(true);
      const u = await getCurrentUser();

      const ownerId = u ? u.id : 'web_user';
      const tagsString = queryTags.length > 0 ? queryTags.join(',') : null;
      const data = await getSongs(ownerId, page * limit, limit, tagsString);
      // Filter out songs without valid data
      const validSongs = data.filter(s => s.videoId);
      setSongs(validSongs);
      setFilteredSongs(validSongs); // Backend handles filtering now
    } catch (error) {
      console.error("Failed to load songs", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleTag = (tagValue) => {
    let newTags;
    if (selectedTags.includes(tagValue)) {
      newTags = selectedTags.filter(t => t !== tagValue);
    } else {
      newTags = [...selectedTags, tagValue];
    }

    const params = new URLSearchParams(location.search);
    if (newTags.length > 0) {
      params.set('tags', newTags.join(','));
    } else {
      params.delete('tags');
    }
    navigate(`/results?${params.toString()}`);
  };

  const formatDuration = (ms) => {
    if (!ms) return '--:--';
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const handlePlayerReady = (event) => {
    setPlayerContext(event.target);
    const dur = event.target.getDuration();
    setDuration(dur || 0);
    setIsPlaying(true);
  };

  const handlePlayerStateChange = (event) => {
    // 1 is playing, 2 is paused
    if (event.data === 1) {
      setIsPlaying(true);
      setDuration(event.target.getDuration());
    } else if (event.data === 2) {
      setIsPlaying(false);
    }
  };

  // Convert seconds to MM:SS
  const formatSeconds = (sec) => {
    if (!sec) return '0:00';
    const totalSeconds = Math.floor(sec);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const handlePlayPause = (song) => {
    if (currentSong?.videoId === song.videoId) {
      if (playerContext) {
        if (isPlaying) playerContext.pauseVideo();
        else playerContext.playVideo();
      }
    } else {
      setCurrentSong(song);
      setPlaybackProgress(0);
      setDuration(0);
      setIsPlaying(false);
      setPlayerContext(null);
    }
  };

  const handleSeek = (e) => {
    if (!playerContext || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, clickX / rect.width));
    const seekTime = percentage * duration;
    playerContext.seekTo(seekTime, true);
    setPlaybackProgress(seekTime);
  };

  return (
    <div className="flex-1 overflow-y-auto pb-32 scroll-smooth bg-surface-darker/20 relative">
      <div className="px-6 py-4">

        {/* Minimal Toolbar Filters */}
        {tags.length > 0 && (
          <div className="mb-6">
            {/* Toolbar */}
            <div className="flex items-center justify-between border-b border-white/5 pb-4">
              <div className="flex flex-wrap items-center gap-6">
                {['genre', 'mood', 'status'].map(type => {
                  const availableTags = tags.filter(t => t.type === type);
                  if (availableTags.length === 0) return null;

                  const hasActive = selectedTags.some(t => availableTags.find(tag => tag.value === t));
                  const isActiveDropdown = activeDropdown === type;

                  return (
                    <button
                      key={type}
                      onClick={() => setActiveDropdown(isActiveDropdown ? null : type)}
                      className={`flex items-center gap-1 text-sm font-semibold transition-colors relative ${isActiveDropdown || hasActive ? 'text-white' : 'text-slate-400 hover:text-white capitalize'}`}
                    >
                      <span className="capitalize">{type}</span>
                      <span className="material-icons text-[16px] leading-none mb-0.5">{isActiveDropdown ? 'expand_less' : 'expand_more'}</span>
                      {hasActive && (
                        <span className="absolute -top-1 -right-2 w-1.5 h-1.5 rounded-full bg-white"></span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Right Controls */}
              <div className="flex items-center gap-4">
                {selectedTags.length > 0 && (
                  <button
                    onClick={() => {
                      const params = new URLSearchParams(location.search);
                      params.delete('tags');
                      navigate(`/results?${params.toString()}`);
                    }}
                    className="flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white transition-all bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg"
                  >
                    <span className="material-icons text-sm">clear_all</span> Clear Filters
                  </button>
                )}
              </div>
            </div>

            {/* Expanded Panel (Inline) */}
            <AnimatePresence>
              {activeDropdown && (
                <motion.div
                  initial={{ opacity: 0, height: 0, marginTop: 0 }}
                  animate={{ opacity: 1, height: 'auto', marginTop: 16 }}
                  exit={{ opacity: 0, height: 0, marginTop: 0 }}
                  transition={{ duration: 0.25, ease: 'easeInOut' }}
                  className="pb-2 relative overflow-hidden"
                >
                  <button onClick={() => setActiveDropdown(null)} className="absolute right-0 top-1 text-xs font-medium text-slate-400 hover:text-white transition-colors px-2 py-1 z-10">
                    Close
                  </button>

                  <div className="flex flex-wrap gap-2.5 pr-14 pt-2">
                    {tags.filter(t => t.type === activeDropdown).map((tag, i) => {
                      const isActive = selectedTags.includes(tag.value);

                      let activeClass = 'bg-white text-black border-white hover:bg-neutral-200';
                      if (tag.type === 'genre') {
                        activeClass = 'bg-gradient-to-r from-indigo-500 via-purple-500 to-fuchsia-500 text-white border-transparent shadow-[0_0_15px_rgba(168,85,247,0.6)] font-semibold flex-1 sm:flex-none';
                      } else if (tag.type === 'mood') {
                        activeClass = 'bg-gradient-to-r from-red-500 via-rose-500 to-pink-500 text-white border-transparent shadow-[0_0_15px_rgba(244,63,94,0.6)] font-semibold flex-1 sm:flex-none';
                      } else if (tag.type === 'status') {
                        activeClass = tag.value === 'Success'
                          ? 'bg-emerald-500 text-white border-transparent shadow-[0_0_15px_rgba(16,185,129,0.5)] font-semibold'
                          : 'bg-red-500 text-white border-transparent shadow-[0_0_15px_rgba(239,68,68,0.5)] font-semibold';
                      }

                      return (
                        <button
                          key={i}
                          onClick={() => toggleTag(tag.value)}
                          className={`px-4 py-1.5 rounded-[20px] text-xs font-medium transition-all flex items-center justify-center border ${isActive
                            ? activeClass
                            : 'bg-transparent text-slate-300 border-white/10 hover:border-white/30'
                            }`}
                        >
                          {tag.value}
                        </button>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex justify-center p-12">
              <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
            </div>
          ) : filteredSongs.length === 0 ? (
            <div className="text-center p-12 text-slate-500">
              <span className="material-icons text-4xl mb-4 block opacity-50">music_off</span>
              <p>No tracks found. Clear filters or load a playlist.</p>
            </div>
            ) : (
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-white/5 bg-surface-darker/50">
                      <th className="px-4 py-3 font-semibold w-16 text-center">Preview</th>
                      <th className="px-4 py-3 font-semibold w-1/3">Title</th>
                      <th className="px-4 py-3 font-semibold">Artist</th>
                      <th className="px-4 py-3 font-semibold">Genre</th>
                      <th className="px-4 py-3 font-semibold">Mood</th>
                      <th className="px-4 py-3 font-semibold w-10"></th>
                    </tr>
                  </thead>
                  <tbody className="text-sm divide-y divide-white/5">
                    {filteredSongs.map(song => (
                      <tr
                        key={song.id}
                        className={`group hover:bg-white/5 transition-colors ${currentSong?.videoId === song.videoId ? 'bg-primary/5' : ''}`}
                        onClick={() => setCurrentSong(song)}
                      >
                        <td className="px-4 py-4 whitespace-nowrap text-center">
                          <button
                            className={`flex items-center justify-center w-8 h-8 rounded-full transition-all mx-auto ${currentSong?.videoId === song.videoId
                              ? 'bg-primary/20 hover:bg-primary text-primary hover:text-white'
                              : 'border border-white/10 hover:bg-white/10 text-slate-400 hover:text-white'
                              }`}
                            onClick={(e) => { e.stopPropagation(); handlePlayPause(song); }}
                          >
                            <span className="material-icons text-sm">{(currentSong?.videoId === song.videoId && isPlaying) ? 'pause' : 'play_arrow'}</span>
                          </button>
                        </td>
                        <td className="px-4 py-4 cursor-pointer">
                          <div className="flex items-center gap-4">
                            {song.thumbnails?.[0]?.url ? (
                              <img
                                src={song.thumbnails[0].url}
                                alt={song.title}
                                className="h-10 w-10 rounded bg-surface-dark object-cover"
                              />
                            ) : (
                              <div className="h-10 w-10 rounded bg-surface-dark flex items-center justify-center">
                                <span className="material-icons text-slate-600 border">music_note</span>
                                </div>
                            )}
                            <div className="min-w-0">
                              <div className={`font-medium truncate transition-colors ${currentSong?.videoId === song.videoId ? 'text-primary' : 'text-white group-hover:text-primary'}`}>
                                {song.title}
                              </div>
                              <div className="text-xs text-slate-500 truncate">ID: {song.videoId}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-slate-300 truncate max-w-[150px]">{song.artists}</td>
                        <td className="px-4 py-4">
                          <div className="flex gap-2 flex-wrap">
                            {song.genres?.map((genre, i) => (
                              <span key={i} className="px-2 py-0.5 rounded text-[10px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 whitespace-nowrap">{genre}</span>
                            ))}
                            {song.success === false && (
                              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-500 border border-red-500/20 whitespace-nowrap">Failed</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex gap-2 flex-wrap">
                            {song.moods?.map((mood, i) => (
                              <span key={i} className="px-2 py-0.5 rounded text-[10px] font-medium bg-pink-500/10 text-pink-400 border border-pink-500/20 whitespace-nowrap">{mood}</span>
                            ))}
                            {(!song.moods || song.moods.length === 0) && (
                              <span className="text-slate-600 text-[10px] italic">Unknown</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4 text-right">
                          {song.url && (
                            <a href={song.url} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-white" onClick={e => e.stopPropagation()}>
                              <span className="material-icons text-sm">open_in_new</span>
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination placeholder matching CyberBase */}
        <div className="mt-8 flex items-center justify-between border-t border-white/5 pt-6">
          <p className="text-xs text-slate-500">
            Showing <span className="text-white font-medium">{songs.length > 0 ? page * limit + 1 : 0}</span> to <span className="text-white font-medium">{Math.min((page + 1) * limit, page * limit + songs.length)}</span> tracks
          </p>
          <div className="flex items-center gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => Math.max(0, p - 1))}
              className="px-3 py-2 rounded-lg bg-surface-darker text-slate-400 hover:text-white hover:bg-white/5 border border-white/10 text-xs font-medium uppercase tracking-wider transition-all disabled:opacity-50"
            >
              Prev
            </button>
            <div className="flex items-center bg-surface-darker rounded-lg border border-white/10 p-1">
              <span className="w-8 h-8 flex items-center justify-center rounded bg-primary text-white text-xs font-bold shadow-neon">{page + 1}</span>
            </div>
            <button
              disabled={songs.length < limit}
              onClick={() => setPage(p => p + 1)}
              className="px-3 py-2 rounded-lg bg-surface-darker text-slate-400 hover:text-white hover:bg-white/5 border border-white/10 text-xs font-medium uppercase tracking-wider transition-all disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
        <div className="h-20"></div>
      </div>

      {/* System Status Box */}
      <div className={`fixed right-8 ${currentSong ? 'bottom-20' : 'bottom-6'} z-40 transition-all duration-300`}>
        <div className="w-80 bg-gradient-to-br from-[#1a1325] to-[#120d1a] border border-purple-500/20 rounded-2xl p-5 shadow-[0_8px_32px_rgba(168,85,247,0.15)] backdrop-blur-xl">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-icons text-purple-400 text-sm">bolt</span>
            <h3 className="text-sm font-bold text-white tracking-widest uppercase truncate">System Status</h3>
          </div>

          {(() => {
            const successCount = tags.find(t => t.type === 'status' && t.value === 'Success')?.count || 0;
            const failedCount = tags.find(t => t.type === 'status' && t.value === 'Failed')?.count || 0;
            const totalCount = successCount + failedCount;
            const successPercentage = totalCount > 0 ? (successCount / totalCount) * 100 : 0;

            return (
              <>
                <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden mb-3">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full shadow-[0_0_10px_rgba(168,85,247,0.8)]"
                    style={{ width: `${successPercentage}%` }}
                  ></div>
                </div>

                <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
                  <span>Songs: {totalCount}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-green-400">{successCount} OK</span>
                    <span className="text-red-400">{failedCount} ERR</span>
                  </div>
                </div>
              </>
            );
          })()}
        </div>
      </div>

      {/* CyberBase Fixed Player */}
      {currentSong && (
        <div className="fixed bottom-0 left-0 right-0 bg-surface-darker/95 backdrop-blur-md border-t border-primary/30 h-16 px-6 flex items-center justify-between z-50 shadow-[0_-5px_20px_rgba(0,0,0,0.5)]">
          <div className="flex items-center gap-3 w-1/3">
            {currentSong.thumbnails?.[0]?.url ? (
              <img src={currentSong.thumbnails[0].url} alt={currentSong.title} className="w-10 h-10 rounded object-cover" />
            ) : (
              <div className="w-10 h-10 flex items-center justify-center bg-primary/20 rounded text-primary">
                <span className="material-icons text-lg">audiotrack</span>
              </div>
            )}
            <div className="min-w-0">
              <h4 className="text-sm font-bold text-white mb-0 truncate">Preview: {currentSong.title}</h4>
              <p className="text-[10px] text-slate-400 font-mono truncate">{formatSeconds(playbackProgress)} / {formatSeconds(duration)} • {currentSong.artists}</p>
            </div>
          </div>

          <div className="flex items-center justify-center gap-4 w-1/3 max-w-lg z-50">
            <div className="opacity-0 absolute pointer-events-none">
              <YouTube
                videoId={currentSong.videoId}
                opts={{
                  height: '40',
                  width: '100',
                  playerVars: {
                    autoplay: 1,
                    controls: 0,
                  },
                }}
                onReady={handlePlayerReady}
                onStateChange={handlePlayerStateChange}
              />
            </div>
            <button className="text-slate-400 hover:text-white transition-colors" onClick={() => window.open(currentSong.url, '_blank')}><span className="material-icons text-xl">open_in_new</span></button>
            <button
              className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center shadow-neon hover:scale-105 transition-transform"
              onClick={() => setCurrentSong(null)}
            >
              <span className="material-icons text-lg">stop</span>
            </button>
            <div className="flex gap-1 h-3 ml-2">
              <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`}></div>
              <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`}></div>
              <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`}></div>
              <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`}></div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-5 w-1/3 hidden md:flex">
            <div
              className="flex-1 max-w-[200px] h-6 flex items-center cursor-pointer group"
              onClick={handleSeek}
            >
              <div className="w-full h-1 bg-white/10 rounded-full relative overflow-hidden pointer-events-none">
                <div
                  className="absolute inset-y-0 left-0 bg-primary group-hover:bg-purple-400 group-hover:shadow-[0_0_10px_rgba(175,37,244,0.8)] transition-all"
                  style={{
                    width: duration ? `${Math.min(100, Math.max(0, (playbackProgress / duration) * 100))}%` : '0%',
                    transition: 'width 0.2s linear'
                  }}
                ></div>
              </div>
            </div>
            <button 
              className="text-xs font-medium bg-white/10 hover:bg-white/20 text-white px-3 py-1.5 rounded transition-colors"
              onClick={() => setCurrentSong(null)}
            >
              Close Preview
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Results;