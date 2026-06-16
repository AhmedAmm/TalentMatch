import React, { useState, useEffect } from 'react';
import { api, Project, User } from '../api/apiClient';
import { Briefcase } from 'lucide-react';

export function AdminDashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getProjects(), api.getUsers()]).then(([projData, userData]) => {
      setProjects(projData);
      setUsers(userData.filter(u => u.role === 'PO'));
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  const handleChangePO = async (projectId: string, newPoId: string) => {
    setLoading(true);
    try {
      await api.reassignProjectPO(projectId, newPoId);
      const updated = await api.getProjects();
      setProjects(updated);
    } catch (e: any) {
      alert(e.message || 'Failed to reassign PO');
    }
    setLoading(false);
  };

  if (loading) return <div className="text-zinc-500 animate-pulse">Loading dashboard...</div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">System Overview</h1>
        <p className="text-zinc-500">Manage ongoing projects and assignments.</p>
      </div>

      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Briefcase size={20} className="text-indigo-500" />
            All Projects
          </h2>
        </div>
        <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {projects.map(project => (
            <div key={project.id} className="p-6 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-medium">{project.name}</h3>
                <p className="text-sm text-zinc-500">{project.client} &bull; {project.status.replace('_', ' ')}</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-sm text-zinc-500 text-right">
                  <span className="block mb-1">Assigned Product Owner:</span>
                  <select
                    value={project.poId}
                    onChange={(e) => handleChangePO(project.id, e.target.value)}
                    className="bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 text-sm rounded-md px-3 py-2 w-48 font-medium focus:ring-2 focus:ring-indigo-500 outline-none"
                  >
                    {users.map(u => (
                      <option key={u.id} value={u.id}>{u.name}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          ))}
          {projects.length === 0 && (
            <div className="p-6 text-center text-zinc-500">No projects found.</div>
          )}
        </div>
      </div>
    </div>
  );
}
