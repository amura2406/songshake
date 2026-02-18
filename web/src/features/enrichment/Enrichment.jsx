import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getEnrichmentStreamUrl } from '../../api';
import { CheckCircle, AlertCircle, Loader2, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';

const Enrichment = () => {
  const { playlistId: taskIdRaw } = useParams();
  const taskId = taskIdRaw;

  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // connect to SSE
    const url = getEnrichmentStreamUrl(taskId);
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setStatus(data);
        if (data.status === 'completed' || data.status === 'error') {
          eventSource.close();
        }
        if (data.status === 'error') {
          setError(data.message || 'Unknown error');
        }
      } catch (e) {
        console.error("SSE Parse Error", e);
      }
    };

    eventSource.onerror = (e) => {
      console.error("SSE Error", e);
      // Verify if it was just closed normally? No, onerror is error.
      // If readyState is closed, we are done.
      if (eventSource.readyState === EventSource.CLOSED) {
        // normal close
      } else {
        setError('Connection lost. Retrying...');
        eventSource.close();
        // Attempt reconnect? EventSource auto-reconnects usually.
      }
    };

    return () => {
      eventSource.close();
    };
  }, [taskId]);

  if (error && !status) { // Only show full screen error if no status yet
    return (
      <div className="min-h-screen bg-background-dark text-white flex items-center justify-center p-4">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">Error</h2>
          <p className="text-slate-400 mb-6">{error}</p>
          <button onClick={() => navigate('/')} className="px-6 py-2 bg-surface-dark rounded-lg hover:bg-surface-darker">Back to Dashboard</button>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="min-h-screen bg-background-dark text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
          <p className="text-slate-400">Connecting to stream...</p>
        </div>
      </div>
    );
  }

  const progress = status.total > 0 ? (status.current / status.total) * 100 : 0;

  return (
    <div className="min-h-screen bg-background-dark text-white p-8 flex flex-col items-center justify-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-2xl w-full bg-surface-dark rounded-2xl p-8 border border-neutral-700 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-2xl font-bold">Enriching Playlist</h2>
          {status.status === 'running' && <Loader2 className="animate-spin text-purple-400" />}
          {status.status === 'completed' && <CheckCircle className="text-green-400" />}
          {status.status === 'error' && <AlertCircle className="text-red-400" />}
        </div>

        <div className="mb-8">
          <div className="flex justify-between text-sm mb-2 text-slate-400">
            <span>Progress</span>
            <span>{status.current} / {status.total}</span>
          </div>
          <div className="h-4 bg-surface-darker rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ ease: "linear" }}
            />
          </div>

          {status.tokens !== undefined && (
            <div className="mt-6 grid grid-cols-2 gap-4">
              <div className="bg-background-dark/50 rounded-xl p-4 border border-neutral-700 flex flex-col items-center justify-center relative overflow-hidden group">
                <div className="absolute inset-0 bg-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <span className="text-xs text-slate-400 uppercase tracking-wider mb-1 font-semibold z-10">Tokens Used</span>
                <span className="text-2xl font-bold text-purple-400 font-mono z-10 transition-all duration-300">
                  {status.tokens.toLocaleString()}
                </span>
              </div>
              <div className="bg-background-dark/50 rounded-xl p-4 border border-neutral-700 flex flex-col items-center justify-center relative overflow-hidden group">
                <div className="absolute inset-0 bg-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <span className="text-xs text-slate-400 uppercase tracking-wider mb-1 font-semibold z-10">
                  {status.status === 'completed' ? 'Total Cost' : 'Est. Cost'}
                </span>
                <span className="text-2xl font-bold text-pink-400 font-mono z-10 transition-all duration-300">
                  ${(status.cost || 0).toFixed(5)}
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="bg-background-dark rounded-xl p-6 border border-neutral-700 mb-8 font-mono text-sm text-neutral-300">
          <p className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${status.status === 'running' ? 'bg-green-400 animate-pulse' : 'bg-neutral-500'}`} />
            {status.message || "Initializing..."}
          </p>
        </div>

        <div className="flex justify-end gap-4">
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 text-slate-400 hover:text-white transition-colors"
          >
            Back to Dashboard
          </button>

          {status.status === 'completed' && (
            <button
              onClick={() => navigate('/results')}
              className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-semibold shadow-lg shadow-purple-500/20"
            >
              View Results
            </button>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default Enrichment;
