import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getEnrichmentStatus } from '../api';
import { CheckCircle, AlertCircle, Loader2, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';

const Enrichment = () => {
  const { playlistId: taskIdRaw } = useParams(); // Note: route param is named playlistId but we passed taskId 
  // Actually in Dashboard we did navigate(`/enrichment/${taskId}`)
  // So the param name in App.jsx should be taskId ideally, but it is playlistId.
  // Let's use it as taskId.
  const taskId = taskIdRaw;
  
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const pollInterval = useRef(null);

  useEffect(() => {
    pollStatus();
    pollInterval.current = setInterval(pollStatus, 1000); // Poll every second

    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, [taskId]);

  const pollStatus = async () => {
    try {
      const data = await getEnrichmentStatus(taskId);
      setStatus(data);
      if (data.status === 'completed' || data.status === 'error') {
        clearInterval(pollInterval.current);
      }
    } catch (err) {
      setError('Failed to fetch status');
      clearInterval(pollInterval.current);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-neutral-900 text-white flex items-center justify-center p-4">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">Error</h2>
          <p className="text-neutral-400 mb-6">{error}</p>
          <button onClick={() => navigate('/')} className="px-6 py-2 bg-neutral-800 rounded-lg hover:bg-neutral-700">Back to Dashboard</button>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="min-h-screen bg-neutral-900 text-white flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-purple-500" />
      </div>
    );
  }

  const progress = status.total > 0 ? (status.current / status.total) * 100 : 0;

  return (
    <div className="min-h-screen bg-neutral-900 text-white p-8 flex flex-col items-center justify-center">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-2xl w-full bg-neutral-800 rounded-2xl p-8 border border-neutral-700 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-8">
           <h2 className="text-2xl font-bold">Enriching Playlist</h2>
           {status.status === 'running' && <Loader2 className="animate-spin text-purple-400" />}
           {status.status === 'completed' && <CheckCircle className="text-green-400" />}
           {status.status === 'error' && <AlertCircle className="text-red-400" />}
        </div>
        
        <div className="mb-8">
          <div className="flex justify-between text-sm mb-2 text-neutral-400">
            <span>Progress</span>
            <span>{status.current} / {status.total}</span>
          </div>
          <div className="h-4 bg-neutral-700 rounded-full overflow-hidden">
            <motion.div 
              className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ ease: "linear" }}
            />
          </div>
        </div>

        <div className="bg-neutral-900 rounded-xl p-6 border border-neutral-700 mb-8 font-mono text-sm text-neutral-300">
          <p className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            {status.message || "Initializing..."}
          </p>
        </div>

        <div className="flex justify-end gap-4">
          <button 
            onClick={() => navigate('/')}
            className="px-6 py-2 text-neutral-400 hover:text-white transition-colors"
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
