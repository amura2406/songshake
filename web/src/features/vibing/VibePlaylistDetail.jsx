import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getVibePlaylist, approveVibePlaylist, deleteVibePlaylist, getYoutubeQuota } from '../../api';
import { ArrowLeft, Sparkles, CheckCircle2, Loader2, ExternalLink, Music, Trash2, Disc3, Heart, AlertTriangle } from 'lucide-react';
import YouTube from 'react-youtube';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import TagIcon from '../../components/ui/TagIcon';

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

const formatSeconds = (sec) => {
    if (!sec) return '0:00';
    const totalSeconds = Math.floor(sec);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

const VibePlaylistDetail = () => {
    const { playlistId } = useParams();
    const navigate = useNavigate();
    const [playlist, setPlaylist] = useState(null);
    const [loading, setLoading] = useState(true);
    const [approving, setApproving] = useState(false);
    const [approveResult, setApproveResult] = useState(null);
    const [error, setError] = useState(null);

    // Player state
    const [currentSong, setCurrentSong] = useState(null);
    const [playerContext, setPlayerContext] = useState(null);
    const [playbackProgress, setPlaybackProgress] = useState(0);
    const [duration, setDuration] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [toast, setToast] = useState(null);
    const [quota, setQuota] = useState(null);

    const loadPlaylist = useCallback(async () => {
        try {
            setLoading(true);
            const data = await getVibePlaylist(playlistId);
            setPlaylist(data);
        } catch (err) {
            console.error('Failed to load playlist', err);
            setError('Failed to load playlist');
        } finally {
            setLoading(false);
        }
    }, [playlistId]);

    useEffect(() => { loadPlaylist(); }, [loadPlaylist]);

    // Fetch quota for draft playlists
    useEffect(() => {
        if (playlist && playlist.status !== 'synced') {
            getYoutubeQuota().then(setQuota).catch(() => { });
        }
    }, [playlist]);

    // Player progress tracker
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

    // ── Playlist stats (genres, moods, BPM range) ──
    const playlistStats = useMemo(() => {
        if (!playlist?.tracks?.length) return null;
        const genreCount = {};
        const moodCount = {};
        const bpms = [];

        for (const t of playlist.tracks) {
            (t.genres || []).forEach(g => { genreCount[g] = (genreCount[g] || 0) + 1; });
            (t.moods || []).forEach(m => { moodCount[m] = (moodCount[m] || 0) + 1; });
            if (t.bpm) bpms.push(typeof t.bpm === 'string' ? parseInt(t.bpm) : t.bpm);
        }

        const topGenres = Object.entries(genreCount)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 6);
        const topMoods = Object.entries(moodCount)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 5);

        const bpmMin = bpms.length ? Math.min(...bpms) : null;
        const bpmMax = bpms.length ? Math.max(...bpms) : null;

        return { topGenres, topMoods, bpmMin, bpmMax };
    }, [playlist]);

    const handleApprove = async () => {
        try {
            setApproving(true);
            setError(null);
            const result = await approveVibePlaylist(playlistId);
            setApproveResult(result);
            await loadPlaylist();
        } catch (err) {
            const detail = err.response?.data?.detail || 'Sync failed';
            setError(detail);
        } finally {
            setApproving(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Delete this playlist? This cannot be undone.')) return;
        try {
            await deleteVibePlaylist(playlistId);
            navigate('/vibing');
        } catch (err) {
            setError(err.response?.data?.detail || 'Delete failed');
        }
    };

    const showToast = (message, type = 'info') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    // --- Player controls ---
    const handlePlayPause = (track) => {
        if (currentSong?.videoId === track.videoId) {
            if (playerContext) {
                if (isPlaying) playerContext.pauseVideo();
                else playerContext.playVideo();
            }
        } else {
            setCurrentSong(track);
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

    const handlePlayerReady = (event) => {
        setPlayerContext(event.target);
        setDuration(event.target.getDuration() || 0);
        setIsPlaying(true);
    };

    const handlePlayerError = () => {
        showToast('Preview unavailable — this track cannot be embedded.', 'warning');
        stopPlayback();
    };

    const handlePlayerStateChange = (event) => {
        if (event.data === 1) { setIsPlaying(true); setDuration(event.target.getDuration()); }
        else if (event.data === 2) { setIsPlaying(false); }
    };

    const handleSeek = (e) => {
        if (!playerContext || !duration) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const seekTime = pct * duration;
        playerContext.seekTo(seekTime, true);
        setPlaybackProgress(seekTime);
    };

    if (loading) return (
        <div className="flex justify-center items-center h-64">
            <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
    );

    if (!playlist) return (
        <div className="p-6 text-center text-slate-500">
            <p>Playlist not found.</p>
            <button onClick={() => navigate('/vibing')} className="text-primary hover:underline mt-2 text-sm">← Back to Vibing</button>
        </div>
    );

    const seedTrack = playlist.tracks?.find(t => t.is_seed);

    // Quota estimation
    const trackTotal = playlist.tracks?.length || 0;
    const estimatedCost = 50 + trackTotal * 50;
    const quotaRemaining = quota ? quota.units_limit - quota.units_used : null;
    const quotaInsufficient = quotaRemaining !== null && estimatedCost > quotaRemaining;

    return (
        <div className="flex-1 overflow-y-auto pb-14">
            <div className="px-6 py-4">
                {/* Back button */}
                <button onClick={() => navigate('/vibing')} className="flex items-center gap-1 text-sm text-slate-400 hover:text-white transition-colors mb-4">
                    <ArrowLeft size={16} /> Back to Vibing
                </button>

                {/* ── Header ── */}
                <div className="flex items-start justify-between gap-4 mb-4">
                    <div>
                        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                            <Sparkles className="text-primary" size={24} />
                            {playlist.title}
                        </h2>
                        <p className="text-slate-400 text-sm mt-1">
                            {playlist.tracks?.length || 0} tracks · Created {new Date(playlist.created_at).toLocaleString()}
                        </p>
                    </div>

                    <div className="flex items-start gap-2 shrink-0">
                        <button onClick={handleDelete} className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium text-slate-400 border border-white/10 hover:border-red-500/30 hover:text-red-400 hover:bg-red-500/5 transition-all" title="Delete playlist">
                            <Trash2 size={15} /> Delete
                        </button>
                        {playlist.status === 'synced' ? (
                            <div className="flex items-center gap-2">
                                <span className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-green-500/10 text-green-400 text-sm font-medium border border-green-500/20">
                                    <CheckCircle2 size={16} /> Synced
                                </span>
                                {(approveResult?.youtube_url || playlist.youtube_playlist_id) && (
                                    <a href={approveResult?.youtube_url || `https://music.youtube.com/playlist?list=${playlist.youtube_playlist_id}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-primary/10 text-primary text-sm font-medium border border-primary/20 hover:bg-primary/20 transition-colors">
                                        <ExternalLink size={14} /> Open on YouTube Music
                                    </a>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-end gap-1">
                                <button onClick={handleApprove} disabled={approving || quotaInsufficient}
                                    className="bg-primary hover:bg-fuchsia-600 text-white px-6 py-2.5 rounded-xl font-bold flex items-center gap-2 shadow-neon disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                    title={quotaRemaining !== null ? `Costs ${estimatedCost.toLocaleString()} units · ${quotaRemaining.toLocaleString()} remaining` : ''}>
                                    {approving ? (<><Loader2 size={18} className="animate-spin" /> Syncing…</>) : (<><CheckCircle2 size={18} /> Approve & Sync</>)}
                                </button>
                                {quotaInsufficient ? (
                                    <span className="text-[10px] text-red-400 flex items-center gap-1">
                                        <AlertTriangle size={10} />
                                        Needs {estimatedCost.toLocaleString()} units, {quotaRemaining?.toLocaleString()} left
                                    </span>
                                ) : quota && (
                                    <span className="text-[10px] text-slate-500">
                                        {estimatedCost.toLocaleString()} of {quotaRemaining?.toLocaleString()} units remaining
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* ── AI Description ── */}
                {playlist.description && (
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-sm text-slate-300 italic mb-5 pl-1 border-l-2 border-primary/30 ml-1 leading-relaxed max-w-3xl"
                    >
                        {playlist.description}
                    </motion.p>
                )}

                {/* ── Playlist Stats (Genres / Moods / BPM range) ── */}
                {playlistStats && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mb-6 grid grid-cols-3 gap-4"
                    >
                        {/* Genres */}
                        <div className="bg-surface-dark rounded-xl border border-white/5 p-4">
                            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2.5 flex items-center gap-1.5">
                                <Disc3 size={11} /> Top Genres
                            </h4>
                            <div className="flex flex-wrap gap-1.5">
                                {playlistStats.topGenres.map(([genre, count]) => (
                                    <span key={genre} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                        <TagIcon type="genre" value={genre} size={10} />{genre}
                                        <span className="text-purple-500/50 ml-0.5">{count}</span>
                                    </span>
                                ))}
                            </div>
                        </div>

                        {/* Moods */}
                        <div className="bg-surface-dark rounded-xl border border-white/5 p-4">
                            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2.5 flex items-center gap-1.5">
                                <Heart size={11} /> Top Moods
                            </h4>
                            <div className="flex flex-wrap gap-1.5">
                                {playlistStats.topMoods.map(([mood, count]) => (
                                    <span key={mood} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-pink-500/10 text-pink-400 border border-pink-500/20">
                                        <TagIcon type="mood" value={mood} size={10} />{mood}
                                        <span className="text-pink-500/50 ml-0.5">{count}</span>
                                    </span>
                                ))}
                            </div>
                        </div>

                        {/* BPM range */}
                        <div className="bg-surface-dark rounded-xl border border-white/5 p-4">
                            <h4 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2.5 flex items-center gap-1.5">
                                <span className="material-icons text-[11px]">speed</span> BPM Range
                            </h4>
                            {playlistStats.bpmMin && playlistStats.bpmMax ? (
                                <div className="flex items-center gap-3">
                                    <span className={`text-xl font-bold tabular-nums ${getBpmColor(playlistStats.bpmMin).text}`}>{playlistStats.bpmMin}</span>
                                    <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden relative">
                                        <div className="absolute inset-0 bg-gradient-to-r from-blue-500 via-emerald-500 via-amber-500 to-rose-500 opacity-50 rounded-full" />
                                    </div>
                                    <span className={`text-xl font-bold tabular-nums ${getBpmColor(playlistStats.bpmMax).text}`}>{playlistStats.bpmMax}</span>
                                </div>
                            ) : (
                                <span className="text-slate-600 text-xs">No BPM data</span>
                            )}
                        </div>
                    </motion.div>
                )}

                {error && (
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-4 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">{error}</motion.div>
                )}

                {approveResult && (
                    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-4 px-4 py-3 bg-green-500/10 border border-green-500/20 rounded-xl text-green-400 text-sm">
                        ✅ Playlist synced! <a href={approveResult.youtube_url} target="_blank" rel="noopener noreferrer" className="underline hover:text-green-300">Open on YouTube Music →</a>
                    </motion.div>
                )}

                {/* Seed Track Highlight */}
                {seedTrack && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 bg-gradient-to-r from-primary/10 to-transparent rounded-xl border border-primary/20 p-5">
                        <div className="flex items-center gap-4">
                            <div className="album-art-wrapper relative flex-shrink-0 cursor-pointer" onClick={() => handlePlayPause(seedTrack)}>
                                {seedTrack.thumbnails?.length > 0 ? (
                                    <img src={seedTrack.thumbnails[seedTrack.thumbnails.length - 1].url} alt={seedTrack.title} referrerPolicy="no-referrer" className="h-16 w-16 rounded-full bg-surface-dark object-cover" />
                                ) : (
                                    <div className="h-16 w-16 rounded-full bg-surface-dark flex items-center justify-center"><Music size={24} className="text-slate-600" /></div>
                                )}
                                {currentSong?.videoId === seedTrack.videoId ? (
                                    <button className={`album-art-overlay album-art-overlay--playing ${isPlaying ? 'is-playing' : ''}`} onClick={(e) => { e.stopPropagation(); handlePlayPause(seedTrack); }}><span className="material-icons text-lg">{isPlaying ? 'pause' : 'play_arrow'}</span></button>
                                ) : (
                                    <button className="album-art-overlay album-art-overlay--playable" onClick={(e) => { e.stopPropagation(); handlePlayPause(seedTrack); }}><span className="material-icons text-lg">play_arrow</span></button>
                                )}
                            </div>
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-primary/20 text-primary border border-primary/30 uppercase tracking-wider">Seed Track</span>
                                </div>
                                <a href={`https://music.youtube.com/watch?v=${seedTrack.videoId}`} target="_blank" rel="noopener noreferrer" className="text-lg font-bold text-white hover:text-primary transition-colors">{seedTrack.title}</a>
                                <div className="text-sm text-slate-400 mt-0.5">
                                    {Array.isArray(seedTrack.artists) ? seedTrack.artists.map(a => a.name || a).join(', ') : seedTrack.artists}
                                    {seedTrack.bpm && <span className={`ml-3 ${getBpmColor(seedTrack.bpm).text}`}>{seedTrack.bpm} BPM</span>}
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}

                {/* ── Track Table ── */}
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-white/5 bg-surface-darker/50">
                                <th className="px-4 py-3 font-semibold w-12 text-center">#</th>
                                <th className="px-4 py-3 font-semibold">Title</th>
                                <th className="px-4 py-3 font-semibold min-w-[200px]">Artist</th>
                                <th className="px-4 py-3 font-semibold">Genre</th>
                                <th className="px-4 py-3 font-semibold">Mood</th>
                                <th className="px-4 py-3 font-semibold text-center">BPM</th>
                            </tr>
                        </thead>
                        <tbody className="text-sm divide-y divide-white/5">
                            {playlist.tracks?.map((track, index) => {
                                const isCurrent = currentSong?.videoId === track.videoId;
                                return (
                                    <tr key={track.videoId} className={`group hover:bg-white/5 transition-colors cursor-pointer ${isCurrent ? 'bg-primary/5' : ''} ${track.is_seed ? 'bg-primary/[0.03]' : ''}`} onClick={() => handlePlayPause(track)}>
                                        <td className="px-4 py-3 whitespace-nowrap text-center">
                                            <span className="text-xs text-slate-500 font-mono tabular-nums">{index + 1}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-3">
                                                <div className="album-art-wrapper relative flex-shrink-0">
                                                    {track.thumbnails?.length > 0 ? (
                                                        <img src={track.thumbnails[track.thumbnails.length - 1].url} alt={track.title} referrerPolicy="no-referrer" className="h-10 w-10 rounded-full bg-surface-dark object-cover" />
                                                    ) : (
                                                        <div className="h-10 w-10 rounded-full bg-surface-dark flex items-center justify-center"><span className="material-icons text-slate-600 text-sm">music_note</span></div>
                                                    )}
                                                    {isCurrent ? (
                                                        <button className={`album-art-overlay album-art-overlay--playing ${isPlaying ? 'is-playing' : ''}`} onClick={(e) => { e.stopPropagation(); handlePlayPause(track); }} title={isPlaying ? 'Pause' : 'Play'}><span className="material-icons text-lg">{isPlaying ? 'pause' : 'play_arrow'}</span></button>
                                                    ) : (
                                                        <button className="album-art-overlay album-art-overlay--playable" onClick={(e) => { e.stopPropagation(); handlePlayPause(track); }} title="Preview song"><span className="material-icons text-lg">play_arrow</span></button>
                                                    )}
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <a href={`https://music.youtube.com/watch?v=${track.videoId}`} target="_blank" rel="noopener noreferrer" className={`font-medium truncate block transition-colors hover:underline ${isCurrent ? 'text-primary' : 'text-white group-hover:text-primary'}`} onClick={e => e.stopPropagation()}>{track.title}</a>
                                                        {track.is_seed && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-primary/20 text-primary border border-primary/30 uppercase shrink-0">Seed</span>}
                                                    </div>
                                                    {/* Album / Year */}
                                                    <div className="text-[10px] text-slate-500 truncate">
                                                        {track.album ? (
                                                            <>
                                                                {typeof track.album === 'object' && track.album.id ? (
                                                                    <a href={`https://music.youtube.com/browse/${track.album.id}`} target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors" onClick={e => e.stopPropagation()}>
                                                                        {track.album.name || track.album}
                                                                    </a>
                                                                ) : (
                                                                    <span>{typeof track.album === 'string' ? track.album : track.album.name}</span>
                                                                )}
                                                                {track.year && <span> · {track.year}</span>}
                                                            </>
                                                        ) : track.year ? (
                                                            <span>{track.year}</span>
                                                        ) : null}
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                        {/* Clickable Artist */}
                                        <td className="px-4 py-3 min-w-[200px]">
                                            <div className="flex gap-1 items-center whitespace-nowrap">
                                                {Array.isArray(track.artists) ? (
                                                    track.artists.map((artist, i) => (
                                                        <span key={i}>
                                                            {artist.id ? (
                                                                <a href={`https://music.youtube.com/channel/${artist.id}`} target="_blank" rel="noopener noreferrer" className="text-slate-300 hover:text-primary transition-colors text-sm" onClick={e => e.stopPropagation()}>
                                                                    {artist.name}
                                                                </a>
                                                            ) : (
                                                                <span className="text-slate-300 text-sm">{artist.name || artist}</span>
                                                            )}
                                                            {i < track.artists.length - 1 && <span className="text-slate-600">, </span>}
                                                        </span>
                                                    ))
                                                ) : (
                                                    <span className="text-slate-300 text-sm">{track.artists}</span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex gap-1.5 flex-wrap">
                                                {track.genres?.slice(0, 3).map((genre, i) => (
                                                    <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 whitespace-nowrap"><TagIcon type="genre" value={genre} size={10} />{genre}</span>
                                                ))}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex gap-1.5 flex-wrap">
                                                {track.moods?.slice(0, 2).map((mood, i) => (
                                                    <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-pink-500/10 text-pink-400 border border-pink-500/20 whitespace-nowrap"><TagIcon type="mood" value={mood} size={10} />{mood}</span>
                                                ))}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-center text-xs font-semibold">
                                            {track.bpm ? (
                                                <span className={`inline-flex items-center gap-1.5 ${getBpmColor(track.bpm).text}`}>
                                                    <span className={`w-1.5 h-1.5 rounded-full ${getBpmColor(track.bpm).dot}`}></span>
                                                    {track.bpm}
                                                </span>
                                            ) : <span className="text-slate-600">-</span>}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* ── Toast ── */}
            <AnimatePresence>
                {toast && (
                    <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }} className={`fixed bottom-20 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-xs font-medium shadow-lg backdrop-blur-xl border ${toast.type === 'warning' ? 'bg-amber-500/20 border-amber-500/30 text-amber-200' : 'bg-white/10 border-white/20 text-white'}`}>{toast.message}</motion.div>
                )}
            </AnimatePresence>

            {/* ── Status Bar (Player) ── */}
            <div className="status-bar">
                <div className="status-bar__left">
                    <p className="text-xs text-slate-500 whitespace-nowrap">
                        Tracks: <span className="text-white font-medium">{playlist.tracks?.length || 0}</span>
                    </p>
                </div>

                <div className="status-bar__center">
                    {currentSong ? (
                        <>
                            <div className="opacity-0 absolute pointer-events-none w-0 h-0 overflow-hidden">
                                <YouTube videoId={currentSong.videoId} opts={{ height: '1', width: '1', playerVars: { autoplay: 1, controls: 0 } }} onReady={handlePlayerReady} onStateChange={handlePlayerStateChange} onError={handlePlayerError} />
                            </div>

                            <button className="status-bar__btn" onClick={() => handlePlayPause(currentSong)} title={isPlaying ? 'Pause' : 'Play'}>
                                <span className="material-icons text-sm">{isPlaying ? 'pause' : 'play_arrow'}</span>
                            </button>
                            <button className="status-bar__btn text-rose-400 hover:text-rose-300" onClick={stopPlayback} title="Stop">
                                <span className="material-icons text-sm">stop</span>
                            </button>

                            <span className="status-bar__time">{formatSeconds(playbackProgress)}</span>

                            <div className="status-bar__seek" onClick={handleSeek}>
                                <div className="status-bar__seek-bg">
                                    <div className="status-bar__seek-fill" style={{ width: duration ? `${Math.min(100, Math.max(0, (playbackProgress / duration) * 100))}%` : '0%' }} />
                                </div>
                            </div>

                            <span className="status-bar__time">{formatSeconds(duration)}</span>

                            <div className="flex gap-0.5 h-3 ml-1">
                                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
                                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
                                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
                                <div className={`eq-bar ${isPlaying ? '' : 'animation-none h-1'}`} />
                            </div>

                            <span className="text-[10px] text-slate-400 ml-2 truncate max-w-[150px]">{currentSong.title}</span>
                        </>
                    ) : (
                        <span className="text-[10px] text-slate-600 italic">Click a track to preview</span>
                    )}
                </div>

                <div className="status-bar__right">
                    {playlist.status === 'synced' ? (
                        <span className="flex items-center gap-1 text-[10px] text-green-400 font-medium"><CheckCircle2 size={10} /> Synced</span>
                    ) : (
                        <span className="text-[10px] text-amber-400 font-medium">Draft</span>
                    )}
                </div>
            </div>
        </div>
    );
};

export default VibePlaylistDetail;
