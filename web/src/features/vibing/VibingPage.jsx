import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { generateVibe, getVibePlaylists, getYoutubeQuota, deleteVibePlaylist } from '../../api';
import { Sparkles, Music, ExternalLink, CheckCircle2, Clock, ListMusic, Trash2 } from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';

const TRACK_PRESETS = [
    { label: '50', value: 49 },
    { label: '100', value: 99 },
    { label: '150', value: 149 },
];

// ── Extravagant AI thinking animation ──
const AiThinkingOverlay = () => {
    const orbs = Array.from({ length: 6 }, (_, i) => i);
    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 backdrop-blur-xl">
            <div className="relative w-64 h-64 mb-8">
                {orbs.map((i) => (
                    <motion.div key={i} className="absolute w-4 h-4 rounded-full" style={{ background: `radial-gradient(circle, ${['#af25f4', '#d946ef', '#00e5ff', '#7c4dff', '#e040fb', '#ff6090'][i]}, transparent)`, boxShadow: `0 0 20px ${['#af25f4', '#d946ef', '#00e5ff', '#7c4dff', '#e040fb', '#ff6090'][i]}`, top: '50%', left: '50%' }}
                        animate={{ x: [0, Math.cos((i * Math.PI * 2) / 6) * 100, Math.cos(((i + 1) * Math.PI * 2) / 6) * 100, 0], y: [0, Math.sin((i * Math.PI * 2) / 6) * 100, Math.sin(((i + 1) * Math.PI * 2) / 6) * 100, 0], scale: [0.5, 1.5, 0.8, 0.5], opacity: [0.3, 1, 0.6, 0.3] }}
                        transition={{ duration: 3 + i * 0.5, repeat: Infinity, ease: 'easeInOut', delay: i * 0.3 }} />
                ))}
                <motion.div className="absolute inset-0 flex items-center justify-center" animate={{ scale: [0.9, 1.1, 0.9], rotate: [0, 360] }} transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}>
                    <motion.div className="w-24 h-24 rounded-full flex items-center justify-center" style={{ background: 'radial-gradient(circle, rgba(175,37,244,0.4) 0%, transparent 70%)', boxShadow: '0 0 60px rgba(175,37,244,0.5), 0 0 120px rgba(175,37,244,0.2)' }}
                        animate={{ boxShadow: ['0 0 60px rgba(175,37,244,0.5), 0 0 120px rgba(175,37,244,0.2)', '0 0 100px rgba(175,37,244,0.8), 0 0 200px rgba(175,37,244,0.4)', '0 0 60px rgba(175,37,244,0.5), 0 0 120px rgba(175,37,244,0.2)'] }}
                        transition={{ duration: 2, repeat: Infinity }}>
                        <Sparkles size={40} className="text-primary" />
                    </motion.div>
                </motion.div>
            </div>
            <motion.h2 className="text-2xl font-bold text-white mb-3" animate={{ opacity: [0.7, 1, 0.7] }} transition={{ duration: 2, repeat: Infinity }}>AI is curating your playlist</motion.h2>
            <AnimatedStatus />
            <div className="w-80 h-1 bg-white/10 rounded-full mt-6 overflow-hidden">
                <motion.div className="h-full rounded-full" style={{ background: 'linear-gradient(90deg, #af25f4, #00e5ff, #d946ef)' }} animate={{ x: ['-100%', '100%'] }} transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }} />
            </div>
        </motion.div>
    );
};

const statusMessages = ['🎵 Analyzing your music library…', '🧠 Understanding genre patterns…', '🎧 Finding the perfect BPM flow…', '✨ Crafting mood transitions…', '🌊 Building the sonic journey…', '🎹 Harmonizing the tracklist…', '🔮 Almost there, finishing touches…'];

const AnimatedStatus = () => {
    const [index, setIndex] = useState(0);
    useEffect(() => {
        const interval = setInterval(() => setIndex((i) => (i + 1) % statusMessages.length), 4000);
        return () => clearInterval(interval);
    }, []);
    return (
        <div className="h-6 overflow-hidden">
            <AnimatePresence mode="wait">
                <motion.p key={index} initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -20, opacity: 0 }} transition={{ duration: 0.4 }} className="text-sm text-slate-400 text-center">{statusMessages[index]}</motion.p>
            </AnimatePresence>
        </div>
    );
};

// ── Countdown timer hook ──
const useCountdown = (resetAtUtc) => {
    const [timeLeft, setTimeLeft] = useState('');

    useEffect(() => {
        if (!resetAtUtc) return;

        const tick = () => {
            const now = Date.now();
            const reset = new Date(resetAtUtc).getTime();
            const diff = Math.max(0, reset - now);
            const h = String(Math.floor(diff / 3_600_000)).padStart(2, '0');
            const m = String(Math.floor((diff % 3_600_000) / 60_000)).padStart(2, '0');
            const s = String(Math.floor((diff % 60_000) / 1_000)).padStart(2, '0');
            setTimeLeft(`${h}:${m}:${s}`);
        };

        tick();
        const interval = setInterval(tick, 1000);
        return () => clearInterval(interval);
    }, [resetAtUtc]);

    return timeLeft;
};

const VibingPage = () => {
    const [playlists, setPlaylists] = useState([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [trackCount, setTrackCount] = useState(49);
    const [error, setError] = useState(null);
    const [deletingId, setDeletingId] = useState(null);
    const [quota, setQuota] = useState(null);
    const navigate = useNavigate();

    const countdown = useCountdown(quota?.reset_at_utc);

    const loadPlaylists = useCallback(async () => {
        try {
            setLoading(true);
            const data = await getVibePlaylists();
            setPlaylists(data);
        } catch (err) {
            console.error('Failed to load vibe playlists', err);
        } finally {
            setLoading(false);
        }
    }, []);

    const loadQuota = useCallback(async () => {
        try {
            const data = await getYoutubeQuota();
            setQuota(data);
        } catch (err) {
            console.error('Failed to load quota', err);
        }
    }, []);

    useEffect(() => {
        loadPlaylists();
        loadQuota();
    }, [loadPlaylists, loadQuota]);

    const handleGenerate = async () => {
        try {
            setGenerating(true);
            setError(null);
            const result = await generateVibe(trackCount);
            navigate(`/vibing/${result.id}`);
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to generate playlist');
        } finally {
            setGenerating(false);
        }
    };

    const handleDelete = async (e, playlistId) => {
        e.stopPropagation();
        if (!window.confirm('Delete this playlist?')) return;
        try {
            setDeletingId(playlistId);
            await deleteVibePlaylist(playlistId);
            setPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
        } catch (err) {
            console.error('Delete failed', err);
        } finally {
            setDeletingId(null);
        }
    };

    const formatDate = (dateString) => {
        try {
            return new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
        } catch { return dateString; }
    };

    const quotaPct = quota ? Math.min(100, (quota.units_used / quota.units_limit) * 100) : 0;
    const quotaColor = quotaPct > 85 ? 'from-red-500 to-rose-500' : quotaPct > 60 ? 'from-amber-500 to-orange-500' : 'from-primary to-blue-500';

    return (
        <div className="p-6">
            <AnimatePresence>{generating && <AiThinkingOverlay />}</AnimatePresence>

            <div className="max-w-5xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <h2 className="text-2xl font-bold text-white mb-2 flex items-center gap-3">
                        <Sparkles className="text-primary" size={28} />
                        Playlist Vibing
                    </h2>
                    <p className="text-slate-400 text-sm">Let AI curate the perfect playlist from your library. The most neglected track becomes the seed for a cohesive musical journey.</p>
                </div>

                {/* Generate Card */}
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="bg-gradient-to-br from-surface-dark to-surface-darker rounded-2xl border border-primary/20 p-8 mb-6 relative overflow-hidden">
                    <div className="absolute -top-20 -right-20 w-60 h-60 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
                    <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

                    <div className="relative z-10">
                        <h3 className="text-lg font-bold text-white mb-5 flex items-center gap-2">
                            <Music size={20} className="text-primary" />
                            Generate AI Playlist
                        </h3>

                        <div className="flex flex-col sm:flex-row items-start sm:items-end gap-6">
                            <div>
                                <label className="text-xs text-slate-400 font-medium mb-2.5 block">Playlist size</label>
                                <div className="flex rounded-lg border border-white/10 overflow-hidden bg-surface-darker">
                                    {TRACK_PRESETS.map((preset) => {
                                        const isActive = trackCount === preset.value;
                                        return (
                                            <button key={preset.value} onClick={() => setTrackCount(preset.value)} disabled={generating}
                                                className={`px-5 py-2 text-sm font-semibold transition-all ${isActive ? 'bg-primary text-white shadow-neon' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}>
                                                {preset.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            <button onClick={handleGenerate} disabled={generating} className="bg-primary hover:bg-fuchsia-600 text-white px-8 py-2.5 rounded-xl font-bold flex items-center gap-2 shadow-neon disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:shadow-neon-strong">
                                <Sparkles size={20} /> Generate Playlist
                            </button>
                        </div>

                        {error && (
                            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs text-red-400 mt-4 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2">{error}</motion.p>
                        )}
                    </div>
                </motion.div>

                {/* ── YouTube API Quota Bar ── */}
                {quota && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-surface-dark rounded-xl border border-white/5 px-5 py-4 mb-8">
                        <div className="flex items-center justify-between mb-2.5">
                            <div className="flex items-center gap-2">
                                <span className="material-icons text-sm text-slate-500">cloud_queue</span>
                                <span className="text-xs text-slate-400 font-medium">YouTube API Quota</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <span className="text-xs text-slate-300 font-mono tabular-nums">
                                    {quota.units_used.toLocaleString()} <span className="text-slate-600">/</span> {quota.units_limit.toLocaleString()}
                                </span>
                                {countdown && (
                                    <span className="text-[10px] text-slate-500 font-mono tabular-nums flex items-center gap-1" title="Time until quota resets (midnight PT)">
                                        <Clock size={10} />
                                        {countdown}
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                            <motion.div
                                className={`h-full rounded-full bg-gradient-to-r ${quotaColor}`}
                                initial={{ width: 0 }}
                                animate={{ width: `${quotaPct}%` }}
                                transition={{ duration: 0.8, ease: 'easeOut' }}
                            />
                        </div>
                        {quotaPct > 85 && (
                            <p className="text-[10px] text-red-400/80 mt-1.5">⚠ Quota nearly exhausted. Large syncs may fail today.</p>
                        )}
                    </motion.div>
                )}

                {/* Playlists List */}
                <div>
                    <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Your Vibe Playlists</h3>

                    {loading ? (
                        <div className="flex justify-center py-12">
                            <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                        </div>
                    ) : playlists.length === 0 ? (
                        <div className="text-center py-16">
                            <Sparkles className="mx-auto mb-4 text-slate-600" size={48} />
                            <p className="text-slate-500 text-sm">No playlists yet. Generate your first AI playlist above!</p>
                        </div>
                    ) : (
                        <div className="grid gap-4 sm:grid-cols-2">
                            {playlists.map((pl, idx) => (
                                <motion.div key={pl.id} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.05 }}
                                    onClick={() => navigate(`/vibing/${pl.id}`)}
                                    className="bg-surface-dark rounded-2xl border border-white/5 hover:border-primary/30 p-5 cursor-pointer transition-all group hover:shadow-neon relative overflow-hidden">
                                    <div className="absolute -top-10 -right-10 w-32 h-32 bg-primary/5 rounded-full blur-2xl pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity" />
                                    <div className="relative z-10">
                                        <div className="flex items-start justify-between gap-3 mb-3">
                                            <div className="flex items-center gap-3 min-w-0">
                                                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/20 to-blue-500/20 flex items-center justify-center shrink-0">
                                                    <Music size={18} className="text-primary" />
                                                </div>
                                                <h4 className="text-white font-semibold truncate group-hover:text-primary transition-colors text-sm leading-snug">{pl.title}</h4>
                                            </div>
                                            <button onClick={(e) => handleDelete(e, pl.id)} disabled={deletingId === pl.id} className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400 transition-all shrink-0" title="Delete playlist">
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                        <div className="grid grid-cols-2 gap-y-2 text-xs text-slate-400 mb-3">
                                            <div className="flex items-center gap-1.5"><ListMusic size={12} className="text-slate-500" /><span>{pl.track_count} tracks</span></div>
                                            <div className="flex items-center gap-1.5"><Clock size={12} className="text-slate-500" /><span>{formatDate(pl.created_at)}</span></div>
                                        </div>
                                        <div className="text-[11px] text-slate-500 truncate mb-3">
                                            Seed: <span className="text-slate-300">{pl.seed_title || pl.seed_video_id}</span>
                                            {pl.seed_artist && <span> · {pl.seed_artist}</span>}
                                        </div>
                                        <div className="flex items-center justify-between gap-2">
                                            {pl.status === 'synced' ? (
                                                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-500/10 text-green-400 text-[11px] font-medium border border-green-500/20">
                                                    <CheckCircle2 size={11} /> Synced to YouTube
                                                </span>
                                            ) : (
                                                <span className="px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 text-[11px] font-medium border border-amber-500/20">Draft</span>
                                            )}
                                            {pl.youtube_playlist_id && (
                                                <a href={`https://music.youtube.com/playlist?list=${pl.youtube_playlist_id}`} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-slate-500 hover:text-primary transition-colors" title="Open on YouTube Music">
                                                    <ExternalLink size={14} />
                                                </a>
                                            )}
                                        </div>
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default VibingPage;
