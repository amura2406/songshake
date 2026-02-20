import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getSongs, getTags, retrySong } from '../../api';
import YouTube from 'react-youtube';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import TagIcon from '../../components/ui/TagIcon';



/**
 * Return Tailwind color classes for BPM based on tempo grouping.
 * Slow (≤70), Slow-Med (71-90), Medium (91-110), Med-Fast (111-130), Fast (>130)
 */
const getBpmColor = (bpm) => {
  if (!bpm) return { text: 'text-slate-600', dot: 'bg-slate-600' };
  const n = typeof bpm === 'string' ? parseInt(bpm) : bpm;
  if (isNaN(n)) return { text: 'text-slate-600', dot: 'bg-slate-600' };
  if (n <= 70) return { text: 'text-blue-400', dot: 'bg-blue-400' };
  if (n <= 90) return { text: 'text-cyan-400', dot: 'bg-cyan-400' };
  if (n <= 110) return { text: 'text-emerald-400', dot: 'bg-emerald-400' };
  if (n <= 130) return { text: 'text-amber-400', dot: 'bg-amber-400' };
  return { text: 'text-rose-400', dot: 'bg-rose-400' };
};

/**
 * Return Tailwind color class for play count based on popularity tier.
 * Parses formatted strings like "12M", "123K", "3.5B".
 */
const getPlayCountColor = (playCount) => {
  if (!playCount || playCount === '-') return 'text-slate-600';
  const str = String(playCount).toUpperCase();
  const numPart = parseFloat(str);
  if (isNaN(numPart)) return 'text-slate-600';

  if (str.includes('B')) return 'text-amber-300';        // Billions — legendary
  if (str.includes('M') && numPart >= 100) return 'text-purple-400'; // 100M+ — mega hit
  if (str.includes('M')) return 'text-fuchsia-400';      // Millions — hit
  if (str.includes('K') && numPart >= 100) return 'text-emerald-400'; // 100K+ — popular
  if (str.includes('K')) return 'text-teal-400';          // Thousands — growing
  return 'text-slate-500';                                // Low / numeric
};

const Results = () => {
  const [songs, setSongs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [totalSongs, setTotalSongs] = useState(0);
  const [currentSong, setCurrentSong] = useState(null);
  const [tags, setTags] = useState([]);
  const [selectedTags, setSelectedTags] = useState([]);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [filteredSongs, setFilteredSongs] = useState([]);
  const [playerContext, setPlayerContext] = useState(null);
  const [playbackProgress, setPlaybackProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [retrying, setRetrying] = useState({});  // videoId → 'loading' | 'done' | 'error'
  const [toast, setToast] = useState(null);  // { message, type }
  const limit = 50;
  const totalPages = Math.max(1, Math.ceil(totalSongs / limit));

  const location = useLocation();
  const navigate = useNavigate();

  // Parse URL query parameter
  const queryTags = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const ts = params.get('tags');
    return ts ? ts.split(',') : [];
  }, [location.search]);

  const queryBpm = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return {
      min: params.get('min_bpm') ? parseInt(params.get('min_bpm')) : null,
      max: params.get('max_bpm') ? parseInt(params.get('max_bpm')) : null
    };
  }, [location.search]);

  const [bpmRange, setBpmRange] = useState([20, 200]);

  // Sync initial state from URL on mount/url change
  useEffect(() => {
    setSelectedTags(queryTags);
    if (queryBpm.min || queryBpm.max) {
      setBpmRange([queryBpm.min || 20, queryBpm.max || 200]);
    } else {
      setBpmRange([20, 200]);
    }
    setPage(0); // Reset page on filter change
  }, [queryTags, queryBpm.min, queryBpm.max]);


  useEffect(() => {
    loadData();
    loadTags();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, queryTags, queryBpm.min, queryBpm.max]); // Reload when page or tags query change

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
  }, [playerContext, isPlaying, duration]);

  const loadTags = useCallback(async () => {
    try {
      const fetchedTags = await getTags();
      const transformedTags = fetchedTags.map(t => ({ type: t.type, value: t.name, count: t.count }));

      // Ensure that URL tags are also present, even if count is 0
      queryTags.forEach(qt => {
        if (!transformedTags.some(t => t.value === qt)) {
          transformedTags.push({ type: 'unknown', value: qt });
        }
      });
      setTags(transformedTags);
    } catch (error) {
      console.error("Failed to fetch available filter tags", error);
    }
  }, [queryTags]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const tagsString = queryTags.length > 0 ? queryTags.join(',') : null;
      const response = await getSongs(page * limit, limit, tagsString, queryBpm.min, queryBpm.max);
      // Support both new { items, total } format and legacy array format
      const items = response.items || response;
      const total = response.total ?? items.length;
      const validSongs = (Array.isArray(items) ? items : []).filter(s => s.videoId);
      setSongs(validSongs);
      setFilteredSongs(validSongs);
      setTotalSongs(total);
    } catch (error) {
      console.error("Failed to load songs", error);
    } finally {
      setLoading(false);
    }
  }, [queryTags, page, limit, queryBpm.min, queryBpm.max]);

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

  const applyBpmFilter = (min, max) => {
    const params = new URLSearchParams(location.search);
    if (min !== null && max !== null) {
      params.set('min_bpm', min);
      params.set('max_bpm', max);
    } else {
      params.delete('min_bpm');
      params.delete('max_bpm');
    }
    navigate(`/results?${params.toString()}`);
  };



  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handlePlayerReady = (event) => {
    setPlayerContext(event.target);
    const dur = event.target.getDuration();
    setDuration(dur || 0);
    setIsPlaying(true);
  };

  const handlePlayerError = () => {
    showToast('Preview unavailable — this track cannot be embedded. Click the title to open on YouTube Music.', 'warning');
    stopPlayback();
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

  const stopPlayback = () => {
    setCurrentSong(null);
    setPlayerContext(null);
    setIsPlaying(false);
    setPlaybackProgress(0);
    setDuration(0);
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

  const handleRetry = async (e, videoId) => {
    e.stopPropagation();
    if (retrying[videoId]) return;
    setRetrying(prev => ({ ...prev, [videoId]: 'loading' }));
    try {
      await retrySong(videoId);
      setRetrying(prev => ({ ...prev, [videoId]: 'done' }));
      // Reload after a brief delay to allow backend processing
      setTimeout(() => {
        loadData();
        setRetrying(prev => {
          const next = { ...prev };
          delete next[videoId];
          return next;
        });
      }, 3000);
    } catch (err) {
      const detail = err.response?.data?.detail || 'Retry failed';
      setRetrying(prev => ({ ...prev, [videoId]: detail }));
      setTimeout(() => {
        setRetrying(prev => {
          const next = { ...prev };
          delete next[videoId];
          return next;
        });
      }, 4000);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto scroll-smooth bg-surface-darker/20 relative flex flex-col pb-14">
      <div className="px-6 py-4 flex-1">

        {/* Minimal Toolbar Filters */}
        {tags.length > 0 && (
          <div className="mb-6">
            {/* Selected Filters (Persistent) */}
            {(selectedTags.length > 0 || queryBpm.min || queryBpm.max) && (
              <div className="flex flex-wrap items-center gap-2 mb-4">
                {selectedTags.map(tag => (
                  <button key={tag} onClick={() => toggleTag(tag)} className="flex items-center gap-1 px-3 py-1 rounded-full border border-white/20 text-xs font-medium text-white hover:bg-white/10 transition-colors">
                    {tag} <span className="material-icons text-[14px]">close</span>
                  </button>
                ))}
                {(queryBpm.min || queryBpm.max) && (
                  <button onClick={() => applyBpmFilter(null, null)} className="flex items-center gap-1 px-3 py-1 rounded-full border border-white/20 text-xs font-medium text-white hover:bg-white/10 transition-colors">
                    BPM: {queryBpm.min || 20} - {queryBpm.max || 200} <span className="material-icons text-[14px]">close</span>
                  </button>
                )}
                <button
                  onClick={() => {
                    const params = new URLSearchParams(location.search);
                    params.delete('tags');
                    params.delete('min_bpm');
                    params.delete('max_bpm');
                    navigate(`/results?${params.toString()}`);
                  }}
                  className="text-xs font-medium text-white underline underline-offset-4 hover:text-primary transition-colors ml-2"
                >
                  Clear All Filters
                </button>
              </div>
            )}

            {/* Toolbar */}
            <div className="flex items-center justify-between border-b border-white/5 pb-4">
              <div className="flex flex-wrap items-center gap-6">
                {['genre', 'mood', 'instrument', 'bpm', 'status'].map(type => {
                  let availableTags = tags.filter(t => t.type === type);
                  if (type === 'bpm') availableTags = [{ value: 'bpm' }];
                  if (availableTags.length === 0) return null;

                  const isActiveDropdown = activeDropdown === type;

                  return (
                    <button
                      key={type}
                      onClick={() => setActiveDropdown(isActiveDropdown ? null : type)}
                      className={`flex items-center gap-1 text-sm font-semibold transition-colors relative ${isActiveDropdown ? 'text-white' : 'text-slate-400 hover:text-white capitalize'}`}
                    >
                      <span className="capitalize">{type}</span>
                      <span className="material-icons text-[16px] leading-none mb-0.5">{isActiveDropdown ? 'expand_less' : 'expand_more'}</span>
                    </button>
                  );
                })}
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
                    {activeDropdown === 'bpm' ? (
                      <div className="w-full max-w-md py-4">
                        <div className="flex items-center justify-between text-xs text-slate-400 font-medium mb-4">
                          <span>BPM Range</span>
                          <span className="text-white bg-white/10 px-2 py-1 rounded">{bpmRange[0]} - {bpmRange[1]}</span>
                        </div>
                        <input
                          type="range"
                          min="20"
                          max="200"
                          value={bpmRange[1]}
                          onChange={(e) => setBpmRange([20, parseInt(e.target.value)])}
                          onMouseUp={() => applyBpmFilter(bpmRange[0], bpmRange[1])}
                          onTouchEnd={() => applyBpmFilter(bpmRange[0], bpmRange[1])}
                          className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer mb-6"
                        />
                        <div className="flex gap-2">
                          {[
                            { label: 'Slow', max: 70 },
                            { label: 'Slow-Med', max: 90 },
                            { label: 'Medium', max: 110 },
                            { label: 'Med-Fast', max: 130 },
                            { label: 'Fast', max: 200 }
                          ].map(preset => (
                            <button
                              key={preset.label}
                              onClick={() => {
                                setBpmRange([20, preset.max]);
                                applyBpmFilter(20, preset.max);
                              }}
                              className="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
                            >
                              {preset.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : (
                      tags.filter(t => t.type === activeDropdown).map((tag, i) => {
                        const isActive = selectedTags.includes(tag.value);

                        let activeClass = 'bg-white text-black border-white hover:bg-neutral-200';
                        if (tag.type === 'genre') {
                          activeClass = 'bg-gradient-to-r from-indigo-500 via-purple-500 to-fuchsia-500 text-white border-transparent shadow-[0_0_15px_rgba(168,85,247,0.6)] font-semibold flex-1 sm:flex-none';
                        } else if (tag.type === 'mood') {
                          activeClass = 'bg-gradient-to-r from-red-500 via-rose-500 to-pink-500 text-white border-transparent shadow-[0_0_15px_rgba(244,63,94,0.6)] font-semibold flex-1 sm:flex-none';
                        } else if (tag.type === 'instrument') {
                          activeClass = 'bg-gradient-to-r from-teal-500 via-cyan-500 to-blue-500 text-white border-transparent shadow-[0_0_15px_rgba(20,184,166,0.6)] font-semibold flex-1 sm:flex-none';
                        } else if (tag.type === 'status') {
                          activeClass = tag.value === 'Success'
                            ? 'bg-emerald-500 text-white border-transparent shadow-[0_0_15px_rgba(16,185,129,0.5)] font-semibold'
                            : 'bg-red-500 text-white border-transparent shadow-[0_0_15px_rgba(239,68,68,0.5)] font-semibold';
                        }

                        return (
                          <button
                            key={i}
                            onClick={() => toggleTag(tag.value)}
                            className={`px-4 py-1.5 rounded-[20px] text-xs font-medium transition-all flex items-center justify-center gap-1.5 border ${isActive
                              ? activeClass
                              : 'bg-transparent text-slate-300 border-white/10 hover:border-white/30'
                              }`}
                          >
                            <TagIcon type={tag.type} value={tag.value} size={14} />
                            {tag.value}
                          </button>
                        );
                      })
                    )}
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
                  <th className="px-4 py-3 font-semibold w-12 text-center">#</th>
                  <th className="px-4 py-3 font-semibold">Title</th>
                  <th className="px-4 py-3 font-semibold min-w-[220px]">Artist</th>
                  <th className="px-4 py-3 font-semibold">Genre</th>
                  <th className="px-4 py-3 font-semibold">Mood</th>
                  <th className="px-4 py-3 font-semibold">Instrument</th>
                  <th className="px-4 py-3 font-semibold text-center">BPM</th>
                  <th className="px-4 py-3 font-semibold text-center">Plays</th>
                </tr>
              </thead>
              <tbody className="text-sm divide-y divide-white/5">
                {filteredSongs.map((song, index) => {
                  const isCurrent = currentSong?.videoId === song.videoId;
                  const isPlayable = song.isMusic !== false;
                  return (
                    <tr
                      key={song.id}
                      className={`group hover:bg-white/5 transition-colors ${isCurrent ? 'bg-primary/5' : ''} ${isPlayable ? 'cursor-pointer' : 'cursor-default'}`}
                      onClick={() => { if (isPlayable) handlePlayPause(song); }}
                    >
                      <td className="px-4 py-4 whitespace-nowrap text-center">
                        <span className="text-xs text-slate-500 font-mono tabular-nums">{page * limit + index + 1}</span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-4">
                          <div className="album-art-wrapper relative flex-shrink-0">
                            {song.thumbnails?.length > 0 ? (
                              <img
                                src={song.thumbnails[song.thumbnails.length - 1].url}
                                alt={song.title}
                                referrerPolicy="no-referrer"
                                className="h-12 w-12 rounded-full bg-surface-dark object-cover"
                              />
                            ) : (
                              <div className="h-12 w-12 rounded-full bg-surface-dark flex items-center justify-center">
                                <span className="material-icons text-slate-600">music_note</span>
                              </div>
                            )}
                            {/* Play/Block overlay */}
                            {!isPlayable ? (
                              <div className="album-art-overlay album-art-overlay--blocked" title="Non-music content">
                                <span className="material-icons text-lg">block</span>
                              </div>
                            ) : isCurrent ? (
                              <button
                                className={`album-art-overlay album-art-overlay--playing ${isPlaying ? 'is-playing' : ''}`}
                                onClick={(e) => { e.stopPropagation(); handlePlayPause(song); }}
                                title={isPlaying ? 'Pause' : 'Play'}
                              >
                                <span className="material-icons text-lg">
                                  {isPlaying ? 'pause' : 'play_arrow'}
                                </span>
                              </button>
                            ) : (
                              <button
                                className="album-art-overlay album-art-overlay--playable"
                                onClick={(e) => { e.stopPropagation(); handlePlayPause(song); }}
                                title="Preview song"
                              >
                                <span className="material-icons text-lg">play_arrow</span>
                              </button>
                            )}
                          </div>
                          <div className="min-w-0">
                            {song.success === false && song.isMusic !== false && (
                              <span className="inline-flex items-center gap-1 mb-0.5">
                                <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-500 border border-red-500/20 whitespace-nowrap">Failed</span>
                                {retrying[song.videoId] === 'loading' ? (
                                  <span className="w-4 h-4 rounded-full border border-primary border-t-transparent animate-spin inline-block" title="Retrying…" />
                                ) : retrying[song.videoId] === 'done' ? (
                                  <span className="material-icons text-emerald-400 text-sm" title="Retry queued">check_circle</span>
                                ) : typeof retrying[song.videoId] === 'string' ? (
                                  <span className="text-[10px] text-red-400 italic" title={retrying[song.videoId]}>error</span>
                                ) : (
                                  <button
                                    className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-white/10"
                                    onClick={(e) => handleRetry(e, song.videoId)}
                                    title="Retry enrichment"
                                  >
                                    <span className="material-icons text-slate-400 hover:text-primary text-sm">refresh</span>
                                  </button>
                                )}
                              </span>
                            )}
                            <a
                              href={song.url || `https://music.youtube.com/watch?v=${song.videoId}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={`font-medium truncate block transition-colors hover:underline ${isCurrent ? 'text-primary' : 'text-white group-hover:text-primary'}`}
                              onClick={e => e.stopPropagation()}
                            >
                              {song.title}
                            </a>
                            <div className="text-[10px] text-slate-500 truncate">
                              {song.isMusic === false ? (
                                <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 whitespace-nowrap">Non-Music</span>
                              ) : song.album ? (
                                <>
                                  {song.album.id ? (
                                    <a
                                      href={`https://music.youtube.com/browse/${song.album.id}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="hover:text-primary transition-colors"
                                      onClick={e => e.stopPropagation()}
                                    >
                                      {song.album.name || song.album}
                                    </a>
                                  ) : (
                                    <span>{typeof song.album === 'string' ? song.album : song.album.name}</span>
                                  )}
                                  {song.year && <span> · {song.year}</span>}
                                </>
                              ) : song.year ? (
                                <span>{song.year}</span>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4 min-w-[220px]">
                        <div className="flex gap-1 items-center whitespace-nowrap">
                          {Array.isArray(song.artists) ? (
                            song.artists.map((artist, i) => (
                              <span key={i}>
                                {artist.id ? (
                                  <a
                                    href={`https://music.youtube.com/channel/${artist.id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-slate-300 hover:text-primary transition-colors text-sm"
                                    onClick={e => e.stopPropagation()}
                                  >
                                    {artist.name}
                                  </a>
                                ) : (
                                  <span className="text-slate-300 text-sm">{artist.name}</span>
                                )}
                                {i < song.artists.length - 1 && <span className="text-slate-600">, </span>}
                              </span>
                            ))
                          ) : (
                            <span className="text-slate-300 text-sm">{song.artists}</span>
                          )}
                        </div>
                      </td>

                      <td className="px-4 py-4">
                        <div className="flex gap-2 flex-wrap">
                          {song.genres?.map((genre, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 whitespace-nowrap"><TagIcon type="genre" value={genre} size={10} />{genre}</span>
                          ))}

                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex gap-2 flex-wrap">
                          {song.moods?.map((mood, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-pink-500/10 text-pink-400 border border-pink-500/20 whitespace-nowrap"><TagIcon type="mood" value={mood} size={10} />{mood}</span>
                          ))}
                          {(!song.moods || song.moods.length === 0) && (
                            <span className="text-slate-600 text-[10px] italic">Unknown</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex gap-2 flex-wrap">
                          {song.instruments?.map((inst, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-teal-500/10 text-teal-400 border border-teal-500/20 whitespace-nowrap"><TagIcon type="instrument" value={inst} size={10} />{inst}</span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-4 text-center text-xs font-semibold">
                        {song.bpm ? (
                          <span className={`inline-flex items-center gap-1.5 ${getBpmColor(song.bpm).text}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${getBpmColor(song.bpm).dot}`}></span>
                            {song.bpm}
                          </span>
                        ) : (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>
                      <td className={`px-4 py-4 text-center text-xs font-semibold ${getPlayCountColor(song.playCount)}`}>
                        {song.playCount || <span className="text-slate-600">-</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

      </div>

      {/* ── Toast Notification ── */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 30 }}
            transition={{ duration: 0.3 }}
            className={`fixed bottom-20 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-xs font-medium shadow-lg backdrop-blur-xl border ${toast.type === 'warning'
              ? 'bg-amber-500/20 border-amber-500/30 text-amber-200'
              : 'bg-white/10 border-white/20 text-white'
              }`}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Fixed Status Bar ── */}
      <div className="status-bar">
        {/* Left: track count */}
        <div className="status-bar__left">
          <p className="text-xs text-slate-500 whitespace-nowrap">
            Songs: <span className="text-white font-medium">{totalSongs}</span>
            {' · '}
            <span className="text-white font-medium">{songs.length > 0 ? page * limit + 1 : 0}</span>–<span className="text-white font-medium">{Math.min((page + 1) * limit, page * limit + songs.length)}</span>
          </p>
        </div>

        {/* Center: trackbar (60%) */}
        <div className="status-bar__center">
          {currentSong ? (
            <>
              {/* Hidden YouTube player */}
              <div className="opacity-0 absolute pointer-events-none w-0 h-0 overflow-hidden">
                <YouTube
                  videoId={currentSong.playableVideoId || currentSong.videoId}
                  opts={{
                    height: '1',
                    width: '1',
                    playerVars: { autoplay: 1, controls: 0 },
                  }}
                  onReady={handlePlayerReady}
                  onStateChange={handlePlayerStateChange}
                  onError={handlePlayerError}
                />
              </div>

              <button
                className="status-bar__btn"
                onClick={() => handlePlayPause(currentSong)}
                title={isPlaying ? 'Pause' : 'Play'}
              >
                <span className="material-icons text-sm">{isPlaying ? 'pause' : 'play_arrow'}</span>
              </button>
              <button
                className="status-bar__btn text-rose-400 hover:text-rose-300"
                onClick={stopPlayback}
                title="Stop"
              >
                <span className="material-icons text-sm">stop</span>
              </button>

              <span className="status-bar__time">{formatSeconds(playbackProgress)}</span>

              <div className="status-bar__seek" onClick={handleSeek}>
                <div className="status-bar__seek-bg">
                  <div
                    className="status-bar__seek-fill"
                    style={{ width: duration ? `${Math.min(100, Math.max(0, (playbackProgress / duration) * 100))}%` : '0%' }}
                  />
                </div>
              </div>

              <span className="status-bar__time">{formatSeconds(duration)}</span>

              {/* EQ visualiser */}
              <div className="flex gap-0.5 h-3 ml-1">
                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
              </div>
            </>

          ) : (
            <span className="text-[10px] text-slate-600 italic">No track playing</span>
          )}
        </div>

        {/* Right: pagination */}
        <div className="status-bar__right">
          <span className="text-[10px] text-slate-500 mr-1">{page + 1}/{totalPages}</span>
          <button
            disabled={page === 0}
            onClick={() => setPage(p => Math.max(0, p - 1))}
            className="px-3 py-1.5 rounded-lg bg-surface-darker text-slate-400 hover:text-white hover:bg-white/5 border border-white/10 text-xs font-medium uppercase tracking-wider transition-all disabled:opacity-50"
          >
            Prev
          </button>
          <div className="flex items-center bg-surface-darker rounded-lg border border-white/10 p-0.5">
            <span className="w-7 h-7 flex items-center justify-center rounded bg-primary text-white text-xs font-bold shadow-neon">{page + 1}</span>
          </div>
          <button
            disabled={page + 1 >= totalPages}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 rounded-lg bg-surface-darker text-slate-400 hover:text-white hover:bg-white/5 border border-white/10 text-xs font-medium uppercase tracking-wider transition-all disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default Results;