import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { X, Loader2, CheckCircle, AlertCircle, Ban, Clock, ChevronDown, ChevronUp, Music } from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import { useJobs } from './useJobs';

const statusConfig = {
    pending: { icon: Clock, color: 'text-yellow-400', bg: 'bg-yellow-400/10', label: 'Pending' },
    running: { icon: Loader2, color: 'text-blue-400', bg: 'bg-blue-400/10', label: 'Running', spin: true },
    completed: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-400/10', label: 'Completed' },
    error: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-400/10', label: 'Error' },
    cancelled: { icon: Ban, color: 'text-slate-400', bg: 'bg-slate-400/10', label: 'Cancelled' },
};

const JobCard = ({ job, onCancel }) => {
    const [errorsExpanded, setErrorsExpanded] = useState(false);
    const cfg = statusConfig[job.status] || statusConfig.pending;
    const StatusIcon = cfg.icon;
    const progress = job.total > 0 ? (job.current / job.total) * 100 : 0;
    const isActive = ['pending', 'running'].includes(job.status);
    const errorCount = job.errors?.length || 0;
    const successCount = job.current > 0 ? job.current - errorCount : 0;

    return (
        <div className="bg-background-dark/60 rounded-xl p-5 border border-white/5 space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-3 min-w-0">
                    <span className={`shrink-0 flex items-center justify-center w-8 h-8 rounded-lg ${cfg.bg}`}>
                        <StatusIcon size={16} className={`${cfg.color} ${cfg.spin ? 'animate-spin' : ''}`} />
                    </span>
                    <div className="min-w-0">
                        <p className="text-sm font-semibold text-white truncate">
                            {job.type === 'enrichment' ? 'Song Enrichment' : job.type}
                        </p>
                        <p className="text-xs text-slate-500 truncate flex items-center gap-1">
                            <Music size={10} className="shrink-0" />
                            {job.playlist_name || job.playlist_id}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                        {cfg.label}
                    </span>
                    {isActive && (
                        <button
                            onClick={() => onCancel(job.id)}
                            className="px-3 py-1 text-xs font-medium text-red-400 bg-red-400/10 rounded-lg hover:bg-red-400/20 transition-colors border border-red-400/20"
                        >
                            Cancel
                        </button>
                    )}
                </div>
            </div>

            {/* Progress */}
            {(isActive || job.total > 0) && (
                <div>
                    {isActive && (
                        <p className="text-xs text-slate-400 mb-1.5 truncate">
                            {job.message || 'Processing…'}
                        </p>
                    )}
                    <div className="h-1.5 bg-black/40 rounded-full overflow-hidden mb-2">
                        <motion.div
                            className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full"
                            initial={{ width: 0 }}
                            animate={{ width: `${progress}%` }}
                            transition={{ ease: 'linear', duration: 0.3 }}
                        />
                    </div>

                    {/* Song counts row */}
                    <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">
                            {job.current}/{job.total} songs processed
                        </span>
                        <div className="flex items-center gap-2">
                            {successCount > 0 && (
                                <span className="text-green-400 flex items-center gap-1">
                                    <CheckCircle size={10} />
                                    {successCount} OK
                                </span>
                            )}
                            {errorCount > 0 && (
                                <span className="text-red-400 flex items-center gap-1">
                                    <AlertCircle size={10} />
                                    {errorCount} ERR
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* AI Usage */}
            {job.ai_usage && (job.ai_usage.input_tokens > 0 || job.ai_usage.cost > 0) && (
                <div className="flex items-center gap-3 text-xs text-slate-500 pt-1 border-t border-white/5">
                    <span>Tokens: {(job.ai_usage.input_tokens || 0).toLocaleString()}</span>
                    <span>Cost: ${(job.ai_usage.cost || 0).toFixed(5)}</span>
                </div>
            )}

            {/* Errors expandable */}
            {errorCount > 0 && (
                <div>
                    <button
                        onClick={() => setErrorsExpanded(!errorsExpanded)}
                        className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors"
                    >
                        {errorsExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        {errorCount} error{errorCount > 1 ? 's' : ''}
                    </button>
                    {errorsExpanded && (
                        <div className="mt-2 space-y-1 max-h-32 overflow-y-auto text-xs font-mono">
                            {job.errors.map((err, i) => (
                                <div key={i} className="bg-red-400/5 text-red-300 rounded px-2 py-1 border border-red-400/10">
                                    {err.track_title && <span className="text-slate-400">{err.track_title}: </span>}
                                    {err.message}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Timestamp */}
            {!isActive && job.updated_at && (
                <p className="text-[10px] text-slate-600">{new Date(job.updated_at).toLocaleString()}</p>
            )}
        </div>
    );
};

const JobModal = ({ onClose }) => {
    const { activeJobs, jobHistory, cancelJob, fetchJobs } = useJobs();
    const [tab, setTab] = useState('active');

    useEffect(() => {
        fetchJobs();
    }, [fetchJobs]);

    const displayJobs = tab === 'active'
        ? activeJobs.filter(j => ['pending', 'running'].includes(j.status))
        : jobHistory;

    return ReactDOM.createPortal(
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm"
            onClick={onClose}
        >
            <motion.div
                initial={{ opacity: 0, y: 30, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 30, scale: 0.95 }}
                transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                className="w-full max-w-lg mx-4 bg-surface-dark rounded-2xl border border-white/10 shadow-2xl overflow-hidden max-h-[85vh] flex flex-col"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 shrink-0">
                    <h2 className="text-lg font-bold text-white">Background Jobs</h2>
                    <button
                        onClick={onClose}
                        className="p-1 rounded-lg hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-white/10 shrink-0">
                    <button
                        onClick={() => setTab('active')}
                        className={`flex-1 py-3 text-sm font-medium transition-colors ${tab === 'active'
                            ? 'text-primary border-b-2 border-primary'
                            : 'text-slate-500 hover:text-white'
                            }`}
                    >
                        Active
                        {activeJobs.filter(j => ['pending', 'running'].includes(j.status)).length > 0 && (
                            <span className="ml-2 px-1.5 py-0.5 text-[10px] bg-primary/20 text-primary rounded-full">
                                {activeJobs.filter(j => ['pending', 'running'].includes(j.status)).length}
                            </span>
                        )}
                    </button>
                    <button
                        onClick={() => setTab('history')}
                        className={`flex-1 py-3 text-sm font-medium transition-colors ${tab === 'history'
                            ? 'text-primary border-b-2 border-primary'
                            : 'text-slate-500 hover:text-white'
                            }`}
                    >
                        History
                    </button>
                </div>

                {/* Content */}
                <div className="p-4 space-y-3 overflow-y-auto flex-1">
                    {displayJobs.length === 0 ? (
                        <div className="text-center py-12 text-slate-500">
                            <p className="text-sm">{tab === 'active' ? 'No active jobs' : 'No job history yet'}</p>
                        </div>
                    ) : (
                        displayJobs.map(job => (
                            <JobCard key={job.id} job={job} onCancel={cancelJob} />
                        ))
                    )}
                </div>
            </motion.div>
        </motion.div>,
        document.body
    );
};

export default JobModal;
