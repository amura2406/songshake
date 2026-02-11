import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api';
import { ShieldCheck, Music, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';

const Login = () => {
  const [headers, setHeaders] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(headers);
      navigate('/');
    } catch (err) {
      setError('Invalid headers. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-white flex items-center justify-center p-4">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md w-full bg-neutral-800 rounded-2xl shadow-xl p-8 border border-neutral-700"
      >
        <div className="flex items-center justify-center mb-8">
          <div className="w-12 h-12 bg-primary-500 rounded-full flex items-center justify-center bg-gradient-to-tr from-purple-500 to-pink-500">
            <Music className="w-6 h-6 text-white" />
          </div>
        </div>
        
        <h2 className="text-3xl font-bold text-center mb-2">Song Shake</h2>
        <p className="text-neutral-400 text-center mb-8">Login to access your YouTube Music playlists.</p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-neutral-300 mb-2">
              YouTube Music Headers
            </label>
            <textarea
              value={headers}
              onChange={(e) => setHeaders(e.target.value)}
              className="w-full h-32 bg-neutral-900 border border-neutral-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none transition-all"
              placeholder="Paste your request headers here..."
              required
            />
            <p className="mt-2 text-xs text-neutral-500">
              Need help? <a href="https://ytmusicapi.readthedocs.io/en/latest/setup/browser.html" target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline">Follow these instructions</a> to get your headers.
            </p>
          </div>

          {error && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 p-3 rounded-lg border border-red-900/50"
            >
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </motion.div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-semibold py-3 px-6 rounded-lg transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <ShieldCheck className="w-5 h-5" />
                <span>Login Securely</span>
              </>
            )}
          </button>
        </form>
      </motion.div>
    </div>
  );
};

export default Login;
