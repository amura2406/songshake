import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkAuth } from '../../api';
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import logoImg from '../../assets/logo.png';

const Login = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // On mount, check if already authenticated
  React.useEffect(() => {
    checkAuth().then(user => {
      if (user) navigate('/');
    }).catch(() => { });
  }, [navigate]);

  const handleGoogleLogin = () => {
    setLoading(true);
    setError('');
    // Redirect to backend OAuth endpoint — if backend is down, redirect will fail
    window.location.href = 'http://localhost:8000/auth/google/login';
  };

  return (
    <div className="nebula-bg min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Login panel */}
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-sm mx-4"
      >
        <div className="bg-surface-dark/80 backdrop-blur-xl rounded-2xl border border-white/10 p-8 shadow-pulse">
          {/* Logo, title & subtitle */}
          <div className="text-center mb-8">
            <img
              src={logoImg}
              alt="SongShake"
              className="w-20 h-20 mx-auto mb-4 drop-shadow-lg"
            />
            <h1 className="title-gradient text-2xl font-black tracking-widest uppercase select-none mb-2">
              SONGSHAKE
            </h1>
            <p className="text-sm text-slate-400 leading-relaxed">
              Redistribute your songs into<br />
              AI-powered playlists
            </p>
          </div>

          {/* Error display */}
          {error && (
            <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
              {error}
            </div>
          )}

          {/* Google Sign-in */}
          <button
            onClick={handleGoogleLogin}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-xl bg-white text-gray-800 font-semibold text-sm hover:bg-gray-100 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <img src="https://www.google.com/favicon.ico" className="w-5 h-5" alt="G" />
            )}
            Sign in with Google
          </button>

          <p className="text-xs text-slate-500 text-center mt-4">
            Redirects to Google for authentication
          </p>

          {/* Footer */}
          <div className="mt-8 pt-4 border-t border-white/5 text-center">
            <p className="text-[10px] text-slate-600">
              Requires YouTube Music access via Google account
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
