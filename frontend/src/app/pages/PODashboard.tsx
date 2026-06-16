import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, Project } from '../api/apiClient';
import { Plus, Briefcase, FileText, CheckCircle2, XCircle, Clock, ChevronRight, Upload, Loader2, Sparkles, FolderOpen } from 'lucide-react';
import { useNavigate } from 'react-router';
import { BipartiteMatching } from '../components/BipartiteMatching';
import { ExtractionAnimation } from '../components/ExtractionAnimation';

type UploadStep = 'idle' | 'uploading' | 'parsing' | 'matching' | 'done' | 'error';

export function PODashboard() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddProject, setShowAddProject] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Upload flow state
  const [uploadStep, setUploadStep] = useState<UploadStep>('idle');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [extractedData, setExtractedData] = useState<{ name: string; client: string; description: string; jobs: string[] } | null>(null);
  const [createdProject, setCreatedProject] = useState<Project | null>(null);
  const [uploadError, setUploadError] = useState('');

  useEffect(() => {
    loadProjects();
    const openNew = () => { resetUpload(); setShowAddProject(true); };
    window.addEventListener('diapo:new-project', openNew);
    return () => window.removeEventListener('diapo:new-project', openNew);
  }, []);

  const loadProjects = async () => {
    setLoading(true);
    try {
      const all = await api.getProjects(user ? { po_id: user.id } : undefined);
      setProjects(all);
    } catch (err: any) {
      console.error('Failed to load projects:', err);
    }
    setLoading(false);
  };

  const resetUpload = () => {
    setShowAddProject(false);
    setUploadStep('idle');
    setUploadedFile(null);
    setExtractedData(null);
    setCreatedProject(null);
    setUploadError('');
  };

  const handleFileSelect = async (file: File) => {
    setUploadedFile(file);
    setUploadError('');
    setUploadStep('uploading');

    try {
      // Step 1: Parse PDF to preview extracted data
      setUploadStep('parsing');
      const parsed = await api.parsePDF(file);
      setExtractedData(parsed);

      // Step 2: Ingest PDF — creates project + jobs + triggers matching
      setUploadStep('matching');
      const newProj = await api.ingestPDF(file, user!.id);
      setCreatedProject(newProj);
      setUploadStep('done');
      await loadProjects();
      window.dispatchEvent(new CustomEvent('diapo:sidebar-refresh'));
    } catch (err: any) {
      console.error('Upload flow error:', err);
      setUploadError(err.message || 'An error occurred during upload.');
      setUploadStep('error');
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      handleFileSelect(file);
    }
  };

  const statusConfig: Record<string, { color: string; icon: React.ElementType }> = {
    IN_PROGRESS: { color: 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800', icon: Clock },
    FINISHED: { color: 'text-emerald-600 bg-emerald-50 dark:text-emerald-400 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800', icon: CheckCircle2 },
    CANCELED: { color: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20 border-red-200 dark:border-red-800', icon: XCircle },
  };

  if (loading && projects.length === 0) return <div className="animate-pulse text-zinc-500">Loading dashboard...</div>;

  const stepLabels: Record<UploadStep, string> = {
    idle: '',
    uploading: 'Uploading PDF...',
    parsing: 'AI is extracting project info & job roles...',
    matching: 'Creating project & matching candidates...',
    done: 'Project created & candidates matched!',
    error: 'Something went wrong.',
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-black tracking-tight mb-1">My Projects</h1>
          <p className="text-zinc-500 text-sm">Manage your clients and matching candidates.</p>
        </div>
        <button
          onClick={() => { resetUpload(); setShowAddProject(true); }}
          className="bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-bold rounded-xl px-5 py-2.5 transition-all flex items-center gap-2 shadow-lg shadow-indigo-600/20 hover:shadow-indigo-600/30"
        >
          <Plus size={18} />
          New Project
        </button>
      </div>

      {/* Upload Project Flow */}
      {showAddProject && (
        <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-lg overflow-hidden">
          {uploadStep === 'idle' ? (
            <div
              className="p-10"
              onDragOver={e => e.preventDefault()}
              onDrop={handleFileDrop}
            >
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 flex items-center justify-center text-indigo-600">
                  <Upload size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold">Upload Project Brief</h2>
                  <p className="text-sm text-zinc-500">Drop a PDF — we'll extract everything automatically.</p>
                </div>
              </div>

              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-zinc-300 dark:border-zinc-700 rounded-2xl p-12 text-center cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/50 dark:hover:bg-indigo-900/5 transition-all group"
              >
                <input
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  ref={fileInputRef}
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center group-hover:bg-indigo-100 dark:group-hover:bg-indigo-900/30 transition-colors">
                  <FileText size={28} className="text-zinc-400 group-hover:text-indigo-600 transition-colors" />
                </div>
                <p className="font-bold text-zinc-700 dark:text-zinc-300 mb-1">Click to upload or drag & drop</p>
                <p className="text-sm text-zinc-400">PDF files only</p>
              </div>

              <div className="flex justify-between items-center mt-6">
                <button onClick={resetUpload} className="text-sm font-semibold text-zinc-500 hover:text-zinc-900 transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="p-10">
              {/* Progress Steps */}
              <div className="flex items-center gap-3 mb-8">
                {(['uploading', 'parsing', 'matching', 'done'] as UploadStep[]).map((step, idx) => {
                  const stepOrder = ['uploading', 'parsing', 'matching', 'done'];
                  const currentIdx = stepOrder.indexOf(uploadStep === 'error' ? 'matching' : uploadStep);
                  const isActive = uploadStep === step;
                  const isPast = currentIdx > idx;
                  const isError = uploadStep === 'error' && idx === currentIdx;
                  return (
                    <React.Fragment key={step}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                        isError ? 'bg-red-600 text-white' :
                        isPast ? 'bg-indigo-600 text-white' : isActive ? 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 ring-2 ring-indigo-600 ring-offset-2 dark:ring-offset-zinc-900' : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400'
                      }`}>
                        {isPast ? <CheckCircle2 size={16} /> : isError ? <XCircle size={16} /> : idx + 1}
                      </div>
                      {idx < 3 && <div className={`flex-1 h-0.5 rounded-full transition-all ${isPast ? 'bg-indigo-600' : 'bg-zinc-200 dark:bg-zinc-800'}`} />}
                    </React.Fragment>
                  );
                })}
              </div>

              {/* Current step status */}
              <div className="flex items-center gap-3 mb-6">
                {uploadStep === 'done' ? (
                  <Sparkles size={20} className="text-emerald-500" />
                ) : uploadStep === 'error' ? (
                  <XCircle size={20} className="text-red-500" />
                ) : (
                  <Loader2 size={20} className="text-indigo-600 animate-spin" />
                )}
                <span className={`font-bold ${uploadStep === 'done' ? 'text-emerald-600' : uploadStep === 'error' ? 'text-red-600' : 'text-zinc-700 dark:text-zinc-300'}`}>
                  {stepLabels[uploadStep]}
                </span>
              </div>

              {/* Error message */}
              {uploadStep === 'error' && uploadError && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4 mb-6 text-sm text-red-700 dark:text-red-400">
                  {uploadError}
                  <button onClick={resetUpload} className="ml-4 underline font-semibold">Try again</button>
                </div>
              )}

              {/* File info */}
              {uploadedFile && (
                <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-4 mb-6 flex items-center gap-3 border border-zinc-100 dark:border-zinc-800">
                  <FileText size={20} className="text-red-500" />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm truncate">{uploadedFile.name}</p>
                    <p className="text-xs text-zinc-400">{(uploadedFile.size / 1024).toFixed(0)} KB</p>
                  </div>
                </div>
              )}

              {/* Extracted data preview */}
              {extractedData && (uploadStep === 'matching' || uploadStep === 'done') && (
                <div className="space-y-4 mb-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-4 border border-zinc-100 dark:border-zinc-800">
                      <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-1">Project Name</p>
                      <p className="font-bold text-zinc-900 dark:text-zinc-100">{extractedData.name}</p>
                    </div>
                    <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-4 border border-zinc-100 dark:border-zinc-800">
                      <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-1">Client</p>
                      <p className="font-bold text-zinc-900 dark:text-zinc-100">{extractedData.client}</p>
                    </div>
                  </div>
                  <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-4 border border-zinc-100 dark:border-zinc-800">
                    <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-2">Extracted Job Roles</p>
                    <div className="flex flex-wrap gap-2">
                      {extractedData.jobs.map((job, i) => (
                        <span key={i} className="bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-800 px-3 py-1.5 rounded-lg text-sm font-semibold flex items-center gap-1.5">
                          <Briefcase size={14} /> {job}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Phase 1 — Extraction animation */}
              {(uploadStep === 'uploading' || uploadStep === 'parsing') && (
                <div className="mb-6 max-w-md mx-auto">
                  <ExtractionAnimation />
                </div>
              )}

              {/* Phase 2 — Bipartite matching visualization */}
              {uploadStep === 'matching' && (
                <div className="mb-6 max-w-sm mx-auto">
                  <BipartiteMatching
                    candidates={6}
                    jobs={extractedData?.jobs?.length ? extractedData.jobs.slice(0, 3) : ['Frontend', 'Backend', 'Design']}
                    active
                  />
                </div>
              )}

              {/* Done state */}
              {uploadStep === 'done' && createdProject && (
                <div className="flex gap-3">
                  <button
                    onClick={() => navigate(`/project/${createdProject.id}`)}
                    className="flex-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-bold rounded-xl px-5 py-3 transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20"
                  >
                    <Sparkles size={18} /> View Matches
                  </button>
                  <button
                    onClick={resetUpload}
                    className="px-5 py-3 rounded-xl border border-zinc-200 dark:border-zinc-800 text-sm font-bold text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                  >
                    Close
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Project Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {projects.map(project => {
          const sc = statusConfig[project.status] || statusConfig.IN_PROGRESS;
          const StatusIcon = sc.icon;
          return (
            <div
              key={project.id}
              onClick={() => navigate(`/project/${project.id}`)}
              className="group bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 cursor-pointer hover:border-indigo-400 hover:shadow-lg hover:shadow-indigo-600/5 transition-all flex flex-col h-full"
            >
              <div className="flex justify-between items-start mb-4">
                <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-900/30 transition-colors">
                  <Briefcase size={22} />
                </div>
                <span className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border flex items-center gap-1 ${sc.color}`}>
                  <StatusIcon size={12} />
                  {project.status.replace('_', ' ')}
                </span>
              </div>
              
              <h3 className="text-lg font-bold mb-1 group-hover:text-indigo-600 transition-colors">{project.name}</h3>
              <p className="text-zinc-500 text-sm mb-4 flex-1">{project.client}</p>
              
              <div className="flex flex-wrap gap-1.5 mb-4">
                {project.jobs.slice(0, 3).map(job => (
                  <span key={job.id} className="bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2 py-0.5 rounded-md text-[11px] font-semibold">
                    {job.title}{job.headcount > 1 ? ` (x${job.headcount})` : ''}
                  </span>
                ))}
                {project.jobs.length > 3 && (
                  <span className="text-[11px] font-bold text-zinc-400">+{project.jobs.length - 3}</span>
                )}
              </div>
              
              <div className="flex items-center justify-between text-sm text-zinc-400 font-semibold pt-4 border-t border-zinc-100 dark:border-zinc-800">
                <span className="flex items-center gap-1.5">
                  {project.jobs.reduce((s, j) => s + j.headcount, 0)} positions
                </span>
                <ChevronRight size={16} className="group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          );
        })}
        {projects.length === 0 && !showAddProject && (
          <div
            onClick={() => { resetUpload(); setShowAddProject(true); }}
            className="col-span-full py-16 text-center bg-white dark:bg-zinc-900 rounded-2xl border-2 border-dashed border-zinc-300 dark:border-zinc-800 cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/30 dark:hover:bg-indigo-900/5 transition-all group"
          >
            <FolderOpen size={48} className="mx-auto mb-4 text-zinc-300 group-hover:text-indigo-400 transition-colors" />
            <h3 className="text-lg font-bold mb-1 text-zinc-600 group-hover:text-indigo-600 transition-colors">No projects yet</h3>
            <p className="text-sm text-zinc-400">Upload a PDF brief to create your first project.</p>
          </div>
        )}
      </div>
    </div>
  );
}