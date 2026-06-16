import React, { useState, useEffect } from 'react';
import { api, User, Role } from '../api/apiClient';
import { Users, UserPlus, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function ManageUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const { user: currentUser } = useAuth();
  
  const [formData, setFormData] = useState({ name: '', email: '', role: 'PO' as Role, password: '' });

  useEffect(() => { loadUsers(); }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await api.getUsers();
      setUsers(data);
    } catch (e: any) { console.error(e); }
    setLoading(false);
  };

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.addUser({
        name: formData.name,
        email: formData.email,
        role: formData.role,
        password: formData.password || undefined,
      });
      setFormData({ name: '', email: '', role: 'PO', password: '' });
      await loadUsers();
    } catch (err: any) {
      alert(err.message || "An error occurred");
      setLoading(false);
    }
  };

  const handleDeleteUser = async (id: string) => {
    if (id === currentUser?.id) return alert("Cannot delete yourself.");
    setLoading(true);
    try {
      await api.deleteUser(id);
    } catch (e: any) { alert(e.message); }
    await loadUsers();
  };

  if (loading) return <div className="animate-pulse">Loading users...</div>;

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">User Management</h1>
        <p className="text-zinc-500">Add or remove System Administrators, Product Owners, and HR staff.</p>
      </div>

      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden p-6">
        <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
          <UserPlus size={20} className="text-indigo-500" />
          Add New Account
        </h2>
        <form onSubmit={handleAddUser} className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[150px]">
            <label className="block text-sm font-medium mb-1">Name</label>
            <input required type="text" placeholder="John Doe" value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none" />
          </div>
          <div className="flex-1 min-w-[150px]">
            <label className="block text-sm font-medium mb-1">Email</label>
            <input required type="email" placeholder="john@diapo.com" value={formData.email}
              onChange={e => setFormData({ ...formData, email: e.target.value })}
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none" />
          </div>
          <div className="w-40">
            <label className="block text-sm font-medium mb-1">Password</label>
            <input required type="password" placeholder="••••••••" value={formData.password}
              onChange={e => setFormData({ ...formData, password: e.target.value })}
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none" />
          </div>
          <div className="w-40">
            <label className="block text-sm font-medium mb-1">Role</label>
            <select value={formData.role} onChange={e => setFormData({ ...formData, role: e.target.value as Role })}
              className="w-full bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none">
              <option value="PO">Product Owner</option>
              <option value="RH">HR (RH)</option>
              <option value="ADMIN">Admin</option>
            </select>
          </div>
          <button type="submit" className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-md px-6 py-2 transition-colors flex items-center gap-2 h-[38px]">
            Create
          </button>
        </form>
      </div>

      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800 flex justify-between items-center">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Users size={20} className="text-indigo-500" />
            System Accounts
          </h2>
          <span className="bg-zinc-100 dark:bg-zinc-800 text-sm px-3 py-1 rounded-full font-medium">Total: {users.length}</span>
        </div>
        <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {users.map(u => (
            <div key={u.id} className="p-6 flex items-center justify-between hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center font-bold text-lg text-zinc-600 dark:text-zinc-300">{u.name.charAt(0)}</div>
                <div>
                  <h3 className="text-lg font-medium">{u.name}</h3>
                  <p className="text-sm text-zinc-500">{u.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <span className={`px-3 py-1 text-xs font-bold rounded-full uppercase tracking-wider
                  ${u.role === 'ADMIN' ? 'bg-red-100 text-red-700' : u.role === 'PO' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                  {u.role}
                </span>
                <button onClick={() => handleDeleteUser(u.id)} disabled={u.id === currentUser?.id}
                  className="text-zinc-400 hover:text-red-500 disabled:opacity-50 disabled:hover:text-zinc-400 p-2 rounded-full hover:bg-red-50 dark:hover:bg-red-900/20 transition-all"
                  title={u.id === currentUser?.id ? "Cannot delete yourself" : "Delete User"}>
                  <Trash2 size={20} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
