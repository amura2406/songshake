import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { initGoogleAuth, pollGoogleAuth, login, getAuthConfig } from '../api';
import { ShieldCheck, Music, AlertCircle, Loader2, ExternalLink, Copy, HelpCircle, Terminal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const Login = () => {
  const [activeTab, setActiveTab] = useState('google'); // 'google' | 'manual'

  // Google Auth State
  const [useEnvAuth, setUseEnvAuth] = useState(false);
  const [clientId, setClientId] = useState(() => localStorage.getItem('google_client_id') || '');
  const [clientSecret, setClientSecret] = useState(() => localStorage.getItem('google_client_secret') || '');
  const [authData, setAuthData] = useState(null);
  const [polling, setPolling] = useState(false);

  // Manual Auth State
  const [headers, setHeaders] = useState('');

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // Check if backend has env vars configured
    getAuthConfig().then(config => {
      if (config.use_env) {
        setUseEnvAuth(true);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (!useEnvAuth) {
      localStorage.setItem('google_client_id', clientId);
      localStorage.setItem('google_client_secret', clientSecret);
    }
  }, [clientId, clientSecret, useEnvAuth]);

  const handleInitAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      if (useEnvAuth) {
        // Redirect to backend login endpoint for Web Flow
        window.location.href = 'http://localhost:8000/auth/google/login';
        return;
      }

      // Manual flow (Device Code)
      const data = await initGoogleAuth(clientId, clientSecret);
      setAuthData(data);
      setPolling(true);
    } catch (err) {
      setError(err.message || 'Failed to initialize Google Auth');
    } finally {
      setLoading(false);
    }
  };

  const handleManualLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(headers);
      navigate('/');
    } catch (err) {
      setError('Invalid headers. Please check format and try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let interval;
    if (polling && authData) {
      interval = setInterval(async () => {
        try {
          const res = await pollGoogleAuth(authData.device_code, clientId, clientSecret);
          if (res.status === 'success') {
            clearInterval(interval);
            navigate('/');
          }
        } catch (err) {
          console.error("Polling error", err);
          if (err.message && (err.message.includes('expired') || err.message.includes('invalid_grant'))) {
            setError('Session expired. Please try again.');
            setPolling(false);
            clearInterval(interval);
          }
        }
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [polling, authData, clientId, clientSecret, navigate]);

  return (
    <div className="min-h-screen bg-neutral-950 text-white flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-900/20 rounded-full blur-[100px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-900/20 rounded-full blur-[100px]" />
      </div>

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md w-full bg-neutral-900/80 backdrop-blur-xl rounded-2xl border border-neutral-800 shadow-2xl relative z-10 overflow-hidden"
      >
        <div className="p-8 pb-0 text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-purple-500/20">
            <Music className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-neutral-400">
            Song Shake
          </h1>
          <p className="text-neutral-400 mt-2 text-sm">Enrich your library with AI</p>
        </div>

        {/* Tabs */}
        <div className="flex p-2 gap-2 mt-6 mx-8 bg-neutral-800/50 rounded-lg">
          <button
            onClick={() => setActiveTab('google')}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'google' ? 'bg-neutral-700 text-white shadow-sm' : 'text-neutral-400 hover:text-white'}`}
          >
            Google Login
          </button>
          <button
            onClick={() => setActiveTab('manual')}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'manual' ? 'bg-neutral-700 text-white shadow-sm' : 'text-neutral-400 hover:text-white'}`}
          >
            Manual Input
          </button>
        </div>

        <div className="p-8 pt-6">
          <AnimatePresence mode="wait">
            {activeTab === 'google' ? (
              <motion.div
                key="google"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
              >
                {!authData ? (
                  <form onSubmit={handleInitAuth} className="space-y-4">
                    {!useEnvAuth && (
                      <div className="bg-blue-900/20 border border-blue-500/20 rounded-lg p-3 flex gap-3 text-xs text-blue-200">
                        <HelpCircle className="w-4 h-4 shrink-0 mt-0.5" />
                        <div>
                          To login securely, you need your own Google Client ID.
                          <br />
                          <a href="https://console.cloud.google.com/apis/credentials" target="_blank" className="underline hover:text-white mt-1 inline-block">
                            Create one (TVs/Limited Input type)
                          </a>
                        </div>
                      </div>
                    )}

                    {!useEnvAuth && (
                      <div className="space-y-3">
                        <input
                          type="text"
                          value={clientId}
                          onChange={(e) => setClientId(e.target.value)}
                          className="w-full bg-neutral-800/80 border border-neutral-700 rounded-lg px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all placeholder-neutral-500"
                          placeholder="Client ID (e.g. 123...apps.googleusercontent.com)"
                          required
                        />
                        <input
                          type="password"
                          value={clientSecret}
                          onChange={(e) => setClientSecret(e.target.value)}
                          className="w-full bg-neutral-800/80 border border-neutral-700 rounded-lg px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all placeholder-neutral-500"
                          placeholder="Client Secret (e.g. GOCSPX-...)"
                          required
                        />
                      </div>
                    )}

                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full bg-white text-black font-semibold py-3 rounded-lg hover:bg-neutral-200 focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 mt-2"
                    >
                      {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <img src="https://www.google.com/favicon.ico" className="w-4 h-4" alt="G" />}
                      {useEnvAuth ? "Login with Google" : "Start Login Flow"}
                    </button>

                    {useEnvAuth && <p className="text-xs text-neutral-500 text-center">Redirects to Google for authentication</p>}
                  </form>
                ) : (
                  <div className="space-y-6 text-center">
                    <div className="bg-neutral-800/50 p-6 rounded-xl border border-neutral-700/50">
                      <p className="text-neutral-400 text-sm mb-4">Enter this code on the Google validation page:</p>
                      <div className="text-3xl font-mono font-bold tracking-[0.2em] text-purple-400 select-all cursor-pointer hover:text-purple-300 transition-colors" onClick={() => navigator.clipboard.writeText(authData.user_code)}>
                        {authData.user_code}
                      </div>
                    </div>

                    <a
                      href={authData.verification_url}
                      target="_blank"
                      rel="noreferrer"
                      className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-500/20"
                    >
                      <span>Continue to {authData.verification_url}</span>
                      <ExternalLink className="w-4 h-4" />
                    </a>

                    <button
                      onClick={() => { setAuthData(null); setPolling(false); }}
                      className="text-sm text-neutral-500 hover:text-neutral-300"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="manual"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                <div className="bg-neutral-800/50 border border-neutral-700 rounded-lg p-3 text-xs text-neutral-400">
                  <p className="flex items-center gap-2 mb-1 text-neutral-300 font-medium"><Terminal className="w-3 h-3" /> Advanced Users</p>
                  Paste the raw Request Headers (JSON or text) from a YouTube Music browser request.
                </div>

                <textarea
                  value={headers}
                  onChange={(e) => setHeaders(e.target.value)}
                    className="w-full bg-neutral-800/80 border border-neutral-700 rounded-lg p-4 text-xs font-mono text-neutral-300 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all h-32 resize-none leading-relaxed"
                    placeholder='{"User-Agent": "...", "Cookie": "..."}'
                    required
                  />

                  <button
                    onClick={handleManualLogin}
                    disabled={loading}
                    className="w-full bg-neutral-700 hover:bg-neutral-600 text-white font-semibold py-3 rounded-lg disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                  >
                  {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ShieldCheck className="w-5 h-5" />}
                  Login with Headers
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-start gap-3 mt-4"
            >
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
              <p className="text-sm text-red-400 text-left">{error}</p>
            </motion.div>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
