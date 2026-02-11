import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { getCurrentUser, logoutUser } from '../api';

const Layout = ({ children }) => {
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const loadUser = async () => {
      try {
        const u = await getCurrentUser();
        setUser(u);
      } catch (error) {
        console.error("Failed to load user", error);
      }
    };
    loadUser();
  }, []);

  const handleLogout = async () => {
    await logoutUser();
    window.location.href = '/';
  };

  const menuItems = [
    { path: '/', icon: 'queue_music', label: 'Playlists' },
    { path: '/results', icon: 'storage', label: 'Database' },
  ];

  return (
    <div className="bg-background-light dark:bg-background-dark font-display text-slate-800 dark:text-slate-200 antialiased overflow-hidden h-screen flex flex-col">
      {/* Top Navigation */}
      <nav className="h-16 border-b border-white/10 dark:bg-surface-darker/50 backdrop-blur-md flex items-center justify-between px-6 z-20 shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center shadow-neon">
            <span className="material-icons text-white">dns</span>
          </div>
          <h1 className="text-xl font-bold tracking-wide uppercase">
            Song<span className="text-primary">Shake</span>
          </h1>
        </div>
        
        <div className="flex-1"></div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={handleLogout}
            className="text-slate-400 hover:text-white transition-colors"
            title="Logout"
          >
            <span className="material-icons text-xl">logout</span>
          </button>
          
          {user && (
            <div className="flex items-center gap-3 pl-4 border-l border-white/10">
              <div className="text-right hidden sm:block">
                <p className="text-sm font-medium text-white">{user.name}</p>
                <p className="text-xs text-primary truncate max-w-[100px]">{user.email || 'User'}</p>
              </div>
              <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-primary to-blue-500 p-[2px]">
                {user.thumbnail ? (
                  <img 
                    src={user.thumbnail} 
                    alt={user.name} 
                    className="h-full w-full rounded-full object-cover" 
                  />
                ) : (
                  <div className="h-full w-full rounded-full bg-surface-dark flex items-center justify-center">
                    <span className="material-icons text-sm text-slate-400">person</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </nav>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar */}
        <aside className="w-64 bg-surface-darker/30 border-r border-white/5 flex flex-col pt-6 pb-24 overflow-y-auto hidden md:flex backdrop-blur-sm shrink-0">
          <div className="px-6 mb-8">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Management</h3>
            <nav className="space-y-1">
              {menuItems.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                      isActive 
                        ? 'bg-primary/20 text-primary border border-primary/30 shadow-neon' 
                        : 'text-slate-400 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    <span className="material-icons text-lg">{item.icon}</span>
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="px-6 mb-8">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Moods</h3>
            <nav className="space-y-1">
              {/* Mock placeholders to match design */}
              <div className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer">
                <span className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span>
                  Chill
                </span>
              </div>
              <div className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer">
                <span className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.8)]"></span>
                  Energetic
                </span>
              </div>
              <div className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer">
                <span className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></span>
                  Aggressive
                </span>
              </div>
              <div className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer">
                <span className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"></span>
                  Focus
                </span>
              </div>
            </nav>
          </div>

          <div className="px-6 mb-8">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Genres</h3>
            <nav className="space-y-1">
              <div className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer">
                <span className="flex items-center gap-3">
                  <span className="material-icons text-xs">radio</span>
                  Synthwave
                </span>
              </div>
              <div className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer">
                <span className="flex items-center gap-3">
                  <span className="material-icons text-xs">settings_input_component</span>
                  Techno
                </span>
              </div>
              <div className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer">
                <span className="flex items-center gap-3">
                  <span className="material-icons text-xs">blur_on</span>
                  Ambient
                </span>
              </div>
            </nav>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col overflow-y-auto bg-surface-darker/20">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
