import React, { useState, useEffect, useRef } from 'react';
import { api, Employee } from '../api/apiClient';
import { Upload, Users, FileText, CheckCircle2, AlertCircle, ChevronRight, Search } from 'lucide-react';
import { useNavigate } from 'react-router';
import { CVProcessingOverlay } from '../components/CVProcessingOverlay';

export function RHDashboard() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  
  const [uploadEmail, setUploadEmail] = useState('');
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadDone, setUploadDone] = useState(false);
  const [processingFileName, setProcessingFileName] = useState<string | undefined>(undefined);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => { loadEmployees(); }, []);

  const loadEmployees = async () => {
    setLoading(true);
    try {
      const data = await api.getEmployees();
      setEmployees(data);
    } catch (e: any) { console.error(e); }
    setLoading(false);
  };

  const handleUploadCV = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadEmail || !cvFile) return alert('Please provide an email and select a CV file.');
    setUploading(true);
    setUploadDone(false);
    setProcessingFileName(cvFile.name);
    try {
      await api.uploadCV(uploadEmail, cvFile);
      setUploadDone(true);
      setUploadEmail('');
      setCvFile(null);
      await loadEmployees();
      window.dispatchEvent(new CustomEvent('diapo:sidebar-refresh'));
    } catch (err: any) {
      setUploading(false);
      setProcessingFileName(undefined);
      alert(err.message || "Error uploading CV.");
    }
  };

  const closeOverlay = () => {
    setUploading(false);
    setUploadDone(false);
    setProcessingFileName(undefined);
  };

  const filteredEmployees = employees.filter(emp => 
    emp.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    emp.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">
      <CVProcessingOverlay open={uploading} done={uploadDone} fileName={processingFileName} onClose={closeOverlay} />
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">HR Operations</h1>
        <p className="text-zinc-500">Manage employee profiles and update curriculum vitae.</p>
      </div>

      <div className="bg-indigo-50 dark:bg-indigo-900/10 border border-indigo-200 dark:border-indigo-900/50 rounded-2xl p-8 shadow-sm">
        <h2 className="text-2xl font-bold mb-6 flex items-center gap-3 text-indigo-900 dark:text-indigo-400">
          <Upload size={28} /> Add or Update Employee CV
        </h2>
        <form onSubmit={handleUploadCV} className="flex flex-col md:flex-row gap-6 items-end">
          <div className="flex-1 w-full">
            <label className="block text-sm font-bold text-indigo-900 dark:text-indigo-400 mb-2">Employee Email</label>
            <input required type="email" placeholder="employee@diapo.com" value={uploadEmail}
              onChange={e => setUploadEmail(e.target.value)}
              className="w-full bg-white dark:bg-zinc-900 border border-indigo-200 dark:border-indigo-900/50 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 outline-none shadow-sm transition-shadow hover:shadow-md" />
          </div>
          <div className="flex-1 w-full">
            <label className="block text-sm font-bold text-indigo-900 dark:text-indigo-400 mb-2">CV File (PDF)</label>
            <div className="relative">
              <input type="file" accept="application/pdf" className="hidden" ref={fileInputRef}
                onChange={e => setCvFile(e.target.files?.[0] || null)} />
              <button type="button" onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center justify-between bg-white dark:bg-zinc-900 border border-indigo-200 dark:border-indigo-900/50 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500 shadow-sm transition-shadow hover:shadow-md text-zinc-500 hover:text-indigo-600">
                <span className="truncate pr-4">{cvFile ? cvFile.name : "Select PDF Document..."}</span>
                <FileText size={20} className="shrink-0" />
              </button>
            </div>
          </div>
          <button type="submit" disabled={uploading}
            className="w-full md:w-auto bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-bold rounded-xl px-8 py-3 transition-colors flex items-center justify-center gap-2 shadow-sm">
            {uploading ? 'Processing...' : 'Upload & Parse'}
          </button>
        </form>
      </div>

      <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800 flex flex-col sm:flex-row justify-between items-center gap-4 bg-zinc-50 dark:bg-zinc-800/50">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Users size={24} className="text-indigo-500" /> Employee Directory
          </h2>
          <div className="relative w-full sm:w-72">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input type="text" placeholder="Search employees..." value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg pl-10 pr-4 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none" />
          </div>
        </div>
        {loading ? (
          <div className="p-8 text-center text-zinc-500 animate-pulse">Loading directory...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-6">
            {filteredEmployees.map(emp => (
              <div key={emp.id} onClick={() => navigate(`/employee/${emp.id}`)}
                className="group border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 hover:border-indigo-500 hover:shadow-md transition-all cursor-pointer flex flex-col bg-white dark:bg-zinc-900 h-full relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-50 dark:bg-indigo-900/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
                <div className="flex items-start gap-4 mb-4 z-10">
                  {emp.avatarUrl ? (
                    <img src={emp.avatarUrl} alt={emp.name} className="w-16 h-16 rounded-full object-cover ring-2 ring-zinc-100 dark:ring-zinc-800 group-hover:ring-indigo-500 transition-all" />
                  ) : (
                    <div className="w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-bold text-2xl group-hover:ring-2 ring-indigo-500 transition-all">
                      {emp.name.charAt(0)}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-bold group-hover:text-indigo-600 transition-colors truncate">{emp.name}</h3>
                    <p className="text-sm text-zinc-500 truncate mb-2">{emp.email}</p>
                    <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase inline-flex items-center gap-1 w-fit
                      ${emp.isAvailable ? 'bg-green-100 text-green-700' : 'bg-zinc-200 text-zinc-700'}`}>
                      {emp.isAvailable ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                      {emp.isAvailable ? 'Available' : 'Assigned'}
                    </span>
                  </div>
                </div>
                <div className="mt-auto z-10 border-t border-zinc-100 dark:border-zinc-800 pt-4 flex justify-between items-center text-sm font-medium text-zinc-400 group-hover:text-indigo-600 transition-colors">
                  <span className="flex items-center gap-1.5"><FileText size={16} /> View Profile & CV</span>
                  <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            ))}
            {filteredEmployees.length === 0 && (
              <div className="col-span-full py-12 text-center text-zinc-500 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700">
                <Users size={48} className="mx-auto mb-4 opacity-50" />
                <h3 className="text-lg font-medium mb-1">No employees found</h3>
                <p>Try adjusting your search criteria or add a new CV.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
