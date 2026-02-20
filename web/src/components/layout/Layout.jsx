import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { getCurrentUser, logoutUser, getTags } from '../../api';
import logoImg from '../../assets/logo.png';
import JobIcon from '../../features/jobs/JobIcon';
import AIUsageFooter from '../../features/jobs/AIUsageFooter';
import TagIcon from '../ui/TagIcon';

const Layout = ({ children }) => {
  const [user, setUser] = useState(null);
  const [tags, setTags] = useState({ genres: [], moods: [], status: [] });
  const [showAllGenres, setShowAllGenres] = useState(false);
  const [showAllMoods, setShowAllMoods] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    let intervalId;

    const loadData = async () => {
      try {
        const u = await getCurrentUser();
        setUser(u);

        if (u) {
          const fetchTags = async () => {
            const fetchedTags = await getTags(u.id);
            const genres = fetchedTags.filter(t => t.type === 'genre');
            const moods = fetchedTags.filter(t => t.type === 'mood');
            const status = fetchedTags.filter(t => t.type === 'status');
            setTags({ genres, moods, status });
          };

          await fetchTags();

          // Poll tags every 60s to update the stats box dynamically
          clearInterval(intervalId);
          intervalId = setInterval(fetchTags, 60000);
        }
      } catch (error) {
        console.error("Failed to load user or tags", error);
      }
    };

    loadData();

    return () => clearInterval(intervalId);
  }, [location.pathname]);

  // Close profile dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    await logoutUser();
    window.location.href = '/';
  };

  const handleTagClick = (tagValue) => {
    navigate(`/results?tags=${encodeURIComponent(tagValue)}`);
  };

  const menuItems = [
    { path: '/', icon: 'queue_music', label: 'Playlists' },
    { path: '/results', icon: 'storage', label: 'Database' },
    { path: '/vibing', icon: 'auto_awesome', label: 'Playlist Vibing' },
  ];

  return (
    <div className="nebula-bg bg-background-light dark:bg-background-dark font-display text-slate-800 dark:text-slate-200 antialiased overflow-hidden h-screen flex flex-col">
      {/* Top Navigation */}
      <nav className="h-16 border-b border-white/10 dark:bg-surface-darker/50 backdrop-blur-md flex items-center justify-between px-6 z-20 shrink-0 relative">
        <div className="flex items-center gap-4">
          <img src={logoImg} alt="Song Shake" className="w-10 h-10 rounded-lg shadow-neon" />
          <h1 className="title-gradient text-3xl font-black tracking-widest uppercase leading-none">
            SONGSHAKE
          </h1>
        </div>

        <div className="flex-1"></div>

        {/* Job icon + Profile dropdown */}
        {user && (
          <div className="flex items-center gap-3">
            <JobIcon />
            <div className="relative" ref={profileRef}>
              <button
                onClick={() => setProfileOpen(prev => !prev)}
                className="flex items-center gap-2 rounded-full p-[2px] bg-gradient-to-tr from-primary to-blue-500 hover:shadow-neon transition-shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background-dark"
                aria-expanded={profileOpen}
                aria-haspopup="true"
                aria-label="User menu"
              >
                <div className="h-9 w-9 rounded-full overflow-hidden">
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
              </button>

              {profileOpen && (
                <div
                  role="menu"
                  className="absolute right-0 top-full mt-2 w-56 rounded-xl bg-surface-dark/95 backdrop-blur-xl border border-white/10 shadow-2xl py-3 z-50 animate-in"
                  style={{ animation: 'fadeSlideIn 0.15s ease-out' }}
                >
                  <div className="px-4 pb-3 border-b border-white/10">
                    <p className="text-sm font-semibold text-white truncate">{user.name}</p>
                    {user.email && (
                      <p className="text-xs text-slate-400 truncate mt-0.5">{user.email}</p>
                    )}
                  </div>
                  <div className="pt-2 px-2">
                    <button
                      onClick={handleLogout}
                      role="menuitem"
                      className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-300 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    >
                      <span className="material-icons text-lg">logout</span>
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </nav>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar */}
        <aside className="w-64 bg-surface-darker/30 border-r border-white/5 flex flex-col hidden md:flex backdrop-blur-sm shrink-0">
          <div className="flex-1 overflow-y-auto pt-6 pb-6 flex flex-col">
            <div className="px-6 mb-8">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Management</h3>
              <nav className="space-y-1">
                {menuItems.map((item) => {
                  const isActive = location.pathname === item.path;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${isActive
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
                {(showAllMoods ? tags.moods : tags.moods.slice(0, 7)).map((mood, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleTagClick(mood.name)}
                    className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <span className="flex items-center gap-3">
                      <TagIcon type="mood" value={mood.name} size={14} className="opacity-70" />
                      {mood.name}
                    </span>
                    <span className="text-[10px] text-slate-500 bg-black/20 px-1.5 py-0.5 rounded group-hover:bg-primary/20 group-hover:text-primary transition-colors">{mood.count}</span>
                  </div>
                ))}
                {tags.moods.length > 7 && (
                  <button
                    onClick={() => setShowAllMoods(!showAllMoods)}
                    className="w-full text-left px-3 py-2 mt-2 text-xs font-medium text-slate-500 hover:text-white transition-colors"
                  >
                    {showAllMoods ? 'Show less' : `Show all (${tags.moods.length})`}
                  </button>
                )}
                {tags.moods.length === 0 && (
                  <div className="px-3 py-2 text-sm text-slate-600 italic">No moods found</div>
                )}
              </nav>
            </div>

            <div className="px-6 mb-8">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Genres</h3>
              <nav className="space-y-1">
                {(showAllGenres ? tags.genres : tags.genres.slice(0, 7)).map((genre, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleTagClick(genre.name)}
                    className="group flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <span className="flex items-center gap-3">
                      <TagIcon type="genre" value={genre.name} size={14} className="opacity-70" />
                      {genre.name}
                    </span>
                    <span className="text-[10px] text-slate-500 bg-black/20 px-1.5 py-0.5 rounded group-hover:bg-primary/20 group-hover:text-primary transition-colors">{genre.count}</span>
                  </div>
                ))}
                {tags.genres.length > 7 && (
                  <button
                    onClick={() => setShowAllGenres(!showAllGenres)}
                    className="w-full text-left px-3 py-2 mt-2 text-xs font-medium text-slate-500 hover:text-white transition-colors"
                  >
                    {showAllGenres ? 'Show less' : `Show all (${tags.genres.length})`}
                  </button>
                )}
                {tags.genres.length === 0 && (
                  <div className="px-3 py-2 text-sm text-slate-600 italic">No genres found</div>
                )}
              </nav>
            </div>
          </div>

          {(() => {
            const successCount = tags.status.find(t => t.name === 'Success')?.count || 0;
            const failedCount = tags.status.find(t => t.name === 'Failed')?.count || 0;
            const totalCount = successCount + failedCount;
            const successPercentage = totalCount > 0 ? (successCount / totalCount) * 100 : 0;

            if (totalCount === 0) return null;

            return (
              <div className="p-6 border-t border-white/5 bg-surface-darker/50 shrink-0">
                <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden mb-2">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full shadow-[0_0_10px_rgba(168,85,247,0.8)]"
                    style={{ width: `${successPercentage}%` }}
                  ></div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium">
                  <span>Songs: {totalCount}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-green-400">{successCount} OK</span>
                    <span className="text-red-400">{failedCount} ERR</span>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* AI Usage Footer */}
          <div className="p-4 border-t border-white/5 shrink-0">
            <AIUsageFooter />
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
