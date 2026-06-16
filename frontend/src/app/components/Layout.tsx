import React, { useEffect, useState, useCallback } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router';
import { useAuth } from '../context/AuthContext';
import { LayoutDashboard, Users, FileText, LogOut, Shield, Briefcase, UserCircle, Plus, ChevronRight, FolderKanban } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { LoginPage } from '../pages/LoginPage';
import { api, Project, Employee } from '../api/apiClient';

export function Layout() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [projects, setProjects] = useState<Project[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);

  const refreshSidebar = useCallback(async () => {
    if (!user) return;
    try {
      if (user.role === 'PO') {
        const all = await api.getProjects({ po_id: user.id });
        setProjects(all);
      } else if (user.role === 'RH') {
        const data = await api.getEmployees();
        setEmployees(data);
      }
    } catch (e) { console.error('sidebar refresh failed', e); }
  }, [user]);

  useEffect(() => { refreshSidebar(); }, [refreshSidebar]);

  // Allow pages to trigger a sidebar refresh after a mutation
  useEffect(() => {
    const handler = () => refreshSidebar();
    window.addEventListener('diapo:sidebar-refresh', handler);
    return () => window.removeEventListener('diapo:sidebar-refresh', handler);
  }, [refreshSidebar]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center text-white font-black text-lg animate-pulse">D</div>
          <span className="text-sm text-zinc-400">Loading...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  const navLinks = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard', roles: ['ADMIN', 'PO', 'RH'] },
    { to: '/users', icon: Users, label: 'Manage Users', roles: ['ADMIN'] },
    { to: '/cv', icon: FileText, label: 'Upload CV', roles: ['RH'] },
  ];

  const filteredLinks = navLinks.filter(l => l.roles.includes(user.role));

  const roleConfig: Record<string, { label: string; color: string; icon: React.ElementType }> = {
    ADMIN: { label: 'System Admin', color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400', icon: Shield },
    PO: { label: 'Product Owner', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400', icon: Briefcase },
    RH: { label: 'HR Manager', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400', icon: UserCircle },
  };
  const rc = roleConfig[user.role] || roleConfig.PO;

  const isDashboard = location.pathname === '/';

  return (
    <div className="flex h-screen bg-zinc-50 dark:bg-zinc-950 font-sans text-zinc-900 dark:text-zinc-100">
      {/* Sidebar */}
      <aside className="w-72 border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex flex-col">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center text-white font-black text-lg shadow-lg shadow-indigo-600/20">D</div>
          <span className="text-xl font-black tracking-tight">Diapo</span>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {filteredLinks.map(link => {
            const Icon = link.icon;
            const isActive = location.pathname === link.to;
            const isDashLink = link.to === '/';
            return (
              <div key={link.to}>
                <Link
                  to={link.to}
                  className={`flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all ${
                    isActive
                      ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 font-semibold shadow-sm'
                      : 'hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'
                  }`}
                >
                  <Icon size={18} />
                  <span className="text-sm">{link.label}</span>
                </Link>

                {/* PO project list under Dashboard */}
                {isDashLink && user.role === 'PO' && (
                  <div className="mt-1 ml-4 pl-3 border-l border-zinc-200 dark:border-zinc-800 space-y-0.5">
                    <button
                      onClick={() => {
                        navigate('/');
                        // Open the new-project flow from the dashboard
                        setTimeout(() => window.dispatchEvent(new CustomEvent('diapo:new-project')), 50);
                      }}
                      className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-bold text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors group"
                    >
                      <span className="w-5 h-5 rounded-md bg-gradient-to-br from-indigo-500 to-violet-500 text-white flex items-center justify-center group-hover:scale-110 transition-transform shadow-sm">
                        <Plus size={12} strokeWidth={3} />
                      </span>
                      New Project
                    </button>
                    <AnimatePresence initial={false}>
                      {projects.map(p => {
                        const active = location.pathname === `/project/${p.id}`;
                        return (
                          <motion.button
                            key={p.id}
                            layout
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -8 }}
                            onClick={() => navigate(`/project/${p.id}`)}
                            className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-colors group ${
                              active
                                ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 font-semibold'
                                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800/50'
                            }`}
                          >
                            <FolderKanban size={12} className="shrink-0" />
                            <span className="truncate flex-1 text-left">{p.name}</span>
                            <ChevronRight size={10} className={`shrink-0 transition-opacity ${active ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'}`} />
                          </motion.button>
                        );
                      })}
                    </AnimatePresence>
                    {projects.length === 0 && (
                      <p className="px-2.5 py-1.5 text-[11px] text-zinc-400 italic">No projects yet</p>
                    )}
                  </div>
                )}

                {/* RH employee list under Dashboard */}
                {isDashLink && user.role === 'RH' && employees.length > 0 && (
                  <div className="mt-1 ml-4 pl-3 border-l border-zinc-200 dark:border-zinc-800 space-y-0.5 max-h-72 overflow-y-auto">
                    <p className="px-2.5 py-1 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">Candidates ({employees.length})</p>
                    {employees.map(e => {
                      const active = location.pathname === `/employee/${e.id}`;
                      return (
                        <button
                          key={e.id}
                          onClick={() => navigate(`/employee/${e.id}`)}
                          className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                            active
                              ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 font-semibold'
                              : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800/50'
                          }`}
                        >
                          <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                            e.isAvailable ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800'
                          }`}>
                            {e.name.charAt(0)}
                          </span>
                          <span className="truncate flex-1 text-left">{e.name}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 space-y-3">
          <div className="flex items-center gap-3 px-3 py-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center text-white font-bold text-sm shadow-sm">
              {user.name.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold truncate">{user.name}</div>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${rc.color}`}>
                {user.role}
              </span>
            </div>
          </div>

          <button
            onClick={() => { logout(); navigate('/'); }}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-zinc-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/10 dark:hover:text-red-400 transition-all"
          >
            <LogOut size={16} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="p-8 max-w-6xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
